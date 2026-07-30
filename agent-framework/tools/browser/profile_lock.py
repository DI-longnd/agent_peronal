"""Khoá độc quyền cho profile trình duyệt (user_data_dir).

Vì sao tự làm thay vì tin Chromium: tài liệu Playwright viết "Browsers do not
allow launching multiple instances with the same User Data Directory", nhưng đo
thực tế trên Windows thì Chromium KHÔNG hề báo lỗi — nó mở luôn cửa sổ thứ hai
trên cùng thư mục. Hai tiến trình cùng ghi vào một profile có thể làm hỏng cơ sở
dữ liệu cookie/IndexedDB, tức là mất phiên đăng nhập — đúng thứ ta đang cố giữ.

Cơ chế: khoá theo byte-range của hệ điều hành trên file .agent-profile-lock nằm
trong chính thư mục profile. Ưu điểm so với cách ghi PID rồi kiểm tra: khi tiến
trình chết (kể cả bị kill cứng), HĐH tự nhả khoá — không bao giờ để lại khoá mồ
côi khiến app không khởi động được nữa.

Kèm thêm một sổ đăng ký trong tiến trình: khoá của Windows/POSIX cấp theo file
handle nên hành vi khi cùng một tiến trình khoá hai lần là không đồng nhất giữa
các nền tảng — sổ này đảm bảo kết quả giống nhau ở mọi nơi.
"""

from __future__ import annotations
import os
import threading
from pathlib import Path

LOCK_FILENAME = '.agent-profile-lock'
OWNER_FILENAME = '.agent-profile-owner'  # chỉ để chẩn đoán, KHÔNG dùng để quyết định


class ProfileInUse(RuntimeError):
    """Profile đang được một cửa sổ/tiến trình khác sử dụng."""


_held: set[str] = set()
_held_guard = threading.Lock()


if os.name == 'nt':
    import msvcrt

    def _os_lock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def _os_unlock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _os_lock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _os_unlock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _owner_hint(profile: Path) -> str:
    try:
        pid = (profile / OWNER_FILENAME).read_text(encoding='utf-8').strip()
        return f' (tiến trình đang giữ: PID {pid})' if pid else ''
    except OSError:
        return ''


class ProfileLock:
    def __init__(self, profile_dir: str | Path):
        self._dir = Path(profile_dir)
        # Windows không phân biệt hoa thường trong đường dẫn — chuẩn hoá để hai
        # cách viết khác nhau của cùng một thư mục vẫn coi là một.
        self._key = os.path.normcase(str(self._dir.resolve()))
        self._path = self._dir / LOCK_FILENAME
        self._fh = None

    def acquire(self) -> None:
        with _held_guard:
            if self._key in _held:
                raise ProfileInUse(
                    f'Profile {self._dir} đang được dùng bởi một trình duyệt khác '
                    'trong cùng tiến trình này.'
                )
            _held.add(self._key)

        fh = None
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            fh = open(self._path, 'a+b')
            _os_lock(fh)
        except OSError as e:
            if fh is not None:
                fh.close()
            with _held_guard:
                _held.discard(self._key)
            raise ProfileInUse(
                f'Profile {self._dir} đang được một cửa sổ khác sử dụng'
                f'{_owner_hint(self._dir)}.\n'
                'Thường gặp khi chạy "--login" trong lúc app chính vẫn đang chạy — '
                'hãy đóng bớt rồi thử lại. Hai cửa sổ dùng chung profile có thể làm '
                'hỏng phiên đăng nhập đã lưu.'
            ) from e

        self._fh = fh
        # Ghi PID ra file RIÊNG, không phải file đang bị khoá byte-range.
        try:
            (self._dir / OWNER_FILENAME).write_text(str(os.getpid()), encoding='utf-8')
        except OSError:
            pass  # chỉ là thông tin chẩn đoán, thiếu cũng không sao

    def release(self) -> None:
        if self._fh is not None:
            try:
                _os_unlock(self._fh)
            except OSError:
                pass
            finally:
                self._fh.close()
                self._fh = None
        try:
            (self._dir / OWNER_FILENAME).unlink()
        except OSError:
            pass
        with _held_guard:
            _held.discard(self._key)

    def __enter__(self) -> 'ProfileLock':
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
