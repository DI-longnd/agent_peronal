"""
Đăng nhập thủ công 1 lần trên MÁY KHÁCH (PLAN.md quyết định #10): mở cửa sổ
Chrome thật, khách tự đăng nhập (mật khẩu/OTP), phiên đăng nhập ở lại trong
PROFILE trình duyệt của agent. Mật khẩu không bao giờ rời máy này.

Chạy: PersonalAgent --login https://affiliate.tiktok.com
(hoặc: python local-agent/app.py --login <url>)

Ba quy tắc của luồng này, mỗi cái đổi bằng một lần hỏng thật:

  1. Đăng nhập vào ĐÚNG profile mà agent sẽ dùng (user_data_dir), không phải một
     cửa sổ tạm. Chromium tự giữ và tự gia hạn cookie/localStorage/IndexedDB ở đó
     — đây là chỗ phiên sống lâu nhất.

  2. Nếu profile đang chứa phiên ĐÃ HẾT HẠN thì dọn đi rồi làm lại từ đầu. Đăng
     nhập đè lên phiên chết khiến trang rơi vào trạng thái cookie-chết/cache-sống
     và lặp reload — chính người dùng cũng không đăng nhập lại được. Chỉ dọn khi
     thật sự chết, để không xoá oan phiên của các trang khác trong cùng profile.

  3. KHÔNG reload trang trước khi lưu bản sao lưu. storage_state() đọc thẳng từ
     context; reload chỉ thêm cơ hội TargetClosedError (tab đã bị đóng) và làm
     mất trắng công đăng nhập của khách.
"""

from __future__ import annotations
import shutil
import time
from datetime import datetime
from pathlib import Path


def _archive(profile: Path, attempts: int = 6) -> Path:
    """Dời profile cũ sang một tên có mốc thời gian (không xoá hẳn — lỡ tay còn cứu).

    Thử lại nhiều lần: trên Windows, ngay sau khi Chromium thoát thì các handle
    của nó có thể chưa được giải phóng hết, di chuyển thư mục sẽ dính
    'WinError 32: file đang được tiến trình khác sử dụng'."""
    dest = profile.with_name(f"{profile.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    last = None
    for i in range(attempts):
        try:
            shutil.move(str(profile), str(dest))
            return dest
        except OSError as e:
            last = e
            time.sleep(0.5 * (i + 1))
    raise OSError(
        f"Không dọn được profile cũ {profile} sau {attempts} lần thử: {last}\n"
        "Hãy đóng hết cửa sổ Chrome/Chromium của agent rồi chạy lại."
    ) from last


def run_login(cfg: dict, url: str) -> None:
    from tools.browser.browser_tool import SyncBrowserTool
    from tools.browser import session_state

    state_path = cfg["storage_state_path"]
    profile = Path(cfg["user_data_dir"]) if cfg.get("user_data_dir") else None

    def open_browser() -> SyncBrowserTool:
        b = SyncBrowserTool(
            llm=None,
            headless=False,  # login luôn cần cửa sổ thật
            storage_state_path=None if profile else state_path,
            user_data_dir=str(profile) if profile else None,
        )
        b.start()
        return b

    browser = open_browser()

    # Quy tắc 2: soi phiên đang có trong profile, chết thì dọn và mở lại sạch.
    if profile:
        try:
            code, message = session_state.status(browser.export_state())
        except Exception:
            code, message = 'unknown', ''
        if code == 'empty':
            print("Profile trình duyệt còn trống — đây là lần đăng nhập đầu tiên.")
        else:
            print(f"Phiên trong profile: {message or code}")
        if code == 'expired':
            browser.stop()
            moved = _archive(profile)
            print(f"Phiên đã chết — dọn profile cũ sang {moved.name} và mở lại sạch.")
            browser = open_browser()
    else:
        print(f"Phiên hiện tại: {session_state.describe(state_path)}")

    # Ghi nhật ký điều hướng/lỗi cho riêng lần đăng nhập. Nếu trang rơi vào vòng
    # lặp reload, file này cho biết nó nhảy qua những URL nào và server trả mã gì —
    # đủ để kết luận, khác với việc chỉ nhìn ảnh chụp console.
    log_path = Path(state_path).parent / f"login-debug-{datetime.now():%Y%m%d-%H%M%S}.log"
    try:
        browser.enable_event_log(str(log_path))
        print(f"Nhật ký lần đăng nhập này: {log_path}")
    except Exception as e:
        print(f"(không bật được nhật ký: {type(e).__name__}) — vẫn đăng nhập bình thường")

    print(f"\nĐang mở trình duyệt tới {url} ...")
    print("Hãy đăng nhập như bình thường trong cửa sổ vừa mở.")
    try:
        browser.navigate(url)
        input("\nĐăng nhập XONG thì quay lại đây, nhấn Enter để lưu phiên đăng nhập...\n")
        # Quy tắc 3: lưu thẳng, không navigate lại. Bọc try để dù browser có trục
        # trặc thì cũng in lỗi rõ ràng thay vì ném traceback vào mặt khách.
        try:
            p = Path(state_path)
            if p.exists():
                p.replace(p.with_suffix(p.suffix + ".bak"))
            print(browser.save_storage_state(state_path))
            if profile:
                print(f"✓ Phiên nằm trong profile: {profile}")
                print("  Agent sẽ dùng đúng profile này, và trình duyệt tự gia hạn phiên mỗi lần chạy.")
            print("✓ Từ giờ agent mở trang này sẽ ở trạng thái đăng nhập sẵn.")
        except Exception as e:
            print(f"✗ Không lưu được bản sao lưu phiên: {type(e).__name__}: {e}")
            if profile:
                print("  (Phiên trong profile thì vẫn còn — chỉ thiếu file sao lưu JSON.)")
        summary = browser.event_log_summary()
        if summary:
            print(f"\n{summary}")
            print("  Nếu trang bị lặp reload, gửi file nhật ký này để xem nó nhảy qua đâu.")
    finally:
        try:
            browser.stop()
        except Exception:
            pass
