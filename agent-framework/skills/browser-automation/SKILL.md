---
name: browser-automation
description: >
  Điều khiển trình duyệt web để duyệt trang, điền form, tìm kiếm, đăng nhập, hoặc
  trích xuất thông tin. Dùng khi task nhắc tới website, trang web, form online,
  đăng nhập vào 1 dịch vụ, hoặc cần lấy dữ liệu từ 1 URL cụ thể.
---

# Browser Automation

## Khi nào dùng skill này
Task cần tương tác thật với 1 trang web (không phải chỉ gọi API có sẵn) — vd:
điền form không có API, tìm kiếm sản phẩm trên 1 sàn không hỗ trợ API, đăng nhập
vào 1 dịch vụ để lấy thông tin.

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
