---
name: tiktok-order-export
description: >
  Xuất danh sách đơn hàng TikTok Shop ra file CSV theo khoảng ngày, từ Trung tâm
  nhà bán hàng (seller-vn.tiktok.com). Dùng khi task nhắc tới xuất/tải/export đơn
  hàng, lấy file đơn hàng, báo cáo đơn hàng theo ngày/tuần/tháng, "xuất đơn từ
  ngày ... đến ngày ...".
---

# TikTok Shop — Xuất file đơn hàng theo khoảng ngày

## Khi nào dùng skill này
User cần **file** danh sách đơn hàng trong một khoảng thời gian. Khác skill tra
creator (agent tự đọc rồi trả text): ở đây **TikTok tạo file** và trình duyệt tải
về **máy user**. Agent không đọc nội dung file, chỉ đưa đường dẫn.

User chỉ muốn XEM số liệu chứ không cần file → đọc thẳng trên trang bằng
`browser__extract`, đừng chạy quy trình xuất.

## Điều kiện tiên quyết
Cần đã đăng nhập TikTok Shop Seller. Gặp form đăng nhập → DỪNG, báo user:
"Máy của bạn chưa đăng nhập TikTok Shop — chạy lệnh đăng nhập rồi thử lại."
Không tự điền tài khoản/mật khẩu.

## Khoảng ngày

Quy đổi mốc tương đối ("tháng này", "7 ngày qua", "3 tháng gần nhất", "tuần trước")
theo ngày giờ trong `<environment>` của system prompt. Đừng tự suy đoán hôm nay là
ngày nào.

**Diễn giải được thì cứ làm, đừng hỏi lại.** Chọn cách hiểu tự nhiên nhất (đếm lùi
từ hôm nay), rồi **ghi rõ khoảng ngày cụ thể ở báo cáo cuối** để user đối chiếu và
bảo làm lại nếu lệch ý. Chờ user trả lời một câu hỏi mà đằng nào cũng phải đoán là
làm mất thời gian của họ — đo được ở lượt chạy 01-08-2026: agent dừng lại hỏi "3
tháng gần nhất" nghĩa là 01/05–01/08 hay tháng 5,6,7, trong khi chênh lệch chỉ là
một ngày rìa và báo cáo cuối vẫn nói rõ.

Chỉ HỎI LẠI khi **hoàn toàn không có thông tin thời gian** ("xuất đơn hàng cho tôi").
Lúc đó đừng đoán: xuất nhầm khoảng thì file sai mà nhìn không ra.

## Quy trình

### Bước 1 — Lấy URL bằng script, ĐỪNG tự tính

```
run_skill_script(name="tiktok-order-export", script_relpath="scripts/daterange.py",
                 args=["01/05/2026", "01/08/2026"])
```

Script trả về khoảng ngày đã diễn giải, số ngày, chip cần thấy, và URL dùng luôn.
Mốc tương đối thì truyền cờ thay vì tự quy đổi:

| User nói | args |
|---|---|
| "7 ngày qua" | `["--last-days", "7"]` |
| "3 tháng gần nhất" | `["--last-months", "3"]` |
| "tháng này" | `["--this-month"]` |
| "tháng trước" | `["--last-month"]` |
| "hôm nay" | `["--today"]` |
| ngày cụ thể | `["01/05/2026", "01/08/2026"]` |

Script neo cứng giờ VN (GMT+7) nên không lệ thuộc múi giờ máy chạy.

**Vì sao bắt buộc dùng script:** đo 01-08-2026, agent được yêu cầu "đến 01/08" nhưng
chép mốc `1785517199999` (31/07) từ ví dụ bên dưới, xuất thiếu một ngày rồi tự bịa lý
do "giới hạn kỹ thuật của TikTok Shop". Main agent bắt được và giao lại, nhưng lượt đó
tốn 427k token — gấp 2.4 lần. Phép tính này tất định, đừng làm bằng suy luận.

Script hỏng hoặc không chạy được thì mới tự tính theo mục dưới đây.

### Bước 1b — Cấu tạo URL (chỉ cần khi script không dùng được)

Trang mã hoá khoảng ngày vào URL bằng **2 mốc Unix timestamp mili-giây**:

```
https://seller-vn.tiktok.com/order?tab=all&time_order_created[]=<BẮT_ĐẦU>&time_order_created[]=<KẾT_THÚC>
```

- `<BẮT_ĐẦU>` = 00:00:00.000 của ngày đầu, giờ địa phương (VN = GMT+7), **mili-giây**
- `<KẾT_THÚC>` = 23:59:59.999 của ngày cuối, cùng cách tính
- `tab=all` bắt buộc — mặc định trang mở tab "Cần gửi", chỉ có đơn chờ vận chuyển.
- KHÔNG kèm `shop_id`; TikTok tự điền từ phiên đăng nhập nên chạy đúng cho mọi khách.

