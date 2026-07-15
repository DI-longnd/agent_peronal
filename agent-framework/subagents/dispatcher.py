"""
Subagent Dispatcher — implement pattern "Manager/agents-as-tools" (OpenAI Agents SDK)
+ Subagent (Claude Code .claude/agents/*.md): main agent luôn giữ quyền trả lời
cuối cho user, nhưng giao việc "bẩn" (nhiều tool call, nhiều noise trung gian)
cho 1 subagent chạy trong context RIÊNG BIỆT — chỉ kết quả cô đọng quay về.

Subagent được định nghĩa bằng file Markdown (YAML frontmatter + system prompt),
đúng format Claude Code dùng, để dễ đọc/sửa mà không cần đụng code Python.

Phase 0 (PLAN.md mục 4.6 + 4.7): hỗ trợ tool chạy trên MÁY KHÁCH (kiến trúc
"não trên server, tay trên máy khách"):
  - Subagent có `needs_device: true` trong frontmatter nghĩa là tool của nó
    (browser__*) phải thực thi trên thiết bị của khách.
  - local_tools_factory: dispatcher KHÔNG biết tool local đến từ đâu — nó chỉ gọi
    factory để lấy 1 ToolRegistry. Ở CLI all-in-one, factory bind SyncBrowserTool
    chạy cùng máy; ở server, factory bind RPC stub gửi lệnh xuống device của khách.
    Factory raise RuntimeError khi device offline — dispatcher trả message actionable
    NGAY, không tốn LLM call nào.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import yaml

from core.llm_client import LLMClient
from core.context_manager import ContextManager
from core.agent_loop import AgentLoop, _preview
from tools.registry import ToolRegistry
from tools.skill_loader import SkillLoader


@dataclass
class SubagentConfig:
    name: str
    description: str  # dùng để orchestrator route tự động — viết như 1 luật phân loại
    allowed_tools: list[str]  # least-privilege: chỉ tool thuộc domain này
    system_prompt: str
    needs_device: bool = False  # tool của subagent này chạy trên máy khách (qua local_tools_factory)


def load_subagent_config(md_path: Path) -> SubagentConfig:
    text = md_path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    meta = yaml.safe_load(frontmatter)
    return SubagentConfig(
        name=meta["name"],
        description=meta["description"],
        allowed_tools=meta.get("tools", []),
        system_prompt=body.strip(),
        needs_device=bool(meta.get("needs_device", False)),
    )


class SubagentDispatcher:
    def __init__(
        self,
        llm: LLMClient,
        full_registry: ToolRegistry,
        skills: SkillLoader,
        notes_dir: Path,
        local_tools_factory: Callable[[], ToolRegistry] | None = None,
    ):
        self._llm = llm
        self._full_registry = full_registry
        self._skills = skills
        self._notes_dir = notes_dir
        self._local_tools_factory = local_tools_factory
        self._configs: dict[str, SubagentConfig] = {}

    def register(self, config: SubagentConfig) -> None:
        self._configs[config.name] = config

    def routing_prompt_block(self) -> str:
        """Nạp vào system prompt của main agent để nó biết khi nào nên dispatch."""
        lines = [f"- {c.name}: {c.description}" for c in self._configs.values()]
        return "Các subagent chuyên biệt (dùng dispatch_subagent để giao việc):\n" + "\n".join(lines)

    def dispatch(
        self,
        subagent_name: str,
        task: str,
        on_event: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> str:
        """
        Spawn 1 AgentLoop MỚI, context RIÊNG, chỉ thấy tool trong allowed_tools.
        Trả về output cuối cùng — mọi tool call/log trung gian ở lại bên trong
        context của subagent, nhưng vẫn PHÁT EVENT ra ngoài qua on_event (với
        field "agent" = tên subagent) để UI hiển thị tiến trình realtime.
        """
        emit = on_event or (lambda e: None)

        config = self._configs.get(subagent_name)
        if config is None:
            return f"Không tìm thấy subagent '{subagent_name}'."

        emit({"type": "subagent_started", "name": subagent_name, "task": _preview(task)})

        scoped_registry = ToolRegistry()
        for tool in self._full_registry.all_tools():
            if tool.name in config.allowed_tools:
                scoped_registry.register(tool)

        if config.needs_device:
            local_registry = self._build_local_tools(subagent_name)
            if isinstance(local_registry, str):  # message lỗi actionable, trả ngay không chạy LLM
                emit({"type": "subagent_finished", "name": subagent_name, "result_preview": _preview(local_registry)})
                return local_registry
            for tool in local_registry.all_tools():
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
        result = sub_loop.run(
            task, on_event=on_event, should_stop=should_stop, agent_name=subagent_name
        )
        emit({"type": "subagent_finished", "name": subagent_name, "result_preview": _preview(result)})
        return result

    def _build_local_tools(self, subagent_name: str) -> ToolRegistry | str:
        """Lấy registry tool local từ factory. Trả string = message lỗi cho LLM
        (thay vì raise) — đúng triết lý 'lỗi phải actionable' của registry.execute."""
        if self._local_tools_factory is None:
            return (
                f"Subagent '{subagent_name}' cần thực thi tool trên máy khách nhưng hệ thống "
                "chưa cấu hình local_tools_factory. Báo người dùng kiểm tra lại cấu hình."
            )
        try:
            return self._local_tools_factory()
        except RuntimeError as e:
            return (
                f"Máy của khách đang offline hoặc chưa sẵn sàng ({e}). "
                "Yêu cầu khách mở app Personal Agent trên máy tính rồi thử lại."
            )


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
