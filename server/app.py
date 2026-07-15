"""
FastAPI app — điểm vào của server (não). Protocol: PLAN.md 4.2 (web WS + REST)
và 4.3 (pairing + device WS).

Chạy dev:   uv --project agent-framework run uvicorn server.app:app --port 8000
Import path: agent-framework/ có dấu gạch ngang nên không import trực tiếp được
— chèn vào sys.path (quyết định trong PLAN.md, CẤM đổi tên thư mục/làm package).
"""

from __future__ import annotations
import asyncio
import sys
import time
from pathlib import Path
from contextlib import asynccontextmanager

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "agent-framework"))

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from tools.skill_loader import SkillLoader
from server.config import load_config
from server.sessions import SessionStore
from server.pairing import PairingManager
from server.device_hub import DeviceHub
from server.runner import AgentRunner


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    store = SessionStore(config.data_dir / "app.db")
    hub = DeviceHub()
    hub.set_loop(asyncio.get_running_loop())
    pairing = PairingManager()
    skills = SkillLoader(ROOT / "agent-framework" / "skills")
    runner = AgentRunner(config, store, hub, skills)

    # web_conns: user_id -> các web WS đang mở của user đó (1 user có thể mở nhiều tab)
    web_conns: dict[str, set[WebSocket]] = {}

    def device_status_event(user_id: str) -> dict:
        device = store.get_device(user_id)
        return {
            "type": "device_status",
            "online": hub.is_online(user_id),
            "device_name": hub.device_name(user_id) or (device["name"] if device else None),
        }

    async def push_device_status(user_id: str) -> None:
        ev = device_status_event(user_id)
        for ws in list(web_conns.get(user_id, ())):
            try:
                await ws.send_json(ev)
            except Exception:
                pass

    hub.on_presence_change = push_device_status

    app.state.config = config
    app.state.store = store
    app.state.hub = hub
    app.state.pairing = pairing
    app.state.runner = runner
    app.state.web_conns = web_conns
    app.state.device_status_event = device_status_event
    yield


app = FastAPI(lifespan=lifespan)


# ============ AUTH ============

