#!/usr/bin/env python3
"""
Đăng nhập thủ công 1 lần cho CLI all-in-one (main.py): mở cửa sổ Chrome thật, tự
đăng nhập, phiên ở lại trong PROFILE trình duyệt của agent.

Vì sao đứng NGOÀI AgentLoop, không phải 1 tool/skill: đăng nhập lần đầu (mật khẩu,
2FA) là thao tác CON NGƯỜI phải tự làm. AgentLoop không có khái niệm "dừng giữa
chừng chờ người dùng", nên việc này không có chỗ hợp lý trong vòng lặp LLM <-> tool
call — và cũng không nên có, vì LLM không bao giờ được phép cầm mật khẩu thật.

Profile mặc định TRÙNG với companion app (%APPDATA%/PersonalAgent/browser-profile),
nên đăng nhập một lần là cả hai đường đều dùng được. Đổi bằng BROWSER_USER_DATA_DIR.
Hai bên không chạy đồng thời được — profile_lock sẽ chặn kèm thông báo rõ.

Logic thật nằm ở tools/browser/manual_login.py, dùng chung với local-agent.

Cách dùng:
    uv run python scripts/setup_browser_login.py             # đăng nhập (mặc định TikTok Affiliate)
    uv run python scripts/setup_browser_login.py <url>       # đăng nhập trang khác
    uv run python scripts/setup_browser_login.py --check     # kiểm tra phiên còn sống không
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

DEFAULT_URL = "https://affiliate.tiktok.com/"


def main() -> None:
    from tools.browser.manual_login import (
        run_manual_login, check_session, default_profile_dir, default_state_path,
    )

    args = sys.argv[1:]
    check_only = "--check" in args
    url = next((a for a in args if not a.startswith("--")), DEFAULT_URL)

    # Mặc định trùng companion app. Trước đây bắt buộc phải có BROWSER_STORAGE_STATE
    # trong .env, và giá trị mẫu lại trỏ vào chỗ riêng của agent-framework — nên bản
    # sao lưu của CLI và của app trôi khỏi nhau mà không ai để ý.
    storage_state_path = os.environ.get("BROWSER_STORAGE_STATE") or str(default_state_path())
    profile = os.environ.get("BROWSER_USER_DATA_DIR") or str(default_profile_dir())
    Path(storage_state_path).parent.mkdir(parents=True, exist_ok=True)

    if check_only:
        ok = check_session(url, user_data_dir=profile, storage_state_path=storage_state_path)
        sys.exit(0 if ok else 1)

    run_manual_login(url, user_data_dir=profile, storage_state_path=storage_state_path)


if __name__ == "__main__":
    main()
