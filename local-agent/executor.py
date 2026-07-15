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
                    use_vision=False,
                )
                browser.start()
                self._browser = browser
            return self._browser

    def _reset_idle_timer(self) -> None:
        with self._lock:
            if self._idle_timer is not None:
                self._idle_timer.cancel()
            idle = int(self._cfg.get("browser_idle_seconds", 300))
            self._idle_timer = threading.Timer(idle, self.close)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def close(self) -> None:
        with self._lock:
            if self._idle_timer is not None:
                self._idle_timer.cancel()
                self._idle_timer = None
            if self._browser is not None:
                print("→ Đóng trình duyệt (hết việc / nhàn rỗi).")
                try:
                    self._browser.stop()
                except Exception:
                    pass
                self._browser = None
