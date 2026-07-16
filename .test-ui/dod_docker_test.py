"""Phase 4 DoD (local) — stack Docker (app + caddy) qua http://localhost:
invite -> device online -> task browser end-to-end xuyên Caddy proxy."""
import sys

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
from playwright.sync_api import sync_playwright

INVITE = "W2_PnxToBwLSZ5l2YPjrfn6HZfKleQJ5"
BASE = "http://localhost"
TASK = "Vào example.com và cho tôi biết tiêu đề trang"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    page.goto(f"{BASE}/?invite={INVITE}")
    page.wait_for_selector("text=Tester", timeout=10000)
    print("1. OK — web UI qua Caddy, auth_ok")

    page.wait_for_selector("text=Máy: PC-That-Cua-Long", timeout=15000)
    print("2. OK — device online (WS /ws/device xuyên Caddy)")

    page.fill("textarea", TASK)
    page.keyboard.press("Enter")
    page.wait_for_selector("text=Đang xử lý", timeout=15000)
    page.wait_for_selector("text=browser-agent", timeout=120000)
    print("3. OK — browser-agent chạy realtime (WS /ws xuyên Caddy)")

    page.wait_for_selector(".md", timeout=300000)
    print("4. OK — kết quả cuối render markdown")
    page.screenshot(path=".test-ui/dod_docker_4_answer.png")

    browser.close()
    print("=== PHASE 4 DoD LOCAL PASS ===")
