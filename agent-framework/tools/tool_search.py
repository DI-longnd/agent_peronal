"""
Tool Search — implement ý tưởng "Tool Search Tool" của Anthropic
(anthropic.com/engineering/advanced-tool-use) nhưng không phụ thuộc vào
Anthropic API. Dùng BM25-lite (term overlap có trọng số) thay vì embedding
model — vì mục tiêu là tránh nạp hết N tool description vào context, không
nhất thiết cần độ chính xác semantic cao của embedding. Nếu sau này cần
chính xác hơn, có thể thay _score() bằng embedding cosine-similarity mà
không đổi phần còn lại của agent loop.
"""

from __future__ import annotations
import re
from collections import Counter
from tools.registry import ToolRegistry


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    doc_counts = Counter(doc_tokens)
    return sum(doc_counts[t] for t in query_tokens)


TOOL_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tool_search",
        "description": (
            "Tìm tool phù hợp theo domain/việc cần làm khi tool bạn cần chưa "
            "xuất hiện trong danh sách tool hiện có. Vd: tool_search('gửi email') "
            "sẽ trả về các tool thuộc domain email."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mô tả ngắn việc cần làm"}
            },
            "required": ["query"],
        },
    },
}


def tool_search(registry: ToolRegistry, query: str, top_k: int = 5) -> str:
    query_tokens = _tokenize(query)
    scored = []
    for tool in registry.all_tools():
        doc_tokens = _tokenize(tool.name + " " + tool.description)
        s = _score(query_tokens, doc_tokens)
        if s > 0:
            scored.append((s, tool))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    if not top:
        return "Không tìm thấy tool phù hợp. Thử mô tả cụ thể hơn hoặc kiểm tra skill liên quan."

    for _, tool in top:
        registry.activate(tool.name)  # mở khoá vào context cho lượt gọi tiếp theo

    names = "\n".join(f"- {t.name}: {t.description}" for _, t in top)
    return f"Đã tìm thấy và kích hoạt {len(top)} tool:\n{names}"
