"""Cả luồng tra một creator TikTok Affiliate gói trong MỘT lời gọi tool.

VÌ SAO CÓ FILE NÀY
Đo lượt chạy 01-08-2026: tra 3 creator mất 10,8 phút, trong đó 82% là thời gian LLM
suy nghĩ, chỉ 15% là trình duyệt làm việc thật. Lý do: kiến trúc bắt LLM ra quyết
định ở MỌI bước, kể cả bảy bước không có gì để quyết định (URL cố định, ô tìm kiếm
cố định, danh sách trường JSON cố định). Mỗi bước tốn trọn một vòng gọi LLM ~6 giây.

Đây là "mức 1" trong thang tự chủ của Browserbase: chương trình điều khiển luồng,
LLM chỉ vào cuộc ở chỗ thật sự cần nghĩ. Đúng loại việc cho quy trình đã biết trước.
LOOP (arXiv 2605.14237) đo được cách này nhanh hơn 10-50 lần ở phần thay thế được.

ĐÁNH ĐỔI PHẢI BIẾT
Luồng cứng thì TikTok đổi giao diện là gãy. Nên: (1) mọi bước đều báo lỗi nói rõ
gãy ở đâu, (2) skill tiktok-affiliate-creators giữ nguyên bản thao tác từng bước làm
đường lui, agent tự chuyển sang đó khi tool này báo hỏng.
"""

from __future__ import annotations

import asyncio
import json
import time

SEARCH_URL = "https://affiliate.tiktok.com/connection/creator?shop_region=VN"
# Hai thứ tiếng: trang tải giao diện tiếng Anh trước rồi mới đổi sang tiếng Việt.
# Đo 01-08-2026: giây thứ 3 còn "Search creators", giây thứ 6 mới thành tiếng Việt.
# Khớp cả hai thì không phụ thuộc vào việc chờ bao lâu.
SEARCH_BOX = "Tìm kiếm tên, sản phẩm|Search creators|Tìm kiếm|Search"
API_MATCH = "marketplace/profile"

# Trường lấy từ JSON của trang. Đây là DỮ LIỆU, không phải logic — TikTok đổi tên
# trường thì sửa đúng danh sách này.
FIELDS = [
    "creator_profile.handle.value",
    "creator_profile.nickname.value",
    "creator_profile.follower_cnt.value",
    "creator_profile.contact_info_available.value",
    "creator_profile.units_sold.value",
    "creator_profile.med_gmv_revenue.value.format",
    "creator_profile.med_gmv_revenue_range.value",
    "creator_profile.gpm.value.format",
    "creator_profile.avg_revenue_per_buyer.value.format",
    "creator_profile.video_engagement.value",
    "creator_profile.med_commission_rate.value",
    "creator_profile.collaborated_brands_num.value",
    "creator_profile.product_price_range.value",
    "creator_profile.industry_groups.value[0].name",
]

_SHORT = {  # tên ngắn cho agent đọc, khỏi phải nhìn đường dẫn JSON dài
    "handle": "creator_profile.handle.value",
    "ten_hien_thi": "creator_profile.nickname.value",
    "follower": "creator_profile.follower_cnt.value",
    "co_lien_he_cong_khai": "creator_profile.contact_info_available.value",
    "so_mon_ban_ra": "creator_profile.units_sold.value",
    "gmv": "creator_profile.med_gmv_revenue.value.format",
    "gmv_khoang": "creator_profile.med_gmv_revenue_range.value",
    "gpm": "creator_profile.gpm.value.format",
    "gmv_moi_khach_hang": "creator_profile.avg_revenue_per_buyer.value.format",
    "ty_le_tuong_tac_video": "creator_profile.video_engagement.value",
    "hoa_hong_pho_bien": "creator_profile.med_commission_rate.value",
    "so_nhan_hang_da_hop_tac": "creator_profile.collaborated_brands_num.value",
    "khoang_gia_san_pham": "creator_profile.product_price_range.value",
    "danh_muc_chinh": "creator_profile.industry_groups.value[0].name",
}


def _parse(api_text: str) -> dict:
    """Đọc lại kết quả dạng chữ của api_json thành dict."""
    out = {}
    for line in api_text.splitlines():
        line = line.strip()
        if not line.startswith("creator_profile.") or " = " not in line:
            continue
        path, _, raw = line.partition(" = ")
        try:
            out[path] = json.loads(raw)
        except Exception:
            out[path] = raw
    return out


