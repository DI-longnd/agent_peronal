"""
Agent Loop — vòng lặp cơ bản (LLM -> tool call -> observation -> lặp lại),
đúng tinh thần "Building Effective Agents": "Agents are typically just LLMs
using tools based on environmental feedback in a loop."

Điểm khác biệt so với vòng lặp for-loop cơ bản:
  - Tool active theo defer_loading, không nạp hết mọi tool ngay từ đầu
  - Có tool_search để agent tự mở khoá tool khi cần
  - Có skill discovery block trong system prompt + read_skill/run_skill_script
  - Tự động compact khi context vượt ngưỡng

Phase 0 (PLAN.md mục 4.7 + 5): AgentLoop chạy được trong chế độ server mà không
đổi bản chất sync của nó:
  - on_event: phát event (tool_call/tool_result/llm_usage) theo schema PLAN.md 4.1
    — server đẩy các event này qua WebSocket cho UI hiển thị tiến trình realtime.
  - history: các lượt user/assistant cũ (multi-turn chat) do caller lưu và truyền vào.
  - should_stop: kiểm tra ở ĐẦU mỗi iteration để dừng lịch sự (user hủy / quá timeout).
  - agent_name: gắn vào field "agent" của mọi event, để UI phân biệt event của
    main agent với event bên trong subagent.
"""

from __future__ import annotations
import json
from typing import Callable
from core.llm_client import LLMClient
from core.context_manager import ContextManager, WRITE_NOTE_SCHEMA, READ_NOTES_SCHEMA
from tools.registry import ToolRegistry
from tools.tool_search import tool_search, TOOL_SEARCH_SCHEMA
from tools.skill_loader import SkillLoader, READ_SKILL_SCHEMA, RUN_SKILL_SCRIPT_SCHEMA

MAX_ITERATIONS = 35
PREVIEW_MAX_CHARS = 500


def _preview(text: object, limit: int = PREVIEW_MAX_CHARS) -> str:
    """Cắt gọn nội dung trước khi đưa vào event — event đi qua WebSocket tới UI,
    không được phình to theo tool output (chỉ final_answer mới giữ nguyên vẹn)."""
    s = str(text)
    return s if len(s) <= limit else s[:limit] + "…"


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        skills: SkillLoader,
        context_mgr: ContextManager,
        system_prompt: str,
        dispatcher=None,  # subagents.dispatcher.SubagentDispatcher, optional (main agent mới cần)
    ):
        self._llm = llm
        self._registry = registry
        self._skills = skills
        self._ctx = context_mgr
        self._system_prompt = system_prompt
        self._dispatcher = dispatcher

    def _full_system_prompt(self) -> str:
        # Theo "Effective context engineering": tổ chức prompt thành section rõ ràng
        prompt = (
            f"{self._system_prompt}\n\n"
            f"<available_skills>\n{self._skills.discovery_prompt_block()}\n</available_skills>"
        )
        if self._dispatcher is not None:
            prompt += f"\n\n<subagents>\n{self._dispatcher.routing_prompt_block()}\n</subagents>"
        return prompt

    def _framework_tool_schemas(self) -> list[dict]:
        schemas = [TOOL_SEARCH_SCHEMA, READ_SKILL_SCHEMA, RUN_SKILL_SCRIPT_SCHEMA, WRITE_NOTE_SCHEMA, READ_NOTES_SCHEMA]
        if self._dispatcher is not None:
            # Lazy import: tránh circular import (subagents.dispatcher import AgentLoop từ module này)
            from subagents.dispatcher import DISPATCH_SUBAGENT_SCHEMA

            schemas.append(DISPATCH_SUBAGENT_SCHEMA)
        return schemas

    def _dispatch_framework_tool(
        self,
        name: str,
        args: dict,
        on_event: Callable[[dict], None],
        should_stop: Callable[[], bool],
    ) -> str | None:
        """Tool do framework cung cấp (không thuộc registry của domain).
        on_event/should_stop chỉ dispatch_subagent cần — truyền tiếp xuống subagent
        để event bên trong nó cũng nổi lên UI và lệnh hủy cũng dừng được nó."""
        if name == "tool_search":
            return tool_search(self._registry, args["query"])
        if name == "read_skill":
            return self._skills.read_skill(args["name"])
        if name == "run_skill_script":
            return self._skills.run_script(args["name"], args["script_relpath"], args.get("args", []))
        if name == "write_note":
            return self._ctx.write_note(args["content"])
        if name == "read_notes":
            return self._ctx.read_notes()
        if name == "dispatch_subagent" and self._dispatcher is not None:
            return self._dispatcher.dispatch(
                args["subagent_name"], args["task"], on_event=on_event, should_stop=should_stop
            )
        return None

    def run(
        self,
        user_message: str,
        history: list[dict] | None = None,
        on_event: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        agent_name: str = "main",
    ) -> str:
        emit = on_event or (lambda e: None)
        stop = should_stop or (lambda: False)

        # System prompt luôn dựng lại mới mỗi run (danh sách skill/subagent có thể đổi);
        # history là các lượt user/assistant cũ do caller lưu — KHÔNG chứa system message.
        messages: list[dict] = [{"role": "system", "content": self._full_system_prompt()}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_ITERATIONS):
            if stop():
                return "(run đã dừng: bị hủy hoặc quá thời gian)"

            if self._ctx.should_compact(messages):
                messages = self._ctx.compact(messages)

            tools = self._framework_tool_schemas() + self._registry.active_schemas()
            response = self._llm.chat(messages, tools=tools)

            usage = getattr(response.raw, "usage", None)
            if usage is not None:
                emit(
                    {
                        "type": "llm_usage",
                        "agent": agent_name,
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    }
                )

            if not response.tool_calls:
                return response.content or ""

            # Ghi lại đúng format chuẩn OpenAI cho lượt gọi tiếp theo: "arguments"
            # phải là JSON string (không phải dict đã parse), và mỗi tool call
            # phải bọc trong {"type": "function", "function": {...}}. response.tool_calls
            # (dạng dict đã parse arguments) chỉ dùng nội bộ để dispatch/execute bên dưới.
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                            },
                        }
                        for call in response.tool_calls
                    ],
                }
            )

            for call in response.tool_calls:
                emit(
                    {
                        "type": "tool_call",
                        "agent": agent_name,
                        "tool": call["name"],
                        "args_preview": _preview(json.dumps(call["arguments"], ensure_ascii=False)),
                    }
                )
                result = self._dispatch_framework_tool(call["name"], call["arguments"], emit, stop)
                if result is None:
                    result = self._registry.execute(call["name"], call["arguments"])
                emit(
                    {
                        "type": "tool_result",
                        "agent": agent_name,
                        "tool": call["name"],
                        "result_preview": _preview(result),
                    }
                )
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

        return (
            "Đã đạt giới hạn số bước lặp (MAX_ITERATIONS) trước khi hoàn tất — đây KHÔNG "
            "hẳn là thất bại và KHÔNG có nghĩa là chưa đăng nhập (chỉ kết luận 'chưa đăng "
            "nhập' nếu thực sự thấy form đăng nhập). Thường do trang SPA tải chậm hoặc gặp "
            "captcha/xác minh. Hãy tóm tắt dữ liệu ĐÃ thu được (nếu có) và nêu bước còn dở."
        )
