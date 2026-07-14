---
name: ecommerce-order-processing
description: >
  Xử lý đơn hàng thương mại điện tử — kiểm tra trạng thái, hoàn tiền, cập nhật tồn kho.
  Dùng khi task nhắc tới đơn hàng, mã đơn, khách hàng, hoàn tiền, hoặc sàn TMĐT.
---

# Ecommerce Order Processing

## Khi nào dùng skill này
Task nhắc tới đơn hàng cụ thể (có mã đơn hoặc tên khách hàng) cần tra cứu/xử lý.
KHÔNG dùng cho câu hỏi chung chung về chính sách bán hàng (thuộc skill khác).

## Quy trình kiểm tra đơn hàng
1. Chạy `run_skill_script(name="ecommerce-order-processing", script_relpath="scripts/check_order.py", args=[<order_id>])`
2. Đọc kết quả trả về (JSON: status, amount, customer)
3. Nếu status là "disputed", đọc thêm `references/refund_policy.md` trước khi đề xuất hướng xử lý

## Gotchas
- Mã đơn trên sàn A có format `SA-XXXXX`, trên sàn B là `SB_XXXXX` — không dùng chung 1 regex parse cho cả 2.
- Trạng thái "pending" có thể kéo dài >48h vào cuối tuần do bên vận chuyển không xử lý T7/CN — đây KHÔNG phải lỗi hệ thống.
- Số tiền trả về từ script là đơn vị nghìn đồng (vd: 200 nghĩa là 200,000đ), không phải đồng.

## Output format khi báo cáo cho user
Luôn trả lời theo mẫu:
- Mã đơn: ...
- Trạng thái: ...
- Số tiền: ... (đã quy đổi ra đồng)
- Hành động đề xuất (nếu có): ...
