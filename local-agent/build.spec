# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — đóng gói companion app thành app Windows (PLAN.md 2.7).
#
# Build:  uv --project agent-framework run pyinstaller local-agent/build.spec --noconfirm
# Output: dist/PersonalAgent/PersonalAgent.exe  (onedir — KHÔNG dùng onefile vì
#         Playwright cần cấu trúc thư mục driver nguyên vẹn)
#
# Lưu ý phân phối cho tester:
# - Copy Dang-nhap-trang-web.bat vào dist/PersonalAgent/ (helper --login cho khách)
# - Zip cả thư mục dist/PersonalAgent/ gửi khách; khách giải nén, chạy PersonalAgent.exe
# - Exe chưa ký code -> SmartScreen cảnh báo, khách bấm "More info" -> "Run anyway"
#   (chấp nhận ở quy mô tester; ký code nằm ở backlog Phase 5)
# - Lần chạy đầu app tự tải Chromium (~150MB) về %LOCALAPPDATA%/ms-playwright

import os
from PyInstaller.utils.hooks import collect_all

# Playwright cần bundle cả driver node + package data
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")

root = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    ["app.py"],
    pathex=[
        SPECPATH,  # local-agent/: config, pairing, executor, login_setup
        os.path.join(root, "agent-framework"),  # tools.browser.*
    ],
    binaries=pw_binaries,
    datas=pw_datas,
    hiddenimports=pw_hidden + [
        "websockets",
        "websockets.sync.client",
        "markdownify",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["openai"],  # LLM key/client KHÔNG được nằm trên máy khách (PLAN.md #8)
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="PersonalAgent",
    console=True,  # MVP console app; tray app nằm ở backlog Phase 5
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="PersonalAgent",
)
