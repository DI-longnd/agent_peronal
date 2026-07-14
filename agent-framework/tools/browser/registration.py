"""
Đăng ký các tool browser__* (namespaced) vào ToolRegistry, dựa trên 1
SyncBrowserTool đã start() sẵn.

Sensitive data (password, API key dùng để login...) được nạp từ biến môi
trường có tiền tố BROWSER_SECRET_ (vd: BROWSER_SECRET_SITE_PASSWORD ->
key 'site_password'), KHÔNG bao giờ lộ ra schema của browser__type_sensitive
gửi cho LLM — LLM chỉ thấy tham số 'placeholder' (tên key), không thấy
'sensitive_data' (giá trị thật đã được đóng gói sẵn qua closure).
"""

from __future__ import annotations
import os
from tools.registry import ToolRegistry, Tool
from tools.browser.browser_tool import SyncBrowserTool


def load_sensitive_data_from_env(prefix: str = "BROWSER_SECRET_") -> dict[str, str]:
    data = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            placeholder = key[len(prefix):].lower()
            data[placeholder] = value
    return data


def build_browser_registry(sync_browser: SyncBrowserTool, sensitive_data: dict[str, str] | None = None) -> ToolRegistry:
    sensitive_data = sensitive_data or {}
    registry = ToolRegistry()

    registry.register(Tool(
        name="browser__navigate",
        description="Mở 1 URL trong trình duyệt.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "new_tab": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
        handler=sync_browser.navigate,
    ))

    registry.register(Tool(
        name="browser__get_state",
        description=(
            "Xem các element tương tác được (link, button, input...) trên trang hiện tại, "
            "kèm chỉ số [index] để dùng cho browser__click/browser__type. "
            "LUÔN gọi tool này đầu tiên trước khi click/type, và gọi lại sau khi trang thay đổi."
        ),
        parameters={
            "type": "object",
            "properties": {
                "with_screenshot": {
                    "type": "boolean", "default": False,
                    "description": "Chỉ bật nếu model đang dùng có vision (GPT-4o, Claude...). DeepSeek không có vision.",
                },
            },
        },
        handler=sync_browser.get_state,
    ))

    registry.register(Tool(
        name="browser__click",
        description="Click 1 element theo [index] lấy từ browser__get_state.",
        parameters={
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "coordinate_x": {"type": "integer"},
                "coordinate_y": {"type": "integer"},
            },
            "required": ["index"],
        },
        handler=sync_browser.click,
    ))

    registry.register(Tool(
        name="browser__type",
        description="Gõ text vào ô input theo [index] lấy từ browser__get_state.",
        parameters={
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "text": {"type": "string"},
                "clear": {"type": "boolean", "default": True, "description": "Xoá text cũ trước khi gõ"},
            },
            "required": ["index", "text"],
        },
        handler=sync_browser.input_text,
    ))

    registry.register(Tool(
        name="browser__extract",
        description=(
            "Trích xuất thông tin từ trang hiện tại bằng LLM (đọc nội dung trang đã chuyển "
            "sang markdown). Dùng khi cần lấy dữ liệu cụ thể (giá sản phẩm, danh sách kết quả...) "
            "thay vì tự đọc toàn bộ trang."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mô tả thông tin cần lấy"},
                "extract_links": {"type": "boolean", "default": False},
                "start_from_char": {"type": "integer", "default": 0, "description": "Tiếp tục đọc từ vị trí ký tự này nếu bị cắt"},
            },
            "required": ["query"],
        },
        handler=sync_browser.extract,
    ))

    # --- Các tool ít dùng hơn -> defer_loading, agent tự tool_search khi cần ---
    registry.register(Tool(
        name="browser__search",
        description="Tìm kiếm trên web (DuckDuckGo/Google/Bing) thay vì mở URL cụ thể.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "engine": {"type": "string", "enum": ["duckduckgo", "google", "bing"], "default": "duckduckgo"},
            },
            "required": ["query"],
        },
        handler=sync_browser.search,
        defer_loading=True,
    ))

    registry.register(Tool(
        name="browser__go_back",
        description="Quay lại trang trước đó trong lịch sử duyệt web.",
        parameters={"type": "object", "properties": {}},
        handler=sync_browser.go_back,
        defer_loading=True,
    ))

    registry.register(Tool(
        name="browser__scroll",
        description="Cuộn trang lên/xuống theo số 'trang' (1.0 = 1 viewport height).",
        parameters={
            "type": "object",
            "properties": {
                "pages": {"type": "number", "default": 1.0},
                "direction": {"type": "string", "enum": ["down", "up"], "default": "down"},
            },
        },
        handler=sync_browser.scroll,
        defer_loading=True,
    ))

    registry.register(Tool(
        name="browser__press_key",
        description="Gửi 1 phím đặc biệt (Enter, Escape, Tab...) tới trang.",
        parameters={
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Vd: Enter, Escape, Tab"}},
            "required": ["key"],
        },
        handler=sync_browser.press_key,
        defer_loading=True,
    ))

    registry.register(Tool(
        name="browser__wait",
        description="Chờ N giây (tối đa 30s) — dùng khi trang đang tải/animate.",
        parameters={
            "type": "object",
            "properties": {"seconds": {"type": "integer", "default": 3}},
        },
        handler=sync_browser.wait,
        defer_loading=True,
    ))

    registry.register(Tool(
        name="browser__type_sensitive",
        description=(
            "Gõ 1 giá trị NHẠY CẢM (mật khẩu, API key...) vào ô input theo [index]. "
            "Chỉ truyền 'placeholder' (tên key, vd 'site_password') — KHÔNG BAO GIỜ truyền giá trị "
            "thật, vì bạn (LLM) không được phép biết giá trị thật. Giá trị được nạp sẵn từ "
            "biến môi trường BROWSER_SECRET_<PLACEHOLDER>."
        ),
        parameters={
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "placeholder": {"type": "string", "description": "Tên key trong sensitive data, vd 'site_password'"},
            },
            "required": ["index", "placeholder"],
        },
        handler=lambda index, placeholder: sync_browser.type_sensitive(index, placeholder, sensitive_data),
        defer_loading=True,
    ))

    return registry
