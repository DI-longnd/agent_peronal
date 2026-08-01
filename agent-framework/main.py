"""
main.py — CLI ALL-IN-ONE (não + tay cùng tiến trình): wiring toàn bộ framework
để chạy thử/debug nhanh mà không cần dựng server + companion app + web.

Đây là công cụ debug quan trọng nhất của dự án (PLAN.md quyết định #20):
event stream in ra console ở đây CHÍNH LÀ thứ sau này chảy qua WebSocket
lên giao diện web — thấy sai ở đây thì sửa trước khi đụng tới server.

Chạy thử:
    python main.py                       # chạy câu lệnh mẫu
    python main.py "câu lệnh của bạn"    # chạy đúng yêu cầu muốn thử

Cần DEEPSEEK_API_KEY. Đổi model bằng LLM_MODEL, đổi provider bằng LLM_BASE_URL.

Browser dùng CHUNG profile với companion app (%APPDATA%/PersonalAgent/browser-profile)
nên đăng nhập một lần là cả hai đường đều chạy được — xem scripts/setup_browser_login.py.
Hai bên không chạy đồng thời được, profile_lock sẽ chặn kèm thông báo rõ.
"""

from subagents.dispatcher import SubagentDispatcher, load_subagent_config
from tools.skill_loader import SkillLoader
from tools.registry import ToolRegistry, Tool
from core.agent_loop import AgentLoop
from core.context_manager import ContextManager
from core.llm_client import LLMClient
import sys
import os
import json
from pathlib import Path

from dotenv import load_dotenv

# line_buffering: khi hứng output ra file (`main.py ... > run.log`) Python đệm theo
# khối, nên nhật ký event đứng im tới lúc tiến trình thoát — đúng lúc cần theo dõi
# một lượt chạy dài thì lại không thấy gì. Ép xả từng dòng.
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

load_dotenv()


ROOT = Path(__file__).parent

DEFAULT_TASK = "Tra thông tin nhà sáng tạo TikTok Affiliate có handle thanhdongian.dtt"


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
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        # deepseek-chat ĐÃ BỊ KHAI TỬ — gọi vào là HTTP 400 "supported API model
        # names are deepseek-v4-pro or deepseek-v4-flash". Server đã đổi từ
        # commit 02ba946; CLI này bị bỏ quên nên đứng hỏng cho tới 31-07-2026.
        model=os.environ.get("LLM_MODEL", "deepseek-v4-pro"),
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
        from tools.browser.manual_login import default_profile_dir, default_state_path
        from tools.browser.registration import build_browser_registry, load_sensitive_data_from_env

        if browser_holder["tool"] is None:
            sync_browser = SyncBrowserTool(
                llm,
                headless=os.environ.get(
                    "BROWSER_HEADLESS", "false").lower() == "true",
                # Cùng profile với companion app: đăng nhập 1 lần dùng cho cả hai.
                user_data_dir=os.environ.get(
                    "BROWSER_USER_DATA_DIR") or str(default_profile_dir()),
                # Cùng file sao lưu với app — xem default_state_path().
                storage_state_path=os.environ.get(
                    "BROWSER_STORAGE_STATE") or str(default_state_path()),
                downloads_dir=os.environ.get("BROWSER_DOWNLOADS_DIR")
                or str(Path.home() / "Downloads" / "PersonalAgent"),
                viewport={"width": 1280, "height": 950},
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
    dispatcher.register(load_subagent_config(
        ROOT / "subagents/browser-agent.md"))

    main_agent = AgentLoop(
        llm=llm,
        registry=ToolRegistry(),  # main agent không cầm tool trực tiếp, chỉ điều phối
        skills=skills,
        context_mgr=context_mgr,
        system_prompt="Bạn là trợ lý cá nhân. Điều phối task xuống đúng subagent hoặc skill phù hợp.",
        dispatcher=dispatcher,
    )

    # Nhận yêu cầu từ dòng lệnh — thử skill mới chỉ cần đổi câu lệnh, không phải
    # sửa file rồi chạy lại.
    task = " ".join(sys.argv[1:]).strip() or DEFAULT_TASK
    print(f"[task] {task}\n")

    try:
        result = main_agent.run(task, on_event=print_event)
        print(result)
    finally:
        if browser_holder["tool"] is not None:
            browser_holder["tool"].stop()


if __name__ == "__main__":
    main()
