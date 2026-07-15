"""
main.py — CLI ALL-IN-ONE (não + tay cùng tiến trình): wiring toàn bộ framework
để chạy thử/debug nhanh mà không cần dựng server + companion app + web.

Đây là công cụ debug quan trọng nhất của dự án (PLAN.md quyết định #20):
event stream in ra console ở đây CHÍNH LÀ thứ sau này chảy qua WebSocket
lên giao diện web — thấy sai ở đây thì sửa trước khi đụng tới server.

Chạy thử: python main.py
(cần set biến môi trường DEEPSEEK_API_KEY, hoặc đổi base_url/model cho provider khác)
"""

import sys
import os
import json
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


def print_event(event: dict) -> None:
    """Mô phỏng đầu nhận WebSocket: mỗi event 1 dòng JSON — chính là format
    UI sẽ nhận. Debug event stream bằng mắt ở đây."""
    print(f"[event] {json.dumps(event, ensure_ascii=False)}")


def main() -> None:
    llm = LLMClient(
        api_key=os.environ.get("DEEPSEEK_API_KEY", "dummy"),
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )

    # full_registry của dispatcher chỉ chứa tool server-side (ecom). Browser tools
    # KHÔNG nằm ở đây — chúng đến từ local_tools_factory khi subagent needs_device
    # được dispatch (PLAN.md 4.6). Ở CLI all-in-one, factory bind SyncBrowserTool
    # chạy cùng máy, khởi động LAZY (chỉ tốn Chromium khi task thật sự cần browser
    # — giống hệt hành vi của companion app sau này).
    full_registry = build_ecom_registry()
    skills = SkillLoader(ROOT / "skills")
    context_mgr = ContextManager(llm, notes_path=ROOT / "memory/notes/main.md")

    browser_holder: dict = {"tool": None}

    def local_tools_factory() -> ToolRegistry:
        # Import ở đây (không phải đầu file) để CLI vẫn chạy được các task không
        # cần browser trong môi trường chưa cài playwright.
        from tools.browser.browser_tool import SyncBrowserTool
        from tools.browser.registration import build_browser_registry, load_sensitive_data_from_env

        if browser_holder["tool"] is None:
            sync_browser = SyncBrowserTool(
                llm,
                headless=os.environ.get("BROWSER_HEADLESS", "false").lower() == "true",
                storage_state_path=os.environ.get("BROWSER_STORAGE_STATE") or None,
                use_vision=False,  # DeepSeek không có vision
            )
            sync_browser.start()
            browser_holder["tool"] = sync_browser
        return build_browser_registry(browser_holder["tool"], load_sensitive_data_from_env())

    dispatcher = SubagentDispatcher(
        llm,
        full_registry,
        skills,
        notes_dir=ROOT / "memory/notes",
        local_tools_factory=local_tools_factory,
    )
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

    try:
        result = main_agent.run(
            "Kiểm tra tình trạng đơn hàng SA-00123 giúp tôi", on_event=print_event
        )
        print(result)
    finally:
        if browser_holder["tool"] is not None:
            browser_holder["tool"].stop()


if __name__ == "__main__":
    main()
