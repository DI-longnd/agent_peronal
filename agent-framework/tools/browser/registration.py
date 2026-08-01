"""
Khai báo + đăng ký các tool browser__* (namespaced).

Phase 0 (PLAN.md mục 4.6): chuyển sang SPEC-DRIVEN — `BROWSER_TOOL_SPECS` là
NGUỒN KHAI BÁO DUY NHẤT (tên, mô tả, JSON schema, method tương ứng trên
SyncBrowserTool) cho cả 3 nơi dùng:
  1. CLI all-in-one (main.py): build_browser_registry() bind handler = method local.
  2. Server (server/remote_tools.py): bind handler = RPC stub gửi lệnh xuống device.
  3. Companion app (local-agent/executor.py): whitelist tool được phép thực thi.

QUAN TRỌNG: file này phải import được khi KHÔNG cài playwright (server không cài
playwright — nó chỉ cần specs). Vì vậy KHÔNG import playwright/browser_tool ở
module level — chỉ import trong TYPE_CHECKING.

Sensitive data (password, API key dùng để login...) được nạp từ biến môi trường
có tiền tố BROWSER_SECRET_ (vd: BROWSER_SECRET_SITE_PASSWORD -> key 'site_password'),
KHÔNG bao giờ lộ ra schema của browser__type_sensitive gửi cho LLM — LLM chỉ thấy
tham số 'placeholder' (tên key), không thấy giá trị thật (đóng gói qua closure).
"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING
from tools.registry import ToolRegistry, Tool

if TYPE_CHECKING:
    from tools.browser.browser_tool import SyncBrowserTool


# Mỗi spec: name (tên tool namespaced), description + parameters (JSON schema gửi LLM),
# method (tên method trên SyncBrowserTool), defer_loading (tool ít dùng -> agent phải
# tool_search mới thấy).
BROWSER_TOOL_SPECS: list[dict] = [
    {
        "name": "browser__navigate",
        "description": "Mở 1 URL trong trình duyệt.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "new_tab": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
        "method": "navigate",
        "defer_loading": False,
    },
    {
        "name": "browser__get_state",
        "description": (
            "Xem các element tương tác được (link, button, input...) trên trang hiện tại, "
            "kèm chỉ số [index] để dùng cho browser__click/browser__type. "
            "LUÔN gọi tool này đầu tiên trước khi click/type, và gọi lại sau khi trang thay đổi."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "with_screenshot": {
                    "type": "boolean",
                    "default": False,
                    "description": "Chỉ bật nếu model đang dùng có vision (GPT-4o, Claude...). DeepSeek không có vision.",
                },
                "contains": {
                    "type": "string",
                    "description": (
                        "Chỉ hiện element có chữ khớp, ngăn cách bằng '|' (vd \"Xuất|Tải xuống\"). "
                        "[index] VẪN đúng vì chỉ ẩn dòng hiển thị, không đánh số lại. "
                        "Dùng khi ĐÃ BIẾT mình tìm nút nào: trang lớn có ~75 element mà "
                        "quá nửa là menu điều hướng lặp lại, lọc bớt thì rẻ hơn nhiều. "
                        "Chưa quen trang thì cứ gọi không kèm tham số này để xem đầy đủ."
                    ),
                },
            },
        },
        "method": "get_state",
        "defer_loading": False,
    },
    {
        "name": "browser__click",
        "description": "Click 1 element theo [index] lấy từ browser__get_state.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "coordinate_x": {"type": "integer"},
                "coordinate_y": {"type": "integer"},
            },
            "required": ["index"],
        },
        "method": "click",
        "defer_loading": False,
    },
    {
        "name": "browser__tiktok_creator_lookup",
        "description": (
            "TRA MỘT CREATOR TIKTOK AFFILIATE — CẢ LUỒNG TRONG MỘT LỜI GỌI. "
            "Tự làm hết: mở trang tìm creator, gõ handle, Enter, mở trang chi tiết, "
            "đọc số liệu thẳng từ API (giá trị GỐC, không phải chữ đã làm tròn trên "
            "giao diện). Trả về follower, GMV, số món bán ra, GPM, GMV/khách, tỷ lệ "
            "tương tác, hoa hồng, danh mục... \n"
            "DÙNG TOOL NÀY THAY VÌ tự navigate/type/click từng bước: 7 bước đó không có "
            "gì để bạn quyết định, làm thủ công tốn ~7 lượt gọi LLM cho cùng kết quả. "
            "Chỉ quay lại thao tác từng bước khi tool này báo giao diện đã đổi. \n"
            "Tool KHÔNG lấy bio/hotline/Zalo/badge (không có trong API) — kết quả sẽ "
            "nói rõ creator có công khai liên hệ hay không để bạn biết có cần "
            "browser__extract thêm hay không."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {"type": "string", "description": "Handle creator, vd 'nghiendecor.co.ltd'"},
                "timeout_seconds": {"type": "integer", "default": 60},
            },
            "required": ["handle"],
        },
        "method": "tiktok_creator_lookup",
        "defer_loading": False,
    },
    {
        "name": "browser__click_label",
        "description": (
            "Bấm element theo NHÃN HIỂN THỊ (vd \"Xuất\", \"Tải xuống\", \"Áp dụng\") — "
            "KHÔNG cần gọi browser__get_state trước. NHANH GẤP ĐÔI browser__click: tự quét "
            "trang và tra chỉ số bằng code thay vì bắt bạn đọc danh sách element. "
            "DÙNG TOOL NÀY khi đã biết chữ trên nút (skill có ghi, hoặc vừa thấy ở lượt trước). "
            "Chỉ dùng browser__click + [index] khi phải tự dò trang lạ hoặc nút không có chữ. "
            "Khớp chính xác trước, rồi mới khớp chứa; nhiều kết quả thì lấy nhãn ngắn nhất. "
            "Không tìm thấy sẽ liệt kê các nhãn đang có trên trang."
        ),
        "parameters": {
            "type": "object",
            "properties": {"label": {"type": "string", "description": "Chữ hiện trên nút/link"}},
            "required": ["label"],
        },
        "method": "click_label",
        "defer_loading": False,
    },
    {
        "name": "browser__type_label",
        "description": (
            "Gõ text vào ô nhập tìm theo NHÃN/placeholder (vd \"Tìm kiếm tên, sản phẩm\") — "
            "KHÔNG cần browser__get_state trước. Đặt submit=true để bấm Enter luôn sau khi gõ: "
            "gộp gõ + Enter vào MỘT lượt thay vì hai."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Placeholder hoặc nhãn của ô nhập"},
                "text": {"type": "string"},
                "submit": {"type": "boolean", "default": False,
                           "description": "true = bấm Enter ngay sau khi gõ"},
                "clear": {"type": "boolean", "default": True},
            },
            "required": ["label", "text"],
        },
        "method": "type_label",
        "defer_loading": False,
    },
    {
        "name": "browser__type",
        "description": ("Gõ text vào ô input theo [index] lấy từ browser__get_state. "
                        "Biết placeholder của ô thì dùng browser__type_label sẽ nhanh hơn. "
                        "submit=true để bấm Enter luôn, gộp 2 lượt thành 1."),
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "text": {"type": "string"},
                "clear": {"type": "boolean", "default": True, "description": "Xoá text cũ trước khi gõ"},
                "submit": {"type": "boolean", "default": False,
                           "description": "true = bấm Enter ngay sau khi gõ (đỡ 1 lượt gọi)"},
            },
            "required": ["index", "text"],
        },
        "method": "input_text",
        "defer_loading": False,
    },
    {
        # LƯU Ý kiến trúc phân tán: tool này KHÔNG chạy nguyên vẹn trên device.
        # Device chỉ chạy browser__page_markdown (lấy nội dung trang); nửa LLM
        # extraction chạy trên server (extract_from_markdown) — vì LLM key không
        # được nằm trên máy khách. CLI all-in-one thì method extract() ghép cả 2.
        "name": "browser__extract",
        "description": (
            "Trích xuất thông tin từ trang hiện tại bằng LLM (đọc nội dung trang đã chuyển "
            "sang markdown). Dùng khi cần lấy dữ liệu cụ thể (giá sản phẩm, danh sách kết quả...) "
            "thay vì tự đọc toàn bộ trang."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mô tả thông tin cần lấy"},
                "extract_links": {"type": "boolean", "default": False},
                "start_from_char": {"type": "integer", "default": 0, "description": "Tiếp tục đọc từ vị trí ký tự này nếu bị cắt"},
            },
            "required": ["query"],
        },
        "method": "extract",
        "defer_loading": False,
    },
    # --- Các tool ít dùng hơn -> defer_loading, agent tự tool_search khi cần ---
    {
        "name": "browser__search",
        "description": "Tìm kiếm trên web (DuckDuckGo/Google/Bing) thay vì mở URL cụ thể.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "engine": {"type": "string", "enum": ["duckduckgo", "google", "bing"], "default": "duckduckgo"},
            },
            "required": ["query"],
        },
        "method": "search",
        "defer_loading": True,
    },
    {
        "name": "browser__go_back",
        "description": "Quay lại trang trước đó trong lịch sử duyệt web.",
        "parameters": {"type": "object", "properties": {}},
        "method": "go_back",
        "defer_loading": True,
    },
    {
        "name": "browser__scroll",
        "description": "Cuộn trang lên/xuống theo số 'trang' (1.0 = 1 viewport height).",
        "parameters": {
            "type": "object",
            "properties": {
                "pages": {"type": "number", "default": 1.0},
                "direction": {"type": "string", "enum": ["down", "up"], "default": "down"},
            },
        },
        "method": "scroll",
        "defer_loading": False,  # thao tác duyệt web cơ bản -> luôn sẵn cho agent
    },
    {
        "name": "browser__press_key",
        "description": "Gửi 1 phím đặc biệt (Enter, Escape, Tab...) tới trang.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Vd: Enter, Escape, Tab"}},
            "required": ["key"],
        },
        "method": "press_key",
        "defer_loading": False,  # nhấn Enter sau khi gõ tìm kiếm là thao tác rất hay dùng
    },
    {
        "name": "browser__wait",
        "description": "Chờ N giây (tối đa 30s) — dùng khi trang đang tải/animate.",
        "parameters": {
            "type": "object",
            "properties": {"seconds": {"type": "integer", "default": 3}},
        },
        "method": "wait",
        "defer_loading": False,  # trang SPA tải chậm -> chờ là thao tác cơ bản
    },
    {
        # KHÔNG defer: đây là fallback quan trọng, agent phải luôn biết nó tồn tại
        # để gọi ngay khi get_state báo có captcha (agent không có vision).
        "name": "browser__wait_for_human",
        "description": (
            "Tạm dừng cho NGƯỜI DÙNG tự xử lý xác minh/CAPTCHA (vd captcha kéo của TikTok) "
            "trên cửa sổ trình duyệt đang hiện. Gọi tool này khi browser__get_state báo phát "
            "hiện captcha, hoặc khi trang không phản hồi đúng sau thao tác hợp lệ. TUYỆT ĐỐI "
            "KHÔNG tự click/kéo để giải captcha. Tool tự chờ tới khi xác minh xong rồi báo tiếp tục."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Lý do cần người xử lý (để hiển thị cho user)"},
                "timeout_seconds": {"type": "integer", "default": 90, "description": "Tối đa ~100s"},
            },
        },
        "method": "wait_for_human",
        "defer_loading": False,
    },
    {
        # KHÔNG defer: skill xuất đơn hàng phụ thuộc hẳn vào tool này. Click thường
        # cũng tải được file (đã có hook bắt download), nhưng agent sẽ không biết
        # file về chưa/ở đâu — tool này chờ tải xong rồi trả đường dẫn thật.
        "name": "browser__download_file",
        "description": (
            "Click 1 element [index] là nút/link TẢI FILE, rồi CHỜ file tải xong và trả về "
            "đường dẫn file đã lưu trên máy người dùng. Dùng cho nút Tải xuống/Download/Xuất "
            "của trang web. Nếu trang cần thời gian tạo file trước khi có nút tải (vd xuất đơn "
            "hàng TikTok Shop), hãy chờ nút tải xuất hiện rồi mới gọi tool này vào đúng nút đó."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "timeout_seconds": {"type": "integer", "default": 120, "description": "Tối đa ~110s"},
            },
            "required": ["index"],
        },
        "method": "download_file",
        "defer_loading": False,
    },
    {
        # Ghi tự động, agent không phải "bật" trước — lúc nhận ra cần xem thì
        # request đã bay qua rồi.
        "name": "browser__api_responses",
        "description": (
            "Xem các phản hồi API (JSON) mà trang web vừa nhận được. Dùng khi thao tác nào đó "
            "chạy NGẦM ở phía server và giao diện chưa cập nhật — ví dụ bấm 'Xuất' rồi phải chờ "
            "server tạo file: phản hồi API cho biết chính xác trạng thái và thường chứa sẵn link "
            "tải. Đáng tin hơn nhiều so với dò lại giao diện bằng browser__get_state."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url_contains": {
                    "type": "string",
                    "description": "Lọc theo một đoạn trong URL API, vd 'export_record' hoặc 'order/export'",
                },
                "max_results": {"type": "integer", "default": 3},
                "body_chars": {"type": "integer", "default": 1200, "description": "Số ký tự nội dung mỗi phản hồi"},
            },
        },
        "method": "api_responses",
        "defer_loading": False,
    },
    {
        "name": "browser__api_json",
        "description": (
            "Lấy ĐÚNG vài trường từ JSON mà trang vừa nhận, thay vì đọc cả trang. "
            "NHANH VÀ CHÍNH XÁC HƠN browser__extract cho SỐ LIỆU: extract phải nhờ LLM đọc "
            "chữ trên trang rồi chép lại, còn tool này lấy thẳng giá trị thô từ API — "
            "vd giao diện hiện '1,5K người theo dõi' nhưng JSON có đúng 1489. "
            "Chỉ những trường bạn xin mới vào context, không phải cả JSON. "
            "Tự gộp nhiều phản hồi cùng endpoint (trang hay chia dữ liệu làm nhiều lượt gọi). "
            "Chưa biết tên trường thì xem browser__api_responses trước."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url_contains": {
                    "type": "string",
                    "description": "Một đoạn trong URL API, vd 'marketplace/profile'",
                },
                "fields": {
                    "type": "string",
                    "description": (
                        "Các đường dẫn JSON ngăn bằng dấu phẩy, hỗ trợ chấm và chỉ số mảng. "
                        "Vd: 'creator_profile.handle.value, creator_profile.gpm.value.format, "
                        "creator_profile.industry_groups.value[0].name'"
                    ),
                },
                "max_responses": {"type": "integer", "default": 8},
            },
            "required": ["url_contains", "fields"],
        },
        "method": "api_json",
        "defer_loading": False,
    },
    {
        "name": "browser__list_downloads",
        "description": "Liệt kê các file đã tải về máy người dùng trong phiên làm việc này (đường dẫn + dung lượng).",
        "parameters": {"type": "object", "properties": {}},
        "method": "list_downloads",
        "defer_loading": True,
    },
    {
        "name": "browser__type_sensitive",
        "description": (
            "Gõ 1 giá trị NHẠY CẢM (mật khẩu, API key...) vào ô input theo [index]. "
            "Chỉ truyền 'placeholder' (tên key, vd 'site_password') — KHÔNG BAO GIỜ truyền giá trị "
            "thật, vì bạn (LLM) không được phép biết giá trị thật. Giá trị được nạp sẵn từ "
            "biến môi trường BROWSER_SECRET_<PLACEHOLDER>."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 1},
                "placeholder": {"type": "string", "description": "Tên key trong sensitive data, vd 'site_password'"},
            },
            "required": ["index", "placeholder"],
        },
        "method": "type_sensitive",
        "defer_loading": True,
    },
]

# Tool NỘI BỘ của kiến trúc phân tán — KHÔNG cho agent thấy (không nằm trong
# BROWSER_TOOL_SPECS). Server gọi nó qua RPC để lấy nội dung trang, rồi tự chạy
# LLM extraction (extract_from_markdown) — xem PLAN.md 4.6.
PAGE_MARKDOWN_SPEC: dict = {
    "name": "browser__page_markdown",
    "description": "Nội bộ: trả JSON {url, markdown, truncated, next_start} của trang hiện tại.",
    "parameters": {
        "type": "object",
        "properties": {"start_from_char": {"type": "integer", "default": 0}},
    },
    "method": "page_markdown",
    "defer_loading": True,
}


def load_sensitive_data_from_env(prefix: str = "BROWSER_SECRET_") -> dict[str, str]:
    data = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            placeholder = key[len(prefix):].lower()
            data[placeholder] = value
    return data


def build_browser_registry(
    sync_browser: "SyncBrowserTool", sensitive_data: dict[str, str] | None = None
) -> ToolRegistry:
    """Bind mỗi spec vào method local của SyncBrowserTool — dùng cho CLI all-in-one
    và companion app (nơi browser chạy cùng tiến trình)."""
    sensitive_data = sensitive_data or {}
    registry = ToolRegistry()
    for spec in BROWSER_TOOL_SPECS:
        method = getattr(sync_browser, spec["method"])
        if spec["name"] == "browser__type_sensitive":
            # Closure đóng gói sensitive_data — LLM chỉ truyền placeholder, không thấy giá trị
            handler = lambda index, placeholder, _m=method: _m(index, placeholder, sensitive_data)
        else:
            handler = method
        registry.register(
            Tool(
                name=spec["name"],
                description=spec["description"],
                parameters=spec["parameters"],
                handler=handler,
                defer_loading=spec["defer_loading"],
            )
        )
    return registry
