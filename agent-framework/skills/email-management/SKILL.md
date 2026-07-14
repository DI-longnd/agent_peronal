---
name: email-management
description: >
  Đọc, phân loại, và soạn nháp trả lời email. Dùng khi task nhắc tới mail, hộp thư,
  hoặc cần soạn nội dung gửi ai đó qua email.
---

# Email Management

## Phân loại email khi đọc inbox
Xếp mỗi email vào 1 trong 3 nhóm: `cần trả lời gấp`, `cần trả lời không gấp`, `chỉ cần đọc qua`.
Tiêu chí "gấp": có deadline trong vòng 24h, hoặc từ khách hàng đang có vấn đề chưa xử lý.

## Gotchas
- Email từ noreply@ hoặc có tiền tố "[Automated]" không bao giờ xếp vào nhóm "cần trả lời".
- Nếu email có đính kèm hợp đồng/hoá đơn, luôn note lại trong write_note trước khi trả lời,
  vì nội dung đính kèm không tự động vào context của lần đọc sau.

## Khi soạn nháp trả lời
Giữ giọng văn ngắn gọn, không dùng template chào hỏi dài dòng. Luôn có 1 câu hành động rõ ràng ở cuối.
