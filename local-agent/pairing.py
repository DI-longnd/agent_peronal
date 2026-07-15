"""
Pairing phía app (PLAN.md 4.3): xin mã 6 số từ server, hiện to rõ cho khách,
poll mỗi 2s tới khi khách nhập mã trên web -> nhận device_token.

Dùng urllib stdlib (không thêm dependency requests — chỉ 2 call JSON đơn giản).
"""

from __future__ import annotations
import json
import platform
import time
import urllib.request


def http_base(server_url: str) -> str:
    """ws://host -> http://host, wss://domain -> https://domain."""
    url = server_url.rstrip("/")
    if url.startswith("wss://"):
        return "https://" + url[len("wss://"):]
    if url.startswith("ws://"):
        return "http://" + url[len("ws://"):]
    return url


def ws_device_url(server_url: str) -> str:
    return server_url.rstrip("/") + "/ws/device"


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pair(cfg: dict) -> None:
    """Chạy tới khi pairing thành công — ghi device_token vào cfg (caller save)."""
    if not cfg.get("device_name"):
        cfg["device_name"] = platform.node() or "May-cua-toi"
    base = http_base(cfg["server_url"])

    while True:
        data = _post_json(f"{base}/api/device/pair/start", {"device_name": cfg["device_name"]})
        code, poll_token = data["pairing_code"], data["poll_token"]

        print()
        print("=" * 46)
        print("  GHÉP MÁY VỚI TÀI KHOẢN CỦA BẠN")
        print()
        print(f"  Mã ghép:   {code[:3]} {code[3:]}")
        print()
        print("  Mở trang web Personal Agent, nhập mã này")
        print("  vào ô 'Ghép máy'. Mã có hiệu lực 10 phút.")
        print("=" * 46)
        print()

        while True:
            time.sleep(2)
            status = _get_json(f"{base}/api/device/pair/poll?poll_token={poll_token}")
            if status["status"] == "paired":
                cfg["device_token"] = status["device_token"]
                print("✓ Ghép máy thành công!")
                return
            if status["status"] == "expired":
                print("Mã đã hết hạn — tạo mã mới...")
                break  # vòng ngoài xin mã mới
