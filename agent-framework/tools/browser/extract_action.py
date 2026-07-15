"""
Extract Action — dùng LLM để đọc nội dung trang (đã chuyển sang markdown) và
trích xuất thông tin, thay vì bắt agent chính tự đọc toàn bộ HTML/markdown thô
(vốn có thể rất dài) vào context.

Phase 0 (PLAN.md mục 4.6): tách thành 2 NỬA ĐỘC LẬP vì kiến trúc phân tán
("não trên server, tay trên máy khách") — LLM key không được nằm trên máy khách:

  1. page_to_markdown(page, start_from_char) -> dict
     Chạy trên DEVICE (máy khách): lấy HTML -> markdown -> cắt bớt. KHÔNG cần LLM.
  2. extract_from_markdown(payload, query, llm) -> str
     Chạy trên SERVER: gửi markdown + query cho LLM, format kết quả.

CLI all-in-one (main.py) ghép cả 2 nửa trong cùng tiến trình qua
ExtractAction.extract (giữ nguyên chữ ký cũ để không phá code hiện có).
"""

from __future__ import annotations
import json
from markdownify import markdownify as md

MAX_CHAR_LIMIT = 100000


async def page_to_markdown(page, start_from_char: int = 0) -> dict:
    """Nửa 'device': chụp nội dung chữ của trang. Trả dict JSON-serializable:
    {"url", "markdown" (≤ MAX_CHAR_LIMIT chars), "truncated", "next_start"}."""
    html = await page.content()
    markdown = md(html, heading_style="ATX")

    lines = [l for l in markdown.split("\n") if l.strip()]
    markdown = "\n".join(lines)

    total_len = len(markdown)
    if 0 < start_from_char < total_len:
        markdown = markdown[start_from_char:]

    if len(markdown) > MAX_CHAR_LIMIT:
        markdown = markdown[:MAX_CHAR_LIMIT]
        truncated = True
        next_start = start_from_char + MAX_CHAR_LIMIT
    else:
        truncated = False
        next_start = None

    return {
        "url": page.url,
        "markdown": markdown,
        "truncated": truncated,
        "next_start": next_start,
    }


def extract_from_markdown(
    payload: dict, query: str, llm, output_schema: dict | None = None
) -> str:
    """Nửa 'server': LLM đọc markdown (từ page_to_markdown) và trích xuất theo query.
    `llm` là core.llm_client.LLMClient (sync)."""
    system_prompt = """You are an expert at extracting data from webpage markdown.
<instructions>
- Extract ONLY information present in the webpage. Do not guess.
- If information is not available, say so explicitly.
- If content was truncated, extract what is visible.
</instructions>"""

    prompt_parts = [f"<query>\n{query}\n</query>"]
    if output_schema:
        schema_json = json.dumps(output_schema, indent=2)
        prompt_parts.append(f"<output_schema>\n{schema_json}\n</output_schema>")
    prompt_parts.append(f"<webpage_content>\n{payload['markdown']}\n</webpage_content>")
    prompt = "\n\n".join(prompt_parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    response = llm.chat(messages).content

    result = (
        f"<url>\n{payload['url']}\n</url>\n<query>\n{query}\n</query>\n<result>\n{response}\n</result>"
    )
    if payload.get("truncated"):
        result += f"\n\nContent was truncated. Use start_from_char={payload['next_start']} to continue."
    return result


class ExtractAction:
    MAX_CHAR_LIMIT = MAX_CHAR_LIMIT  # backward compat cho code cũ tham chiếu qua class

    @staticmethod
    async def extract(
        page,
        query: str,
        llm,
        extract_links: bool = False,
        extract_images: bool = False,
        start_from_char: int = 0,
        output_schema: dict | None = None,
    ) -> str:
        """Chế độ all-in-one: ghép 2 nửa trong cùng tiến trình. Lệnh gọi LLM chặn
        (block) một chút cũng không sao vì BrowserTool chạy trên 1 thread nền riêng."""
        payload = await page_to_markdown(page, start_from_char)
        return extract_from_markdown(payload, query, llm, output_schema=output_schema)

    @staticmethod
    def chunk_markdown_by_structure(markdown: str, max_chars: int = 100000,
                                     start_from: int = 0) -> list[dict]:
        """Chia markdown theo cấu trúc để tránh cắt ngang giữa bảng/danh sách."""
        chunks = []
        pos = start_from
        while pos < len(markdown):
            end = min(pos + max_chars, len(markdown))
            safe_end = end
            if end < len(markdown):
                for scan in range(end, max(pos + max_chars // 2, pos), -1):
                    if markdown[scan] == '\n':
                        safe_end = scan
                        break

            chunk = markdown[pos:safe_end]
            chunks.append({
                'content': chunk,
                'char_offset_start': pos,
                'char_offset_end': safe_end,
                'has_more': safe_end < len(markdown),
            })
            pos = safe_end

        return chunks
