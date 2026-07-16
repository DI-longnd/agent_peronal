"""Phase 3 DoD — flow trọn vẹn: invite -> pairing app -> task browser -> refresh.

Chạy: python .test-ui/dod_test.py <PAIRING_CODE>
Yêu cầu: server :8000 đang chạy, local-agent đang chờ pairing với mã đã in.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
from playwright.sync_api import sync_playwright

INVITE = "W2_PnxToBwLSZ5l2YPjrfn6HZfKleQJ5"
BASE = "http://localhost:8000"
CODE = sys.argv[1]
TASK = "Vào duckduckgo.com tìm giá bitcoin hiện tại"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    # 1. Vào bằng invite link (build tĩnh qua port 8000, không dev server)
    page.goto(f"{BASE}/?invite={INVITE}")
    page.wait_for_selector("text=Tester", timeout=10000)
    assert "invite" not in page.url
    print("1. OK — invite link, auth_ok, token xóa khỏi URL")

    # 2. Pairing: mở panel từ banner, nhập mã 6 số
    page.click("text=Hướng dẫn ghép máy")
    page.wait_for_selector("text=Ghép máy của bạn", timeout=5000)
    page.fill("input[placeholder='000000']", CODE)
    page.click("button:text-is('Ghép')")
    page.wait_for_selector("text=Đã ghép thành công", timeout=10000)
    print("2. OK — nhập mã pairing, server báo ghép thành công")
    page.screenshot(path=".test-ui/dod_2_paired.png")
    page.click("button:has-text('Xong')")

    # 3. App poll nhận token -> kết nối WS -> device_status online đẩy về web
    page.wait_for_selector("text=Máy: PC-That-Cua-Long", timeout=30000)
    print("3. OK — DeviceBadge hiện tên máy (device online realtime)")
    page.screenshot(path=".test-ui/dod_3_device_online.png")

    # 4. Chat task browser
    page.fill("textarea", TASK)
    page.keyboard.press("Enter")
    page.wait_for_selector("text=Đang xử lý", timeout=15000)
    print("4. OK — progress group xuất hiện")

    # 5. Sub-block browser-agent hiện realtime (Chrome bật lên trên máy)
    page.wait_for_selector("text=browser-agent", timeout=120000)
    print("5. OK — sub-block 'browser-agent' hiện realtime")
    page.screenshot(path=".test-ui/dod_5_browser_agent.png")

    # 6. Kết quả cuối render markdown
    page.wait_for_selector(".md", timeout=300000)
    print("6. OK — câu trả lời cuối render markdown")
    page.screenshot(path=".test-ui/dod_6_answer.png")

    # 7. Refresh: history load từ REST, progress cũ mất (đúng thiết kế #16)
    page.reload()
    page.wait_for_selector("text=Tester", timeout=10000)
    page.click("nav >> text=tìm giá bitcoin")
    page.wait_for_selector(".md", timeout=10000)
    assert not page.is_visible("text=Đã xử lý")
    print("7. OK — refresh xong history load từ REST, progress ephemeral đã mất")
    page.screenshot(path=".test-ui/dod_7_after_refresh.png")

    browser.close()
    print("=== PHASE 3 DoD PASS ===")
