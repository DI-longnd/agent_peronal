"""
Subagent Dispatcher — implement pattern "Manager/agents-as-tools" (OpenAI Agents SDK)
+ Subagent (Claude Code .claude/agents/*.md): main agent luôn giữ quyền trả lời
cuối cho user, nhưng giao việc "bẩn" (nhiều tool call, nhiều noise trung gian)
cho 1 subagent chạy trong context RIÊNG BIỆT — chỉ kết quả cô đọng quay về.

Subagent được định nghĩa bằng file Markdown (YAML frontmatter + system prompt),
đúng format Claude Code dùng, để dễ đọc/sửa mà không cần đụng code Python.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

from core.llm_client import LLMClient
from core.context_manager import ContextManager
from core.agent_loop import AgentLoop
from tools.registry import ToolRegistry
from tools.skill_loader import SkillLoader


@dataclass
class SubagentConfig:
    name: str
    description: str  # dùng để orchestrator route tự động — viết như 1 luật phân loại
    allowed_tools: list[str]  # least-privilege: chỉ tool thuộc domain này
    system_prompt: str


def load_subagent_config(md_path: Path) -> SubagentConfig:
    text = md_path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    meta = yaml.safe_load(frontmatter)
    return SubagentConfig(
        name=meta["name"],
        description=meta["description"],
        allowed_tools=meta.get("tools", []),
        system_prompt=body.strip(),
    )


class SubagentDispatcher:
    def __init__(self, llm: LLMClient, full_registry: ToolRegistry, skills: SkillLoader, notes_dir: Path):
        self._llm = llm
        self._full_registry = full_registry
        self._skills = skills
        self._notes_dir = notes_dir
        self._configs: dict[str, SubagentConfig] = {}

    def register(self, config: SubagentConfig) -> None:
        self._configs[config.name] = config

    def routing_prompt_block(self) -> str:
        """Nạp vào system prompt của main agent để nó biết khi nào nên dispatch."""
        lines = [f"- {c.name}: {c.description}" for c in self._configs.values()]
        return "Các subagent chuyên biệt (dùng dispatch_subagent để giao việc):\n" + "\n".join(lines)

    def dispatch(self, subagent_name: str, task: str) -> str:
        """
        Spawn 1 AgentLoop MỚI, context RIÊNG, chỉ thấy tool trong allowed_tools.
        Trả về output cuối cùng — mọi tool call/log trung gian ở lại bên trong,
        không lọt vào context của main agent (đúng nguyên tắc trong
        "Effective context engineering": subagent trả về bản tóm tắt 1-2K token,
        dù bên trong nó có thể tốn hàng chục nghìn token để hoàn thành việc).
        """
        config = self._configs.get(subagent_name)
        if config is None:
            return f"Không tìm thấy subagent '{subagent_name}'."

        scoped_registry = ToolRegistry()
        for tool in self._full_registry.all_tools():
            if tool.name in config.allowed_tools:
                scoped_registry.register(tool)

        sub_context_mgr = ContextManager(
            self._llm, notes_path=self._notes_dir / f"{subagent_name}.md"
        )
        sub_loop = AgentLoop(
            llm=self._llm,
            registry=scoped_registry,
            skills=self._skills,
            context_mgr=sub_context_mgr,
            system_prompt=config.system_prompt,
        )
        return sub_loop.run(task)


DISPATCH_SUBAGENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "dispatch_subagent",
        "description": (
            "Giao 1 task cho subagent chuyên biệt (xem <subagents> trong system prompt để biết "
            "subagent nào phù hợp). Dùng khi task cần nhiều tool call thuộc 1 domain cụ thể "
            "và bạn chỉ cần kết quả cuối cùng, không cần thấy chi tiết xử lý."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subagent_name": {"type": "string"},
                "task": {"type": "string", "description": "Mô tả task cụ thể, đủ ngữ cảnh để subagent làm độc lập"},
            },
            "required": ["subagent_name", "task"],
        },
    },
}
