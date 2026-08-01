---
name: tiktok-shop-map
description: >
  BẢN ĐỒ + QUY ƯỚC của TikTok Shop: Trung tâm nhà bán hàng (seller-vn.tiktok.com)
  và Trung tâm liên kết (affiliate.tiktok.com) — có những mục nào, mỗi mục làm gì,
  URL ra sao, số/ngày/tiền viết theo kiểu gì, file xuất đơn có những cột nào.
  DÙNG KHI: user hỏi "xem ... ở đâu" / "vào mục nào" / "lấy được dữ liệu gì"; hoặc
  cần làm một việc trên TikTok Shop mà CHƯA có skill riêng; hoặc đang theo một skill
  riêng nhưng phải đi ra ngoài quy trình của nó. Việc đã có skill riêng và chạy đúng
  quy trình thì KHÔNG cần đọc skill này.
---

# Bản đồ TikTok Shop

Skill này KHÔNG hướng dẫn làm một việc cụ thể. Nó cho biết **địa hình**: cái gì nằm
ở đâu, gọi tên là gì, và trang này có những quy ước gì khác thường. Đọc xong thì mới
biết mình đang đứng ở đâu — giống người mới vào phải nhìn menu trước khi bấm.

Khảo sát thật ngày **01-08-2026**, tài khoản người bán Việt Nam (`shop_region=VN`).
Giao diện TikTok đổi khá thường xuyên: mục nào **không thấy trong `get_state`** thì
tin vào `get_state`, đừng tin vào trang này.

## Hai trang khác nhau, đừng lẫn

| | Trung tâm nhà bán hàng | Trung tâm liên kết |
|---|---|---|
| Địa chỉ | `seller-vn.tiktok.com` | `affiliate.tiktok.com` |
| Lo việc | đơn hàng, sản phẩm, kho, tiền | nhà sáng tạo (KOC), hoa hồng |
| Vào từ | trực tiếp | sidebar "Liên kết" → `/affiliate/landing` |
| Quay lại | | mục "Trung tâm nhà bán hàng" trên sidebar |

Cùng một phiên đăng nhập, đi lại giữa hai bên không phải đăng nhập lại.

**Vùng**: `seller-vn` là Việt Nam. Có cả `seller-us`… — sai vùng thì không thấy đơn.
URL tự thêm `?shop_region=VN&shop_id=...` sau khi mở; **đừng tự gõ `shop_id` vào URL**,
TikTok điền từ phiên đăng nhập nên bỏ đi thì chạy đúng cho mọi khách.

## Sidebar Trung tâm nhà bán hàng

Nhóm cấp một phần lớn là `<div>` **phải bấm mới xổ mục con** — chúng KHÔNG phải link
và trong `get_state` không có `href`. Chỉ 3 mục là link trực tiếp: Trang chủ,
Liên kết, Số liệu phân tích.

Bảng dưới đây **đã mở thật từng trang** (01-08-2026), cột "Trong đó có gì" ghi các tab
và nút đọc được. Trang nào tự chuyển hướng thì ghi đích thật.

