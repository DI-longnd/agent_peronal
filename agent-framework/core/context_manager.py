"""
Context Manager — implement 2 kỹ thuật từ "Effective context engineering for
AI agents" (Anthropic) để xử lý long-horizon task (task chạy nhiều bước, dễ
vượt quá context window):

1. Compaction: khi hội thoại gần chạm ngưỡng token, tóm tắt lại toàn bộ
   history thành 1 message, giữ quyết định kiến trúc/việc chưa xong, bỏ
   tool output thô đã dùng xong. Agent tiếp tục với bản tóm tắt.
2. Structured note-taking: agent tự ghi tiến độ ra NOTES.md (ngoài context
   window) — dùng để agent tự đọc lại sau khi bị compact hoặc restart.

Lưu ý: đây là 2 kỹ thuật riêng biệt, dùng tình huống khác nhau — compaction
hợp với hội thoại dài cần liền mạch, note-taking hợp với task có milestone rõ.
"""

from __future__ import annotations
from pathlib import Path
from core.llm_client import LLMClient

# Ước lượng thô: ~4 ký tự/token. Chỉ dùng khi CHƯA có số thật từ API — sau lượt gọi
# đầu tiên thì luôn ưu tiên prompt_tokens do nhà cung cấp trả về.
CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_tokens(messages: list[dict]) -> int:
    """Đếm cả tool_calls, không chỉ content.

    Bản cũ chỉ cộng `m["content"]`. Message của assistant khi gọi tool có
    content=None và toàn bộ nội dung nằm trong tool_calls — bị bỏ sót hoàn toàn.
    Đo lượt chạy 01-08-2026: ngưỡng đặt 6.000 nhưng chỉ kích hoạt khi prompt thật
    đã 13.800 token, hụt 2.3 lần. Phần thiếu chủ yếu là payload tool_calls (có lệnh
    giao việc dài 4.500 token) và schema của 21 tool gửi kèm mỗi lượt."""
    total = 0
    for m in messages:
        total += len(str(m.get("content") or ""))
        for call in m.get("tool_calls") or []:
            fn = call.get("function", {}) if isinstance(call, dict) else {}
            total += len(str(fn.get("name", ""))) + len(str(fn.get("arguments", "")))
    return total // CHARS_PER_TOKEN_ESTIMATE


COMPACTION_PROMPT = """Tóm tắt hội thoại agent bên dưới thành 1 đoạn văn ngắn gọn.
Ưu tiên GIỮ LẠI:
- Quyết định kiến trúc/lựa chọn đã chốt và LÝ DO
- Việc đang làm dở, việc còn phải làm tiếp
- Lỗi đã gặp và cách đã xử lý (để không lặp lại)
Ưu tiên LOẠI BỎ:
- Nội dung thô của tool call/tool result đã xử lý xong
- Các bước trung gian không ảnh hưởng tới quyết định cuối

Hội thoại cần tóm tắt:
{transcript}
"""


class ContextManager:
    # Ngưỡng tính bằng TOKEN THẬT. Giá trị cũ 6.000 là token ƯỚC LƯỢNG và trên thực
    # tế kích hoạt ở ~13.800 token thật; 12.000 giữ nguyên tinh thần đó nhưng nói
    # đúng điều nó làm, và chỉnh được. Đừng hạ quá thấp: mỗi lần compact tốn thêm
    # một lượt gọi LLM có kèm cả bản ghi hội thoại, nén quá dày lại đắt hơn.
    def __init__(self, llm: LLMClient, notes_path: Path, compaction_threshold_tokens: int = 12000):
        self._llm = llm
        self._notes_path = notes_path
        self._threshold = compaction_threshold_tokens

    def should_compact(self, messages: list[dict], actual_prompt_tokens: int | None = None) -> bool:
        """Ưu tiên số THẬT do API trả về ở lượt trước — nó đã tính cả schema tool và
        payload tool_calls, những thứ đếm tay không bao giờ khớp. Ước lượng chỉ dùng
        cho lượt đầu tiên, khi chưa gọi API lần nào."""
        if actual_prompt_tokens:
            return actual_prompt_tokens > self._threshold
        return estimate_tokens(messages) > self._threshold

    def compact(self, messages: list[dict], keep_last_n: int = 4) -> list[dict]:
        """Tóm tắt phần cũ, giữ nguyên system prompt + N message gần nhất."""
        system_msg = [m for m in messages if m["role"] == "system"]
        rest = [m for m in messages if m["role"] != "system"]

        to_summarize, recent = rest[:-keep_last_n], rest[-keep_last_n:]
        if not to_summarize:
            return messages

        transcript = "\n".join(f"[{m['role']}] {m.get('content', '')}" for m in to_summarize)
        summary = self._llm.chat(
            [{"role": "user", "content": COMPACTION_PROMPT.format(transcript=transcript)}]
        ).content

        summary_msg = {"role": "assistant", "content": f"[Tóm tắt phần trước]\n{summary}"}
        return system_msg + [summary_msg] + recent

    # --- Structured note-taking ---

    def write_note(self, content: str) -> str:
        self._notes_path.parent.mkdir(parents=True, exist_ok=True)
        with self._notes_path.open("a", encoding="utf-8") as f:
            f.write(content.rstrip() + "\n")
        return "Đã ghi note."

    def read_notes(self) -> str:
        if not self._notes_path.exists():
            return "(chưa có note nào)"
        return self._notes_path.read_text(encoding="utf-8")


WRITE_NOTE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_note",
        "description": (
            "Ghi lại tiến độ/quyết định quan trọng ra bộ nhớ ngoài context (NOTES.md). "
            "Dùng khi hoàn thành 1 milestone của task dài, để không mất thông tin nếu context bị nén."
        ),
        "parameters": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
}

READ_NOTES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_notes",
        "description": "Đọc lại toàn bộ note đã ghi trước đó — dùng khi bắt đầu 1 task dài hoặc sau khi context bị nén.",
        "parameters": {"type": "object", "properties": {}},
    },
}
