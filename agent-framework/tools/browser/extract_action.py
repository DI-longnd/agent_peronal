"""
Extract Action — dùng LLM để đọc nội dung trang (đã chuyển sang markdown) và
trích xuất thông tin, thay vì bắt agent chính tự đọc toàn bộ HTML/markdown thô
(vốn có thể rất dài) vào context.

Luồng:
1. Lấy HTML -> chuyển thành markdown (markdownify)
2. Cắt bớt nếu quá dài (>100000 chars)
3. Gửi markdown + query cho LLM
4. LLM trả về kết quả

Khác với tài liệu tham chiếu gốc: gốc gọi `await llm.ainvoke(messages)` (kiểu
LangChain/async). LLMClient của framework này là sync (method `.chat()`), nên
gọi thẳng đồng bộ ngay trong hàm async — không sao vì phần async ở đây chỉ để
gọi Playwright (`page.content()`), lệnh gọi LLM chặn (block) một chút cũng
không ảnh hưởng gì do BrowserTool chạy trên 1 thread nền riêng.
"""

from __future__ import annotations
import json
from markdownify import markdownify as md


class ExtractAction:
    MAX_CHAR_LIMIT = 100000

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
        html = await page.content()
        markdown = md(html, heading_style='ATX')

        lines = [l for l in markdown.split('\n') if l.strip()]
        markdown = '\n'.join(lines)

        total_len = len(markdown)
        if start_from_char > 0 and start_from_char < total_len:
            markdown = markdown[start_from_char:]

        if len(markdown) > ExtractAction.MAX_CHAR_LIMIT:
            markdown = markdown[:ExtractAction.MAX_CHAR_LIMIT]
            truncated = True
            next_start = start_from_char + ExtractAction.MAX_CHAR_LIMIT
        else:
            truncated = False
            next_start = None

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

        prompt_parts.append(f"<webpage_content>\n{markdown}\n</webpage_content>")
        prompt = '\n\n'.join(prompt_parts)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = llm.chat(messages).content

        url = page.url
        result = f"<url>\n{url}\n</url>\n<query>\n{query}\n</query>\n<result>\n{response}\n</result>"

        if truncated:
            result += f"\n\nContent was truncated. Use start_from_char={next_start} to continue."

        return result

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