| Nhóm | Mục | Đường dẫn | Trong đó có gì |
|---|---|---|---|
| **Đơn hàng** | Quản lý đơn hàng | `/order` | 7 tab (xem mục dưới) · Bộ lọc · Sắp xếp theo · **Xuất** · tìm theo ID đơn/SP |
| | Quản lý trả hàng | `/order/return` | tab: Tất cả · Đang chờ bạn · Đang chờ TikTok Shop/khách · Đã khiếu nại/tranh chấp · Đã giải quyết |
| **Sản phẩm** | Quản lý sản phẩm | `/product/manage` | tab: Tổng quan · Cải thiện chất lượng bài niêm yết · Quản lý hàng có sẵn · Tất cả · Trên kệ · Đang xem xét · Cần chú ý · Đã vô hiệu hóa · Bản nháp · Đã xóa. Có Hành động hàng loạt, Bộ lọc |
| | Thêm sản phẩm | `/product/listing` | form thêm sản phẩm |
| | Điểm sản phẩm | `/product/rating` | tab Đánh giá / Đánh giá có thưởng · lọc 1-5 sao · lọc ngày Từ–Đến · 7/30 ngày qua |
| | Cơ hội sản phẩm | `/product/opportunity` | tab: Sản phẩm tiềm năng cao · Từ khóa thịnh hành · Hạng mục cạnh tranh thấp |
| | Chẩn đoán giá | `/product/price-diagnosis` | tra theo ID/tên sản phẩm |
| | Công cụ tăng tốc bán hàng | `/product/sales-accelerator-new` | *(chưa mở kiểm)* |
| | Đấu thầu | `/product/price-bidding-new` | *(chưa mở kiểm)* |
| **Kho vận** | Kho hàng | `/logistics/warehouse-setting` | tab Kho lấy hàng / Kho trả hàng · Thêm kho hàng |
| | Hoàn thiện | `/logistics/fulfillment-setting` | cài đặt |
| | Vận chuyển | `/logistics/fee-and-service` | tab Phương thức vận chuyển |
| **Marketing** | Khuyến mãi | `/promotion/marketing-tools` | → chuyển `/tool-choose` |
| | Chiến dịch | `/promotion/campaign-tools` | → `/all` · tab: Đăng ký chiến dịch · Quản lý chiến dịch · Quy tắc xếp chồng |
| | Chương trình | `/promotion/program` | → `/register-program` · tab Đăng ký / Của tôi |
| | Trang cửa hàng | `/decoration` | → `/versions` · tab Thiết kế cửa hàng / Quản lý hạng mục |
| | Quảng cáo cửa hàng | `/ads-creation/dashboard` | *(chưa mở kiểm)* |
| **Liên kết** | sang Trung tâm liên kết | `/affiliate/landing` | xem mục riêng bên dưới |
| **LIVE và video** | Bán hàng qua LIVE | `/live-selling` | → `/overview` · tab: Tổng quan · Quản lý video nhá hàng · Lấy cảm hứng · Cơ bản về LIVE · Lượt xem & tương tác · Doanh số & chuyển đổi · Phân tích hiểu sâu |
| | Video link bán hàng | `/shoppable-videos` | tải chậm, chưa đọc được tab |
| **Tăng trưởng** | Nhiệm vụ và phần thưởng | `/sea-growth/growth` | tab Missions / My rewards (**còn tiếng Anh**) |
| | Cửa hàng ứng dụng | `/services` | → `/services/market` · tab Trang chủ / Ứng dụng |
| | Bảng xếp hạng | `/services/market/leaderboards` | tab Seller service partners / Đối tác ghép đôi nhà sáng tạo |
| | Star Shop | `/health-center/badge` | *(chưa mở kiểm)* |
| | Đối tác TikTok Shop | `/services/market/tsp` | *(chưa mở kiểm)* |
| **Số liệu phân tích** | | `/compass/data-overview` | lọc Theo loại nội dung / Theo nguồn đơn hàng |
| **Tình trạng tài khoản** | Điểm tình trạng tài khoản | `/health-center` | tab: Tổng quan · Hồ sơ vi phạm · Sự kiện cảnh báo · Bảo vệ cửa hàng · Trung tâm đào tạo |
| | Điểm cửa hàng | `/health-center/experience-score` | điểm trải nghiệm |
| | Điểm tình trạng nhà sáng tạo | `/creator` | tab Vi phạm TikTok Shop / Vi phạm chung |
| **Tài chính** | Giao dịch | `/finance/transactions` | tab Đã quyết toán / Sẽ quyết toán · **lọc ngày**: Chọn ngày tạo đơn hàng, Chọn ngày quyết toán |
| | Số tiền rút | `/finance/withdraw-new` | tab Tất cả / Số tiền rút / Thu nhập · **Xuất + Lịch sử xuất dữ liệu** (giống hệt trang đơn hàng) |
| | Giấy tờ thuế | `/finance/invoice` | Hóa đơn nền tảng · Biên nhận hoa hồng liên kết · Chứng nhận thuế khấu trừ · Tải xuống · Xuất chi tiết hóa đơn |

Ô ghi *(chưa mở kiểm)* nghĩa là đường dẫn lấy từ nhãn menu nhưng **chưa tự tay mở** —
mở ra không đúng thì bấm menu tìm lại, đừng cho là mình sai.

**Biết đường dẫn thì navigate thẳng, đừng bấm menu.** Mỗi cú click là một cơ hội dính
captcha và một lượt `get_state`; đi URL là một bước thay cho ba.

**Nhiều trang tự chuyển hướng sau khi tải** (`/promotion/*`, `/decoration`,
`/live-selling`, `/services`). URL cuối khác URL vừa gõ là BÌNH THƯỜNG, không phải lỗi.
Chờ 5-6s rồi mới `get_state`, nếu không sẽ đọc phải trang giữa chừng.

