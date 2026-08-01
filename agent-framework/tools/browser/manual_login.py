"""Đăng nhập thủ công 1 lần + kiểm tra phiên — dùng chung cho MỌI cửa ngõ.

Vì sao gom về đây: trước có hai bản gần giống nhau (local-agent/login_setup.py cho
companion app, scripts/setup_browser_login.py cho CLI all-in-one). Chúng lệch nhau
theo thời gian và CÙNG dính một lỗi — reload trang trước khi lưu, làm hỏng phiên khi
tab đã đóng — rồi được sửa riêng lẻ ở hai nơi vào hai thời điểm khác nhau. Một bản
duy nhất thì không tái diễn được.

Ba quy tắc, mỗi cái đổi bằng một lần hỏng thật:

  1. Đăng nhập vào ĐÚNG profile mà agent sẽ dùng. Chromium tự giữ và tự gia hạn
     cookie/localStorage/IndexedDB ở đó — đây là nơi phiên sống lâu nhất.

  2. Profile đang chứa phiên ĐÃ HẾT HẠN thì dọn đi rồi làm lại từ đầu. Đăng nhập đè
     lên phiên chết khiến trang rơi vào trạng thái cookie-chết/cache-sống và lặp
     reload — chính người dùng cũng không đăng nhập lại được. Chỉ dọn khi thật sự
     chết, để không xoá oan phiên của các trang khác trong cùng profile.

  3. KHÔNG reload trang trước khi lưu bản sao lưu. storage_state() đọc thẳng từ
     context; reload chỉ thêm cơ hội TargetClosedError và làm mất công đăng nhập.
"""

from __future__ import annotations
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from tools.browser import session_state


def default_profile_dir() -> Path:
    """Profile mặc định — CỐ TÌNH trùng với companion app để đăng nhập 1 lần là
    cả CLI lẫn app đều dùng được. Hai bên không chạy đồng thời được (profile_lock
    sẽ chặn kèm thông báo rõ), đó là hành vi mong muốn."""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "PersonalAgent" / "browser-profile"


def default_state_path() -> Path:
    """Bản sao lưu phiên dạng JSON — nằm CẠNH profile, cùng chỗ companion app ghi.

    Trước đây CLI trỏ vào agent-framework/.auth/state.json còn app ghi vào %APPDATA%.
    Hai file trôi khỏi nhau: đo ngày 01-08-2026, file của CLI còn là phiên 18-07 đã
    chết trong khi phiên thật vẫn sống. Không gây lỗi (dùng profile thì file JSON chỉ
    là bản lưu dự phòng, không được nạp), nhưng ai đi kiểm tra bằng file đều bị nó
    đánh lừa. Một đường dẫn duy nhất thì không lệch được."""
    return default_profile_dir().parent / "state.json"


def archive_profile(profile: Path, attempts: int = 6) -> Path:
    """Dời profile cũ sang tên có mốc thời gian (không xoá hẳn — lỡ tay còn cứu).

    Thử lại nhiều lần: trên Windows, ngay sau khi Chromium thoát thì handle của nó
    có thể chưa được giải phóng hết, di chuyển thư mục sẽ dính 'WinError 32'."""
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


def _open(url_hint: str, profile: Path | None, state_path: str | None, headless: bool):
    from tools.browser.browser_tool import SyncBrowserTool

    browser = SyncBrowserTool(
        llm=None,
        headless=headless,
        storage_state_path=None if profile else state_path,
        user_data_dir=str(profile) if profile else None,
    )
    browser.start()
    return browser


def run_manual_login(url: str, *, user_data_dir: str | Path | None,
                     storage_state_path: str) -> None:
    """Mở cửa sổ thật cho người dùng tự đăng nhập, rồi lưu lại phiên."""
    profile = Path(user_data_dir) if user_data_dir else None
    browser = _open(url, profile, storage_state_path, headless=False)

    # Quy tắc 2: soi phiên đang có, chết thì dọn và mở lại sạch.
    if profile:
        try:
            code, message = session_state.status(browser.export_state())
        except Exception:
            code, message = "unknown", ""
        if code == "empty":
            print("Profile trình duyệt còn trống — đây là lần đăng nhập đầu tiên.")
        else:
            print(f"Phiên trong profile: {message or code}")
        if code == "expired":
            browser.stop()
            moved = archive_profile(profile)
            print(f"Phiên đã chết — dọn profile cũ sang {moved.name} và mở lại sạch.")
            browser = _open(url, profile, storage_state_path, headless=False)
    else:
        print(f"Phiên hiện tại: {session_state.describe(storage_state_path)}")

    # Nhật ký điều hướng cho riêng lần đăng nhập: nếu trang lặp reload thì file này
    # cho biết nó nhảy qua những URL nào và server trả mã gì.
    log_path = Path(storage_state_path).parent / f"login-debug-{datetime.now():%Y%m%d-%H%M%S}.log"
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
        try:
            p = Path(storage_state_path)
            if p.exists():
                p.replace(p.with_suffix(p.suffix + ".bak"))
            print(browser.save_storage_state(storage_state_path))
            if profile:
                print(f"✓ Phiên nằm trong profile: {profile}")
                print("  Agent sẽ dùng đúng profile này ở mọi lần chạy sau.")
            print("✓ Từ giờ agent mở trang này sẽ ở trạng thái đăng nhập sẵn.")
        except Exception as e:
            print(f"✗ Không lưu được bản sao lưu phiên: {type(e).__name__}: {e}")
            if profile:
                print("  (Phiên trong profile vẫn còn — chỉ thiếu file sao lưu JSON.)")
        summary = browser.event_log_summary()
        if summary:
            print(f"\n{summary}")
            print("  Nếu trang bị lặp reload, gửi file nhật ký này để xem nó nhảy qua đâu.")
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def check_session(url: str, *, user_data_dir: str | Path | None,
                  storage_state_path: str, headless: bool = True) -> bool:
    """Kiểm tra phiên còn dùng được không. True = còn đăng nhập.

    Bước rẻ trước: đọc hạn từ file, không cần mở browser. Chỉ mở trang khi hạn còn
    hiệu lực — để biết TikTok có thật sự chấp nhận phiên đó không (hết hạn thì khỏi
    mở cho tốn thời gian)."""
    print(f"Phiên đã lưu: {session_state.describe(storage_state_path)}")
    profile = Path(user_data_dir) if user_data_dir else None
    if profile:
        print(f"Profile: {profile}  ({'có' if profile.exists() else 'CHƯA có'})")

    browser = _open(url, profile, storage_state_path, headless=headless)
    try:
        print(browser.navigate(url))
        browser.wait(5)
        state = browser.get_state()
        if "PHÁT HIỆN CAPTCHA" in state:
            print("⚠️  Trang đang bị captcha chặn — chưa kết luận được, thử lại sau.")
            return False
        text = state.lower()
        logged_out = any(k in text for k in ("đăng nhập", "log in", "sign in"))
        print(f"URL sau khi mở : {state.splitlines()[0][5:130]}")
        print(f"Kết luận       : {'CHƯA đăng nhập' if logged_out else 'ĐANG đăng nhập'}")
        return not logged_out
    finally:
        try:
            browser.stop()
        except Exception:
            pass
