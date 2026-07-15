"""
Companion app — "đôi tay" của Personal Agent, chạy trên máy khách (PLAN.md Phase 2).

Vòng đời:
  1. Load config (%APPDATA%/PersonalAgent/config.json); hỏi server_url lần đầu.
  2. Chưa có device_token -> pairing: hiện mã 6 số, khách nhập vào web.
  3. Kết nối WS RA server (/ws/device) — máy khách không cần mở port.
  4. Loop: nhận tool_call -> thực thi browser local -> trả tool_result.
     Nhận ping -> trả pong. Mất kết nối -> tự reconnect (backoff 2s->4s->8s, max 30s).
  5. hello_failed (token bị thu hồi, vd khách pair máy khác) -> xóa token, pairing lại.

Chế độ phụ:
  app.py --login <url>   : mở browser để khách đăng nhập thủ công 1 lần (login_setup)

Chạy source:  uv --project agent-framework run python local-agent/app.py
Đóng gói:     xem build.spec
"""

from __future__ import annotations
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# line_buffering: mã pairing/log phải hiện NGAY cả khi stdout không phải tty
# (chạy nền, redirect ra file) — không được nằm kẹt trong buffer.
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# BẮT BUỘC cho bản đóng gói PyInstaller: driver Playwright trong bundle mặc định
# tìm Chromium BÊN TRONG bundle (_internal/playwright/driver/...) thay vì cache
# chuẩn — set tường minh về %LOCALAPPDATA%/ms-playwright (nơi ensure_chromium
# tải về). Vô hại khi chạy từ source.
if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
    _local_appdata = os.environ.get("LOCALAPPDATA")
    if _local_appdata:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(_local_appdata) / "ms-playwright")

# Chạy từ source: agent-framework/ cần vào sys.path. Khi đóng gói PyInstaller,
# mọi module đã bundle sẵn trong exe (build.spec khai báo pathex) — bỏ qua.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parent.parent / "agent-framework"))

from config import load_config, save_config
from pairing import pair, ws_device_url
from executor import ToolExecutor


class HelloFailed(Exception):
    pass


def ensure_chromium() -> None:
    """Lần chạy đầu: tải Chromium nếu chưa có (playwright lưu tại
    %LOCALAPPDATA%/ms-playwright). Gọi CLI của playwright trực tiếp trong
    tiến trình — subprocess [sys.executable, -m playwright] KHÔNG dùng được
    khi đã đóng gói PyInstaller (sys.executable là exe của app)."""
    cache = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ms-playwright"
    if cache.exists() and any(cache.glob("chromium*")):
        return
    print("Lần chạy đầu: đang tải trình duyệt Chromium (~150MB), chờ chút...")
    import playwright.__main__ as pw_cli

    old_argv = sys.argv
    sys.argv = ["playwright", "install", "chromium"]
    try:
        pw_cli.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
    print("✓ Đã tải xong Chromium.")


def run_session(cfg: dict, executor: ToolExecutor) -> None:
    """1 phiên kết nối WS. Return khi mất kết nối (caller reconnect),
    raise HelloFailed khi token bị từ chối."""
    from websockets.sync.client import connect

    url = ws_device_url(cfg["server_url"])
    print(f"Đang kết nối {url} ...")

    with connect(url) as ws:
        send_lock = threading.Lock()

        def send(obj: dict) -> None:
            with send_lock:  # send từ cả receive-loop (pong) lẫn worker (tool_result)
                ws.send(json.dumps(obj, ensure_ascii=False))

        send({"type": "hello", "device_token": cfg["device_token"]})
        resp = json.loads(ws.recv(timeout=15))
        if resp.get("type") != "hello_ok":
            raise HelloFailed()
        print("✓ Đã kết nối — sẵn sàng nhận việc từ agent. (Ctrl+C để thoát)")

        def run_tool(msg: dict) -> None:
            tool = str(msg.get("tool") or "")
            args = msg.get("args") or {}
            print(f"→ Đang chạy: {tool} {json.dumps(args, ensure_ascii=False)[:80]}")
            result = executor.execute(tool, args)
            try:
                send({"type": "tool_result", "call_id": msg.get("call_id"), "result": result})
            except Exception:
                pass  # kết nối vừa chết — receive loop sẽ thoát và reconnect

        # Tool chạy trên worker pool size 1 (browser thao tác tuần tự) để receive
        # loop luôn rảnh trả lời ping — không bị server coi là chết giữa tool dài.
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            while True:
                msg = json.loads(ws.recv())
                msg_type = msg.get("type")
                if msg_type == "ping":
                    send({"type": "pong"})
                elif msg_type == "tool_call":
                    pool.submit(run_tool, msg)
        finally:
            pool.shutdown(wait=False)


def main() -> None:
    args = sys.argv[1:]
    cfg = load_config()

    if args and args[0] == "--login":
        url = args[1] if len(args) > 1 else input("URL trang cần đăng nhập: ").strip()
        import login_setup

        login_setup.run_login(cfg, url)
        return

    print("Personal Agent — companion app")
    if not cfg["server_url"]:
        cfg["server_url"] = input(
            "Địa chỉ server (vd wss://domain hoặc ws://localhost:8000): "
        ).strip()
        save_config(cfg)

    ensure_chromium()
    executor = ToolExecutor(cfg)
    backoff = 2
    try:
        while True:
            try:
                if not cfg["device_token"]:
                    pair(cfg)
                    save_config(cfg)
                run_session(cfg, executor)
                backoff = 2  # phiên vừa rồi kết nối được -> reset backoff
            except HelloFailed:
                print("Server từ chối token (có thể bạn đã ghép máy khác) — cần ghép lại.")
                cfg["device_token"] = ""
                save_config(cfg)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"Mất kết nối ({type(e).__name__}: {e}) — thử lại sau {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
    except KeyboardInterrupt:
        print("\nĐang thoát...")
    finally:
        executor.close()


if __name__ == "__main__":
    main()
