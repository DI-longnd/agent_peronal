# HƯỚNG DẪN SỬ DỤNG PERSONAL AGENT

Personal Agent là trợ lý AI giúp bạn tra cứu thông tin nhà sáng tạo trên TikTok
Affiliate (và các việc web khác) — bạn gõ yêu cầu trên trang web, agent tự mở
trình duyệt **ngay trên máy tính của bạn** và làm thay bạn.

Bạn sẽ nhận được 2 thứ từ người quản lý:
- **Link mời** (dạng `https://ecomerceagnet.duckdns.org/?invite=...`) — đây là
  "chìa khóa" cá nhân của riêng bạn.
- **File `PersonalAgent-win64.zip`** — app cài trên máy tính Windows.

---

## PHẦN 1 — CÀI ĐẶT LẦN ĐẦU (làm 1 lần, ~5 phút)

### Bước 1: Giải nén app
Chuột phải file `PersonalAgent-win64.zip` → **Extract All...** → chọn nơi dễ nhớ
(vd Desktop) → Extract. Bạn sẽ có thư mục `PersonalAgent`.

### Bước 2: Mở app lần đầu
Vào thư mục vừa giải nén, double-click **`PersonalAgent.exe`**.

- ⚠️ Windows có thể hiện cảnh báo xanh "Windows protected your PC" — bấm
  **More info** → **Run anyway**. (App chưa mua chữ ký số nên Windows cảnh báo
  mặc định — không phải virus.)
- Lần đầu app sẽ tự tải trình duyệt (~150MB) — chờ vài phút.
- Xong sẽ hiện **MÃ GHÉP 6 SỐ** trên cửa sổ đen. Để nguyên cửa sổ đó, đừng đóng.

### Bước 3: Mở link mời và ghép máy
1. Mở **link mời** của bạn trong trình duyệt (Chrome/Edge...) → hiện trang chat
   Personal Agent.
2. Góc trên bên phải, bấm nút **"Chưa ghép máy"** (chấm đỏ).
3. Nhập **mã 6 số** đang hiện trên cửa sổ đen → bấm **Ghép**.
4. Thấy "✓ Đã ghép thành công" và chấm chuyển **xanh** kèm tên máy của bạn — xong!

### Bước 4: Đăng nhập TikTok Shop (cho nghiệp vụ tra creator)
Agent dùng một trình duyệt riêng, sạch — nên cần đăng nhập TikTok Shop một lần:

1. Trong thư mục `PersonalAgent`, double-click **`Dang-nhap-trang-web.bat`**.
2. Dán `https://affiliate.tiktok.com/` vào rồi Enter.
3. Cửa sổ Chrome mở ra → **đăng nhập tài khoản TikTok Shop của bạn** như bình
   thường (mật khẩu, OTP... đều được — thông tin chỉ lưu trên máy bạn, không
   gửi đi đâu).
4. Đăng nhập xong, **giữ nguyên cửa sổ Chrome đang mở**, quay lại cửa sổ đen
   **bấm Enter** để lưu.

> Làm tương tự với trang web khác nếu sau này cần agent thao tác trang đó.

**Vài điều nên biết:**

- **TikTok chỉ cho phiên đăng nhập sống khoảng 3 ngày.** Hết hạn thì làm lại Bước 4
  này — app sẽ báo trước khi khởi động, ví dụ *"Phiên đăng nhập còn hiệu lực tới
  02-08-2026 (còn 3.0 ngày)"*.
- **Mỗi lúc chỉ mở một cửa sổ.** Đừng chạy `Dang-nhap-trang-web.bat` trong khi
  `PersonalAgent.exe` đang chạy — app sẽ báo profile đang bị chiếm và không mở. Đóng
  bớt rồi thử lại.
- **Gặp ô "Xác minh để tiếp tục — Kéo mảnh ghép"?** TikTok bật xác minh này ngẫu
  nhiên, kể cả với người thật. Bạn chỉ cần kéo mảnh ghép trên cửa sổ Chrome đang
  hiện; agent tự chờ bạn rồi làm tiếp. Agent không tự giải, và không được phép giải.

---

## PHẦN 2 — SỬ DỤNG HẰNG NGÀY

1. **Mở `PersonalAgent.exe`** (cửa sổ đen hiện "✓ Đã kết nối") — chỉ khi app đang
   mở, agent mới điều khiển được máy bạn.
2. Vào **link mời** → gõ yêu cầu → Enter. Ví dụ:

   > Tra thông tin các nhà sáng tạo sau trên TikTok Affiliate:
   > thanhdongian.dtt, tenkhac.abc, tenkhac2.xyz

