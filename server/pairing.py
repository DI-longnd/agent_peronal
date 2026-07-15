"""
PairingManager — ghép companion app với user bằng mã 6 số (PLAN.md 4.3).

Lưu in-memory (KHÔNG DB): pairing chỉ sống 10 phút, mất khi restart server là
chấp nhận được — app chỉ việc xin mã mới. Flow:
  1. App:  pair/start(device_name)  -> {pairing_code, poll_token}
  2. Khách nhập code trên web -> server complete(code, user_id) -> tạo device_token
  3. App:  pair/poll(poll_token)    -> {"status":"paired", device_token}
"""

from __future__ import annotations
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field

TTL_SECONDS = 600


@dataclass
class _PendingPair:
    device_name: str
    poll_token: str
    expires_at: float
    device_token: str | None = None  # set khi user complete thành công


class PairingManager:
    def __init__(self):
        self._by_code: dict[str, _PendingPair] = {}
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = time.monotonic()
        for code in [c for c, p in self._by_code.items() if p.expires_at < now]:
            del self._by_code[code]

    def start(self, device_name: str) -> dict:
        with self._lock:
            self._purge()
            # 6 chữ số, tránh trùng với mã đang active
            while True:
                code = f"{secrets.randbelow(1_000_000):06d}"
                if code not in self._by_code:
                    break
            pending = _PendingPair(
                device_name=device_name or "Máy chưa đặt tên",
                poll_token=str(uuid.uuid4()),
                expires_at=time.monotonic() + TTL_SECONDS,
            )
            self._by_code[code] = pending
            return {"pairing_code": code, "poll_token": pending.poll_token}

    def complete(self, code: str, device_token: str) -> str | None:
        """Gọi khi user nhập đúng mã trên web (caller đã tạo device_token qua
        SessionStore.upsert_device). Trả device_name, hoặc None nếu mã sai/hết hạn."""
        with self._lock:
            self._purge()
            pending = self._by_code.get(code)
            if pending is None or pending.device_token is not None:
                return None
            pending.device_token = device_token
            return pending.device_name

    def peek(self, code: str) -> _PendingPair | None:
        """Xem thông tin mã (để lấy device_name trước khi complete)."""
        with self._lock:
            self._purge()
            return self._by_code.get(code)

    def poll(self, poll_token: str) -> dict:
        with self._lock:
            self._purge()
            for code, pending in self._by_code.items():
                if pending.poll_token == poll_token:
                    if pending.device_token is not None:
                        # Giao token xong thì xoá — token chỉ được giao đúng 1 lần
                        token = pending.device_token
                        del self._by_code[code]
                        return {"status": "paired", "device_token": token}
                    return {"status": "pending"}
            return {"status": "expired"}