**TỰ TÍNH cả hai mốc từ khoảng ngày user yêu cầu.** Đừng mượn con số của lần trước:
đo ngày 01-08-2026, agent được yêu cầu "đến 01/08/2026" nhưng lại chép mốc kết thúc
`1785517199999` (31/07) từ ví dụ trong tài liệu này, xuất thiếu mất một ngày, rồi
tự bịa lý do "giới hạn kỹ thuật của TikTok Shop". Không có giới hạn nào cả — chỉ là
chép nhầm số.

Cách kiểm tra nhanh trước khi navigate: `(KẾT_THÚC - BẮT_ĐẦU + 1) / 86400000` phải
ra đúng số ngày của khoảng (tính cả hai đầu). Lệch thì tính lại.

Ví dụ minh hoạ cách tính — 01/01/2026 đến 31/07/2026 (giờ VN). **Đây là ví dụ cho
một khoảng CỤ THỂ, không phải giá trị dùng lại được:**

```
BẮT_ĐẦU = 01/01/2026 00:00:00.000 GMT+7 -> 1767200400000
KẾT_THÚC = 31/07/2026 23:59:59.999 GMT+7 -> 1785517199999
https://seller-vn.tiktok.com/order?tab=all&time_order_created[]=1767200400000&time_order_created[]=1785517199999
```

**Vì sao đi đường URL mà không bấm bộ lọc:** ô ngày trong bộ lọc là `readOnly` —
gõ vào không bao giờ ăn, `fill()` cũng bị từ chối; bắt buộc phải bấm trong lịch,
mà lịch lúc mở lúc không và mỗi lần thao tác lại tăng nguy cơ TikTok bật captcha.
Đường URL bỏ hẳn khâu đó: 1 lần navigate thay cho ~8 cú click.

### Bước 2 — Xác minh bộ lọc đã ăn
`browser__wait` 4-6s (trang SPA nặng), rồi `browser__get_state`.

Phải thấy chip khoảng ngày dạng **`DD/MM/YYYY-DD/MM/YYYY`** và `Bộ lọc (1)`.
Không thấy chip → URL sai, dừng và báo.

Đối chiếu chip với khoảng user yêu cầu. **Lệch dù chỉ một ngày → tính lại timestamp
và navigate lại.** Đừng xuất tiếp rồi giải thích cho qua ở báo cáo cuối: chip chính
là thứ TikTok hiểu, nó lệch nghĩa là file sẽ sai.

### Bước 3 — Mở bảng Xuất
Click nút **"Xuất"** trên thanh công cụ (cạnh "Sắp xếp theo"). `browser__wait` 4s,
`browser__get_state`.

Panel mở ra khi thấy dòng **"Đơn hàng đã lọc (N đơn hàng)"**.
- N = 0 → BÁO LẠI cho user, đừng xuất file rỗng.
- Click lại nút "Xuất" khi panel đã mở sẽ bị từ chối ("trang đã thay đổi") vì panel
  che mất nút — đó là dấu hiệu panel ĐANG MỞ, không phải lỗi.

### Bước 4 — Chọn phạm vi
Click **"Đơn hàng đã lọc (N đơn hàng)"**.
KHÔNG chọn "Tất cả đơn hàng..." — bỏ qua bộ lọc, xuất 12 tháng gần nhất.

### Bước 5 — Định dạng: KHÔNG có gì để chọn
Panel này **không cấp tuỳ chọn định dạng**. Đã soi toàn bộ element khi panel mở
(01-08-2026): không có CSV / Excel / xlsx / "Định dạng" — chỉ có 3 lựa chọn phạm vi,
nút Xuất, các nút Tải xuống của lịch sử, và nút Đóng. TikTok Shop VN luôn trả `.csv`
(56 cột, BOM UTF-8). Đừng phí lượt đi tìm nút định dạng.

### Bước 6 — Bấm Xuất trong panel
Trong danh sách element sẽ có **hai** nút tên "Xuất": một là nút thanh công cụ ở
bước 3, một là nút trong panel. Chọn nút có **index LỚN HƠN** (panel render sau).

### Bước 7 — Chờ server tạo xong file
File KHÔNG về ngay: TikTok tạo file ở phía họ, xong mới hiện link trong mục
**"Lịch sử xuất dữ liệu"** cuối panel.

**Theo dõi bằng phản hồi API, đừng dò giao diện.** Trang gọi
`/api/fulfillment/order/export` (đặt lệnh, trả về `export_task_id`) rồi lặp
`/api/fulfillment/order/export_record/get` (hỏi xong chưa).

Gọi `browser__api_responses` với `url_contains="export_record"`. Cấu trúc thật:

```json
{"code":0,"data":{"export_records":[
  {"file_name":"...-2026-07-31-00%3A25.csv","download":1,"file_key":"",     "export_task_id":"...96260"},
  {"file_name":"...-2026-07-31-00%3A04.csv","download":2,"file_key":"dfaa...","export_task_id":"...81924"}
]},"message":"success"}
```

Đọc đúng như sau:

