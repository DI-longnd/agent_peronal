"""
Đăng nhập thủ công 1 lần trên MÁY KHÁCH (PLAN.md quyết định #10): mở cửa sổ
Chrome thật, khách tự đăng nhập (mật khẩu/OTP), lưu session (cookie+localStorage)
vào storage_state_path local. Mật khẩu không bao giờ rời máy này.

Chạy: PersonalAgent --login https://affiliate.tiktok.com
(hoặc: python local-agent/app.py --login <url>)
"""

from __future__ import annotations


def run_login(cfg: dict, url: str) -> None:
    from tools.browser.browser_tool import SyncBrowserTool

    print(f"Đang mở trình duyệt tới {url} ...")
    print("Hãy đăng nhập như bình thường trong cửa sổ vừa mở.")

    browser = SyncBrowserTool(
        llm=None,
        headless=False,  # login luôn cần cửa sổ thật
        storage_state_path=cfg.get("storage_state_path") or None,
    )
    browser.start()
    try:
        browser.navigate(url)
        input("\nĐăng nhập XONG thì quay lại đây, nhấn Enter để lưu phiên đăng nhập...\n")
        browser.navigate(url)  # reload để chốt state mới nhất sau khi login
        print(browser.save_storage_state(cfg["storage_state_path"]))
        print("✓ Đã lưu. Từ giờ agent mở trang này sẽ ở trạng thái đăng nhập sẵn.")
    finally:
        browser.stop()
