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
import re
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

from tools.browser.detector import ClickableElementDetector, filter_nested_elements, INTERACTIVE_SCAN_JS, CAPTCHA_DETECT_JS
from tools.browser.serializer import DOMSerializer
from tools.browser.extract_action import ExtractAction, page_to_markdown
from tools.browser import session_state
from tools.browser import profile_cache
from tools.browser.profile_lock import ProfileLock, ProfileInUse  # noqa: F401 (ProfileInUse re-export)


# CHẶN CỨNG: nhãn nút mà agent KHÔNG được phép tự click vì đó là HÀNH ĐỘNG THẬT
# gây hậu quả trên tài khoản người dùng (gửi lời mời hợp tác tới creator). Chặn ở
# tầng tool để dù LLM có lỡ chọn nút này thì cũng không bao giờ thực thi được.
# So khớp: nhãn (đã chuẩn hoá, viết thường) BẮT ĐẦU bằng 1 trong các tiền tố này
# VÀ ngắn (nút, không phải cả hàng dữ liệu). Mở rộng qua tham số blocked_click_prefixes.
DEFAULT_BLOCKED_CLICK_PREFIXES = ('mời', 'invite')
_BLOCKED_LABEL_MAX_LEN = 30

# Vòng đệm phản hồi API: số bản ghi giữ lại, và giới hạn kích thước body mỗi bản.
API_LOG_SIZE = 40
API_BODY_LIMIT = 4000        # ký tự lưu lại
API_BODY_MAX_FETCH = 300_000  # body lớn hơn mức này thì bỏ qua, không đọc


