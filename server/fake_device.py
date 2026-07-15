"""
Fake device — giả lập companion app cho việc test Phase 1 (KHÔNG phải code product;
companion app thật nằm ở local-agent/, Phase 2). Kết nối /ws/device, hello bằng
device_token, trả kết quả GIẢ cho mọi tool_call — đủ để chứng minh đường RPC
server ↔ device chạy xuyên suốt trước khi có app thật.

    python -m server.fake_device <device_token>
"""

from __future__ import annotations
import json
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from websockets.sync.client import connect

CANNED = {
    "browser__navigate": "Navigated to https://duckduckgo.com/?q=bitcoin+price",
    "browser__get_state": (
        "URL: https://duckduckgo.com/?q=bitcoin+price\n"
        "Title: bitcoin price at DuckDuckGo\n\n"
        "Interactive elements:\n"
        "[1] <input type=\"number\" value=\"65000.50\" /> (Bitcoin price USD)\n"
        "[2] <a href=/settings>Settings</a>"
    ),
    "browser__page_markdown": json.dumps(
        {
            "url": "https://duckduckgo.com/?q=bitcoin+price",
            "markdown": "# Bitcoin price\n1 Bitcoin (BTC) = 65,000.50 USD (nguồn: kết quả giả để test)",
            "truncated": False,
            "next_start": None,
        },
        ensure_ascii=False,
    ),
}


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    device_token = sys.argv[1]
    url = os.environ.get("TEST_SERVER_DEVICE_WS", "ws://localhost:8000/ws/device")

    with connect(url) as ws:
        ws.send(json.dumps({"type": "hello", "device_token": device_token}))
        print(f"[fake-device] {ws.recv()}")
        while True:
            msg = json.loads(ws.recv())
            if msg["type"] == "ping":
                ws.send(json.dumps({"type": "pong"}))
            elif msg["type"] == "tool_call":
                result = CANNED.get(msg["tool"], f"OK (fake result cho {msg['tool']})")
                print(f"[fake-device] tool_call {msg['tool']} -> trả {len(result)} chars")
                ws.send(json.dumps({"type": "tool_result", "call_id": msg["call_id"], "result": result}))


if __name__ == "__main__":
    main()
