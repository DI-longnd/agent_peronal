"""Kiểm tra sức khoẻ file session (storage_state) trước khi nạp vào browser.

Lý do tồn tại: storage_state gồm 2 phần có tuổi thọ KHÁC NHAU —
  - cookie: có expiry, Chromium tự bỏ cookie hết hạn khi nạp;
  - localStorage: KHÔNG có expiry, luôn được nạp nguyên vẹn.
Nên khi session hết hạn, trang web boot lên trong trạng thái mâu thuẫn: cookie
nói "chưa đăng nhập" còn localStorage vẫn cache "đã đăng nhập shop X" → app gọi
API bị 401 → redirect về login → đọc lại cache → lặp (biểu hiện: trang reload
xoay liên tục, console đầy lỗi JSON.parse cache). Nạp nửa vời còn tệ hơn không
nạp gì, vì vậy: session đã chết -> KHÔNG nạp, để trang login sạch.

Phiên TikTok Seller quan sát được (23-07-2026, tài khoản seller-us) có
max_age = 259199s = đúng 3 ngày. KHÔNG có tài liệu chính thức nào của TikTok
công bố con số này — chính sách cookie của họ không nhắc tới sessionid/sid_guard
hay các biến thể *_tiktokseller. Nên coi đây là quan sát 1 mẫu, không phải hằng
số: hết hạn là bình thường, phải báo rõ cho người dùng thay vì để agent thao tác
mù trên trang đã đăng xuất.

Câu hỏi CÒN BỎ NGỎ mà module này giúp đo: 3 ngày đó là hạn CỨNG (tính từ lúc
đăng nhập, dùng hay không dùng cũng chết) hay hạn TRƯỢT (mỗi lần dùng được TikTok
cấp phiên mới)? renewal_report() so hai bản chụp để trả lời — xem executor.py,
nơi lưu lại phiên sau mỗi lượt chạy.
"""

from __future__ import annotations
import json
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

# Tiền tố tên cookie chứa phiên đăng nhập thật (không phải cookie tracking/fingerprint
# như ttwid/odin_tt/msToken — mấy cái đó sống cả năm và vẫn "còn hạn" kể cả khi đã
# đăng xuất, nên KHÔNG dùng để xét sống/chết). Danh sách theo TikTok/ByteDance;
# site khác không có cookie nào khớp -> trả 'unknown' và ta nạp state như cũ.
AUTH_COOKIE_PREFIXES = (
    'sessionid', 'sid_tt', 'uid_tt', 'sso_uid_tt', 'sso_user', 'sid_ucp', 'ssid_ucp',
)


def _is_auth(name: str) -> bool:
    return any(name.startswith(p) for p in AUTH_COOKIE_PREFIXES)


def _expiry(cookie: dict) -> float | None:
    """None = session-cookie (không hết hạn theo thời gian, còn sống tới khi đóng
    browser — storage_state vẫn lưu/nạp được nên coi là sống)."""
    exp = cookie.get('expires')
    if exp is None or exp <= 0:
        return None
    return float(exp)


def status(state: dict, now: float | None = None) -> tuple[str, str]:
    """('alive' | 'expired' | 'empty' | 'unknown', câu mô tả cho người dùng)."""
    now = now or time.time()
    cookies = state.get('cookies') or []
    if not cookies:
        return 'empty', 'File session không có cookie nào.'

    auth = [c for c in cookies if _is_auth(c.get('name', ''))]
    if not auth:
        return 'unknown', f'{len(cookies)} cookie, không nhận diện được cookie phiên đăng nhập.'

    alive, latest_dead = [], None
    for c in auth:
        exp = _expiry(c)
        if exp is None or exp > now:
            alive.append(c)
        elif latest_dead is None or exp > latest_dead:
            latest_dead = exp

    if alive:
        # Hạn sớm nhất trong nhóm còn sống = lúc phiên thực sự đứt.
        soonest = min((e for e in (_expiry(c) for c in alive) if e is not None), default=None)
        if soonest is None:
            return 'alive', f'{len(alive)}/{len(auth)} cookie phiên còn sống (session-cookie).'
        left = (soonest - now) / 86400
        return 'alive', (f'Phiên đăng nhập còn hiệu lực tới '
                         f'{datetime.fromtimestamp(soonest):%d-%m-%Y %H:%M} (còn {left:.1f} ngày).')

    when = f'{datetime.fromtimestamp(latest_dead):%d-%m-%Y %H:%M}' if latest_dead else '?'
    return 'expired', f'Phiên đăng nhập ĐÃ HẾT HẠN lúc {when} — cần đăng nhập lại.'