**Xuất file không chỉ có ở trang đơn hàng.** `/finance/withdraw-new` có đúng bộ đôi
"Xuất" + "Lịch sử xuất dữ liệu" giống hệt, `/finance/invoice` có "Xuất chi tiết hóa
đơn". Quy trình trong `tiktok-order-export` (đặt lệnh xuất → chờ server tạo → khớp tên
file → tải) nhiều khả năng dùng lại được ở đó — nhưng **chưa kiểm chứng**, phải tự dò
lại chứ đừng cho là chắc chắn.

## Trang Quản lý đơn hàng — nơi làm việc nhiều nhất

7 tab, đều là `<div role="tab">`, ứng với `?tab=`:

| Tab | Nghĩa |
|---|---|
| **Tất cả** (`tab=all`) | mọi đơn — **luôn dùng cái này khi thống kê/xuất file** |
| Cần gửi | chờ đóng gói/giao cho vận chuyển. **Đây là tab MẶC ĐỊNH khi mở `/order`** |
| Đã gửi | đã bàn giao vận chuyển, đang trên đường |
| Đã hoàn tất | giao xong |
| Chờ xử lý | chờ thanh toán/xác nhận |
| Đã hủy | huỷ bởi khách hoặc hệ thống |
| Giao không thành công | giao hỏng, hoàn về |

> **Bẫy hay mắc nhất:** mở `/order` không kèm `tab=all` thì đang đứng ở **Cần gửi**,
> chỉ thấy đơn chờ vận chuyển. Đếm ra số nhỏ rồi tưởng shop ít đơn.

Thanh công cụ: `Bộ lọc` · `Sắp xếp theo` · `Xuất` · ô tìm kiếm theo ID đơn/ID sản phẩm.

Lọc theo khoảng ngày **đi bằng URL, không bấm bộ lọc** — ô ngày là `readOnly`, gõ vào
không ăn, `fill()` cũng bị từ chối. Chi tiết + script tính mốc: skill
`tiktok-order-export`.

## Sidebar Trung tâm liên kết

Toàn bộ là `<div>`, **không có `href`** — bắt buộc phải click, không navigate thẳng được.

| Nhóm | Mục |
|---|---|
| Cộng tác | Khám phá các nhà sáng tạo · Quản lý nhà sáng tạo |
| Làm việc với đối tác | Yêu cầu hàng mẫu |
| Phân tích | Đơn hàng liên kết |
| | Trung tâm nhà bán hàng (quay về seller-vn) |

Trang chủ hiển thị: GMV nhờ nhà sáng tạo · Hoàn tiền · Số món bán ra nhờ nhà sáng tạo ·
Hoa hồng ước tính · Số sản phẩm bán ra trung bình mỗi ngày.

Trang chi tiết một creator: `affiliate.tiktok.com/connection/creator/detail?cid=<id>`.

## Quy ước đọc số và ngày — chỗ dễ hiểu sai nhất

**Dấu phẩy là DẤU THẬP PHÂN, không phải phân cách nghìn.** `183,13K` = 183.130,
`0,3%` = không phẩy ba phần trăm. Đọc theo kiểu Anh–Mỹ là sai cả nghìn lần.

Các dạng gặp thật: `1Mđ+` · `183,13K` · `699,5K` · `0,3%` · `0-50Kđ` (khoảng, không
phải một số) · `0₫`.

**Giữ NGUYÊN VĂN khi báo cáo.** Đừng quy đổi `1Mđ+` thành `1.000.000` — khách đối
chiếu với màn hình họ đang nhìn, đổi đi là họ không dò được.

**Ngày viết ba kiểu khác nhau ở ba nơi**, đây là nguồn lỗi thật:

| Ở đâu | Kiểu | Ví dụ |
|---|---|---|
| Ô nhập trong bộ lọc | `MM/DD/YYYY` | `08/01/2026` = 1 tháng 8 |
| Chip kết quả lọc | `DD/MM/YYYY` | `01/08/2026` = 1 tháng 8 |
| Cột trong file CSV | `DD/MM/YYYY HH:MM:SS` | `05/05/2026 23:22:02` |
| Trong URL | Unix mili-giây, GMT+7 | `1785603599999` |

Cùng một ngày, bốn cách viết. **Đọc chip theo DD/MM.**

