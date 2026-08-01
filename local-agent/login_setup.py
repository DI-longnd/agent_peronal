"""
Đăng nhập thủ công 1 lần trên MÁY KHÁCH (PLAN.md quyết định #10): mở cửa sổ Chrome
thật, khách tự đăng nhập (mật khẩu/OTP), phiên đăng nhập ở lại trong PROFILE trình
duyệt của agent. Mật khẩu không bao giờ rời máy này.

Chạy: PersonalAgent --login https://affiliate.tiktok.com
(hoặc: python local-agent/app.py --login <url>)

Toàn bộ logic nằm ở tools/browser/manual_login.py — dùng chung với CLI all-in-one
(scripts/setup_browser_login.py). File này chỉ ánh xạ config.json sang tham số.
"""

from __future__ import annotations


def run_login(cfg: dict, url: str) -> None:
    from tools.browser.manual_login import run_manual_login

    run_manual_login(
        url,
        user_data_dir=cfg.get("user_data_dir") or None,
        storage_state_path=cfg["storage_state_path"],
    )
