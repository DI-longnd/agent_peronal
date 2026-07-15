"""
DeviceHub — trạm định tuyến RPC giữa agent thread (sync) và companion app
(WebSocket, async) theo PLAN.md 4.6.

Cầu sync→async: call_tool() được gọi từ AGENT THREAD (bên trong Tool.handler),
nhưng gửi/nhận WebSocket phải chạy trên event loop chính. Giải pháp:
  - Gửi: asyncio.run_coroutine_threadsafe(ws.send_json(...), main_loop)
  - Chờ kết quả: concurrent.futures.Future theo call_id — receive loop của
    device WS (async, ở app.py) gọi resolve() để set kết quả.
Device disconnect giữa chừng -> fail toàn bộ future đang chờ với message rõ ràng
(RPC stub trong remote_tools.py sẽ chuyển thành string lỗi actionable cho LLM).
"""

from __future__ import annotations
import asyncio
import threading
import time
import uuid
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from typing import Callable, Awaitable


class DeviceConnection:
    def __init__(self, user_id: str, device_name: str, ws):
        self.user_id = user_id
        self.device_name = device_name
        self.ws = ws
        self.pending: dict[str, Future] = {}
        self.last_pong = time.monotonic()


class DeviceHub:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._conns: dict[str, DeviceConnection] = {}
        self._lock = threading.Lock()
        # app.py gắn callback này để đẩy device_status cho web WS của đúng user
        self.on_presence_change: Callable[[str], Awaitable[None]] | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # --- lifecycle (gọi từ async context của device WS handler) ---

    def register(self, user_id: str, device_name: str, ws) -> DeviceConnection:
        conn = DeviceConnection(user_id, device_name, ws)
        with self._lock:
            old = self._conns.get(user_id)
            self._conns[user_id] = conn
        if old is not None:
            # Kết nối mới thay kết nối cũ (app restart) — fail mọi RPC đang treo trên kết nối cũ
            self._fail_pending(old, "app trên máy khách đã kết nối lại giữa chừng")
        return conn

    def unregister(self, user_id: str, conn: DeviceConnection) -> None:
        with self._lock:
            if self._conns.get(user_id) is conn:
                del self._conns[user_id]
        self._fail_pending(conn, "app trên máy khách mất kết nối")

    def _fail_pending(self, conn: DeviceConnection, reason: str) -> None:
        with self._lock:
            items = list(conn.pending.values())
            conn.pending.clear()
        for fut in items:
            if not fut.done():
                fut.set_exception(RuntimeError(reason))

    # --- presence ---

    def is_online(self, user_id: str) -> bool:
        with self._lock:
            return user_id in self._conns

    def device_name(self, user_id: str) -> str | None:
        with self._lock:
            conn = self._conns.get(user_id)
        return conn.device_name if conn else None

    # --- RPC (gọi từ agent thread — SYNC) ---

    def call_tool(self, user_id: str, tool: str, args: dict, timeout: float) -> str:
        with self._lock:
            conn = self._conns.get(user_id)
        if conn is None or self._loop is None:
            raise RuntimeError("app trên máy khách chưa kết nối")

        call_id = str(uuid.uuid4())
        fut: Future = Future()
        with self._lock:
            conn.pending[call_id] = fut

        try:
            send = asyncio.run_coroutine_threadsafe(
                conn.ws.send_json({"type": "tool_call", "call_id": call_id, "tool": tool, "args": args}),
                self._loop,
            )
            send.result(10)  # gửi lệnh không được quá 10s — quá là kết nối đã chết
        except Exception as e:
            with self._lock:
                conn.pending.pop(call_id, None)
            raise RuntimeError(f"không gửi được lệnh xuống máy khách: {e}")

        try:
            return fut.result(timeout)
        except FutureTimeoutError:
            with self._lock:
                conn.pending.pop(call_id, None)
            raise RuntimeError(f"máy khách không phản hồi sau {int(timeout)}s")

    # --- gọi từ receive loop của device WS (async side) ---

    def resolve(self, conn: DeviceConnection, call_id: str, result: str) -> None:
        with self._lock:
            fut = conn.pending.pop(call_id, None)
        if fut is not None and not fut.done():
            fut.set_result(result)
