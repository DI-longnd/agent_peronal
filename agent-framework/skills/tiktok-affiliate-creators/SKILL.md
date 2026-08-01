---
name: tiktok-affiliate-creators
description: >
  Tra cứu thông tin nhà sáng tạo (creator/KOC) trên TikTok Affiliate — Trung tâm
  liên kết TikTok Shop (affiliate.tiktok.com). Dùng khi task nhắc tới TikTok,
  affiliate, nhà sáng tạo, creator, KOC, tìm/tra thông tin người bán hàng livestream,
  hoặc cần danh sách liên hệ (Zalo/email/hotline) + chỉ số bán hàng của creator.
---

# TikTok Affiliate — Tra cứu nhà sáng tạo

Quy trình dưới đây đã đủ. Chỉ khi phải đi ra ngoài nó thì mới
`read_skill("tiktok-shop-map")` — ở đó có bản đồ cả hai trang TikTok Shop và quy ước
đọc số (dấu phẩy là dấu THẬP PHÂN: `183,13K` = 183.130).

## Khi nào dùng skill này
User đưa MỘT DANH SÁCH TÊN/HANDLE creator (vd `thanhdongian.dtt`) và cần thông tin
chi tiết của từng người: liên hệ, follower, doanh số, chỉ số video. KHÔNG dùng cho
việc gửi lời mời hợp tác hàng loạt (chưa hỗ trợ — không được bấm nút "Mời").

## Điều kiện tiên quyết
Trang affiliate.tiktok.com yêu cầu đăng nhập tài khoản TikTok Shop (seller).
Nếu browser-agent báo gặp trang đăng nhập → DỪNG, trả lời user: "Máy của bạn chưa
đăng nhập TikTok Shop — mở file Dang-nhap-trang-web.bat trong thư mục app, dán
https://affiliate.tiktok.com/ vào, đăng nhập xong chạy lại yêu cầu này." Không
được tự thử điền tài khoản/mật khẩu.

## Quy trình — ĐƯỜNG NHANH trước

Cho MỖI handle, gọi **một tool duy nhất**:

```
browser__tiktok_creator_lookup(handle="<handle>")
```

Nó tự làm cả 7 bước (mở trang tìm → gõ handle → Enter → mở trang chi tiết → đọc số
liệu từ API) và trả về sẵn: `handle`, `ten_hien_thi`, `follower`, `so_mon_ban_ra`,
`gmv`, `gpm`, `gmv_moi_khach_hang`, `ty_le_tuong_tac_video`, `hoa_hong_pho_bien`,
`so_nhan_hang_da_hop_tac`, `khoang_gia_san_pham`, `danh_muc_chinh`, và
`co_lien_he_cong_khai`.

Đo 01-08-2026: **33,6 giây cho một creator, đúng MỘT lượt gọi LLM**. Làm thủ công
7 bước tốn ~7 lượt gọi LLM cho cùng kết quả, vì cả 7 bước đó không có gì để quyết định.

Sau khi có kết quả:
- `co_lien_he_cong_khai = false` → zalo/email/hotline ghi `N/A`, **xong, đi tên tiếp theo**
- `co_lien_he_cong_khai = true` hoặc cần badge/điểm đánh giá → `browser__extract`
  **ĐÚNG 1 LẦN**: "bio, hotline/SĐT, Zalo, email, badge, điểm đánh giá"
- Tool báo **captcha** → `browser__wait_for_human`, rồi gọi lại chính tool đó
- Tool báo **giao diện đã đổi** / không tìm thấy ô tìm kiếm → chuyển sang đường thủ
  công bên dưới

## Đường thủ công — chỉ dùng khi đường nhanh báo hỏng
Chiến lược: làm như MỘT NGƯỜI THẬT — TUẦN TỰ từng tên, KHÔNG song song (song song =
nhiều search dồn dập → TikTok bật captcha ngay + vi phạm ràng buộc 1 máy/1 run).

