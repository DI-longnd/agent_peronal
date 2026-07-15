"""
AgentRunner — chạy AgentLoop (sync) trong thread riêng cho mỗi run, bridge event
sang async qua queue.Queue + sentinel (PLAN.md 4.5, quyết định #3 #4).

Per-run isolation (quyết định #17): LLMClient, ToolRegistry, ContextManager,
SubagentDispatcher đều build MỚI mỗi run — chỉ SkillLoader/DeviceHub/SessionStore
là shared. Lý do: ToolRegistry có state _activated mutable, không được leak
giữa các user/run.

Quy tắc "1 user 1 run": begin() đăng ký user vào active dict ĐỒNG BỘ (trước mọi
await) — app.py gọi begin() ngay trong receive loop nên không có race giữa 2
message chat liên tiếp.
"""

from __future__ import annotations
import asyncio
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from core.llm_client import LLMClient
from core.context_manager import ContextManager
from core.agent_loop import AgentLoop
from tools.registry import ToolRegistry
from tools.skill_loader import SkillLoader
from subagents.dispatcher import SubagentDispatcher, load_subagent_config, SubagentConfig
from main import build_ecom_registry  # CLI và server dùng chung bộ tool demo ecom

from server.config import Config
from server.sessions import SessionStore
from server.device_hub import DeviceHub
from server.remote_tools import build_remote_browser_registry

AGENT_FRAMEWORK_ROOT = Path(__file__).parent.parent / "agent-framework"

MAIN_SYSTEM_PROMPT = (
    "Bạn là trợ lý cá nhân. Điều phối task xuống đúng subagent hoặc skill phù hợp."
)


@dataclass
class RunHandle:
    run_id: str
    user_id: str
    session_id: str
    queue: "queue.Queue[dict]" = field(default_factory=queue.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    deadline: float = 0.0


class AgentRunner:
    def __init__(self, config: Config, store: SessionStore, hub: DeviceHub, skills: SkillLoader):
        self._config = config
        self._store = store
        self._hub = hub
        self._skills = skills
        self._semaphore = threading.Semaphore(config.max_concurrent_runs)
        self._active: dict[str, RunHandle] = {}
        self._lock = threading.Lock()
        # Config subagent load 1 lần (immutable dataclass, share được giữa các run);
        # dispatcher thì per-run vì nó giữ local_tools_factory bind theo user.
        self._subagent_configs: list[SubagentConfig] = [
            load_subagent_config(AGENT_FRAMEWORK_ROOT / "subagents" / "ecom-agent.md"),
            load_subagent_config(AGENT_FRAMEWORK_ROOT / "subagents" / "browser-agent.md"),
        ]

    # --- vòng đời run ---

    def begin(self, user_id: str, session_id: str) -> RunHandle | None:
        """Đăng ký run mới. Trả None nếu user đang có run chạy (busy)."""
        with self._lock:
            if user_id in self._active:
                return None
            handle = RunHandle(
                run_id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                deadline=time.monotonic() + self._config.run_timeout_seconds,
            )
            self._active[user_id] = handle
            return handle

    def cancel(self, user_id: str, run_id: str) -> bool:
        with self._lock:
            handle = self._active.get(user_id)
        if handle is not None and handle.run_id == run_id:
            handle.cancel_event.set()
            return True
        return False

    def is_busy(self, user_id: str) -> bool:
        with self._lock:
            return user_id in self._active

    async def drive(
        self,
        handle: RunHandle,
        message: str,
        send_event: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Async side: phát run_started, spawn agent thread, forward event từ queue
        ra WebSocket, persist kết quả. Web client rớt giữa chừng -> send_event ném
        exception -> bỏ qua và CHẠY TIẾP đến khi lưu xong DB (PLAN.md 4.2)."""

        async def safe_send(ev: dict) -> None:
            try:
                await send_event(ev)
            except Exception:
                pass  # web đóng — run vẫn phải chạy tới cùng và lưu DB

        await safe_send({"type": "run_started", "run_id": handle.run_id, "session_id": handle.session_id})

        # History = messages cũ TRƯỚC message user vừa gửi (đã add vào DB ở app.py)
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in self._store.get_messages(handle.session_id)[:-1]
        ]

        thread = threading.Thread(
            target=self._agent_thread, args=(handle, message, history), daemon=True
        )
        thread.start()

        final_text: str | None = None
        try:
            while True:
                ev = await asyncio.to_thread(handle.queue.get)
                if ev["type"] == "final_answer":
                    final_text = ev["content"]
                await safe_send(ev)
                if ev["type"] == "run_finished":
                    self._store.record_run(
                        handle.run_id,
                        handle.session_id,
                        ev["status"],
                        ev["total_prompt_tokens"],
                        ev["total_completion_tokens"],
                    )
                    break
        finally:
            if final_text is not None:
                self._store.add_message(handle.session_id, "assistant", final_text)
            with self._lock:
                self._active.pop(handle.user_id, None)

    # --- agent thread (sync) ---

    def _agent_thread(self, handle: RunHandle, message: str, history: list[dict]) -> None:
        q = handle.queue
        totals = {"prompt": 0, "completion": 0}

        def on_event(ev: dict) -> None:
            if ev.get("type") == "llm_usage":
                totals["prompt"] += ev.get("prompt_tokens", 0)
                totals["completion"] += ev.get("completion_tokens", 0)
            q.put(ev)

        def should_stop() -> bool:
            return handle.cancel_event.is_set() or time.monotonic() > handle.deadline

        status = "ok"
        try:
            with self._semaphore:
                cfg = self._config
                llm = LLMClient(
                    api_key=cfg.deepseek_api_key, base_url=cfg.llm_base_url, model=cfg.llm_model
                )
                notes_dir = cfg.data_dir / "memory" / "notes" / handle.session_id
                context_mgr = ContextManager(llm, notes_path=notes_dir / "main.md")

                dispatcher = SubagentDispatcher(
                    llm,
                    build_ecom_registry(),
                    self._skills,
                    notes_dir=notes_dir,
                    local_tools_factory=lambda: build_remote_browser_registry(
                        self._hub, handle.user_id, llm, cfg.tool_call_timeout_seconds
                    ),
                )
                for config in self._subagent_configs:
                    dispatcher.register(config)

                agent = AgentLoop(
                    llm=llm,
                    registry=ToolRegistry(),  # main agent không cầm tool trực tiếp
                    skills=self._skills,
                    context_mgr=context_mgr,
                    system_prompt=MAIN_SYSTEM_PROMPT,
                    dispatcher=dispatcher,
                )
                result = agent.run(
                    message, history=history, on_event=on_event, should_stop=should_stop
                )

                if handle.cancel_event.is_set():
                    status = "cancelled"
                elif time.monotonic() > handle.deadline:
                    status = "timeout"
                q.put({"type": "final_answer", "content": result})
        except Exception as e:
            status = "error"
            q.put({"type": "error", "message": f"{type(e).__name__}: {e}"})
            q.put(
                {
                    "type": "final_answer",
                    "content": f"Xin lỗi, hệ thống gặp lỗi khi xử lý yêu cầu này: {e}",
                }
            )
        finally:
            q.put(
                {
                    "type": "run_finished",
                    "run_id": handle.run_id,
                    "status": status,
                    "total_prompt_tokens": totals["prompt"],
                    "total_completion_tokens": totals["completion"],
                }
            )