class BrowserTool:
    def __init__(
        self,
        llm,
        headless: bool = False,
        storage_state_path: str | None = None,
        user_data_dir: str | None = None,
        downloads_dir: str | None = None,
        max_elements: int = 100,
        viewport: dict | None = None,
        use_vision: bool = False,
        delay_range: tuple[float, float] = (0.8, 2.4),
        blocked_click_prefixes: tuple[str, ...] = DEFAULT_BLOCKED_CLICK_PREFIXES,
    ):
        self._llm = llm
        self.headless = headless
        self.storage_state_path = storage_state_path
        # Khi có user_data_dir -> dùng PROFILE CHROME THẬT trên đĩa thay vì
        # chụp-lại-rồi-phục-dựng. Xem docstring start() để biết vì sao.
        self.user_data_dir = user_data_dir
        # Nơi cất file trang web tải về (vd Excel/CSV do TikTok Seller sinh ra khi
        # xuất đơn hàng). Không đặt -> file tải về bị Playwright xoá khi đóng browser.
        self.downloads_dir = downloads_dir
        self.max_elements = max_elements
        self.viewport = viewport or {'width': 1280, 'height': 720}
        self.use_vision = use_vision
        # Nghỉ ngẫu nhiên (giây) sau mỗi hành động tương tác — cho giống người dùng
        # thật, giảm khả năng bị anti-bot của trang bật captcha vì thao tác quá đều/nhanh.
        self.delay_range = delay_range
        self._blocked_click_prefixes = tuple(p.lower() for p in blocked_click_prefixes)

        self._playwright = None
        self._browser = None
        self._profile_lock: ProfileLock | None = None
        self._event_log = None
        self._event_log_path = ''
        self._nav_count = 0
        self._snapshot_note = ''
        self._session_warned = False  # cảnh báo hạn phiên chỉ nói 1 lần/lượt chạy
        self._downloads: list[dict] = []
        # Trang nào đã gắn listener rồi — gắn 2 lần sẽ chạy handler 2 lần. Với
        # download thì 2 handler cùng save_as vào MỘT đường dẫn = hỏng file.
        self._dl_hooked: set = set()
        self._log_hooked: set = set()
        self._api_hooked: set = set()
        # Vòng đệm phản hồi API. Ghi SẴN thay vì bắt agent "bật theo dõi" trước:
        # lúc agent nhận ra cần xem phản hồi thì request đã bay qua từ lâu.
        self._api_log: deque = deque(maxlen=API_LOG_SIZE)
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._selector_map: dict[int, dict] = {}

    # Cờ chống dấu vết "trình duyệt tự động": tắt navigator.webdriver + banner
    # "đang bị điều khiển tự động". Nếu không, anti-bot của TikTok phát captcha
    # khó/không giải được (kéo đúng vẫn báo "Không thể xác minh").
    # KHÔNG thêm init script "ẩn dấu vết" ở đây. Đo thực tế (4 cấu hình, cùng máy):
    #   trơ trụi                -> navigator.webdriver = true            (lộ)
    #   chỉ cờ này              -> navigator.webdriver = false           (giống Chrome thật)
    #   cờ này + init script cũ -> navigator.webdriver = undefined, và navigator có
    #                              OWN-property đọc ngược ra được "() => undefined",
    #                              đồng thời navigator.languages lệch Accept-Language.
    # Tức là init script biến một vân tay đã sạch thành vân tay GIẢ RÕ RÀNG. Riêng cờ
    # launch là đủ; locale của context lo phần ngôn ngữ và giữ header khớp với JS.
    _LAUNCH_ARGS = ['--disable-blink-features=AutomationControlled']

    # Chặn profile phình vô hạn. Đo sau ~4 giờ dùng thật: profile 478MB, trong đó
    # 221MB HTTP cache + 94MB JS code cache — toàn thứ vứt được, còn phần đáng giữ
    # (IndexedDB chứa khoá gắn thiết bị) chỉ ~21MB. Chỉ áp cho profile trên đĩa;
    # context tạm thì Chromium tự xoá khi đóng nên không cần.
    _PERSISTENT_ARGS = ['--disk-cache-size=104857600']  # 100MB

    # ========== LIFECYCLE ==========
    async def start(self):
        """Mở browser ở 1 trong 2 chế độ lưu phiên đăng nhập:

        A. user_data_dir (ƯU TIÊN) — profile Chrome thật trên đĩa. Chính Chromium
           giữ cookie/localStorage/IndexedDB/service worker, và TỰ GHI LẠI mỗi khi
           server cấp cookie mới. Đây là cách giữ phiên lâu nhất: không có bước
           "chụp rồi phục dựng" nên không mất gì, và vân tay thiết bị ổn định qua
           các lần chạy (trang không thấy 'máy lạ cầm đúng thẻ' mỗi lần mở).

        B. storage_state_path — ảnh chụp JSON (cookie + localStorage). Gọn, chuyển
           máy được, nhưng chỉ là ảnh chụp: thiếu IndexedDB (khoá device-binding
           kiểu TikTok Ticket Guard) và mọi thứ trang cấp thêm sau đó đều phải tự
           tay lưu lại. Giữ lại để tương thích ngược + làm bản sao lưu.

        Cả hai: session đã HẾT HẠN thì không nạp (xem session_state) — nạp nửa vời
        (cookie chết + localStorage còn cache 'đã đăng nhập') làm trang lặp reload."""
        if self.user_data_dir:
            # Giữ khoá TRƯỚC khi mở Chromium: đo thực tế cho thấy Chromium trên
            # Windows vẫn mở bình thường khi 2 tiến trình trỏ vào cùng profile
            # (trái với tài liệu Playwright), nên phải tự chặn — xem profile_lock.py.
            lock = ProfileLock(self.user_data_dir)
            lock.acquire()  # ném ProfileInUse kèm hướng dẫn nếu đang bị chiếm
            self._profile_lock = lock

            # Dọn cache khi profile phình quá ngưỡng. Phải làm ở ĐÂY: đã giữ khoá
            # (không ai chen vào) và Chromium chưa mở file (Windows khoá file đang
            # mở). _PERSISTENT_ARGS bên dưới không đủ — nó chỉ chặn HTTP cache, còn
            # Code Cache và Service Worker/CacheStorage vẫn phình tự do; đo 01-08-2026
            # thấy hai mục đó chiếm 200/284MB. Xem profile_cache.py.
            try:
                note = profile_cache.prune(self.user_data_dir)
                if note:
                    print(note)
            except Exception as e:
                # Dọn dẹp hỏng thì KHÔNG được chặn việc mở browser.
                print(f"(không dọn được cache profile: {type(e).__name__}: {e})")

        try:
            await self._launch()
        except Exception:
            # Mở hụt thì phải NHẢ KHOÁ, nếu không profile bị treo cho tới khi
            # thoát hẳn app và lần thử lại nào cũng báo "đang bị chiếm".
            await self._release_profile_lock()
            raise

    async def _launch(self) -> None:
        self._playwright = await async_playwright().start()

        if self.user_data_dir:
            try:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    self.user_data_dir,
                    headless=self.headless,
                    args=self._LAUNCH_ARGS + self._PERSISTENT_ARGS,
                    viewport=self.viewport,
                    locale='vi-VN',  # khớp người dùng Việt thật (navigator.languages + Accept-Language)
                )
            except Exception as e:
                raise RuntimeError(
                    f"Không mở được profile trình duyệt tại {self.user_data_dir}: {e}"
                ) from e
        else:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=self._LAUNCH_ARGS,
            )
            storage_state = session_state.load_for_context(self.storage_state_path, log=print)
            self._context = await self._browser.new_context(
                viewport=self.viewport,
                storage_state=storage_state,
                locale='vi-VN',
            )

        # Trang mở tab mới (window.open / target=_blank, vd click creator trên
        # TikTok Affiliate mở trang chi tiết ở tab khác) -> tự chuyển sang tab mới
        # nhất. Không có bước này, self._page kẹt ở tab cũ và agent tưởng click
        # không ăn rồi lặp vô hạn.
        self._context.on("page", self._on_new_page)
        # Persistent context mở sẵn 1 tab — dùng lại, đừng tạo thêm tab trắng thừa.
        existing = [p for p in self._context.pages if not p.is_closed()]
        self._page = existing[0] if existing else await self._context.new_page()
        for page in self._context.pages:
            self._hook_downloads(page)
            self._hook_api(page)

    def _on_new_page(self, page) -> None:
        self._page = page
        self._hook_downloads(page)
        self._hook_api(page)
        if self._event_log is not None:
            self._hook_event_log(page)

    # ========== NGHE PHẢN HỒI API ==========
    def _hook_api(self, page) -> None:
        """Ghi lại phản hồi JSON của trang.

        Vì sao cần: nhiều thao tác trên web thương mại điện tử là việc CHẠY NGẦM ở
        phía server — bấm "Xuất" xong file chưa có ngay, phải chờ server tạo. Dò
        giao diện để đoán "xong chưa" vừa chậm vừa dễ sai; đọc thẳng phản hồi API
        thì biết chính xác trạng thái và thường có sẵn cả link tải.

        Chỉ ĐỌC, không sửa/không tự gọi API — không đụng tới chữ ký request của trang."""
        if page in self._api_hooked:
            return
        self._api_hooked.add(page)
        page.on('response', lambda r: asyncio.create_task(self._record_api(r)))

    async def _record_api(self, response) -> None:
        try:
            url = response.url
            if '/api/' not in url and '/graphql' not in url:
                return  # bỏ ảnh, css, js, tracking pixel...
            ctype = (response.headers or {}).get('content-type', '')
            if 'json' not in ctype.lower():
                return
            body = ''
            try:
                raw = await response.body()
                if len(raw) <= API_BODY_MAX_FETCH:
                    body = raw.decode('utf-8', errors='replace')[:API_BODY_LIMIT]
            except Exception:
                body = ''  # body đã bị giải phóng / redirect — vẫn ghi phần metadata
            self._api_log.append({
                'at': datetime.now().strftime('%H:%M:%S'),
                'url': url,
                'status': response.status,
                'body': body,
            })
        except Exception:
            pass  # nghe hụt 1 response không được phép làm chết browser

    def api_responses(self, url_contains: str = '', max_results: int = 3,
                      body_chars: int = 1200) -> str:
        """Các phản hồi API đã ghi, mới nhất trước."""
        hits = [h for h in self._api_log if url_contains.lower() in h['url'].lower()]
        if not hits:
            seen = len(self._api_log)
            return (f"Chưa ghi được phản hồi API nào khớp '{url_contains}'. "
                    f"(Đã ghi {seen} phản hồi khác trong phiên này.) "
                    "Có thể trang chưa gọi API đó — chờ thêm rồi hỏi lại.")
        out = [f"{len(hits)} phản hồi khớp '{url_contains}' (mới nhất trước):"]
        for h in list(reversed(hits))[:max(1, max_results)]:
            body = h['body'][:max(200, body_chars)]
            links = self._urls_in(h['body'])
            out.append(f"\n[{h['at']}] HTTP {h['status']} {h['url'][:160]}")
            if links:
                out.append("  Link tìm thấy trong phản hồi: " + " | ".join(links[:5]))
            out.append(f"  Nội dung: {body}" + ("..." if len(h['body']) > len(body) else ""))
        return "\n".join(out)

    @staticmethod
    def _urls_in(text: str) -> list[str]:
        """Rút link http(s) trong body — thường là link tải file server vừa tạo xong."""
        found = re.findall(r'https?:\\?/\\?/[^\s"\'<>,\\]{10,300}', text or '')
        cleaned, seen = [], set()
        for u in found:
            u = u.replace('\\/', '/')
            if u not in seen:
                seen.add(u)
                cleaned.append(u)
        return cleaned

    # ========== TẢI FILE VỀ MÁY ==========
    def _hook_downloads(self, page) -> None:
        """Bắt MỌI file trang web tải về và cất vào downloads_dir.

        Bắt buộc phải tự lưu: Playwright cho file tải về vào thư mục tạm rồi XOÁ
        khi đóng browser. Không lưu lại thì file khách xuất ra sẽ biến mất."""
        if not self.downloads_dir or page in self._dl_hooked:
            return
        self._dl_hooked.add(page)
        page.on('download', lambda d: asyncio.create_task(self._save_download(d)))

    async def _save_download(self, download) -> None:
        try:
            folder = Path(self.downloads_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = download.suggested_filename or 'download.bin'
            # Tiền tố thời gian: xuất 2 lần cùng ngày không đè lên nhau, và khách
            # nhìn tên file biết ngay cái nào mới.
            target = folder / f'{datetime.now():%Y%m%d-%H%M%S}-{name}'
            await download.save_as(str(target))
            size = target.stat().st_size if target.exists() else 0
            self._downloads.append({
                'path': str(target),
                'name': name,
                'size': size,
                'at': datetime.now().strftime('%H:%M:%S'),
            })
            self._write_log('TAI', f'{target} ({size} bytes)')
        except Exception as e:  # noqa: BLE001 - tải hụt không được làm chết browser
            self._downloads.append({'path': '', 'name': 'LỖI', 'size': 0,
                                    'error': f'{type(e).__name__}: {e}',
                                    'at': datetime.now().strftime('%H:%M:%S')})

    @staticmethod
    def _describe_download(entry: dict) -> str:
        if entry.get('error'):
            return f"Tải file thất bại: {entry['error']}"
        kb = entry['size'] / 1024
        return (f"Đã tải xong \"{entry['name']}\" ({kb:.1f} KB) và lưu tại:\n{entry['path']}\n"
                "File nằm trên máy này — mở thư mục đó là thấy.")

    async def wait_for_download(self, timeout_seconds: int = 120) -> str:
        """Chờ tới khi có 1 file được tải xong (dùng khi trang tự bắt đầu tải)."""
        return await self._await_download(len(self._downloads), timeout_seconds)

    async def download_file(self, index: int, timeout_seconds: int = 120) -> str:
        """Click element [index] rồi chờ file tải xong — dùng cho nút Tải/Xuất."""
        if not self.downloads_dir:
            return "Máy này chưa cấu hình thư mục tải file, không nhận được file."
        before = len(self._downloads)
        click_result = await self.click(index)
        if click_result.startswith('TỪ CHỐI') or 'not found' in click_result:
            return click_result
        result = await self._await_download(before, timeout_seconds)
        return f"{click_result}\n{result}"

    async def _await_download(self, before: int, timeout_seconds: int) -> str:
        timeout_seconds = max(5, min(int(timeout_seconds or 120), 110))
        waited, interval = 0.0, 0.5
        while waited < timeout_seconds:
            if len(self._downloads) > before:
                return self._describe_download(self._downloads[-1])
            await asyncio.sleep(interval)
            waited += interval
        return (f"Chờ {int(waited)}s mà chưa có file nào được tải về. "
                "Có thể trang còn đang tạo file (xuất đơn hàng thường mất một lúc rồi mới "
                "hiện nút tải trong mục lịch sử xuất) — hãy gọi browser__get_state để xem "
                "trạng thái, rồi bấm đúng nút tải.")

    def list_downloads(self) -> str:
        if not self._downloads:
            return "Chưa có file nào được tải về trong phiên này."
        lines = [f"{len(self._downloads)} file đã tải về máy này:"]
        for d in self._downloads:
            lines.append(f"  [{d['at']}] {d.get('error') or d['path']} ({d['size']/1024:.1f} KB)")
        return "\n".join(lines)

    # ========== NHẬT KÝ CHẨN ĐOÁN ==========
    def enable_event_log(self, path: str) -> None:
        """Ghi lại điều hướng / lỗi console / HTTP lỗi ra file.

        Dùng cho lúc đăng nhập thủ công: nếu trang rơi vào vòng lặp reload thì
        cần biết nó nhảy qua những URL nào và server trả mã gì — ảnh chụp màn hình
        console không đủ để kết luận. Không bật mặc định khi agent chạy (tốn I/O
        và không có ai đọc)."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._event_log = open(path, 'a', encoding='utf-8')
        self._event_log_path = path
        self._nav_count = 0
        self._write_log('BAT DAU', f'ghi nhat ky luc {datetime.now():%H:%M:%S}')
        for page in self._context.pages:
            self._hook_event_log(page)

    def _write_log(self, kind: str, text: str) -> None:
        if self._event_log is None:
            return
        try:
            self._event_log.write(f'{datetime.now():%H:%M:%S.%f}  {kind:5} {text}\n')
            self._event_log.flush()  # flush ngay: nếu treo/kill cứng vẫn còn dữ liệu
        except (OSError, ValueError):
            pass

    def _hook_event_log(self, page) -> None:
        if page in self._log_hooked:
            return  # gắn 2 lần -> mỗi sự kiện ghi 2 dòng, đếm điều hướng sai gấp đôi
        self._log_hooked.add(page)

        def on_nav(frame) -> None:
            if frame is page.main_frame:
                self._nav_count += 1
                self._write_log('NAV', f'#{self._nav_count} {frame.url[:200]}')

        def on_console(msg) -> None:
            if msg.type == 'error':
                self._write_log('ERR', msg.text.replace('\n', ' ')[:300])

        def on_response(resp) -> None:
            if resp.status >= 400:
                self._write_log('HTTP', f'{resp.status} {resp.url[:200]}')
            elif 300 <= resp.status < 400:
                # Redirect phía server KHÔNG kích hoạt framenavigated (Chromium chỉ
                # báo URL cuối cùng), nên vòng lặp redirect sẽ vô hình nếu không ghi
                # ở đây — mà đó chính là thứ cần chẩn đoán.
                try:
                    if resp.request.resource_type != 'document':
                        return
                    target = resp.headers.get('location', '')
                except Exception:
                    return
                self._write_log('REDIR', f'{resp.status} {resp.url[:120]} -> {target[:120]}')

        page.on('framenavigated', on_nav)
        page.on('console', on_console)
        page.on('response', on_response)

    def event_log_summary(self) -> str:
        if self._event_log is None:
            return ''
        return (f'{self._nav_count} lần điều hướng, nhật ký: {self._event_log_path}')

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
        Không phải tool cho agent gọi (không nằm trong registration.py).

        Đọc thẳng từ context (KHÔNG cần page nào còn sống, cũng không cần reload
        trang trước khi gọi) — nên vẫn lưu được kể cả khi người dùng đã đóng tab."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        state = await self._snapshot(path=path)
        # Xác nhận thứ vừa lưu có phiên đăng nhập thật, không phải file rỗng —
        # tránh trường hợp người dùng tưởng đã lưu xong mà thực ra chưa login.
        note = f"\n   Lưu ý: {self._snapshot_note}" if self._snapshot_note else ""
        code, message = session_state.status(state)
        if code in ('empty', 'expired'):
            return f"⚠️  Đã ghi {path} nhưng KHÔNG có phiên đăng nhập hợp lệ: {message}{note}"
        return f"Đã lưu phiên đăng nhập vào {path}\n   {message}{note}"

    async def _snapshot(self, path: str | None = None) -> dict:
        """storage_state, ưu tiên kèm IndexedDB nhưng KHÔNG chết nếu không kèm được.

        Vì sao cố kèm: ByteDance giữ khoá ký gắn thiết bị (Ticket Guard) trong
        IndexedDB chứ không phải cookie; bản chụp thiếu nó thì mỗi lần phục dựng
        trang lại thấy như một máy khác đang cầm đúng cookie.

        Vì sao phải có đường lùi: đo thực tế trên TikTok Seller, Playwright ném
        "Unable to serialize IndexedDB: Database name is empty" — trang tạo một
        IndexedDB tên rỗng mà bộ serialize của Playwright không xử lý được. Nếu
        không lùi thì hỏng cả bản sao lưu, mất luôn thứ quan trọng hơn (cookie)."""
        try:
            state = await self._context.storage_state(path=path, indexed_db=True)
            self._snapshot_note = ''
            return state
        except Exception as e:  # noqa: BLE001 - mất IndexedDB còn hơn mất cả bản sao lưu
            self._snapshot_note = (
                f'không kèm được IndexedDB ({str(e).splitlines()[0][:90]}) — '
                'bản sao lưu chỉ có cookie + localStorage'
            )
            return await self._context.storage_state(path=path)

    async def export_state(self) -> dict:
        """Bản chụp session hiện tại, KHÔNG ghi ra đĩa — để caller tự quyết định
        có nên đè lên file cũ hay không (xem session_state.should_persist)."""
        return await self._snapshot()

    async def _release_profile_lock(self) -> None:
        if self._profile_lock is not None:
            self._profile_lock.release()
            self._profile_lock = None

    async def stop(self):
        # Persistent context: đóng context là đóng luôn browser (không có
        # self._browser riêng). Ephemeral: đóng context trước rồi mới tới browser —
        # ngược lại thì context.close() thao tác trên browser đã chết.
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        finally:
            if self._event_log is not None:
                self._write_log('KET THUC', f'tong {self._nav_count} lan dieu huong')
                self._event_log.close()
                self._event_log = None
            # Nhả khoá kể cả khi đóng lỗi — bằng không lần chạy sau không mở nổi profile.
            await self._release_profile_lock()

    # ========== NAVIGATION ==========
    async def navigate(self, url: str, new_tab: bool = False) -> str:
        if new_tab:
            self._page = await self._context.new_page()
        else:
            # Bám tab còn sống (như click/press_key/get_state). Thiếu bước này,
            # nếu tab hiện tại đã bị đóng — trang tự mở tab mới rồi tab đó đóng,
            # hoặc người dùng đóng tab trong lúc app chờ ở input() — thì goto ném
            # TargetClosedError dù browser vẫn hoàn toàn khoẻ.
            await self._reconcile_page()
            if self._page is None or self._page.is_closed():
                self._page = await self._context.new_page()
        await self._page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await self._human_pause()
        return f"Navigated to {self._page.url}{self._session_warning()}"

    # Cảnh báo hạn phiên MỘT LẦN, gắn vào navigate đầu tiên. Đặt ở đây vì đây là
    # thao tác mở màn của mọi việc dùng web: biết phiên sắp đứt TRƯỚC khi làm việc
    # dài thì còn kịp báo người dùng, chứ hỏng giữa chừng là mất cả lượt chạy.
    # Con số đọc từ bản sao lưu JSON nên là ƯỚC LƯỢNG — phiên thật nằm trong profile.
    _WARN_UNDER_HOURS = 12

    def _session_warning(self) -> str:
        if self._session_warned or not self.storage_state_path:
            return ""
        self._session_warned = True
        try:
            state = session_state.read(self.storage_state_path)
            if not state:
                return ""
            # Phải hỏi status() cho ca ĐÃ HẾT HẠN: expires_at()/hours_left() chỉ nhìn
            # cookie CÒN SỐNG, phiên chết thì không còn cookie nào sống nên trả None.
            code, _ = session_state.status(state)
            left = session_state.expires_at(state)
            left = None if left is None else (left - time.time()) / 3600
        except Exception:
            return ""
        if code == 'expired':
            return ("\n\n⚠️ PHIÊN ĐĂNG NHẬP ĐÃ HẾT HẠN. Trang nhiều khả năng sẽ hiện form "
                    "đăng nhập. Dừng lại và báo người dùng chạy đăng nhập lại, đừng cố "
                    "thao tác tiếp.")
        if left is None or left > self._WARN_UNDER_HOURS:
            return ""
        return (f"\n\n⚠️ Phiên đăng nhập chỉ còn khoảng {left:.1f} giờ. Làm việc ngắn thì "
                "vẫn kịp, nhưng hãy nhắc người dùng đăng nhập lại sớm — nêu ở cuối báo cáo.")

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
    @staticmethod
    def _keep_matching(text: str, needle: str) -> str:
        """Chỉ giữ dòng element khớp `needle`, giữ nguyên phần đầu (URL/Title/cảnh báo).

        LỌC DÒNG HIỂN THỊ, KHÔNG lọc danh sách element: [index] do serializer đánh số
        trên TOÀN BỘ element và selector_map giữ nguyên, nên số hiện ra vẫn đúng với
        cái click() sẽ bấm. Lọc trước khi đánh số thì index lệch -> bấm nhầm chỗ.
        """
        pattern = re.compile('|'.join(re.escape(p.strip()) for p in needle.split('|') if p.strip()),
                             re.IGNORECASE)
        head, kept, hidden = [], [], 0
        for line in text.splitlines():
            if not re.match(r'\s*\[\d+\]', line):
                head.append(line)
            elif pattern.search(line):
                kept.append(line)
            else:
                hidden += 1
        body = kept or ["(không element nào khớp — gọi lại không kèm 'contains' để xem đầy đủ)"]
        note = f"\n\n(đã ẩn {hidden} element không khớp \"{needle}\")" if hidden else ""
        return "\n".join(head + body) + note

    async def get_state(self, force_include_screenshot: bool | None = None,
                        contains: str = "") -> str | tuple[str, str | None]:
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

        if contains:
            text = self._keep_matching(text, contains)

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

        mismatch = await self._target_moved(index, el, center_x, center_y)
        if mismatch:
            return mismatch

        await self._page.mouse.click(center_x, center_y)
        await asyncio.sleep(0.3)
        await self._reconcile_page()  # click có thể mở tab mới -> bám theo ngay
        await self._human_pause()

        desc = el.get('text', '') or el.get('tag', 'element')
        return f"Clicked [{index}]: {desc[:50]}"

    async def _target_moved(self, index: int, el: dict, x: float, y: float) -> str:
        """Kiểm tra thứ đang NẰM DƯỚI toạ độ sắp bấm có đúng element mong muốn không.

        Toạ độ lấy từ lần get_state trước; trang SPA reflow liên tục (đóng banner,
        panel trượt ra, danh sách tải xong) nên toạ độ có thể đã trỏ vào chỗ khác.
        Không kiểm tra thì cú click âm thầm rơi vào element khác — đúng kiểu lỗi
        'agent bấm lung tung' rất khó truy vết. Thà báo lỗi để agent get_state lại."""
        expect = (el.get('text') or '').strip()
        if not expect:
            return ''  # element không có nhãn -> không có gì để đối chiếu
        try:
            actual = await self._page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    return (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
                }""",
                [x, y],
            )
        except Exception:
            return ''  # không kiểm tra được thì cứ bấm, đừng chặn oan
        if actual is None:
            return (f"Không bấm [{index}]: vị trí của element không còn nằm trong vùng nhìn "
                    "thấy. Gọi browser__get_state để lấy lại danh sách element.")
        a, e = actual.lower(), expect.lower()[:120]
        if a and (a in e or e in a):
            return ''
        return (f"KHÔNG bấm — trang đã thay đổi: chỗ định bấm giờ là \"{actual[:60]}\" "
                f"chứ không phải \"{expect[:60]}\". Gọi browser__get_state để lấy lại "
                "danh sách element rồi bấm theo index mới.")

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

        # Đọc lại giá trị THẬT trong DOM. Nhiều ô ngày/tự-hoàn-thành nuốt text gõ
        # vào (phải chọn trong lịch, hoặc phải Enter mới commit) — không kiểm tra
        # thì agent tưởng đã điền xong và đi tiếp với bộ lọc RỖNG.
        typed = await self._input_value(center_x, center_y)
        shown = text if len(text) <= 30 else text[:30] + '...'
        if typed is None:
            return f"Typed '{shown}' into [{index}]"
        if text not in typed:
            return (f"Đã gõ '{shown}' vào [{index}] nhưng ô hiện đang là '{typed[:40]}' — "
                    "text KHÔNG vào được ô. Ô này có thể cần chọn từ danh sách/lịch gợi ý, "
                    "hoặc cần browser__press_key 'Enter' để xác nhận. Kiểm tra bằng "
                    "browser__get_state trước khi đi tiếp.")
        return f"Typed '{shown}' into [{index}] (ô hiện có: '{typed[:40]}')"

    async def _input_value(self, x: float, y: float) -> str | None:
        try:
            return await self._page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    const inp = el.matches('input, textarea') ? el
                              : el.querySelector('input, textarea') || el.closest('input, textarea');
                    return inp ? inp.value : null;
                }""",
                [x, y],
            )
        except Exception:
            return None

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

    def get_state(self, with_screenshot: bool = False, contains: str = "") -> str:
        result = self._loop_thread.run(
            self._tool.get_state(force_include_screenshot=with_screenshot, contains=contains))
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

    def export_state(self) -> dict:
        return self._loop_thread.run(self._tool.export_state())

    def download_file(self, index: int, timeout_seconds: int = 120) -> str:
        return self._loop_thread.run(self._tool.download_file(index, timeout_seconds))

    def wait_for_download(self, timeout_seconds: int = 120) -> str:
        return self._loop_thread.run(self._tool.wait_for_download(timeout_seconds))

    def list_downloads(self) -> str:
        return self._tool.list_downloads()

    def api_responses(self, url_contains: str = '', max_results: int = 3,
                      body_chars: int = 1200) -> str:
        return self._tool.api_responses(url_contains, max_results, body_chars)

    def enable_event_log(self, path: str) -> None:
        # Đăng ký listener phải chạy TRÊN event loop của browser, không phải thread gọi.
        async def go():
            self._tool.enable_event_log(path)
        self._loop_thread.run(go())

    def event_log_summary(self) -> str:
        return self._tool.event_log_summary()
