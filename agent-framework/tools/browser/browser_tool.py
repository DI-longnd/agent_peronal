"""
BrowserTool — browser automation tool tự viết (không phụ thuộc browser-use),
tích hợp các pattern: ClickableElementDetector, DOMSerializer, ExtractAction.

use_vision:
  False (mặc định) -> get_state() chỉ trả text. Phù hợp DeepSeek (không vision).
  True  -> get_state() trả về tuple (text, base64_screenshot). Phù hợp
           GPT-4o/Claude/Gemini (model có vision).

QUAN TRỌNG — cầu nối sync/async (KHÔNG có trong tài liệu tham chiếu gốc):
AgentLoop/ToolRegistry của framework này chạy đồng bộ (sync), nhưng Playwright
và mọi method của BrowserTool đều là async. Không thể dùng asyncio.run() mỗi
lần gọi vì object Playwright (Page, BrowserContext) bị khoá vào đúng event
loop đã tạo ra chúng — tạo/hủy loop mới mỗi lần gọi sẽ làm session mất hiệu
lực giữa các lần gọi. Giải pháp: chạy 1 event loop riêng, sống suốt vòng đời
browser, trên 1 thread nền (AsyncLoopThread); SyncBrowserTool bọc mỗi method
async thành 1 method sync gọi qua asyncio.run_coroutine_threadsafe(...).
Đây là lớp hạ tầng bắt buộc để tool này chạy được trong ToolRegistry.execute()
(vốn gọi tool.handler(**arguments) và mong đợi nhận thẳng về str).
"""

from __future__ import annotations
import asyncio
import base64
import json
import random
import threading
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

from tools.browser.detector import ClickableElementDetector, filter_nested_elements, INTERACTIVE_SCAN_JS, CAPTCHA_DETECT_JS
from tools.browser.serializer import DOMSerializer
from tools.browser.extract_action import ExtractAction, page_to_markdown


# CHẶN CỨNG: nhãn nút mà agent KHÔNG được phép tự click vì đó là HÀNH ĐỘNG THẬT
# gây hậu quả trên tài khoản người dùng (gửi lời mời hợp tác tới creator). Chặn ở
# tầng tool để dù LLM có lỡ chọn nút này thì cũng không bao giờ thực thi được.
# So khớp: nhãn (đã chuẩn hoá, viết thường) BẮT ĐẦU bằng 1 trong các tiền tố này
# VÀ ngắn (nút, không phải cả hàng dữ liệu). Mở rộng qua tham số blocked_click_prefixes.
DEFAULT_BLOCKED_CLICK_PREFIXES = ('mời', 'invite')
_BLOCKED_LABEL_MAX_LEN = 30


