"""
Remote tools — build ToolRegistry mà handler là RPC STUB gửi lệnh xuống device
của đúng user (PLAN.md 4.6). Từ góc nhìn AgentLoop, đây là tool bình thường
(handler(**args) -> str) — nó không biết và không cần biết tool chạy ở đâu.

Dùng CÙNG BROWSER_TOOL_SPECS với CLI/companion app — 1 nguồn khai báo duy nhất,
đồng thời là whitelist: server không có khả năng gửi lệnh ngoài danh sách này.

Riêng browser__extract là COMPOSITE (LLM key không được nằm trên máy khách):
  1. RPC browser__page_markdown -> device trả JSON {url, markdown, truncated, next_start}
  2. Server chạy extract_from_markdown (LLM) trên payload đó
"""

from __future__ import annotations
import json

from tools.registry import ToolRegistry, Tool
from tools.browser.registration import BROWSER_TOOL_SPECS, PAGE_MARKDOWN_SPEC
from tools.browser.extract_action import extract_from_markdown
from server.device_hub import DeviceHub


def _make_rpc_handler(hub: DeviceHub, user_id: str, tool_name: str, timeout: float):
    def handler(**args) -> str:
        try:
            return hub.call_tool(user_id, tool_name, args, timeout)
        except Exception as e:
            # Lỗi actionable cho LLM, không phải exception — đúng triết lý registry.execute
            return (
                f"Lỗi khi chạy '{tool_name}' trên máy khách: {e}. "
                "Nếu máy khách offline, báo người dùng mở app Personal Agent rồi thử lại."
            )

    return handler


def _make_extract_handler(hub: DeviceHub, user_id: str, llm, timeout: float):
    def handler(query: str, extract_links: bool = False, start_from_char: int = 0) -> str:
        try:
            raw = hub.call_tool(
                user_id, PAGE_MARKDOWN_SPEC["name"], {"start_from_char": start_from_char}, timeout
            )
            payload = json.loads(raw)
        except Exception as e:
            return (
                f"Lỗi khi lấy nội dung trang từ máy khách: {e}. "
                "Nếu máy khách offline, báo người dùng mở app Personal Agent rồi thử lại."
            )
        return extract_from_markdown(payload, query, llm)

    return handler


def build_remote_browser_registry(
    hub: DeviceHub, user_id: str, llm, timeout: float
) -> ToolRegistry:
    """Dùng làm local_tools_factory cho SubagentDispatcher trên server.
    Raise RuntimeError khi device offline — dispatcher bắt và trả message
    hướng dẫn NGAY, không tốn LLM call (PLAN.md 4.6)."""
    if not hub.is_online(user_id):
        raise RuntimeError("app trên máy khách chưa kết nối")

    registry = ToolRegistry()
    for spec in BROWSER_TOOL_SPECS:
        if spec["name"] == "browser__extract":
            handler = _make_extract_handler(hub, user_id, llm, timeout)
        else:
            handler = _make_rpc_handler(hub, user_id, spec["name"], timeout)
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
