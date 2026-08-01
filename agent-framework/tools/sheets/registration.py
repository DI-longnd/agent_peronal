"""Khai báo tool sheet__* — chạy trên MÁY KHÁCH giống browser__*.

Vì sao chạy ở device chứ không phải server: file CSV nằm trong thư mục Downloads của
khách, server không đọc được.

Vì sao URL và token KHÔNG nằm trong tham số của tool: chúng là bí mật. LLM chỉ đưa
đường dẫn file; device tự lấy `sheet_webapp_url` + `sheet_token` từ config.json trên
máy nó. Giống hệt cách browser__type_sensitive nhận mật khẩu — giá trị thật không
bao giờ đi qua LLM, không nằm trong lịch sử hội thoại, không lên log của server.
"""

from __future__ import annotations

from tools.registry import Tool, ToolRegistry
from tools.sheets.client import push_csv

SHEET_TOOL_SPECS = [
    {
        "name": "sheet__push_csv",
        "description": (
            "Đẩy một file CSV đã tải về máy lên Google Sheet của khách, GHI ĐÈ toàn bộ "
            "dữ liệu cũ. Dùng ngay sau khi xuất đơn hàng, để khách mở link sheet quen "
            "thuộc là thấy số liệu mới nhất. "
            "Chỉ cần đường dẫn file — địa chỉ sheet và khoá bí mật đã cấu hình sẵn trên "
            "máy khách, KHÔNG hỏi người dùng và KHÔNG tự bịa. "
            "Chưa cấu hình thì tool sẽ báo rõ, hãy chuyển nguyên thông báo đó cho người dùng."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "csv_path": {
                    "type": "string",
                    "description": ("Đường dẫn đầy đủ tới file CSV, lấy nguyên văn từ "
                                    "browser__download_file hoặc browser__list_downloads"),
                },
            },
            "required": ["csv_path"],
        },
        "method": "push_csv",
        "defer_loading": False,
    },
]


def build_sheet_registry(webapp_url: str, token: str) -> ToolRegistry:
    """Registry cho CLI all-in-one (main.py) — bind sẵn URL/token vào handler."""
    registry = ToolRegistry()
    for spec in SHEET_TOOL_SPECS:
        registry.register(
            Tool(
                name=spec["name"],
                description=spec["description"],
                parameters=spec["parameters"],
                handler=lambda csv_path, _u=webapp_url, _t=token: push_csv(csv_path, _u, _t),
                defer_loading=spec["defer_loading"],
            )
        )
    return registry
