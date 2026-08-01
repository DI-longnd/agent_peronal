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

## Quy trình
Chiến lược: làm như MỘT NGƯỜI THẬT — TUẦN TỰ từng tên, KHÔNG song song (song song =
nhiều search dồn dập → TikTok bật captcha ngay + vi phạm ràng buộc 1 máy/1 run).

Xử lý TỪNG TÊN MỘT — mỗi tên dispatch browser-agent 1 lần với task ghi rõ các bước
dưới đây. Browser giữ nguyên phiên qua các tên (không tắt/mở lại). Mỗi tên mất
~1-2 phút. Danh sách quá **8 tên** thì làm **8 tên đầu**, gom kết quả, rồi nói user
gửi phần còn lại ở lượt sau.

(Trần này bám theo `RUN_TIMEOUT_SECONDS`, mặc định **600s** — xem server/config.py.
Bản trước ghi 300s và tự giới hạn 5 tên: con số đó sai, đang bỏ phí một nửa năng lực.)
Nếu 1 tên gặp captcha, browser-agent gọi `browser__wait_for_human` cho tên đó rồi
đi tiếp — KHÔNG bỏ cả danh sách. Tên không tìm thấy → ghi `N/A` + ghi chú, làm tiếp
tên sau.

Task giao cho browser-agent cho tên `<handle>` (giao diện có thể là tiếng Việt
HOẶC tiếng Anh — trang load tiếng Anh trước rồi đổi sang tiếng Việt; nhãn tương
ứng: "Khám phá các nhà sáng tạo"="Discover creators", "Tìm nhà sáng tạo"="Find
creators", "Mời"="Invite"):

1. `browser__navigate` tới `https://affiliate.tiktok.com/`. `browser__get_state`.
   Nếu thấy form đăng nhập thì dừng và báo lại (xem Điều kiện tiên quyết).
2. Ở sidebar trái, click mục "Khám phá các nhà sáng tạo" / "Discover creators"
   → trang tìm creator (có ô tìm kiếm "Tìm nhà sáng tạo"/"Find creators").
   `browser__get_state` lại.
3. `browser__type` `<handle>` vào ô tìm kiếm (ô input có placeholder "Tìm kiếm
   tên, sản phẩm..." / "Search creators").
4. BẮT BUỘC `browser__press_key` với key `Enter` ngay sau khi gõ — để chạy tìm
   kiếm VÀ đóng dropdown gợi ý. KHÔNG click vào các mục gợi ý trong dropdown
   (chúng KHÔNG mở được trang chi tiết, chỉ làm lạc hướng). `browser__wait` 2-3s.
5. `browser__scroll` xuống 1 chút để khu "Kết quả tìm kiếm" vào tầm nhìn, rồi
   `browser__get_state`. Tìm element là HÀNG KẾT QUẢ của creator — đó là element
   có text gồm cả handle + tên + chỉ số (vd chứa "699,5K", "Trang phục...", GMV).
   Handle phải KHỚP CHÍNH XÁC `<handle>` (cẩn thận handle gần giống, vd
   `thanhdongian.dtt` khác `thanhdongian.dtt_Lý Hồng Ngọc`).
6. `browser__click` vào ĐÚNG hàng kết quả đó (element có chỉ số follower/GMV, KHÔNG
   phải mục dropdown, KHÔNG phải nút "Mời"/"Invite"). Trang chi tiết sẽ mở ở TAB
   MỚI — tool tự chuyển sang tab đó. `browser__wait` 2s rồi `browser__get_state`
   để xác nhận đã ở trang chi tiết (URL chứa `/creator/detail`, có các tab
   "Doanh số/Video/Người theo dõi...").
7. Ở trang chi tiết, gọi `browser__extract` **ĐÚNG 1 LẦN** với query gộp lấy tất
   cả field chính: "Tên hiển thị, handle, số người theo dõi, danh mục hàng, điểm
   đánh giá, badge (vd Bán chạy nhất Top 5), bio/giới thiệu (ĐẶC BIỆT Hotline/SĐT
   và link liên hệ Zalo/email nếu có), khối Doanh số (GMV, Số món bán ra, GPM, GMV
   từ mỗi khách hàng), và chỉ số Video (lượt xem video trung bình, tỷ lệ tương tác)".
   - **GIỚI HẠN CỨNG: ĐÚNG 1 lần `browser__extract` cho mỗi creator.** Tab mặc định
     "Doanh số" đã hiển thị đủ mọi khối cần lấy. KHÔNG bấm sang tab Video / Xu hướng /
     Nhà sáng tạo tương tự. KHÔNG extract lần 2.
   - Field nào không có trong kết quả extract → ghi `N/A`, **không cố bấm thêm để tìm**.
   - Vì sao là giới hạn cứng, không phải lời khuyên: đo 01-08-2026, một lượt chạy đi
     khắp các tab dùng **8 lần extract + 11 lần click**, chạy hết số bước cho phép mà
     vẫn chưa trả được kết quả — trong khi lượt làm đúng chỉ cần **1 extract**. Mỗi
     lần extract là một lượt LLM đọc cả trang, và mỗi cú click là một cơ hội dính
     captcha. Dữ liệu thêm ở các tab kia KHÔNG có trong bảng kết quả, lấy về cũng bỏ.
8. Trả về kết quả có cấu trúc cho tên này (từ 1 lần extract ở trên).

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
