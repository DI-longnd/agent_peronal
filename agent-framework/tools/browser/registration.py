"""
Khai báo + đăng ký các tool browser__* (namespaced).

Phase 0 (PLAN.md mục 4.6): chuyển sang SPEC-DRIVEN — `BROWSER_TOOL_SPECS` là
NGUỒN KHAI BÁO DUY NHẤT (tên, mô tả, JSON schema, method tương ứng trên
SyncBrowserTool) cho cả 3 nơi dùng:
  1. CLI all-in-one (main.py): build_browser_registry() bind handler = method local.
  2. Server (server/remote_tools.py): bind handler = RPC stub gửi lệnh xuống device.
  3. Companion app (local-agent/executor.py): whitelist tool được phép thực thi.

QUAN TRỌNG: file này phải import được khi KHÔNG cài playwright (server không cài
playwright — nó chỉ cần specs). Vì vậy KHÔNG import playwright/browser_tool ở
module level — chỉ import trong TYPE_CHECKING.

Sensitive data (password, API key dùng để login...) được nạp từ biến môi trường
có tiền tố BROWSER_SECRET_ (vd: BROWSER_SECRET_SITE_PASSWORD -> key 'site_password'),
KHÔNG bao giờ lộ ra schema của browser__type_sensitive gửi cho LLM — LLM chỉ thấy
tham số 'placeholder' (tên key), không thấy giá trị thật (đóng gói qua closure).
"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING
from tools.registry import ToolRegistry, Tool

if TYPE_CHECKING:
    from tools.browser.browser_tool import SyncBrowserTool


# Mỗi spec: name (tên tool namespaced), description + parameters (JSON schema gửi LLM),
# method (tên method trên SyncBrowserTool), defer_loading (tool ít dùng -> agent phải
# tool_search mới thấy).
BROWSER_TOOL_SPECS: list[dict] = [
    {
        "name": "browser__navigate",
        "description": "Mở 1 URL trong trình duyệt.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "new_tab": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
        "method": "navigate",
        "defer_loading": False,
    },
    {
        "name": "browser__get_state",
        "description": (
            "Xem các element tương tác được (link, button, input...) trên trang hiện tại, "
            "kèm chỉ số [index] để dùng cho browser__click/browser__type. "
            "LUÔN gọi tool này đầu tiên trước khi click/type, và gọi lại sau khi trang thay đổi."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "with_screenshot": {
                    "type": "boolean",
                    "default": False,
                    "description": "Chỉ bật nếu model đang dùng có vision (GPT-4o, Claude...). DeepSeek không có vision.",
                },
            },
        },
        "method": "get_state",
        "defer_loading": False,
    },
    {
        "name": "browser__click",
        "description": "Click 1 element theo [index] lấy từ browser__get_state.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "coordinate_x": {"type": "integer"},
                "coordinate_y": {"type": "integer"},
            },
            "required": ["index"],
        },
        "method": "click",
        "defer_loading": False,
    },
    {
        "name": "browser__type",
        "description": "Gõ text vào ô input theo [index] lấy từ browser__get_state.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "text": {"type": "string"},
                "clear": {"type": "boolean", "default": True, "description": "Xoá text cũ trước khi gõ"},
            },
            "required": ["index", "text"],
        },
        "method": "input_text",
        "defer_loading": False,
    },
    {
        # LƯU Ý kiến trúc phân tán: tool này KHÔNG chạy nguyên vẹn trên device.
        # Device chỉ chạy browser__page_markdown (lấy nội dung trang); nửa LLM
        # extraction chạy trên server (extract_from_markdown) — vì LLM key không
        # được nằm trên máy khách. CLI all-in-one thì method extract() ghép cả 2.
        "name": "browser__extract",
        "description": (
            "Trích xuất thông tin từ trang hiện tại bằng LLM (đọc nội dung trang đã chuyển "
            "sang markdown). Dùng khi cần lấy dữ liệu cụ thể (giá sản phẩm, danh sách kết quả...) "
            "thay vì tự đọc toàn bộ trang."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mô tả thông tin cần lấy"},
                "extract_links": {"type": "boolean", "default": False},
                "start_from_char": {"type": "integer", "default": 0, "description": "Tiếp tục đọc từ vị trí ký tự này nếu bị cắt"},
            },
            "required": ["query"],
        },
        "method": "extract",
        "defer_loading": False,
    },
    # --- Các tool ít dùng hơn -> defer_loading, agent tự tool_search khi cần ---
    {
        "name": "browser__search",
        "description": "Tìm kiếm trên web (DuckDuckGo/Google/Bing) thay vì mở URL cụ thể.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "engine": {"type": "string", "enum": ["duckduckgo", "google", "bing"], "default": "duckduckgo"},
            },
            "required": ["query"],
        },
        "method": "search",
        "defer_loading": True,
    },
    {
        "name": "browser__go_back",
        "description": "Quay lại trang trước đó trong lịch sử duyệt web.",
        "parameters": {"type": "object", "properties": {}},
        "method": "go_back",
        "defer_loading": True,
    },
    {
        "name": "browser__scroll",
        "description": "Cuộn trang lên/xuống theo số 'trang' (1.0 = 1 viewport height).",
        "parameters": {
            "type": "object",
            "properties": {
                "pages": {"type": "number", "default": 1.0},
                "direction": {"type": "string", "enum": ["down", "up"], "default": "down"},
            },
        },
        "method": "scroll",
        "defer_loading": True,
    },
    {
        "name": "browser__press_key",
        "description": "Gửi 1 phím đặc biệt (Enter, Escape, Tab...) tới trang.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Vd: Enter, Escape, Tab"}},
            "required": ["key"],
        },
        "method": "press_key",
        "defer_loading": True,
    },
    {
        "name": "browser__wait",
        "description": "Chờ N giây (tối đa 30s) — dùng khi trang đang tải/animate.",
        "parameters": {
            "type": "object",
            "properties": {"seconds": {"type": "integer", "default": 3}},
        },
        "method": "wait",
        "defer_loading": True,
    },
    {
        "name": "browser__type_sensitive",
        "description": (
            "Gõ 1 giá trị NHẠY CẢM (mật khẩu, API key...) vào ô input theo [index]. "
            "Chỉ truyền 'placeholder' (tên key, vd 'site_password') — KHÔNG BAO GIỜ truyền giá trị "
            "thật, vì bạn (LLM) không được phép biết giá trị thật. Giá trị được nạp sẵn từ "
            "biến môi trường BROWSER_SECRET_<PLACEHOLDER>."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "placeholder": {"type": "string", "description": "Tên key trong sensitive data, vd 'site_password'"},
            },
            "required": ["index", "placeholder"],
        },
        "method": "type_sensitive",
        "defer_loading": True,
    },
]

# Tool NỘI BỘ của kiến trúc phân tán — KHÔNG cho agent thấy (không nằm trong
# BROWSER_TOOL_SPECS). Server gọi nó qua RPC để lấy nội dung trang, rồi tự chạy
# LLM extraction (extract_from_markdown) — xem PLAN.md 4.6.
PAGE_MARKDOWN_SPEC: dict = {
    "name": "browser__page_markdown",
    "description": "Nội bộ: trả JSON {url, markdown, truncated, next_start} của trang hiện tại.",
    "parameters": {
        "type": "object",
        "properties": {"start_from_char": {"type": "integer", "default": 0}},
    },
    "method": "page_markdown",
    "defer_loading": True,
}


def load_sensitive_data_from_env(prefix: str = "BROWSER_SECRET_") -> dict[str, str]:
    data = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            placeholder = key[len(prefix):].lower()
            data[placeholder] = value
    return data


def build_browser_registry(
    sync_browser: "SyncBrowserTool", sensitive_data: dict[str, str] | None = None
) -> ToolRegistry:
    """Bind mỗi spec vào method local của SyncBrowserTool — dùng cho CLI all-in-one
    và companion app (nơi browser chạy cùng tiến trình)."""
    sensitive_data = sensitive_data or {}
    registry = ToolRegistry()
    for spec in BROWSER_TOOL_SPECS:
        method = getattr(sync_browser, spec["method"])
        if spec["name"] == "browser__type_sensitive":
            # Closure đóng gói sensitive_data — LLM chỉ truyền placeholder, không thấy giá trị
            handler = lambda index, placeholder, _m=method: _m(index, placeholder, sensitive_data)
        else:
            handler = method
        registry.register(
            Tool(
                name=spec["name"],
                description=spec["description"],
                parameters=spec["parameters"],
                handler=handler,
                defer_loading=spec["defer_loading"],
            )
        )
    return registry
