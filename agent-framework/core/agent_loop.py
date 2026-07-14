"""
Agent Loop — vòng lặp cơ bản (LLM -> tool call -> observation -> lặp lại),
đúng tinh thần "Building Effective Agents": "Agents are typically just LLMs
using tools based on environmental feedback in a loop."

Điểm khác biệt so với vòng lặp for-loop cơ bản bạn đang có:
  - Tool active theo defer_loading, không nạp hết mọi tool ngay từ đầu
  - Có tool_search để agent tự mở khoá tool khi cần
  - Có skill discovery block trong system prompt + read_skill/run_skill_script
  - Tự động compact khi context vượt ngưỡng
"""

from __future__ import annotations
import json
from core.llm_client import LLMClient
from core.context_manager import ContextManager, WRITE_NOTE_SCHEMA, READ_NOTES_SCHEMA
from tools.registry import ToolRegistry
from tools.tool_search import tool_search, TOOL_SEARCH_SCHEMA
from tools.skill_loader import SkillLoader, READ_SKILL_SCHEMA, RUN_SKILL_SCRIPT_SCHEMA

MAX_ITERATIONS = 20


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

    def _dispatch_framework_tool(self, name: str, args: dict) -> str | None:
        """Tool do framework cung cấp (không thuộc registry của domain)."""
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
            return self._dispatcher.dispatch(args["subagent_name"], args["task"])
        return None

    def run(self, user_message: str) -> str:
        messages = [
            {"role": "system", "content": self._full_system_prompt()},
            {"role": "user", "content": user_message},
        ]

        for _ in range(MAX_ITERATIONS):
            if self._ctx.should_compact(messages):
                messages = self._ctx.compact(messages)

            tools = self._framework_tool_schemas() + self._registry.active_schemas()
            response = self._llm.chat(messages, tools=tools)

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
                result = self._dispatch_framework_tool(call["name"], call["arguments"])
                if result is None:
                    result = self._registry.execute(call["name"], call["arguments"])
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

        return "Đã đạt giới hạn số bước lặp (MAX_ITERATIONS) mà chưa xong task."
