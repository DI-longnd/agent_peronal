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
Xử lý TỪNG TÊN MỘT — mỗi tên dispatch browser-agent 1 lần với task ghi rõ các bước
dưới đây (mỗi tên mất ~1-2 phút; danh sách dài quá 6-7 tên thì làm 6-7 tên đầu và
nói user gửi phần còn lại ở lượt sau, để không vượt timeout của run).

Task giao cho browser-agent cho tên `<handle>` (giao diện tiếng Việt):
1. `browser__navigate` tới `https://affiliate.tiktok.com/` — nếu thấy form đăng
   nhập thì dừng và báo lại (xem Điều kiện tiên quyết).
2. Vào mục tìm creator: sidebar trái → "Khám phá các nhà sáng tạo" → "Tìm nhà
   sáng tạo" (nếu đã ở trang có ô tìm kiếm "Tìm nhà sáng tạo" thì bỏ qua bước này).
3. Gõ `<handle>` vào ô tìm kiếm, đợi dropdown gợi ý hiện ra (`browser__wait` 1-2s
   nếu cần) rồi nhấn Enter.
4. Trong "Kết quả tìm kiếm", tìm dòng có handle KHỚP CHÍNH XÁC `<handle>` — cẩn
   thận các handle gần giống (vd `.ddt` với `.dtt` là 2 người khác nhau). Dùng
   `browser__extract` lấy luôn chỉ số ở dòng đó: GMV, số món bán ra, lượt xem
   video trung bình, tỷ lệ tương tác.
5. Click vào tên creator đó → trang "Chi tiết về nhà sáng tạo".
6. `browser__extract` với query: "Tên hiển thị, handle, số người theo dõi, danh
   mục hàng, điểm đánh giá và số đánh giá, badge (vd Bán chạy nhất Top 5), toàn bộ
   nội dung bio/giới thiệu (đặc biệt số điện thoại/hotline nếu có), các link liên
   hệ Zalo/email (href của icon cạnh tên), và khối Doanh số: GMV, Số món bán ra,
   GPM, GMV từ mỗi khách hàng".
7. Trả về kết quả có cấu trúc cho tên này.

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