class BrowserTool:
    def __init__(
        self,
        llm,
        headless: bool = False,
        storage_state_path: str | None = None,
        max_elements: int = 100,
        viewport: dict | None = None,
        use_vision: bool = False,
        delay_range: tuple[float, float] = (0.8, 2.4),
        blocked_click_prefixes: tuple[str, ...] = DEFAULT_BLOCKED_CLICK_PREFIXES,
    ):
        self._llm = llm
        self.headless = headless
        self.storage_state_path = storage_state_path
        self.max_elements = max_elements
        self.viewport = viewport or {'width': 1280, 'height': 720}
        self.use_vision = use_vision
        # Nghỉ ngẫu nhiên (giây) sau mỗi hành động tương tác — cho giống người dùng
        # thật, giảm khả năng bị anti-bot của trang bật captcha vì thao tác quá đều/nhanh.
        self.delay_range = delay_range
        self._blocked_click_prefixes = tuple(p.lower() for p in blocked_click_prefixes)

        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._selector_map: dict[int, dict] = {}

    # ========== LIFECYCLE ==========
    async def start(self):
        """Nạp lại session đã đăng nhập từ storage_state_path (cookie + localStorage,
        JSON gọn — KHÔNG phải toàn bộ profile Chromium) nếu file đã tồn tại. File này
        chỉ được TẠO bởi scripts/setup_browser_login.py (đăng nhập thủ công 1 lần,
        ngoài agent) — BrowserTool ở đây chỉ ĐỌC lại, không bao giờ tự đăng nhập."""
        self._playwright = await async_playwright().start()
        # Giảm dấu vết "trình duyệt tự động": --disable-blink-features=AutomationControlled
        # tắt cờ navigator.webdriver + banner "đang bị điều khiển tự động". Nếu không,
        # navigator.webdriver=true khiến anti-bot của TikTok phát captcha khó/không giải
        # được (kéo đúng vẫn báo "Không thể xác minh").
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled'],
        )

        storage_state = (
            self.storage_state_path
            if self.storage_state_path and Path(self.storage_state_path).exists()
            else None
        )
        self._context = await self._browser.new_context(
            viewport=self.viewport,
            storage_state=storage_state,
            locale='vi-VN',  # khớp người dùng Việt thật (navigator.languages + Accept-Language)
        )
        # Ẩn nốt các dấu hiệu tự động còn sót ở tầng JS (chạy trước mọi script của trang).
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            "Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN','vi','en-US']});"
        )
        # Trang mở tab mới (window.open / target=_blank, vd click creator trên
        # TikTok Affiliate mở trang chi tiết ở tab khác) -> tự chuyển sang tab mới
        # nhất. Không có bước này, self._page kẹt ở tab cũ và agent tưởng click
        # không ăn rồi lặp vô hạn.
        self._context.on("page", self._on_new_page)
        self._page = await self._context.new_page()

    def _on_new_page(self, page) -> None:
        self._page = page

    async def _reconcile_page(self) -> None:
        """Đảm bảo self._page trỏ vào 1 tab còn sống và mới nhất (phòng khi tab
        hiện tại bị đóng, hoặc event 'page' chưa kịp cập nhật)."""
        pages = [p for p in self._context.pages if not p.is_closed()]
        if not pages:
            return
        if self._page is None or self._page.is_closed() or self._page not in pages:
            self._page = pages[-1]
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass

    async def _human_pause(self) -> None:
        """Nghỉ ngẫu nhiên sau hành động tương tác (giống người, tránh anti-bot)."""
        lo, hi = self.delay_range
        await asyncio.sleep(random.uniform(lo, hi))

    async def save_storage_state(self, path: str) -> str:
        """Xuất cookie + localStorage hiện tại ra file JSON — dùng bởi
        scripts/setup_browser_login.py sau khi người dùng đăng nhập thủ công.
        Không phải tool cho agent gọi (không nằm trong registration.py)."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=path)
        return f"Saved storage state to {path}"

    async def stop(self):
        # Đóng context trước rồi mới đóng browser — đóng ngược lại có thể khiến
        # context.close() thao tác trên browser đã chết.
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ========== NAVIGATION ==========
    async def navigate(self, url: str, new_tab: bool = False) -> str:
        if new_tab:
            self._page = await self._context.new_page()
        await self._page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await self._human_pause()
        return f"Navigated to {self._page.url}"

    async def go_back(self) -> str:
        await self._page.go_back()
        await asyncio.sleep(0.5)
        return "Went back"

    async def search(self, query: str, engine: str = 'duckduckgo') -> str:
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        engines = {
            'duckduckgo': f'https://duckduckgo.com/?q={encoded}',
            'google': f'https://www.google.com/search?q={encoded}&udm=14',
            'bing': f'https://www.bing.com/search?q={encoded}',
        }
        url = engines.get(engine.lower(), engines['duckduckgo'])
        await self._page.goto(url, wait_until='domcontentloaded')
        return f"Searched {engine} for '{query}'"

    # ========== DOM SCANNING ==========
    async def get_state(self, force_include_screenshot: bool | None = None) -> str | tuple[str, str | None]:
        await self._reconcile_page()  # bám tab mới nhất (nếu vừa mở tab khác)
        await asyncio.sleep(0.1)  # Đợi DOM ổn định

        raw_elements = await self._page.evaluate(INTERACTIVE_SCAN_JS)

        listener_indices = self._detect_click_listeners(raw_elements)
        for i, el in enumerate(raw_elements):
            el['has_listener'] = i in listener_indices

        filtered = []
        for el in raw_elements[:200]:
            if ClickableElementDetector.is_interactive(
                tag=el['tag'],
                attributes=el.get('attributes', {}),
                computed_styles=el.get('computed_styles', {}),
                bounding_box=el.get('rect'),
                has_js_click_listener=el.get('has_listener', False),
            ):
                filtered.append(el)

        filtered = filter_nested_elements(filtered)

        url = self._page.url
        title = await self._page.title()
        serializer = DOMSerializer(max_elements=self.max_elements)
        text, self._selector_map = serializer.serialize(filtered, url, title)

        # Cảnh báo captcha lên đầu output — agent không có vision, nếu không báo
        # thì nó không "thấy" lớp captcha che trang (captcha KHÔNG nằm trong danh
        # sách interactive element) và sẽ thao tác mù, bấm loạn.
        captcha = await self._captcha_hint()
        if captcha:
            text = (
                "⚠️ PHÁT HIỆN CAPTCHA/XÁC MINH đang chặn trang (không tự giải/kéo được). "
                "Hãy gọi browser__wait_for_human để chờ người dùng xử lý, rồi gọi lại "
                "browser__get_state. TUYỆT ĐỐI không tự click/kéo để giải captcha.\n\n"
            ) + text

        include_screenshot = force_include_screenshot if force_include_screenshot is not None else self.use_vision

        if not include_screenshot:
            return text

        try:
            screenshot = await self._page.screenshot()
            b64 = base64.b64encode(screenshot).decode()
            return text, b64
        except Exception:
            return text, None

    # ========== INTERACTION ==========
    async def click(self, index: int,
                     coordinate_x: int | None = None,
                     coordinate_y: int | None = None) -> str:
        if coordinate_x is not None and coordinate_y is not None:
            await self._page.mouse.click(coordinate_x, coordinate_y)
            await self._reconcile_page()
            await self._human_pause()
            return f"Clicked at ({coordinate_x}, {coordinate_y})"

        if index not in self._selector_map:
            return f"Element [{index}] not found. Page may have changed. Call get_state() again."

        el = self._selector_map[index]

        # CHẶN CỨNG nút Mời/Invite (hành động thật trên tài khoản) — xem hằng số ở đầu file.
        label = (el.get('text') or '').strip().lower()
        if label and len(label) <= _BLOCKED_LABEL_MAX_LEN and any(
            label.startswith(p) for p in self._blocked_click_prefixes
        ):
            return (
                f"TỪ CHỐI click [{index}] (\"{el.get('text', '')[:30]}\"): đây là nút Mời/Invite — "
                "bị chặn ở tầng tool để tránh gửi lời mời hợp tác ngoài ý muốn tới creator. "
                "Chỉ ĐỌC/trích xuất thông tin, KHÔNG thực hiện thao tác Mời."
            )

        rect = el['rect']
        center_x = rect['x'] + rect['width'] / 2
        center_y = rect['y'] + rect['height'] / 2

        await self._page.mouse.click(center_x, center_y)
        await asyncio.sleep(0.3)
        await self._reconcile_page()  # click có thể mở tab mới -> bám theo ngay
        await self._human_pause()

        desc = el.get('text', '') or el.get('tag', 'element')
        return f"Clicked [{index}]: {desc[:50]}"

    async def input_text(self, index: int, text: str, clear: bool = True) -> str:
        if index not in self._selector_map:
            return f"Element [{index}] not found. Call get_state() again."

        el = self._selector_map[index]
        rect = el['rect']
        center_x = rect['x'] + rect['width'] / 2
        center_y = rect['y'] + rect['height'] / 2

        await self._page.mouse.click(center_x, center_y)
        await asyncio.sleep(0.1)

        if clear:
            await self._page.keyboard.press('Control+a')
            await asyncio.sleep(0.05)

        await self._page.keyboard.type(text, delay=20)
        await self._human_pause()

        return f"Typed '{text[:30]}...' into [{index}]" if len(text) > 30 else f"Typed '{text}' into [{index}]"

    async def scroll(self, pages: float = 1.0, direction: str = 'down') -> str:
        dy = self.viewport['height'] * pages * (1 if direction == 'down' else -1)
        await self._page.evaluate(f'window.scrollBy(0, {dy})')
        await asyncio.sleep(0.2)
        await self._human_pause()
        return f"Scrolled {'down' if direction == 'down' else 'up'} {pages} page(s)"

    async def press_key(self, key: str) -> str:
        await self._page.keyboard.press(key)
        await self._reconcile_page()  # Enter có thể điều hướng/mở tab
        await self._human_pause()
        return f"Pressed {key}"

    async def wait(self, seconds: int = 3) -> str:
        seconds = min(seconds, 30)
        await asyncio.sleep(seconds)
        return f"Waited {seconds}s"

    # ========== HUMAN-IN-THE-LOOP (CAPTCHA) ==========
    async def _captcha_hint(self) -> str:
        """Trả mô tả captcha nếu có captcha đang chặn trang, rỗng nếu không."""
        try:
            return await self._page.evaluate(CAPTCHA_DETECT_JS)
        except Exception:
            return ''

    async def wait_for_human(self, reason: str = "", timeout_seconds: int = 90) -> str:
        """Tạm dừng cho NGƯỜI DÙNG tự xử lý captcha/xác minh trên cửa sổ browser
        đang hiện — agent KHÔNG tự giải. Poll tới khi captcha biến mất hoặc hết giờ.
        Cap < timeout RPC của server (120s) để trả kết quả sạch trước khi RPC timeout."""
        timeout_seconds = max(5, min(int(timeout_seconds or 90), 100))
        interval, waited = 1.5, 0.0
        saw_captcha = bool(await self._captcha_hint())
        while waited < timeout_seconds:
            await asyncio.sleep(interval)
            waited += interval
            hint = await self._captcha_hint()
            if hint:
                saw_captcha = True
            elif saw_captcha:
                return (f"Người dùng đã xử lý xong xác minh sau ~{int(waited)}s. "
                        "Gọi browser__get_state để tiếp tục.")
            elif waited >= 4:
                # Không hề thấy captcha sau vài giây — có thể agent gọi nhầm hoặc
                # trang chỉ tải chậm; khỏi bắt người dùng chờ vô ích.
                return ("Không thấy captcha/xác minh đang chặn trang. Có thể trang chỉ "
                        "tải chậm — gọi browser__get_state để kiểm tra lại.")
        return (f"Đã chờ {int(waited)}s nhưng xác minh vẫn chưa hoàn tất. Nhờ người dùng "
                "kéo/hoàn tất xác minh trên cửa sổ Chrome đang mở rồi gọi browser__get_state lại.")

    # ========== EXTRACTION ==========
    async def extract(self, query: str, extract_links: bool = False, start_from_char: int = 0) -> str:
        return await ExtractAction.extract(
            self._page, query, self._llm,
            extract_links=extract_links,
            start_from_char=start_from_char,
        )

    async def page_markdown(self, start_from_char: int = 0) -> str:
        """Nửa 'device' của browser__extract (PLAN.md 4.6): chỉ chụp nội dung trang
        thành markdown, KHÔNG gọi LLM — server nhận JSON này rồi tự chạy LLM
        extraction. Trả JSON string {"url","markdown","truncated","next_start"}."""
        payload = await page_to_markdown(self._page, start_from_char)
        return json.dumps(payload, ensure_ascii=False)

    # ========== SENSITIVE DATA ==========
    async def type_sensitive(self, index: int, placeholder: str, sensitive_data: dict) -> str:
        """Gõ sensitive data (password, API key...) an toàn — KHÔNG bao giờ
        echo giá trị thật ra kết quả trả về, vì kết quả này sẽ đi vào context
        của LLM. Không tái dùng input_text() vì nó trả về nguyên văn text đã
        gõ (làm lộ secret)."""
        value = sensitive_data.get(placeholder)
        if not value:
            return f"Sensitive value '{placeholder}' not found"

        if index not in self._selector_map:
            return f"Element [{index}] not found. Call get_state() again."

        el = self._selector_map[index]
        rect = el['rect']
        center_x = rect['x'] + rect['width'] / 2
        center_y = rect['y'] + rect['height'] / 2

        await self._page.mouse.click(center_x, center_y)
        await asyncio.sleep(0.1)
        await self._page.keyboard.press('Control+a')
        await asyncio.sleep(0.05)
        await self._page.keyboard.type(value, delay=20)
        await self._human_pause()

        return f"Typed sensitive value '{placeholder}' into [{index}]"

    # ========== INTERNAL ==========
    def _detect_click_listeners(self, elements: list[dict]) -> set[int]:
        """Đơn giản hóa: kiểm tra attribute onclick (không dùng CDP)."""
        indices = set()
        for i, el in enumerate(elements):
            if 'onclick' in el.get('attributes', {}):
                indices.add(i)
        return indices


class AsyncLoopThread:
    """Chạy 1 event loop asyncio trên 1 thread nền, sống suốt vòng đời browser.
    Cho phép gọi coroutine từ code sync ở thread khác qua run()."""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def stop(self):
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


class SyncBrowserTool:
    """Wrapper sync quanh BrowserTool — mỗi method async được bọc thành 1
    method sync chạy trên AsyncLoopThread, để dùng được làm Tool.handler
    trong ToolRegistry.execute() (vốn gọi handler(**args) đồng bộ)."""

    def __init__(self, llm, **browser_tool_kwargs):
        self._loop_thread = AsyncLoopThread()
        self._tool = BrowserTool(llm, **browser_tool_kwargs)

    def start(self) -> None:
        self._loop_thread.run(self._tool.start())

    def stop(self) -> None:
        self._loop_thread.run(self._tool.stop())
        self._loop_thread.stop()

    def navigate(self, url: str, new_tab: bool = False) -> str:
        return self._loop_thread.run(self._tool.navigate(url, new_tab))

    def go_back(self) -> str:
        return self._loop_thread.run(self._tool.go_back())

    def search(self, query: str, engine: str = 'duckduckgo') -> str:
        return self._loop_thread.run(self._tool.search(query, engine))

    def get_state(self, with_screenshot: bool = False) -> str:
        result = self._loop_thread.run(self._tool.get_state(force_include_screenshot=with_screenshot))
        if isinstance(result, tuple):
            text, screenshot = result
            return f"{text}\n[Screenshot available: {len(screenshot or '')} bytes]"
        return result

    def click(self, index: int, coordinate_x: int | None = None, coordinate_y: int | None = None) -> str:
        return self._loop_thread.run(self._tool.click(index, coordinate_x, coordinate_y))

    def input_text(self, index: int, text: str, clear: bool = True) -> str:
        return self._loop_thread.run(self._tool.input_text(index, text, clear))

    def scroll(self, pages: float = 1.0, direction: str = 'down') -> str:
        return self._loop_thread.run(self._tool.scroll(pages, direction))

    def press_key(self, key: str) -> str:
        return self._loop_thread.run(self._tool.press_key(key))

    def wait(self, seconds: int = 3) -> str:
        return self._loop_thread.run(self._tool.wait(seconds))

    def wait_for_human(self, reason: str = "", timeout_seconds: int = 90) -> str:
        return self._loop_thread.run(self._tool.wait_for_human(reason, timeout_seconds))

    def extract(self, query: str, extract_links: bool = False, start_from_char: int = 0) -> str:
        return self._loop_thread.run(self._tool.extract(query, extract_links, start_from_char))

    def page_markdown(self, start_from_char: int = 0) -> str:
        return self._loop_thread.run(self._tool.page_markdown(start_from_char))

    def type_sensitive(self, index: int, placeholder: str, sensitive_data: dict) -> str:
        return self._loop_thread.run(self._tool.type_sensitive(index, placeholder, sensitive_data))

    def save_storage_state(self, path: str) -> str:
        return self._loop_thread.run(self._tool.save_storage_state(path))