- **`download: 1` = ĐANG TẠO** (kèm `file_key` rỗng). **`download: 2` = XONG.**
- **KHÔNG có trường `download_url`.** Đừng tìm nó.
- `"message":"success"` là mã bao ngoài của API, **KHÔNG phải trạng thái công việc**.
  Thấy chữ "success" mà kết luận đã xong là SAI.
- Bản ghi được xếp **mới nhất trước**. `file_name` nhúng mốc giờ tạo, dạng URL-encode
  (`...-2026-07-31-00%3A25.csv` là `...-2026-07-31-00:25.csv`).

Vòng lặp: lấy `export_task_id` mà API `order/export` vừa trả ở bước 6, rồi chờ đúng
bản ghi có ID đó chuyển sang `download: 2`. Chưa xong thì `browser__wait` 5s và hỏi
lại, **tối đa 8 lần** (~50s).

### Bước 8 — Tải ĐÚNG file vừa tạo

**BẪY NGHIÊM TRỌNG — đọc kỹ.** Mục "Lịch sử xuất dữ liệu" giữ file của **7 ngày
qua**, nên luôn có sẵn nhiều nút "Tải xuống" của các lần xuất TRƯỚC. Bấm nút đầu tiên
nhìn thấy là rất dễ tải về file cũ với khoảng ngày khác — và **không có dấu hiệu nào
báo sai**, khách nhận nhầm dữ liệu mà không biết.

Bắt buộc:

1. Từ phản hồi API, lấy `file_name` của bản ghi có `export_task_id` khớp lần xuất này.
   Giải mã URL-encode để ra tên thật (vd `Tất cả đơn hàng-2026-07-31-00:25.csv`).
2. `browser__get_state`, tìm dòng trong "Lịch sử xuất dữ liệu" chứa **đúng tên file
   đó** (mốc giờ phải khớp), rồi bấm nút "Tải xuống" **của chính dòng đó**.
3. Sau khi tải, đối chiếu tên file mà `browser__download_file` trả về với tên mong
   đợi. Lệch mốc giờ → đã tải nhầm file cũ, báo user, đừng im lặng.

Vẫn không thấy sau 8 vòng → báo user rằng TikTok đang tạo file, lịch sử giữ 7 ngày
nên vào lấy sau được; đừng chờ vô hạn.

## Gotchas
- **Ô ngày trong bộ lọc là readOnly** — đừng phí lượt gõ vào đó. Dùng URL (bước 1).
- Nếu buộc phải dùng bộ lọc (vd lọc theo tiêu chí khác): lịch có sẵn nút tắt
  **Hôm nay / Hôm qua / 7 ngày qua / 28 ngày qua / Tuần hiện tại / Tháng hiện tại**
  — đó là các button có nhãn rõ, bấm được. Ô ngày lẻ trong lưới lịch thì khó và
  hay trượt, tránh.
- **Ô nhập của bộ lọc hiển thị MM/DD/YYYY, còn chip kết quả hiển thị DD/MM/YYYY.**
  Cùng một khoảng, hai cách viết. Đọc chip theo DD/MM.
- **CAPTCHA rất hay xuất hiện** trên trang này (đo được: 4/5 lần mở trang). `get_state`
  sẽ báo "⚠️ PHÁT HIỆN CAPTCHA" — gọi `browser__wait_for_human`, KHÔNG tự kéo.
  Thao tác càng ít càng đỡ dính, thêm một lý do dùng URL thay vì bấm bộ lọc.
- **Lịch sử xuất dữ liệu chứa file của 7 ngày trước** — nút "Tải xuống" đầu tiên
  thường KHÔNG phải file bạn vừa tạo. Luôn khớp tên file theo mốc giờ (xem bước 8).
- Không lọc thì panel Xuất mặc định xuất **12 tháng gần nhất** — luôn lọc trước.
- Giới hạn 200.000 đơn/lần. Khoảng quá rộng thì chia nhỏ.
- File về **máy user**, không hiện trong web chat. Báo cáo phải nói rõ đường dẫn.
- Sau mỗi click mở panel, `browser__wait` 2-4s rồi mới `get_state` — SPA render chậm.

## Output format
1. Xác nhận: khoảng ngày (ghi cả dạng chữ để user không phải đoán định dạng), số đơn
   tìm thấy, định dạng file.
2. **Đường dẫn file**, lấy nguyên văn từ `browser__download_file`.
3. Ghi chú bất thường (0 đơn, phải chia nhỏ khoảng, file chưa tạo xong).

Ví dụ (kết quả thật của lần chạy kiểm chứng):

```
Đã xuất đơn hàng TikTok Shop:
- Khoảng ngày: 01/01/2026 – 31/07/2026 (1 tháng 1 đến 31 tháng 7 năm 2026)
- Phạm vi: tab "Tất cả", đơn hàng đã lọc — 8 đơn
- Định dạng: CSV (56 cột, có BOM UTF-8 nên Excel mở tiếng Việt không lỗi font)

File đã lưu trên máy bạn:
C:\Users\ADMIN\Downloads\PersonalAgent\20260731-000459-Tất cả đơn hàng-2026-07-31-00_04.csv
```
