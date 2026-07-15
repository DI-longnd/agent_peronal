"""
Test client — mô phỏng web UI qua WebSocket, in mọi event tới run_finished.

    python -m server.test_client <invite_token> "câu hỏi" [session_id]
    python -m server.test_client <invite_token> "câu hỏi" --cancel   # hủy ngay sau run_started

Server URL đổi qua env TEST_SERVER_WS (mặc định ws://localhost:8000/ws).
"""

from __future__ import annotations
import json
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from websockets.sync.client import connect


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--cancel"]
    cancel_after_start = "--cancel" in sys.argv
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    invite_token, message = args[0], args[1]
    session_id = args[2] if len(args) > 2 else None

    url = os.environ.get("TEST_SERVER_WS", "ws://localhost:8000/ws")
    with connect(url) as ws:
        ws.send(json.dumps({"type": "auth", "invite_token": invite_token}))
        while True:
            ev = json.loads(ws.recv(timeout=180))
            print(f"[{ev['type']}] {json.dumps(ev, ensure_ascii=False)[:300]}")

            if ev["type"] == "auth_failed":
                sys.exit(1)
            if ev["type"] == "auth_ok":
                ws.send(json.dumps({"type": "chat", "session_id": session_id, "message": message}))
            if ev["type"] == "session_created":
                print(f">>> session_id={ev['session_id']} (dùng cho câu hỏi tiếp theo)")
            if ev["type"] == "run_started" and cancel_after_start:
                ws.send(json.dumps({"type": "cancel", "run_id": ev["run_id"]}))
                print(">>> đã gửi cancel")
            if ev["type"] == "final_answer":
                print("=== FINAL ANSWER ===")
                print(ev["content"])
            if ev["type"] in ("run_finished", "busy"):
                break


if __name__ == "__main__":
    main()
