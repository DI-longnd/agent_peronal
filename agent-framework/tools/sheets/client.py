"""Đẩy file CSV trên máy khách lên Google Sheet qua Apps Script Web App.

VÌ SAO KHÔNG DÙNG API GOOGLE
Ba cách được cân nhắc, đo thật ngày 01-08-2026:

  - Bấm menu Tệp > Nhập trong trình duyệt: 30-60s, 10 bước phụ thuộc giao diện, và
    KHÔNG chạy được khi chưa đăng nhập — đo thấy menu Tệp của người dùng ẩn danh chỉ
    có Tải xuống / Cài đặt / In, không có mục Nhập. Tức là vẫn phải đăng nhập Google
    vào profile của agent, đồng nghĩa trao cho agent toàn quyền tài khoản đó.
  - Dán clipboard: không cần đăng nhập nhưng buộc sheet phải mở công khai, mà file
    đơn hàng có cột Recipient / Phone # / Detail Address — thông tin cá nhân người mua.
  - OAuth API: nhanh và bền, nhưng phải dựng Google Cloud project, khách thấy cảnh
    báo "ứng dụng chưa xác minh", và gói thêm thư viện Google làm exe nặng thêm.

Apps Script thắng cả ba: đo được **1,1-2,0 giây**, không phụ thuộc giao diện, không
thêm phụ thuộc nào (chỉ dùng urllib của thư viện chuẩn), và quan trọng nhất là
**agent KHÔNG hề giữ thông tin đăng nhập Google**. Nó chỉ có một URL và một token,
và thứ duy nhất làm được là ghi vào đúng một sheet qua đúng một script.

Phía Google, script gọi Utilities.parseCsv — hàm sẵn có đọc đúng quy tắc trích dẫn.
Đã kiểm chứng ô vừa chứa dấu phẩy vừa chứa xuống dòng vẫn về nguyên vẹn trong MỘT ô;
đây là ca làm hỏng mọi cách tách chuỗi thủ công.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_MB = 8          # ~8MB CSV đã là vài chục nghìn đơn; quá đó thì chia nhỏ
TIMEOUT_SECONDS = 120


def _post(url: str, payload: dict, timeout: int) -> tuple[int, str]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]


def push_csv(csv_path: str, webapp_url: str, token: str,
             timeout_seconds: int = TIMEOUT_SECONDS) -> str:
    """Ghi đè nội dung Google Sheet bằng file CSV trên máy này. Trả chuỗi cho agent."""
    if not webapp_url or not token:
        return ("Chưa cấu hình Google Sheet trên máy này. Cần đặt `sheet_webapp_url` "
                "và `sheet_token` trong config.json của app (xem HUONG-DAN-SU-DUNG.md). "
                "Báo người dùng, KHÔNG tự bịa URL.")
    if "/exec" not in webapp_url:
        return (f"URL Apps Script phải kết thúc bằng /exec, đang là: {webapp_url[:80]}. "
                "URL /dev chỉ chạy cho chủ script, agent gọi không được.")

    path = Path(csv_path)
    if not path.is_file():
        return (f"Không thấy file {csv_path}. Dùng browser__list_downloads để xem "
                "các file đã tải trong phiên này rồi lấy đúng đường dẫn.")
    size_mb = path.stat().st_size / 1024 / 1024
    if size_mb > MAX_MB:
        return (f"File {path.name} nặng {size_mb:.1f}MB, vượt ngưỡng {MAX_MB}MB. "
                "Chia nhỏ khoảng ngày rồi xuất lại.")

    try:
        # utf-8-sig: file TikTok xuất ra có BOM. Không bỏ BOM thì ký tự ﻿ dính
        # vào tên cột đầu tiên, và mọi phép so cột theo tên đều trượt.
        csv_text = path.read_text(encoding="utf-8-sig")
    except Exception as e:
        return f"Không đọc được {path.name}: {type(e).__name__}: {e}"
    if not csv_text.strip():
        return f"File {path.name} rỗng — không đẩy lên để khỏi xoá trắng sheet."

    t0 = time.time()
    try:
        status, body = _post(webapp_url, {"token": token, "csv": csv_text},
                             timeout_seconds)
    except Exception as e:
        return (f"Không gọi được Apps Script ({type(e).__name__}: {e}). "
                "Kiểm tra mạng, hoặc mở URL đó bằng trình duyệt xem còn sống không.")
    dt = time.time() - t0

    try:
        data = json.loads(body)
    except Exception:
        return (f"Apps Script trả về nội dung không phải JSON (HTTP {status}). "
                "Thường là do bản triển khai đã bị gỡ, hoặc quyền truy cập không "
                f"phải 'Bất kỳ ai'. Đầu phản hồi: {body[:150]}")

    if not data.get("ok"):
        err = data.get("error", "không rõ")
        if "token" in str(err).lower():
            return ("Apps Script từ chối: SAI TOKEN. Token trong config.json của máy "
                    "này phải khớp hằng số TOKEN trong script. Báo người dùng kiểm tra.")
        return f"Apps Script báo lỗi: {err}"

    rows, cols = data.get("rows", "?"), data.get("cols", "?")
    return (f"Đã đẩy {path.name} lên Google Sheet trong {dt:.1f}s — GHI ĐÈ dữ liệu cũ.\n"
            f"  {rows} dòng dữ liệu × {cols} cột, ghi vào trang '{data.get('sheet','?')}'\n"
            f"  Thời điểm ghi: {data.get('at','?')}\n"
            "Báo cáo cuối nên nói rõ đã cập nhật lên Google Sheet và số dòng đã ghi.")