async def creator_lookup(bt, handle: str, timeout_seconds: int = 60) -> str:
    """Tìm creator theo handle, mở trang chi tiết, trả về số liệu đọc từ API.

    `bt` là BrowserTool (bản async). Trả về chuỗi cho agent đọc.
    """
    handle = (handle or "").strip().lstrip("@")
    if not handle:
        return "Chưa nêu handle cần tra."

    t0 = time.time()
    trace = []

    def left() -> float:
        return timeout_seconds - (time.time() - t0)

    async def captcha_stop(where: str) -> str | None:
        hint = await bt._captcha_hint()
        if hint:
            return (f"DỪNG ở bước '{where}': trang đang bị captcha/xác minh chặn. "
                    "Gọi browser__wait_for_human để người dùng tự kéo, rồi gọi lại "
                    f"tiktok__creator_lookup('{handle}'). KHÔNG tự giải captcha.")
        return None

    # --- 1. tới trang tìm creator ---------------------------------------------
    try:
        await bt.navigate(SEARCH_URL)
    except Exception as e:
        return f"Không mở được trang tìm creator ({type(e).__name__}: {e}). Thử lại sau."
    await asyncio.sleep(4)
    trace.append("mở trang tìm creator")

    stop = await captcha_stop("mở trang tìm creator")
    if stop:
        return stop

    state = await bt.get_state()
    if any(k in state.lower() for k in ("đăng nhập tiktok", "log in to tiktok", "sign in")):
        return ("Máy chưa đăng nhập TikTok Shop — trang hiện form đăng nhập. Báo người "
                "dùng mở Dang-nhap-trang-web.bat, dán https://affiliate.tiktok.com/ vào "
                "rồi đăng nhập, xong chạy lại. KHÔNG tự điền tài khoản/mật khẩu.")

    # --- 2. gõ handle + Enter --------------------------------------------------
    # Thử vài lần: ô tìm kiếm có thể chưa render, hoặc nhãn còn đang là tiếng Anh.
    typed = ""
    for _ in range(3):
        typed = await bt.type_label(SEARCH_BOX, handle, submit=True)
        if "Không thấy element" not in typed:
            break
        if left() < 8:
            break
        await asyncio.sleep(3)
    if "Không thấy element" in typed:
        return (f"Không tìm thấy ô tìm kiếm — giao diện TikTok có thể đã đổi. "
                f"Làm thủ công theo skill tiktok-affiliate-creators.\n{typed}")
    trace.append("gõ handle + Enter")
    await asyncio.sleep(3.5)

    stop = await captcha_stop("sau khi tìm kiếm")
    if stop:
        return stop

    # --- 3. mở trang chi tiết --------------------------------------------------
    # Kết quả tìm kiếm về không đồng bộ. Đo 01-08-2026: 3,5s đủ cho creator này
    # nhưng không đủ cho creator khác — lúc đó trang vẫn đang hiện danh sách gợi ý
    # mặc định, và tool kết luận nhầm là "không tìm thấy". Chờ thêm rồi thử lại.
    clicked = ""
    for attempt in range(3):
        clicked = await bt.click_label(handle)
        if "Clicked" in clicked or "TỪ CHỐI" in clicked:
            break
        if left() < 8:
            break
        await asyncio.sleep(3.5)
        if await bt._captcha_hint():
            return (f"DỪNG: captcha xuất hiện khi đang chờ kết quả tìm '{handle}'. "
                    "Gọi browser__wait_for_human rồi chạy lại tool này.")
    # Bất cứ kết quả nào KHÔNG phải "Clicked" đều là thất bại. Trước đây chỉ bắt
    # "Không thấy element" và "TỪ CHỐI", nên khi guard chặn click (thông báo
    # "KHÔNG bấm — trang đã thay đổi") luồng vẫn chạy tiếp và báo lỗi sai chỗ.
    if "Clicked" not in clicked:
        if "Không thấy element" in clicked:
            return (f"Tìm '{handle}' không ra kết quả nào khớp. Kiểm tra chính tả, hoặc "
                    f"creator không có trong Trung tâm liên kết.\n{clicked}")
        return (f"Không mở được trang chi tiết của '{handle}'. Làm thủ công theo skill "
                f"tiktok-affiliate-creators.\n{clicked}")
    trace.append("mở trang chi tiết")
    await asyncio.sleep(4)

    stop = await captcha_stop("mở trang chi tiết")
    if stop:
        return stop

    # --- 4. đọc số liệu từ API -------------------------------------------------
    # Trang gọi API theo nhiều lượt, lượt số liệu thường tới sau cùng. Chờ và hỏi
    # lại tối đa 3 vòng thay vì kết luận "không có".
    data = {}
    for attempt in range(3):
        data = _parse(bt.api_json(API_MATCH, ", ".join(FIELDS)))
        if _SHORT["gmv"] in data or _SHORT["so_mon_ban_ra"] in data:
            break
        if left() < 6:
            break
        await asyncio.sleep(3)
    trace.append(f"đọc API ({attempt + 1} vòng)")

    if not data:
        return ("Đã mở được trang chi tiết nhưng KHÔNG đọc được API số liệu "
                f"('{API_MATCH}'). TikTok có thể đã đổi endpoint. Thử "
                "browser__api_responses để xem trang gọi những API nào, hoặc dùng "
                "browser__extract đọc trang như cách cũ.")

    got_handle = str(data.get(_SHORT["handle"], "")).strip()
    if got_handle and got_handle.lower() != handle.lower():
        return (f"MỞ NHẦM CREATOR: yêu cầu '{handle}' nhưng trang chi tiết là "
                f"'{got_handle}'. Không dùng dữ liệu này. Tìm lại thủ công theo skill.")

    # --- 5. trả kết quả gọn ----------------------------------------------------
    lines = [f"Tra xong '{handle}' trong {time.time() - t0:.1f}s "
             f"({' → '.join(trace)}). Số liệu đọc thẳng từ API, là giá trị gốc:"]
    for short, path in _SHORT.items():
        if path in data:
            lines.append(f"  {short} = {json.dumps(data[path], ensure_ascii=False)}")
    missing = [s for s, p in _SHORT.items() if p not in data]
    if missing:
        lines.append(f"  (không có: {', '.join(missing)} — ghi N/A)")

    if data.get(_SHORT["co_lien_he_cong_khai"]) is False:
        lines.append("Creator KHÔNG công khai liên hệ → zalo/email/hotline ghi N/A, "
                     "ĐỪNG đi tìm thêm.")
    else:
        lines.append("Có thể có liên hệ công khai → gọi browser__extract MỘT LẦN hỏi "
                     "'bio, hotline/SĐT, Zalo, email, badge, điểm đánh giá' nếu cần.")
    return "\n".join(lines)
