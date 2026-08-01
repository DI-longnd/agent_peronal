---
name: ecom-demo-mock-api
description: >
  SKILL DEMO KỸ THUẬT, KHÔNG DÙNG CHO VIỆC THẬT. Minh hoạ đường tool chạy phía
  server (không cần máy khách) và cách gọi script trong skill. Dữ liệu trả về là
  BỊA. Chỉ dùng khi user nói rõ "chạy demo ecom" hoặc "thử tool mock". Yêu cầu
  thật về đơn hàng TikTok Shop -> dùng tiktok-order-export.
---

# DEMO — Tool phía server + script trong skill

> ⚠️ **Skill này KHÔNG nối với sàn thật.** `ecom__check_order_status`,
> `ecom__process_refund`, `ecom__update_inventory` đều trả chuỗi bịa sẵn.
> Tuyệt đối không báo con số từ đây cho user như dữ liệu thật — nếu lỡ chạy,
> phải nói rõ "đây là dữ liệu demo".
>
> Nó tồn tại để giữ một ví dụ chạy được của hai cơ chế: tool thực thi trên server
> (khác `browser__*` chạy trên máy khách) và `run_skill_script` (tầng 3).

## Khi nào dùng skill này
CHỈ khi user nói rõ đang muốn thử demo. Việc thật về đơn hàng → `tiktok-order-export`.

## Quy trình kiểm tra đơn hàng (demo)
1. Chạy `run_skill_script(name="ecom-demo-mock-api", script_relpath="scripts/check_order.py", args=[<order_id>])`
2. Đọc kết quả trả về (JSON: status, amount, customer) — **dữ liệu bịa**

## Gotchas
- Mã đơn trên sàn A có format `SA-XXXXX`, trên sàn B là `SB_XXXXX` — không dùng chung 1 regex parse cho cả 2.
- Trạng thái "pending" có thể kéo dài >48h vào cuối tuần do bên vận chuyển không xử lý T7/CN — đây KHÔNG phải lỗi hệ thống.
- Số tiền trả về từ script là đơn vị nghìn đồng (vd: 200 nghĩa là 200,000đ), không phải đồng.

## Output format khi báo cáo cho user
Mở đầu bằng một dòng "⚠️ Dữ liệu demo, không phải đơn hàng thật", rồi theo mẫu:
- Mã đơn: ...
- Trạng thái: ...
- Số tiền: ... (đã quy đổi ra đồng)
- Hành động đề xuất (nếu có): ...