Xử lý TỪNG TÊN MỘT — mỗi tên dispatch browser-agent 1 lần. Browser giữ nguyên phiên
qua các tên (không tắt/mở lại). Mỗi tên mất ~1-2 phút. Danh sách quá **8 tên** thì làm
**8 tên đầu**, gom kết quả, rồi nói user gửi phần còn lại ở lượt sau.

> **MỖI TÊN LÀ MỘT LƯỢT GIAO VIỆC SẠCH — `resume=false`.**
> Đừng dùng `resume=true` để sang tên tiếp theo. Đo 01-08-2026: tra 3 tên bằng
> resume, tới tên thứ 3 subagent nhìn thấy cả 3 tên trong context, tưởng mình phải
> làm cả danh sách nên **quay lại tra lại tên số 1** rồi bắt đầu thêm một tên nữa —
> 71 bước thay vì 40, hết số bước mà chưa trả được kết quả.
> `resume=true` chỉ dùng khi CÙNG MỘT TÊN bị dở dang giữa chừng.
>
> Context sạch không tốn thêm gì đáng kể: browser vẫn đang mở đúng trang, subagent
> chỉ mất 1-2 bước điều hướng lại.

(Trần này bám theo `RUN_TIMEOUT_SECONDS`, mặc định **600s** — xem server/config.py.
Bản trước ghi 300s và tự giới hạn 5 tên: con số đó sai, đang bỏ phí một nửa năng lực.)
Nếu 1 tên gặp captcha, browser-agent gọi `browser__wait_for_human` cho tên đó rồi
đi tiếp — KHÔNG bỏ cả danh sách. Tên không tìm thấy → ghi `N/A` + ghi chú, làm tiếp
tên sau.

