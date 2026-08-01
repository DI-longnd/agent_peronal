"""Dọn cache trong profile Chrome của agent, giữ nguyên phần chứa phiên đăng nhập.

Vì sao cần, dù đã có `--disk-cache-size=104857600`: cờ đó chỉ chi phối HTTP cache.
Đo profile thật ngày 01-08-2026, tổng 284MB:

    Cache                        33MB   <- nằm dưới trần, cờ có tác dụng
    Code Cache                   90MB   <- ngoài tầm với của cờ
    Service Worker/CacheStorage 110MB   <- ngoài tầm với của cờ
    IndexedDB                    32MB   <- PHẢI GIỮ, chứa khoá gắn thiết bị
    còn lại                    ~19MB

Hai mục ngốn nhất không bị cờ nào chặn, nên phải tự dọn.

RANH GIỚI PHẢI THUỘC — xoá nhầm một trong những mục dưới đây là mất phiên đăng nhập,
và khách phải đăng nhập lại (TikTok chỉ cho ~3 ngày mỗi lần):

    GIỮ   Network/          cookie (Chrome đời mới để Cookies trong này)
    GIỮ   Local Storage/    localStorage
    GIỮ   Session Storage/
    GIỮ   IndexedDB/        khoá device-binding kiểu TikTok Ticket Guard
    GIỮ   Login Data, Preferences, Local State
    GIỮ   Service Worker/Database/   đăng ký service worker (chỉ ~40KB)

Chỉ chạy khi Chromium ĐÃ ĐÓNG (Windows khoá file đang mở) — gọi trong start(),
sau khi giữ được ProfileLock và trước khi launch.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Đường dẫn tương đối tính từ gốc profile. Toàn bộ đều tái tạo được: Chromium tự
# dựng lại khi cần, chỉ tốn thêm một ít thời gian tải ở lần mở kế tiếp.
DISPOSABLE = (
    "Default/Cache",
    "Default/Code Cache",
    "Default/GPUCache",
    "Default/DawnWebGPUCache",
    "Default/DawnGraphiteCache",
    "Default/Service Worker/CacheStorage",
    "Default/Service Worker/ScriptCache",
    "GrShaderCache",
    "ShaderCache",
)

DEFAULT_LIMIT_MB = 150


def _size_mb(path: Path) -> float:
    total = 0
    for f in path.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass  # file bị xoá/khoá giữa chừng — bỏ qua, đây chỉ là số đo
    return total / (1024 * 1024)


def prune(profile: str | Path, limit_mb: float | None = None) -> str:
    """Xoá cache nếu profile vượt `limit_mb`. Trả về mô tả việc đã làm ('' = không làm gì).

    Chỉ dọn khi vượt ngưỡng, không dọn mỗi lần mở: cache còn thì trang tải nhanh
    hơn nhiều, dọn vô cớ là tự làm chậm mình.

    Ngưỡng đọc trong thân hàm (không đặt ở giá trị mặc định của tham số) để test
    hạ ngưỡng xuống được mà không phải nhét 200MB rác vào profile giả."""
    if limit_mb is None:
        limit_mb = DEFAULT_LIMIT_MB
    root = Path(profile)
    if not root.is_dir():
        return ""

    before = _size_mb(root)
    if before <= limit_mb:
        return ""

    freed, failed = 0.0, []
    for rel in DISPOSABLE:
        target = root / rel
        if not target.is_dir():
            continue
        size = _size_mb(target)
        try:
            shutil.rmtree(target)
            freed += size
        except OSError as e:
            # Chromium chưa nhả hết handle, hoặc thiếu quyền. Không phải lỗi chí
            # mạng: lần mở sau thử lại. Đừng chặn việc mở browser vì chuyện dọn dẹp.
            failed.append(f"{rel} ({type(e).__name__})")

    msg = (f"Đã dọn cache profile: {before:.0f}MB -> {before - freed:.0f}MB "
           f"(giải phóng {freed:.0f}MB, giữ nguyên phiên đăng nhập).")
    if failed:
        msg += f" Chưa xoá được: {', '.join(failed)}."
    return msg
