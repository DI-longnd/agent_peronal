"""
ToolExecutor — thực thi tool_call từ server trên máy khách (PLAN.md 4.6).

An toàn (defense in depth): dù server ĐÃ chỉ gửi tool trong whitelist, app vẫn
tự validate lại tên tool trước khi chạy — server bị chiếm cũng không thể đẩy
lệnh ngoài danh sách BROWSER_TOOL_SPECS xuống máy khách.

Browser lifecycle: khởi động LAZY ở tool_call đầu tiên (không tốn RAM khi nhàn
rỗi), tự đóng sau browser_idle_seconds không có lệnh (threading.Timer reset mỗi
call). Mặc định headless=False — khách NHÌN THẤY cửa sổ Chrome agent đang làm gì.

Lưu ý: browser__extract KHÔNG có trong whitelist device — server không bao giờ
gửi nó xuống (server tự ghép page_markdown + LLM). SyncBrowserTool vì thế được
tạo với llm=None.
"""

from __future__ import annotations
import threading

from tools.browser.registration import BROWSER_TOOL_SPECS, PAGE_MARKDOWN_SPEC

# Chu kỳ sao lưu phiên đăng nhập trong lúc browser đang chạy (giây).
BACKUP_INTERVAL_SECONDS = 120


def _build_whitelist() -> dict[str, str]:
    """tool name -> method name trên SyncBrowserTool."""
    allowed = {
        spec["name"]: spec["method"]
        for spec in BROWSER_TOOL_SPECS
        if spec["name"] != "browser__extract"  # extract là composite phía server
    }
    allowed[PAGE_MARKDOWN_SPEC["name"]] = PAGE_MARKDOWN_SPEC["method"]
    return allowed


class ToolExecutor:
    def __init__(self, cfg: dict):
        self._cfg = cfg
        self._allowed = _build_whitelist()
        self._browser = None
        self._idle_timer: threading.Timer | None = None
        self._backup_timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def execute(self, tool: str, args: dict) -> str:
        """LUÔN trả string (kể cả lỗi) — WS loop không bao giờ được chết vì 1 tool."""
        method_name = self._allowed.get(tool)
        if method_name is None:
            return f"Từ chối: tool '{tool}' không nằm trong danh sách cho phép của app này."

        try:
            browser = self._ensure_browser()
            method = getattr(browser, method_name)
            if tool == "browser__type_sensitive":
                # secrets nằm trong config.json local — không bao giờ rời máy này
                return method(args["index"], args["placeholder"], self._cfg.get("secrets", {}))
            return method(**args)
        except Exception as e:
            return f"Lỗi khi chạy '{tool}' trên máy này: {type(e).__name__}: {e}"
        finally:
            self._reset_idle_timer()

    def _ensure_browser(self):
        with self._lock:
            if self._browser is None:
                # Import ở đây để app vẫn khởi động được (pairing, menu) khi
                # playwright chưa cài xong
                from tools.browser.browser_tool import SyncBrowserTool

                print("→ Khởi động trình duyệt...")
                browser = SyncBrowserTool(
                    llm=None,  # extract không chạy trên device
                    headless=bool(self._cfg.get("headless", False)),
                    storage_state_path=self._cfg.get("storage_state_path") or None,
                    user_data_dir=self._cfg.get("user_data_dir") or None,
                    downloads_dir=self._cfg.get("downloads_dir") or None,
                    viewport={
                        "width": int(self._cfg.get("viewport_width", 1280)),
                        "height": int(self._cfg.get("viewport_height", 950)),
                    },
                    use_vision=False,
                )
                browser.start()
                self._browser = browser
                self._start_backup_timer()
            return self._browser

    def _start_backup_timer(self) -> None:
        """Sao lưu phiên định kỳ trong lúc browser đang chạy.

        Vì sao không chỉ lưu lúc đóng: nếu người dùng tắt cứng app (bấm X trên cửa
        sổ console, máy sập) thì close() không bao giờ chạy và mọi cookie trang web
        cấp mới trong phiên đó mất sạch. Với profile Chrome thật thì Chromium tự lo,
        nhưng bản sao lưu JSON vẫn cần được làm tươi."""
        timer = threading.Timer(BACKUP_INTERVAL_SECONDS, self._backup_tick)
        timer.daemon = True
        self._backup_timer = timer
        timer.start()

    def _backup_tick(self) -> None:
        # KHÔNG chờ lấy lock: sao lưu là việc phụ, không được phép làm nghẽn
        # execute() khi một tool dài (vd wait 30s) đang chạy. Bận thì hẹn kỳ sau.
        if not self._lock.acquire(blocking=False):
            self._start_backup_timer()
            return
        try:
            if self._browser is None:
                return  # browser đã đóng -> dừng hẳn chuỗi timer
            self._persist_session(quiet=True)
            self._start_backup_timer()
        finally:
            self._lock.release()

    def _reset_idle_timer(self) -> None:
        with self._lock:
            if self._idle_timer is not None:
                self._idle_timer.cancel()
            idle = int(self._cfg.get("browser_idle_seconds", 300))
            self._idle_timer = threading.Timer(idle, self.close)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _persist_session(self, quiet: bool = False) -> None:
        """Sao lưu phiên đăng nhập ra file JSON.

        Với profile Chrome thật (user_data_dir) thì chính Chromium đã giữ phiên rồi;
        file JSON ở đây là BẢN SAO LƯU — để chuyển máy được, và để đọc ra mốc cấp
        phiên mà biết trang có gia hạn cho mình hay không.

        Ghi có điều kiện (should_persist): một lượt chạy hỏng hoặc chưa từng mở
        trang cần login KHÔNG được phép xoá mất phiên còn tốt trên đĩa."""
        from tools.browser import session_state

        path = self._cfg.get("storage_state_path")
        if not path or self._browser is None:
            return
        try:
            new = self._browser.export_state()
        except Exception as e:
            if not quiet:
                print(f"   (không chụp được phiên để lưu: {type(e).__name__})")
            return

        old = session_state.read(path)
        ok, reason = session_state.should_persist(old, new)
        if not ok:
            if not quiet:
                print(f"   {reason}")
            return
        try:
            session_state.write(path, new)
            report = session_state.renewal_report(old, new)
            # Bản sao lưu định kỳ chỉ lên tiếng khi có tin đáng chú ý (được gia hạn),
            # tránh spam log mỗi 2 phút.
            if not quiet:
                print(f"   Đã lưu lại phiên. {report}")
            elif 'GIA HẠN' in report:
                print(f"→ {report}")
        except OSError as e:
            if not quiet:
                print(f"   (không ghi được {path}: {e})")

    def close(self) -> None:
        with self._lock:
            for attr in ("_idle_timer", "_backup_timer"):
                timer = getattr(self, attr)
                if timer is not None:
                    timer.cancel()
                    setattr(self, attr, None)
            if self._browser is not None:
                print("→ Đóng trình duyệt (hết việc / nhàn rỗi).")
                self._persist_session()
                try:
                    self._browser.stop()
                except Exception:
                    pass
                self._browser = None