Task giao cho browser-agent cho tên `<handle>` (giao diện có thể là tiếng Việt
HOẶC tiếng Anh — trang load tiếng Anh trước rồi đổi sang tiếng Việt; nhãn tương
ứng: "Khám phá các nhà sáng tạo"="Discover creators", "Tìm nhà sáng tạo"="Find
creators", "Mời"="Invite"):

1. `browser__navigate` **THẲNG tới trang tìm creator** (đừng qua trang chủ):
   ```
   https://affiliate.tiktok.com/connection/creator?shop_region=VN
   ```
   TikTok tự thêm `shop_id` từ phiên đăng nhập, nên URL này đúng cho mọi khách.
   Rồi `browser__get_state`. Thấy form đăng nhập thì dừng, báo lại (xem Điều kiện
   tiên quyết).

   **ĐỪNG vào `affiliate.tiktok.com/` rồi bấm menu "Khám phá các nhà sáng tạo".**
   Đo 01-08-2026: đường vòng đó tốn 6 bước (navigate trang chủ → get_state →
   get_state lần nữa → click menu → wait → get_state) cho việc 2 bước làm xong,
   và trang chủ là SPA nặng phải tải lại toàn bộ.
2. *(bỏ — bước 1 đã tới thẳng nơi cần)*
3. **Gõ và tìm trong MỘT lượt** — không cần `get_state`, không cần `press_key` riêng:

   ```
   browser__type_label(label="Tìm kiếm tên, sản phẩm", text="<handle>", submit=true)
   ```

   `submit=true` bấm Enter luôn: vừa chạy tìm kiếm, vừa đóng dropdown gợi ý.
   KHÔNG click vào mục trong dropdown — chúng không mở được trang chi tiết.
4. *(bỏ — `submit=true` ở bước 3 đã Enter)*
5. `browser__wait` 3s.
6. **Mở trang chi tiết bằng nhãn:**

   ```
   browser__click_label(label="<handle>")
   ```

   Hàng kết quả có text gồm handle + tên + chỉ số, nên khớp theo handle là trúng.
   Tool ưu tiên nhãn NGẮN NHẤT nên tự tránh được handle gần giống (`thanhdongian.dtt`
   sẽ không dính vào `thanhdongian.dtt_Lý Hồng Ngọc`). Nút "Mời" bị chặn ở tầng tool.

   `browser__wait` 3s. Trang chi tiết mở ở TAB MỚI, tool tự chuyển sang.

   **Không cần `get_state` để xác nhận** — bước 7 sẽ trả về `handle`, đối chiếu ở đó.
7. **SỐ LIỆU: lấy từ API, KHÔNG dùng extract.** Trang đã tự gọi JSON có sẵn mọi con
   số ở dạng THÔ. Gọi `browser__api_json` một lần:

   ```
   url_contains: marketplace/profile
   fields: creator_profile.handle.value, creator_profile.nickname.value,
           creator_profile.follower_cnt.value, creator_profile.contact_info_available.value,
           creator_profile.units_sold.value, creator_profile.med_gmv_revenue.value.format,
           creator_profile.gpm.value.format, creator_profile.avg_revenue_per_buyer.value.format,
           creator_profile.video_engagement.value, creator_profile.med_gmv_revenue_range.value,
           creator_profile.industry_groups.value[0].name
   ```

   Vì sao không để `extract` đọc số: `extract` chuyển cả trang sang chữ rồi nhờ LLM
   đọc lại — con số phải đi qua khâu "nhìn chữ rồi chép". API cho giá trị thô.
   Đo 01-08-2026: trang hiện **1,5K** người theo dõi, JSON có đúng **1489**. Tool
   này mất **0,00s và không tốn lượt gọi LLM nào**.

   `contact_info_available = false` nghĩa là creator **không công khai liên hệ** —
   ghi `N/A` cho zalo/email/hotline và ĐI TIẾP, đừng đi tìm.

   Trường nào báo KHÔNG tìm thấy → `browser__wait` 3s rồi gọi lại 1 lần (trang có
   thể chưa gọi xong API). Vẫn không có thì ghi `N/A`.

   **ĐỐI CHIẾU `handle` trả về với handle được yêu cầu.** Lệch nghĩa là bước 6 đã mở
   nhầm creator — quay lại bước 1 tìm lại, ĐỪNG báo cáo dữ liệu của người khác.

8. **CHỮ: `browser__extract` ĐÚNG 1 LẦN**, chỉ hỏi những gì API không có:
   "Điểm đánh giá, badge (vd 'Bán chạy nhất Top 5'), bio/giới thiệu của creator —
   ĐẶC BIỆT Hotline/SĐT và link Zalo/email nếu bio có ghi."

   Bỏ hẳn bước này khi `contact_info_available = false` **và** không cần badge.

   **SAU `extract` LÀ DỪNG.** Không scroll, không `get_state`, không tìm thêm.
   `extract` đọc TOÀN BỘ nội dung trang (không chỉ phần đang hiển thị) — cuộn thêm
   không lộ ra dữ liệu mới. Đo 01-08-2026: sau khi extract đã đủ, agent còn scroll
   xuống → get_state → scroll lên → get_state → scroll lên tìm Zalo: **5 bước, không
   ra thêm gì**.
   - **GIỚI HẠN CỨNG: ĐÚNG 1 lần `browser__extract` cho mỗi creator.** Tab mặc định
     "Doanh số" đã hiển thị đủ mọi khối cần lấy. KHÔNG bấm sang tab Video / Xu hướng /
     Nhà sáng tạo tương tự. KHÔNG extract lần 2.
   - Field nào không có trong kết quả extract → ghi `N/A`, **không cố bấm thêm để tìm**.
   - Vì sao là giới hạn cứng, không phải lời khuyên: đo 01-08-2026, một lượt chạy đi
     khắp các tab dùng **8 lần extract + 11 lần click**, chạy hết số bước cho phép mà
     vẫn chưa trả được kết quả — trong khi lượt làm đúng chỉ cần **1 extract**. Mỗi
     lần extract là một lượt LLM đọc cả trang, và mỗi cú click là một cơ hội dính
     captcha. Dữ liệu thêm ở các tab kia KHÔNG có trong bảng kết quả, lấy về cũng bỏ.
9. Trả về kết quả có cấu trúc cho tên này, ghép **số liệu từ bước 7** với **chữ từ
   bước 8**. Ưu tiên con số của API khi hai nguồn lệch nhau — API là giá trị gốc,
   chữ trên trang chỉ là bản đã làm tròn để hiển thị.

Main agent gom kết quả các tên rồi báo cáo theo Output format.

## Gotchas
- Handle phải khớp chính xác từng ký tự — trên trang có nhiều tài khoản tên gần
  giống nhau (kể cả cùng ảnh đại diện).
- Creator ít hoạt động có thể hiện "Không có video", GMV "0-50Kđ"... — ghi nguyên
  văn, đừng bỏ qua và đừng suy diễn thành 0.
- Giữ NGUYÊN VĂN định dạng số của trang (`1Mđ+`, `183,13K`, `0,3%`) — không tự quy
  đổi, khách đối chiếu với giao diện họ quen nhìn.
- Hotline/SĐT nằm trong bio dạng text tự do — chỉ lấy khi thật sự có, không bịa.
- Icon Zalo/email cạnh tên là link — cần href thật, không phải chữ "Zalo".
- TUYỆT ĐỐI không bấm "Mời", "Mời hàng loạt" hay checkbox chọn creator — chỉ đọc.
- Trang là SPA load chậm: sau mỗi navigate/click dùng `browser__wait` 1-2s rồi mới
  `browser__get_state` nếu trang chưa sẵn sàng.
- CAPTCHA KÉO: TikTok hay bật captcha kéo (slider) ngẫu nhiên khi tìm kiếm. Không tự
  giải — gọi `browser__wait_for_human` để khách tự kéo trên cửa sổ Chrome rồi tiếp tục.
  Gặp captcha KHÁC với gặp trang đăng nhập: chỉ báo "chưa đăng nhập" khi thật sự thấy
  form đăng nhập, đừng nhầm captcha thành lỗi đăng nhập.

## Output format
Báo cáo 2 phần:
1. Bảng markdown tổng hợp (mỗi creator 1 dòng) để đọc nhanh trên web.
2. Khối CSV trong code block để khách copy dán vào Excel / lưu thành .csv — đúng
   thứ tự cột:

```csv
handle,ten_hien_thi,follower,danh_muc,diem_danh_gia,badge,zalo,email,hotline,gmv,so_mon_ban_ra,gpm,gmv_moi_khach_hang,luot_xem_video_tb,ty_le_tuong_tac,ghi_chu
```

Ô nào không có dữ liệu ghi `N/A`. Cột `ghi_chu` dành cho bất thường (vd "handle
không tìm thấy", "trang chi tiết không mở được").

### BẮT BUỘC: bọc dấu ngoặc kép quanh MỌI ô chứa dấu phẩy

Số của TikTok dùng **dấu phẩy làm dấu thập phân** (`699,9K`, `0,29%`, `145,22K`) — mà
dấu phẩy cũng chính là dấu phân cách cột của CSV. Không bọc thì mỗi con số tự tách
thành hai cột.

Đo lượt chạy thật 01-08-2026: header 16 cột, dòng dữ liệu ra **22 trường — lệch 6 cột**.
Dán vào Excel là sai toàn bộ mà **không có dấu hiệu nào báo**, khách cứ thế dùng.

SAI:
```
thanhdongian.dtt,Thành Đơn Giản,699,9K,Trang phục nam,1.03,...
```
ĐÚNG:
```
thanhdongian.dtt,Thành Đơn Giản,"699,9K","Trang phục nam & Đồ lót",1.03,...
```

Quy tắc: ô nào chứa `,` hoặc `"` thì bọc trong `"…"` (dấu `"` bên trong nhân đôi thành
`""`). An toàn nhất là **bọc hết mọi ô có số**. Trước khi trả lời, **đếm lại số dấu
phẩy ngăn cột ở dòng dữ liệu phải bằng đúng dòng header** — lệch thì sửa, đừng trả ra.
