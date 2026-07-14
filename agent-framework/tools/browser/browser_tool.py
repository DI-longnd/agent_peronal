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
import threading
from playwright.async_api import async_playwright, Page, BrowserContext

from tools.browser.detector import ClickableElementDetector, filter_nested_elements, INTERACTIVE_SCAN_JS
from tools.browser.serializer import DOMSerializer
from tools.browser.extract_action import ExtractAction


class BrowserTool:
    def __init__(
        self,
        llm,
        headless: bool = False,
        profile_dir: str | None = None,
        max_elements: int = 100,
        viewport: dict | None = None,
        use_vision: bool = False,
    ):
        self._llm = llm
        self.headless = headless
        self.profile_dir = profile_dir
        self.max_elements = max_elements
        self.viewport = viewport or {'width': 1280, 'height': 720}
        self.use_vision = use_vision

        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._selector_map: dict[int, dict] = {}

    # ========== LIFECYCLE ==========
    async def start(self):
        self._playwright = await async_playwright().start()

        if self.profile_dir:
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                headless=self.headless,
                viewport=self.viewport,
            )
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        else:
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context(viewport=self.viewport)
            self._page = await self._context.new_page()

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    # ========== NAVIGATION ==========
    async def navigate(self, url: str, new_tab: bool = False) -> str:
        if new_tab:
            self._page = await self._context.new_page()
        await self._page.goto(url, wait_until='domcontentloaded', timeout=30000)
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
            return f"Clicked at ({coordinate_x}, {coordinate_y})"

        if index not in self._selector_map:
            return f"Element [{index}] not found. Page may have changed. Call get_state() again."

        el = self._selector_map[index]
        rect = el['rect']
        center_x = rect['x'] + rect['width'] / 2
        center_y = rect['y'] + rect['height'] / 2

        await self._page.mouse.click(center_x, center_y)
        await asyncio.sleep(0.3)

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

        return f"Typed '{text[:30]}...' into [{index}]" if len(text) > 30 else f"Typed '{text}' into [{index}]"

    async def scroll(self, pages: float = 1.0, direction: str = 'down') -> str:
        dy = self.viewport['height'] * pages * (1 if direction == 'down' else -1)
        await self._page.evaluate(f'window.scrollBy(0, {dy})')
        await asyncio.sleep(0.2)
        return f"Scrolled {'down' if direction == 'down' else 'up'} {pages} page(s)"

    async def press_key(self, key: str) -> str:
        await self._page.keyboard.press(key)
        return f"Pressed {key}"

    async def wait(self, seconds: int = 3) -> str:
        seconds = min(seconds, 30)
        await asyncio.sleep(seconds)
        return f"Waited {seconds}s"

    # ========== EXTRACTION ==========
    async def extract(self, query: str, extract_links: bool = False, start_from_char: int = 0) -> str:
        return await ExtractAction.extract(
            self._page, query, self._llm,
            extract_links=extract_links,
            start_from_char=start_from_char,
        )

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

    def extract(self, query: str, extract_links: bool = False, start_from_char: int = 0) -> str:
        return self._loop_thread.run(self._tool.extract(query, extract_links, start_from_char))

    def type_sensitive(self, index: int, placeholder: str, sensitive_data: dict) -> str:
        return self._loop_thread.run(self._tool.type_sensitive(index, placeholder, sensitive_data))