def expires_at(state: dict, now: float | None = None) -> float | None:
    """Thời điểm phiên đứt (giây epoch), None nếu không xác định được.

    Cùng cách tính với status(): hạn SỚM NHẤT trong nhóm cookie phiên còn sống —
    một cookie chết là cả phiên hỏng, nên hạn sớm nhất mới là hạn thật."""
    now = now or time.time()
    auth = [c for c in (state.get('cookies') or []) if _is_auth(c.get('name', ''))]
    exps = [e for e in (_expiry(c) for c in auth) if e is not None and e > now]
    return min(exps) if exps else None


def hours_left(path: str | Path | None, now: float | None = None) -> float | None:
    """Số giờ còn lại của phiên đã lưu. None = không đọc được / không xác định."""
    state = read(path) if path else None
    if not state:
        return None
    exp = expires_at(state, now)
    return None if exp is None else (exp - (now or time.time())) / 3600


def issued_at(state: dict) -> float | None:
    """Thời điểm server cấp phiên hiện tại, đọc từ cookie sid_guard*.

    Giá trị sid_guard có dạng  <sessionid>|<created_ts>|<max_age>|<expires>
    (thường bị url-encode, dấu | thành %7C). Đây là mốc DUY NHẤT cho biết phiên
    có được cấp lại hay không — expiry của cookie thì luôn = created + max_age
    nên không phân biệt được 'cấp mới' với 'vẫn cái cũ'."""
    for c in state.get('cookies') or []:
        if not c.get('name', '').startswith('sid_guard'):
            continue
        parts = urllib.parse.unquote(c.get('value', '')).replace('%7C', '|').split('|')
        if len(parts) >= 2 and parts[1].isdigit():
            return float(parts[1])
    return None


def renewal_report(old: dict | None, new: dict) -> str:
    """So 2 bản chụp để trả lời: TikTok có gia hạn phiên khi ta dùng không?"""
    new_at = issued_at(new)
    if new_at is None:
        return 'Không đọc được mốc cấp phiên (không có cookie sid_guard).'
    old_at = issued_at(old) if old else None
    if old_at is None:
        return f'Phiên cấp lúc {datetime.fromtimestamp(new_at):%d-%m-%Y %H:%M} (chưa có bản trước để so).'
    if new_at > old_at + 1:
        moved = (new_at - old_at) / 3600
        return (f'✓ TikTok ĐÃ GIA HẠN phiên: cấp lại lúc '
                f'{datetime.fromtimestamp(new_at):%d-%m-%Y %H:%M} '
                f'(bản trước {datetime.fromtimestamp(old_at):%d-%m-%Y %H:%M}, tiến {moved:.1f}h) '
                f'→ hạn là hạn TRƯỢT, cứ dùng đều thì không mất phiên.')
    return (f'• Phiên KHÔNG được cấp lại (vẫn mốc '
            f'{datetime.fromtimestamp(old_at):%d-%m-%Y %H:%M}) → nhiều khả năng là hạn CỨNG '
            f'tính từ lúc đăng nhập.')


def should_persist(old: dict | None, new: dict) -> tuple[bool, str]:
    """Có nên ghi đè file session bằng bản chụp mới không?

    Nguyên tắc: KHÔNG BAO GIỜ để một lượt chạy hỏng (bị đăng xuất giữa chừng,
    hoặc chưa từng mở trang cần login) xoá mất phiên còn tốt đang có trên đĩa."""
    new_code = status(new)[0]
    old_code = status(old)[0] if old else 'missing'
    if new_code in ('empty', 'expired') and old_code == 'alive':
        return False, (f'Giữ nguyên file cũ: bản chụp mới không có phiên hợp lệ '
                       f'({new_code}) trong khi file hiện tại vẫn còn hạn.')
    if new_code in ('empty',) and old_code != 'missing':
        return False, 'Giữ nguyên file cũ: bản chụp mới rỗng.'
    return True, ''


def write(path: str | Path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')


def read(path: str | Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None


def describe(path: str | Path) -> str:
    """Một dòng mô tả tình trạng session, để app in lúc khởi động."""
    state = read(path)
    if state is None:
        return f'Chưa có phiên đăng nhập nào được lưu ({path}).'
    return status(state)[1]


def load_for_context(path: str | Path | None, log=None) -> dict | None:
    """State để truyền vào browser_context, hoặc None nếu không nên nạp.

    Trả None khi: không có file / file hỏng / phiên đã hết hạn. Riêng trường hợp
    hết hạn phải trả None (chứ không nạp rồi để Chromium tự lọc cookie) — xem
    docstring đầu file: nạp nửa vời gây vòng lặp reload."""
    if not path:
        return None
    state = read(path)
    if state is None:
        return None

    code, message = status(state)
    if code == 'expired':
        if log:
            log(f'⚠️  {message}')
            log(f'    Bỏ qua file session cũ ({path}) để tránh trang web bị lặp reload.')
            log('    Chạy lại:  PersonalAgent --login https://affiliate.tiktok.com')
        return None
    if log and code == 'alive':
        log(f'✓ {message}')
    return state
