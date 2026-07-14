"""
LLM Client — thin wrapper quanh OpenAI-compatible chat completion API.

Vì sao provider-agnostic: theo khuyến nghị Anthropic ("Building Effective Agents"),
nên gọi thẳng LLM API thay vì qua framework nặng. DeepSeek, OpenAI, và nhiều
local model server (vLLM, Ollama) đều tương thích format OpenAI, nên 1 wrapper
mỏng là đủ mà không khoá cứng vào 1 vendor.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from openai import OpenAI


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict[str, Any]]  # [{"id", "name", "arguments": dict}]
    raw: Any


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        """
        base_url ví dụ:
          - DeepSeek:  https://api.deepseek.com
          - OpenAI:    https://api.openai.com/v1
          - local:     http://localhost:11434/v1 (Ollama, ...)
        """
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        completion = self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0].message

        tool_calls = []
        for tc in getattr(choice, "tool_calls", None) or []:
            import json

            tool_calls.append(
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments or "{}"),
                }
            )

        return LLMResponse(content=choice.content, tool_calls=tool_calls, raw=completion)
