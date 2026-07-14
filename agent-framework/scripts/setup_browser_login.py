#!/usr/bin/env python3
"""
Setup one-off: đăng nhập thủ công vào 1 trang cần login (mặc định Facebook), lưu
cookie + localStorage (Playwright storageState) ra file JSON tại BROWSER_STORAGE_STATE
(.env). Từ lần chạy agent kế tiếp, browser-agent nạp lại file này và đã ở trạng thái
đăng nhập sẵn — không cần đăng nhập lại.

Vì sao đứng NGOÀI AgentLoop, không phải 1 tool/skill: đăng nhập lần đầu (mật khẩu,
2FA) là thao tác CON NGƯỜI phải tự làm. AgentLoop không có khái niệm "dừng giữa
chừng chờ người dùng", nên việc này không có chỗ hợp lý trong vòng lặp LLM <-> tool
call — và cũng không nên có, vì LLM không bao giờ được phép cầm mật khẩu thật.

Vì sao dùng storageState (JSON cookie+localStorage) thay vì persistent profile
(nguyên thư mục Chromium): đây là cách Playwright chính thức khuyến nghị cho việc
tái sử dụng đăng nhập — gọn hơn, chỉ chứa đúng phạm vi cần bảo vệ (không kèm cache,
extension, GPU cache... như 1 profile Chromium đầy đủ).

Cách dùng:
    uv run python scripts/setup_browser_login.py             # đăng nhập Facebook (mặc định)
    uv run python scripts/setup_browser_login.py <url>        # đăng nhập vào 1 URL khác
    uv run python scripts/setup_browser_login.py --check      # kiểm tra session đã lưu còn sống không (headless, không cần thao tác gì)
"""
from __future__ import annotations
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
import os

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))
from tools.browser.browser_tool import SyncBrowserTool

DEFAULT_URL = "https://www.facebook.com"


def main() -> None:
    args = sys.argv[1:]
    check_only = "--check" in args
    url = next((a for a in args if a != "--check"), DEFAULT_URL)

    storage_state_path = os.environ.get("BROWSER_STORAGE_STATE")
    if not storage_state_path:
        print("Lỗi: chưa set BROWSER_STORAGE_STATE trong .env — không có nơi để lưu/đọc session.")
        sys.exit(1)

    sync_browser = SyncBrowserTool(llm=None, headless=check_only, storage_state_path=storage_state_path)
    sync_browser.start()
    try:
        sync_browser.navigate(url)

        if not check_only:
            print(f"\nĐăng nhập thủ công trong cửa sổ Chrome vừa mở ({url}).")
            input("Xong thì quay lại đây, nhấn Enter để lưu session và đóng browser...\n")
            sync_browser.navigate(url)  # reload để lấy state mới nhất sau khi login
            print(sync_browser.save_storage_state(storage_state_path))

        print(sync_browser.get_state())
    finally:
        sync_browser.stop()


if __name__ == "__main__":
    main()