def require_user(
    request: Request,
    x_invite_token: str | None = Header(default=None, alias="X-Invite-Token"),
) -> dict:
    if not x_invite_token:
        raise HTTPException(status_code=401, detail="Thiếu X-Invite-Token")
    user = request.app.state.store.get_user_by_invite(x_invite_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invite token không hợp lệ")
    return user


# ============ REST ============

@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/api/me")
def api_me(request: Request, user: dict = Depends(require_user)) -> dict:
    state = request.app.state
    device = state.store.get_device(user["id"])
    return {
        "user_name": user["name"],
        "device": (
            {"online": state.hub.is_online(user["id"]), "name": device["name"]} if device else None
        ),
    }


@app.get("/api/sessions")
def api_sessions(request: Request, user: dict = Depends(require_user)) -> list[dict]:
    return request.app.state.store.list_sessions(user["id"])


def _owned_session(state, session_id: str, user: dict) -> dict:
    session = state.store.get_session(session_id)
    if session is None or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session không tồn tại")
    return session


@app.get("/api/sessions/{session_id}/messages")
def api_messages(session_id: str, request: Request, user: dict = Depends(require_user)) -> list[dict]:
    state = request.app.state
    _owned_session(state, session_id, user)
    return state.store.get_messages(session_id)


@app.delete("/api/sessions/{session_id}")
def api_delete_session(session_id: str, request: Request, user: dict = Depends(require_user)) -> dict:
    state = request.app.state
    _owned_session(state, session_id, user)
    state.store.delete_session(session_id)
    return {"ok": True}


# ============ PAIRING (PLAN.md 4.3) ============

@app.post("/api/device/pair/start")
def pair_start(body: dict, request: Request) -> dict:
    """App gọi — KHÔNG cần auth (app chưa có token). Trả mã 6 số + poll_token."""
    device_name = str(body.get("device_name") or "").strip()[:50]
    return request.app.state.pairing.start(device_name)


@app.get("/api/device/pair/poll")
def pair_poll(poll_token: str, request: Request) -> dict:
    return request.app.state.pairing.poll(poll_token)


@app.post("/api/pair/complete")
async def pair_complete(body: dict, request: Request, user: dict = Depends(require_user)) -> dict:
    """Khách nhập mã 6 số trên web. Tạo device + token; app đang poll sẽ nhận token."""
    state = request.app.state
    code = str(body.get("code") or "").strip()
    pending = state.pairing.peek(code)
    if pending is None or pending.device_token is not None:
        raise HTTPException(status_code=404, detail="Mã không đúng hoặc đã hết hạn")
    device_token = state.store.upsert_device(user["id"], pending.device_name)
    device_name = state.pairing.complete(code, device_token)
    if device_name is None:
        raise HTTPException(status_code=404, detail="Mã không đúng hoặc đã hết hạn")
    # Đẩy trạng thái mới cho các tab web đang mở (device sẽ online sau khi app hello)
    for ws in list(state.web_conns.get(user["id"], ())):
        try:
            await ws.send_json(state.device_status_event(user["id"]))
        except Exception:
            pass
    return {"ok": True, "device_name": device_name}


# ============ WEB WEBSOCKET (PLAN.md 4.2) ============

async def _handle_chat(state, ws: WebSocket, user: dict, msg: dict) -> None:
    message = str(msg.get("message") or "").strip()
    if not message:
        return

    session_id = msg.get("session_id")
    if session_id:
        session = state.store.get_session(session_id)
        if session is None or session["user_id"] != user["id"]:
            await ws.send_json({"type": "error", "message": "Session không tồn tại."})
            return
    else:
        session = state.store.create_session(user["id"], message)
        session_id = session["id"]
        await ws.send_json(
            {"type": "session_created", "session_id": session_id, "title": session["title"]}
        )

    # begin() TRƯỚC khi lưu message: nếu busy thì message không được lưu —
    # FE giữ nguyên text trong ô nhập để user gửi lại sau.
    handle = state.runner.begin(user["id"], session_id)
    if handle is None:
        await ws.send_json({"type": "busy", "session_id": session_id})
        return

    state.store.add_message(session_id, "user", message)
    # create_task để receive loop rảnh nhận lệnh cancel trong lúc run đang chạy
    asyncio.create_task(state.runner.drive(handle, message, ws.send_json))


@app.websocket("/ws")
async def ws_web(ws: WebSocket) -> None:
    await ws.accept()
    state = ws.app.state

    try:
        msg = await ws.receive_json()
    except Exception:
        await ws.close()
        return

    user = None
    if msg.get("type") == "auth":
        user = state.store.get_user_by_invite(str(msg.get("invite_token") or ""))
    if user is None:
        try:
            await ws.send_json({"type": "auth_failed"})
        finally:
            await ws.close()
        return

    await ws.send_json({"type": "auth_ok", "user_name": user["name"]})
    state.web_conns.setdefault(user["id"], set()).add(ws)
    await ws.send_json(state.device_status_event(user["id"]))

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")
            if msg_type == "chat":
                await _handle_chat(state, ws, user, msg)
            elif msg_type == "cancel":
                state.runner.cancel(user["id"], str(msg.get("run_id") or ""))
    except WebSocketDisconnect:
        pass
    finally:
        state.web_conns.get(user["id"], set()).discard(ws)


# ============ DEVICE WEBSOCKET (PLAN.md 4.3) ============

PING_INTERVAL_SECONDS = 30
PONG_DEAD_SECONDS = 75  # 2 lần ping không pong -> coi như chết


@app.websocket("/ws/device")
async def ws_device(ws: WebSocket) -> None:
    await ws.accept()
    state = ws.app.state

    try:
        hello = await ws.receive_json()
    except Exception:
        await ws.close()
        return

    row = None
    if hello.get("type") == "hello":
        row = state.store.get_user_by_device_token(str(hello.get("device_token") or ""))
    if row is None:
        try:
            await ws.send_json({"type": "hello_failed"})
        finally:
            await ws.close()
        return

    user_id = row["id"]
    conn = state.hub.register(user_id, row["device_name"], ws)
    state.store.touch_device(user_id)
    await ws.send_json({"type": "hello_ok"})
    await state.hub.on_presence_change(user_id)

    async def pinger() -> None:
        while True:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            if time.monotonic() - conn.last_pong > PONG_DEAD_SECONDS:
                try:
                    await ws.close()
                except Exception:
                    pass
                return
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                return

    ping_task = asyncio.create_task(pinger())
    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")
            if msg_type == "tool_result":
                state.hub.resolve(conn, str(msg.get("call_id") or ""), str(msg.get("result") or ""))
            elif msg_type == "pong":
                conn.last_pong = time.monotonic()
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        state.hub.unregister(user_id, conn)
        state.store.touch_device(user_id)
        try:
            await state.hub.on_presence_change(user_id)
        except Exception:
            pass


# ============ STATIC (React build — Phase 3) ============
# Mount SAU CÙNG để /api, /ws, /healthz được match trước.
_web_dist = ROOT / "web" / "dist"
if _web_dist.exists():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="web")
