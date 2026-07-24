---
name: tiktok-affiliate-creators
description: >
  Tra cứu thông tin nhà sáng tạo (creator/KOC) trên TikTok Affiliate — Trung tâm
  liên kết TikTok Shop (affiliate.tiktok.com). Dùng khi task nhắc tới TikTok,
  affiliate, nhà sáng tạo, creator, KOC, tìm/tra thông tin người bán hàng livestream,
  hoặc cần danh sách liên hệ (Zalo/email/hotline) + chỉ số bán hàng của creator.
---

# TikTok Affiliate — Tra cứu nhà sáng tạo

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
~1-2 phút. Danh sách quá **5 tên** thì làm **5 tên đầu**, gom kết quả, rồi nói user
gửi phần còn lại ở lượt sau (tránh vượt timeout run 300s do đã có delay giống người).
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
7. Ở trang chi tiết, `browser__extract` với query: "Tên hiển thị, handle, số người
   theo dõi, danh mục hàng, điểm đánh giá và số đánh giá, badge (vd Bán chạy nhất
   Top 5), toàn bộ nội dung bio/giới thiệu (ĐẶC BIỆT số điện thoại/Hotline CSKH
   nếu có), các link/thông tin liên hệ Zalo/email, và khối Doanh số: GMV, Số món
   bán ra, GPM, GMV từ mỗi khách hàng".
8. Trả về kết quả có cấu trúc cho tên này.

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
