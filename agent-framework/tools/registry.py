"""
Tool Registry — áp dụng 3 nguyên tắc từ "Writing effective tools for AI agents"
và "Advanced tool use" (Anthropic):

1. Namespacing: tool đặt tên theo domain__action (vd: ecom__check_order) để
   agent khoanh vùng đúng nhóm trước khi chọn tool cụ thể.
2. defer_loading: tool không "nặng ký" (ít dùng, hoặc thuộc domain phụ) được
   đánh dấu defer=True — không nạp vào context ngay, chỉ xuất hiện sau khi
   agent gọi tool_search và tìm thấy nó.
3. Consolidation: khuyến khích gộp nhiều API call nhỏ thành 1 tool "nặng"
   (vd: schedule_event thay vì list_users + list_events + create_event riêng lẻ)
   — việc này do người viết tool quyết định khi register, registry không ép.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str  # namespaced, vd "ecom__check_order"
    description: str
    parameters: dict[str, Any]  # JSON schema
    handler: Callable[..., str]
    defer_loading: bool = False

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._activated: set[str] = set()  # tool đã được tool_search mở khoá trong session này

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        if not tool.defer_loading:
            self._activated.add(tool.name)

    def activate(self, tool_name: str) -> Tool | None:
        """Được gọi bởi tool_search khi tìm thấy match — 'mở khoá' tool vào context."""
        if tool_name in self._tools:
            self._activated.add(tool_name)
            return self._tools[tool_name]
        return None

    def active_schemas(self) -> list[dict[str, Any]]:
        """Chỉ trả về schema của tool đang active — đây là phần load vào context model."""
        return [self._tools[name].to_openai_schema() for name in self._activated]

    def all_tools(self) -> list[Tool]:
        """Toàn bộ tool đã đăng ký (kể cả deferred) — dùng cho tool_search quét."""
        return list(self._tools.values())

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Lỗi: tool '{name}' không tồn tại. Dùng tool_search để tìm tool đúng."
        try:
            return tool.handler(**arguments)
        except Exception as e:
            # Lỗi phải actionable, không phải traceback thô (theo "Writing effective tools")
            return f"Lỗi khi chạy '{name}': {e}. Kiểm tra lại tham số: {arguments}"
