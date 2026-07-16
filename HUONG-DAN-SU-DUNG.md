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
4. Đăng nhập xong, quay lại cửa sổ đen **bấm Enter** để lưu.

> Làm tương tự với trang web khác nếu sau này cần agent thao tác trang đó.

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
