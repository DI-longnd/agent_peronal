"""
Skill Loader — implement "Agent Skills" progressive disclosure
(anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills):

  Tầng 1 - Discovery:  chỉ đọc frontmatter (name + description) của MỌI skill,
                       nạp vào system prompt lúc khởi động. Rẻ (~50-200 token/skill).
  Tầng 2 - Activation: khi task khớp description, agent gọi read_skill(name)
                       để đọc toàn bộ nội dung SKILL.md vào context.
  Tầng 3 - Execution:  nếu SKILL.md trỏ tới script (vd: scripts/check_order.py),
                       agent chạy qua run_skill_script — chỉ stdout vào context,
                       không phải toàn bộ code hay data trung gian.

Tổ chức theo capability tree (skills/<domain>/<skill-name>/SKILL.md) để tránh
"routing collapse" khi số skill tăng lên (theo nghiên cứu SkillsBench).
"""

from __future__ import annotations
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path  # thư mục chứa SKILL.md


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir
        self._index: dict[str, SkillMeta] = {}
        self._scan()

    def _scan(self) -> None:
        """Tầng 1: quét toàn bộ SKILL.md, chỉ đọc frontmatter."""
        for skill_md in self._skills_dir.rglob("SKILL.md"):
            text = skill_md.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            _, frontmatter, _ = text.split("---", 2)
            meta = yaml.safe_load(frontmatter)
            self._index[meta["name"]] = SkillMeta(
                name=meta["name"],
                description=meta["description"],
                path=skill_md.parent,
            )

    def discovery_prompt_block(self) -> str:
        """Nội dung nạp sẵn vào system prompt — chỉ name+description, không phải full skill."""
        lines = [f"- {m.name}: {m.description}" for m in self._index.values()]
        return "Các skill khả dụng (dùng read_skill để xem chi tiết):\n" + "\n".join(lines)

    def read_skill(self, name: str) -> str:
        """Tầng 2: activation — trả full nội dung SKILL.md."""
        meta = self._index.get(name)
        if meta is None:
            return f"Không tìm thấy skill '{name}'. Các skill có sẵn: {list(self._index)}"
        return (meta.path / "SKILL.md").read_text(encoding="utf-8")

    def run_script(self, name: str, script_relpath: str, args: list[str]) -> str:
        """Tầng 3: execution — chạy script bên trong skill, chỉ trả stdout/stderr."""
        meta = self._index.get(name)
        if meta is None:
            return f"Không tìm thấy skill '{name}'."
        script_path = meta.path / script_relpath
        if not script_path.exists():
            return f"Không tìm thấy script '{script_relpath}' trong skill '{name}'."

        result = subprocess.run(
            [sys.executable, str(script_path), *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Script lỗi (exit {result.returncode}): {result.stderr.strip()}"
        return result.stdout.strip()


READ_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_skill",
        "description": "Đọc toàn bộ hướng dẫn (SKILL.md) của 1 skill khi task khớp mô tả của nó.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Tên skill (field 'name' trong frontmatter)"}},
            "required": ["name"],
        },
    },
}

RUN_SKILL_SCRIPT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_skill_script",
        "description": "Chạy 1 script thuộc về skill (đường dẫn lấy từ nội dung SKILL.md đã đọc).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tên skill"},
                "script_relpath": {"type": "string", "description": "Đường dẫn tương đối, vd 'scripts/check_order.py'"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Tham số dòng lệnh"},
            },
            "required": ["name", "script_relpath"],
        },
    },
}
