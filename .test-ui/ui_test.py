"""E2E test UI bằng Playwright — mô phỏng người dùng thật (không phải code product)."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

INVITE = "W2_PnxToBwLSZ5l2YPjrfn6HZfKleQJ5"
BASE = "http://localhost:8000"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    # 1. Vào bằng invite link
    page.goto(f"{BASE}/?invite={INVITE}")
    page.wait_for_selector("text=Personal Agent", timeout=10000)
    page.wait_for_selector("text=Tester", timeout=10000)  # auth_ok -> tên user hiện trên header
    assert "invite" not in page.url, "invite token phải bị xóa khỏi URL"
    print("1. OK — vào bằng invite link, auth_ok, token đã xóa khỏi URL")

    # 2. Gửi yêu cầu
    page.fill("textarea", "Kiểm tra tình trạng đơn hàng SA-00123 giúp tôi")
    page.keyboard.press("Enter")
    page.wait_for_selector("text=Đang xử lý", timeout=15000)
    print("2. OK — progress group xuất hiện (Đang xử lý...)")
    page.screenshot(path=".test-ui/2_progress.png")

    # 3. Chờ tool row của subagent hiện realtime
    page.wait_for_selector("text=ecom-agent", timeout=60000)
    print("3. OK — sub-block 'ecom-agent' hiện realtime")
    page.screenshot(path=".test-ui/3_subagent.png")

    # 4. Chờ câu trả lời cuối (markdown table có chữ 'Trạng thái')
    page.wait_for_selector(".md", timeout=120000)
    print("4. OK — câu trả lời cuối render markdown")
    page.screenshot(path=".test-ui/4_answer.png")

    # 5. Session xuất hiện trong sidebar + refresh giữ history
    page.wait_for_selector("nav >> text=Kiểm tra tình trạng", timeout=5000)
    page.reload()
    page.wait_for_selector("text=Tester", timeout=10000)
    page.click("nav >> text=Kiểm tra tình trạng")
    page.wait_for_selector(".md", timeout=10000)
    print("5. OK — refresh xong, chọn lại session, history load từ REST")
    page.screenshot(path=".test-ui/5_history.png")

    # 6. Banner device offline + panel pairing
    assert page.is_visible("text=Máy của bạn chưa kết nối")
    page.click("text=Hướng dẫn ghép máy")
    page.wait_for_selector("text=Ghép máy của bạn", timeout=5000)
    print("6. OK — banner offline + panel pairing mở được")
    page.screenshot(path=".test-ui/6_pairing.png")

    browser.close()
    print("=== TẤT CẢ PASS ===")