## Riêng của TikTok Shop, không có ở trang khác

Chỉ liệt kê thứ KHÁC THƯỜNG. Quy tắc lái browser chung (get_state trước khi click,
captcha thì gọi `wait_for_human`, tải file bằng `browser__download_file`, chưa đăng
nhập thì dừng) đã nằm trong system prompt của browser-agent — không nhắc lại ở đây.

- **Cookie phiên có hậu tố riêng**: `sessionid_tiktokseller`, `sid_guard_tiktokseller`,
  `sid_tt_tiktokseller` — khác cookie TikTok thường. Phiên đo được **~3 ngày** và
  **không tự gia hạn** khi ghé lại (2 mẫu, cùng một tài khoản — không phải con số
  chính thức của TikTok).
- **Trang load tiếng Anh trước rồi mới đổi sang tiếng Việt.** Nhãn đổi giữa chừng:
  "Discover creators" → "Khám phá các nhà sáng tạo". Chờ đủ 5-6s rồi hãy đọc nhãn,
  không thì bắt nhầm nhãn tiếng Anh vào lúc trang chưa dịch xong.
- **`get_state` ở đây trả ~75 element, quá nửa là sidebar lặp lại.** Biết mình tìm nút
  gì thì `browser__get_state(contains="Xuất|Tải xuống")`.
- **Panel mở đè lên chính nút vừa bấm.** Bấm lại "Xuất" khi panel đang mở sẽ bị chặn
  kèm "trang đã thay đổi" — đó là dấu hiệu panel ĐANG MỞ, không phải lỗi.
- **API bọc kết quả trong vỏ ngoài**: `{"code":0, ..., "message":"success"}`. Chữ
  `success` chỉ nghĩa là *gọi API thành công*, KHÔNG phải *việc đã xong*. Trạng thái
  thật nằm trong `data`. Nhầm chỗ này là tải về file của lần xuất trước.

## Dữ liệu lấy được từ file xuất đơn hàng

56 cột, **tên cột bằng TIẾNG ANH** dù giao diện tiếng Việt. Biết trước danh sách này
thì trả lời được ngay "có lấy được trường X không" mà không phải xuất thử.

| Nhóm | Cột |
|---|---|
| Định danh | `Order ID` `SKU ID` `Seller SKU` `Package ID` `Tracking ID` |
| Trạng thái | `Order Status` `Order Substatus` `Cancelation/Return Type` `Normal or Pre-order` `Checked Status` `Checked Marked by` |
| Hàng | `Product Name` `Variation` `Quantity` `Sku Quantity of return` `Product Category` `Weight(kg)` |
| Tiền | `SKU Unit Original Price` `SKU Subtotal Before Discount` `SKU Platform Discount` `SKU Seller Discount` `SKU Subtotal After Discount` `Original Shipping Fee` `Shipping Fee After Discount` `Shipping Fee Seller Discount` `Shipping Fee Platform Discount` `Payment platform discount` `Taxes` `Order Amount` `Order Refund Amount` |
| Mốc thời gian | `Created Time` `Paid Time` `RTS Time` `Shipped Time` `Delivered Time` `Cancelled Time` |
| Huỷ | `Cancel By` `Cancel Reason` |
| Giao hàng | `Fulfillment Type` `Warehouse Name` `Delivery Option` `Shipping Provider Name` |
| Người mua | `Buyer Username` `Buyer Message` `Recipient` `Phone #` |
| Địa chỉ | `Country` `Province` `District` `Commune` `Detail Address` `Additional address information` |
| Khác | `Payment Method` `Seller Note` `Order Channel` **`Creator Handle`** |

`Creator Handle` là cầu nối sang Trung tâm liên kết: từ đơn hàng biết được creator nào
mang về đơn đó, ghép được với dữ liệu của `tiktok-affiliate-creators`.

Định dạng file: CSV, có BOM UTF-8 (Excel mở tiếng Việt không lỗi font). Ngày trong file
là `DD/MM/YYYY HH:MM:SS`. Bảng Xuất **không cho chọn định dạng** — CSV là thứ duy nhất.

## Đi tiếp đâu

| Cần làm | Skill |
|---|---|
| Xuất danh sách đơn ra file theo khoảng ngày | `tiktok-order-export` |
| Tra thông tin nhà sáng tạo theo handle | `tiktok-affiliate-creators` |
| Việc khác trên TikTok Shop | tự làm theo bản đồ trên + `browser-automation` |
