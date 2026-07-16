"""
Config companion app — lưu tại %APPDATA%/PersonalAgent/config.json (PLAN.md 3.4).

Chứa: server_url, device_token (nhận sau pairing), tùy chọn browser, và secrets
(thay cho BROWSER_SECRET_* env — CHỈ nằm trên máy khách, không bao giờ lên server).

PERSONAL_AGENT_CONFIG_DIR: env override thư mục config — dùng cho test/chạy
nhiều instance, người dùng thường không cần đụng tới.
"""

from __future__ import annotations
import json
import os
from pathlib import Path


def config_dir() -> Path:
    override = os.environ.get("PERSONAL_AGENT_CONFIG_DIR")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PersonalAgent"
    return Path.home() / ".personal-agent"  # fallback non-Windows


def config_path() -> Path:
    return config_dir() / "config.json"


# Server mặc định cho bản build phát hành — tester chạy exe là kết nối luôn,
# không phải nhập gì. Đổi domain: sửa dòng này rồi build lại (PLAN.md 4.5/9.4).
DEFAULT_SERVER_URL = "wss://ecomerceagnet.duckdns.org"


def _defaults() -> dict:
    return {
        "server_url": DEFAULT_SERVER_URL,  # để "" nếu muốn app hỏi lần đầu chạy
        "device_token": "",  # nhận sau pairing, app tự ghi
        "device_name": "",  # mặc định = tên máy (platform.node())
        "headless": False,  # mặc định HIỆN cửa sổ browser (khách thấy agent làm gì)
        "browser_idle_seconds": 300,  # browser tự đóng sau N giây không có lệnh
        "storage_state_path": str(config_dir() / "state.json"),  # session đăng nhập web
        "secrets": {},  # {"site_password": "..."} cho browser__type_sensitive
    }


def load_config() -> dict:
    cfg = _defaults()
    path = config_path()
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            print(f"Cảnh báo: {path} hỏng — dùng config mặc định.")
    return cfg


def save_config(cfg: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
