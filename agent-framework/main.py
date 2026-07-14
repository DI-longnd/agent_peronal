"""
main.py — wiring toàn bộ framework: LLM client, tool registry, skill loader,
context manager, subagent dispatcher, rồi chạy 1 ví dụ.

Chạy thử: python main.py
(cần set biến môi trường DEEPSEEK_API_KEY, hoặc đổi base_url/model cho provider khác)
"""

import sys
import os
from pathlib import Path

from dotenv import load_dotenv

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from core.llm_client import LLMClient
from core.context_manager import ContextManager
from core.agent_loop import AgentLoop
from tools.registry import ToolRegistry, Tool
from tools.skill_loader import SkillLoader
from subagents.dispatcher import SubagentDispatcher, load_subagent_config
from tools.browser.browser_tool import SyncBrowserTool
from tools.browser.registration import build_browser_registry, load_sensitive_data_from_env

ROOT = Path(__file__).parent


# --- Ví dụ tool thuộc domain ecom (namespaced: ecom__...) ---
def _ecom_check_order_status(order_id: str) -> str:
    return f"Đơn {order_id}: pending (mock — thay bằng API thật của sàn)"


def _ecom_process_refund(order_id: str, amount_vnd: int) -> str:
    return f"Đã hoàn {amount_vnd}đ cho đơn {order_id} (mock)"


def _ecom_update_inventory(sku: str, quantity_delta: int) -> str:
    return f"Đã cập nhật tồn kho SKU {sku}: {quantity_delta:+d} (mock)"


def build_ecom_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="ecom__check_order_status",
            description="Kiểm tra trạng thái 1 đơn hàng theo mã đơn.",
            parameters={
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
            handler=_ecom_check_order_status,
        )
    )
    registry.register(
        Tool(
            name="ecom__process_refund",
            description="Xử lý hoàn tiền cho 1 đơn hàng.",
            parameters={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount_vnd": {"type": "integer", "description": "Số tiền hoàn, đơn vị đồng"},
                },
                "required": ["order_id", "amount_vnd"],
            },
            handler=_ecom_process_refund,
            defer_loading=True,  # ít dùng hơn check_order_status -> defer
        )
    )
    registry.register(
        Tool(
            name="ecom__update_inventory",
            description="Cập nhật số lượng tồn kho theo SKU.",
            parameters={
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                    "quantity_delta": {"type": "integer"},
                },
                "required": ["sku", "quantity_delta"],
            },
            handler=_ecom_update_inventory,
            defer_loading=True,
        )
    )
    return registry


def build_full_registry(sync_browser: SyncBrowserTool, sensitive_data: dict) -> ToolRegistry:
    """Gộp tool của mọi domain vào 1 registry — SubagentDispatcher cần thấy
    TOÀN BỘ tool đã đăng ký để lọc theo allowed_tools của từng subagent."""
    full = ToolRegistry()
    for tool in build_ecom_registry().all_tools():
        full.register(tool)
    for tool in build_browser_registry(sync_browser, sensitive_data).all_tools():
        full.register(tool)
    return full


def main() -> None:
    llm = LLMClient(
        api_key=os.environ.get("DEEPSEEK_API_KEY", "dummy"),
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )

    sync_browser = SyncBrowserTool(
        llm,
        headless=os.environ.get("BROWSER_HEADLESS", "false").lower() == "true",
        storage_state_path=os.environ.get("BROWSER_STORAGE_STATE") or None,
        use_vision=False,  # DeepSeek không có vision
    )
    sync_browser.start()

    try:
        sensitive_data = load_sensitive_data_from_env()
        registry = build_full_registry(sync_browser, sensitive_data)
        skills = SkillLoader(ROOT / "skills")
        context_mgr = ContextManager(llm, notes_path=ROOT / "memory/notes/main.md")

        dispatcher = SubagentDispatcher(llm, registry, skills, notes_dir=ROOT / "memory/notes")
        dispatcher.register(load_subagent_config(ROOT / "subagents/ecom-agent.md"))
        dispatcher.register(load_subagent_config(ROOT / "subagents/browser-agent.md"))

        main_agent = AgentLoop(
            llm=llm,
            registry=ToolRegistry(),  # main agent không cầm tool trực tiếp, chỉ điều phối
            skills=skills,
            context_mgr=context_mgr,
            system_prompt="Bạn là trợ lý cá nhân. Điều phối task xuống đúng subagent hoặc skill phù hợp.",
            dispatcher=dispatcher,
        )

        result = main_agent.run("Kiểm tra tình trạng đơn hàng SA-00123 giúp tôi")
        print(result)
    finally:
        sync_browser.stop()


if __name__ == "__main__":
    main()