3. Theo dõi tiến trình chạy ngay trên trang — đồng thời **cửa sổ Chrome sẽ tự
   bật lên trên máy bạn** và tự thao tác. Cứ để nó chạy, **đừng bấm chuột vào
   cửa sổ đó**.
4. Xong việc, agent trả về **bảng kết quả + khối CSV**. Bấm copy khối CSV → dán
   vào Excel là ra bảng (hoặc lưu thành file `.csv`).
5. Muốn dừng giữa chừng: bấm nút **Dừng** cạnh ô chat.

### Xuất file đơn hàng

Ngoài tra creator, agent còn xuất được danh sách đơn hàng TikTok Shop ra file. Ví dụ:

> Xuất đơn hàng TikTok Shop từ ngày 01/01/2026 đến 31/07/2026

Khác với tra creator (kết quả hiện thẳng trên web), **file đơn hàng do TikTok tạo và
tải về máy bạn** — agent sẽ báo đường dẫn, mặc định:

```
C:\Users\<tên bạn>\Downloads\PersonalAgent\
```

Tên file có mốc thời gian ở đầu nên xuất nhiều lần không đè lên nhau.

File luôn là **CSV** — TikTok Shop không cho chọn Excel ở bảng xuất này. File có sẵn
BOM UTF-8 nên mở bằng Excel không lỗi font tiếng Việt.

Khoảng ngày nói kiểu nào cũng được: ghi rõ ngày (`từ 01/12/2025 đến 31/07/2026`) hoặc
nói tương đối (`tháng này`, `7 ngày qua`, `tuần trước`) — agent biết hôm nay là ngày
nào. Không nói gì về thời gian thì agent hỏi lại chứ không tự đoán. Báo cáo cuối luôn
ghi lại khoảng ngày cụ thể, **đối chiếu chỗ đó** trước khi dùng file.

### Tự động cập nhật lên Google Sheet

Xuất đơn xong, agent đẩy luôn dữ liệu lên một Google Sheet cố định — khách mở đúng
link quen thuộc là thấy số mới nhất, không phải gửi file qua lại. Mất khoảng 3 giây.

Mỗi lần chạy là **ghi đè toàn bộ** sheet, không nối thêm.

Cần cài đặt một lần cho mỗi khách (làm theo phần "Nối Google Sheet" trong tài liệu
kỹ thuật): dán một đoạn mã vào sheet của khách, lấy về một địa chỉ web, rồi điền địa
chỉ đó cùng một chuỗi khoá vào `config.json` của app trên máy khách.

Chưa cài đặt thì agent vẫn xuất file bình thường, chỉ báo "chưa cấu hình Google
Sheet" rồi thôi.

> **Sheet này chứa tên, số điện thoại và địa chỉ người mua.** Đặt chế độ chia sẻ
> **Bị hạn chế** và chỉ thêm đúng người cần xem. Đừng để "Bất kỳ ai có đường liên
> kết" — cách nối này không cần sheet công khai.

Mẹo:
- Mỗi lần nên tra **tối đa 6-7 tên** — danh sách dài hơn thì chia làm nhiều lần.
- Lịch sử các cuộc trò chuyện nằm ở cột bên trái, bấm để xem lại.

---

## PHẦN 3 — KHI GẶP VẤN ĐỀ

| Hiện tượng | Cách xử lý |
|---|---|
| Chấm đỏ "Máy chưa kết nối" trên web | Mở lại `PersonalAgent.exe` trên máy tính |
| Agent báo "chưa đăng nhập TikTok Shop" | Làm lại Bước 4 (session hết hạn) |
| Cửa sổ đen hiện lại mã 6 số | Nhập lại mã vào web như Bước 3 (bấm vào tên máy → Ghép máy) |
| Muốn dùng máy tính khác | Cài app lên máy mới và ghép lại — máy cũ tự mất hiệu lực |
| Đang chạy mà muốn hủy | Bấm nút **Dừng** trên web |

---

## PHẦN 4 — LƯU Ý AN TOÀN (đọc 1 lần)

- **Link mời = chìa khóa của bạn.** Không gửi cho người khác, không đăng lên
  nhóm/mạng xã hội. Ai có link sẽ điều khiển được agent trên máy bạn. Nếu nghi
  bị lộ — báo người quản lý để cấp link mới.
- **Tắt `PersonalAgent.exe` khi không dùng** — app tắt là máy bạn "offline",
  không ai làm gì được máy, kể cả có link.
- Cửa sổ Chrome của agent **tự bật khi có việc** — nếu nó tự chạy mà bạn không
  hề gõ yêu cầu nào, hãy tắt app ngay và báo người quản lý.
- Chỉ đăng nhập (Bước 4) những trang web cần cho công việc.
