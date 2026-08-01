---
name: browser-automation
description: >
  Cách lái trình duyệt cho trang web BẤT KỲ — kỹ thuật chung, không gắn với trang
  nào. Dùng làm PHƯƠNG ÁN CUỐI khi không có skill chuyên biệt cho trang đó. Trang
  TikTok Shop / TikTok Affiliate LUÔN có skill riêng, dùng skill đó thay vì skill này.
---

# Browser Automation — kỹ thuật chung

## Khi nào dùng skill này
Chỉ khi trang cần thao tác KHÔNG có skill riêng. Kiểm tra danh sách skill trước:
- TikTok Shop, đơn hàng → `tiktok-order-export`
- TikTok Affiliate, creator → `tiktok-affiliate-creators`
- Cách TikTok Shop được tổ chức (có những mục nào, ở đâu) → `tiktok-shop-map`

Còn lại — trang lạ, form không có API, sàn khác — thì dùng skill này.

## Quy trình chuẩn
1. `browser__navigate` tới URL cần mở (hoặc `browser__search` nếu chưa biết URL).
2. `browser__get_state` để xem các element tương tác được và [index] của chúng.
3. Click/gõ text theo [index]. Sau MỖI hành động làm trang đổi (click gây navigate,
   submit form...), gọi lại `browser__get_state` — không tái sử dụng [index] cũ.
4. Dùng `browser__extract` để lấy dữ liệu cụ thể thay vì tự đọc toàn bộ trang.

## Gotchas
- **[index] chỉ có giá trị cho tới lần `browser__get_state` gần nhất.** Nếu trang
  đã thay đổi (navigate, click vào link, submit form) mà vẫn dùng [index] cũ, có thể
  click nhầm element khác hoặc nhận lỗi "not found".
- **Không có screenshot mặc định** (`use_vision=False`, vì model chính là DeepSeek —
  không hỗ trợ vision). Agent chỉ "nhìn thấy" trang qua text từ `browser__get_state`.
  Vì vậy tin vào đúng text/label của element, không suy đoán vị trí trực quan.
- **Mật khẩu, API key, thông tin đăng nhập nhạy cảm**: LUÔN dùng `browser__type_sensitive`
  với `placeholder` (vd `"site_password"`), KHÔNG dùng `browser__type`. Không bao giờ
  được yêu cầu hoặc tự bịa ra giá trị thật — giá trị được nạp sẵn từ biến môi trường
  `BROWSER_SECRET_<PLACEHOLDER>`, agent không bao giờ thấy giá trị thật.
- **Cookie banner / popup / modal** thường che khuất element cần tương tác. Luôn kiểm
  tra và đóng/chấp nhận chúng trước khi làm các bước khác — nếu `browser__click` báo
  đã click nhưng trang không phản ứng như mong đợi, khả năng cao là đã click trúng
  overlay che phía trên thay vì element thật bên dưới.
- **`browser__extract` dùng LLM để đọc trang** — nếu trang rất dài (>100,000 ký tự),
  kết quả sẽ báo bị cắt kèm `start_from_char` để tiếp tục đọc phần sau.
- **Trang cần đăng nhập**: agent KHÔNG tự đăng nhập. Phiên nằm trong PROFILE Chrome
  thật của agent (không phải file JSON — cơ chế `BROWSER_STORAGE_STATE` cũ chỉ còn
  là bản sao lưu). Người dùng đăng nhập một lần bằng `Dang-nhap-trang-web.bat` trên
  máy họ, hoặc `scripts/setup_browser_login.py <url>` nếu chạy từ mã nguồn. Vẫn thấy
  form đăng nhập nghĩa là phiên hết hạn hoặc chưa từng đăng nhập trang đó — báo lại
  cho người dùng, không cố tự điền tài khoản/mật khẩu.
- **Gặp captcha KHÁC với chưa đăng nhập.** Chỉ báo "chưa đăng nhập" khi thật sự thấy
  form đăng nhập. Thấy captcha thì gọi `browser__wait_for_human`, không tự giải.
- **Tải file**: bấm nút tải bằng `browser__download_file`, không phải `browser__click`
  — chỉ tool đó mới bắt được file và lưu về máy user. Báo cáo phải ghi nguyên văn
  đường dẫn tool trả về.
