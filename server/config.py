"""
Config server — đọc env theo bảng PLAN.md 3.4, fail sớm với message rõ ràng
nếu thiếu biến bắt buộc (thà chết lúc khởi động còn hơn lỗi khó hiểu giữa run).
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent


@dataclass
class Config:
    deepseek_api_key: str
    llm_base_url: str
    llm_model: str
    data_dir: Path
    max_concurrent_runs: int
    run_timeout_seconds: int
    tool_call_timeout_seconds: int
    port: int


def load_config() -> Config:
    # .env chuẩn nằm ở root; load thêm agent-framework/.env (setup cũ) làm fallback
    # — dotenv không override biến đã có nên thứ tự này an toàn.
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "agent-framework" / ".env")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit(
            "Thiếu DEEPSEEK_API_KEY — tạo file .env ở root repo (xem PLAN.md 3.4) rồi chạy lại."
        )

    data_dir = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        deepseek_api_key=api_key,
        llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        llm_model=os.environ.get("LLM_MODEL", "deepseek-chat"),
        data_dir=data_dir,
        max_concurrent_runs=int(os.environ.get("MAX_CONCURRENT_RUNS", "3")),
        run_timeout_seconds=int(os.environ.get("RUN_TIMEOUT_SECONDS", "300")),
        tool_call_timeout_seconds=int(os.environ.get("TOOL_CALL_TIMEOUT_SECONDS", "120")),
        port=int(os.environ.get("PORT", "8000")),
    )
