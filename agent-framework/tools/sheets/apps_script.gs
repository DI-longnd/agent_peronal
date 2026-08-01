/**
 * Personal Agent — điểm nhận dữ liệu cho Google Sheet của khách.
 *
 * Đây là NỬA CHẠY TRÊN GOOGLE của tính năng đẩy đơn hàng lên Sheet.
 * Nửa còn lại: agent-framework/tools/sheets/client.py (chạy trên máy khách).
 *
 * Giữ file này trong repo vì nó không nằm ở đâu khác — mã đã deploy chỉ tồn tại
 * bên trong tài khoản Google của từng khách. Mất file này là phải viết lại từ đầu.
 *
 * ─── CÀI CHO MỘT KHÁCH MỚI ────────────────────────────────────────────────────
 *  1. Mở Google Sheet của khách → Tiện ích mở rộng → Apps Script
 *  2. Xoá `function myFunction() {}` có sẵn, dán toàn bộ file này vào
 *  3. Đổi TOKEN thành chuỗi ngẫu nhiên MỚI cho khách đó
 *     (tạo bằng: python -c "import secrets; print('pa-'+secrets.token_urlsafe(24))")
 *  4. Ctrl+S để lưu
 *  5. Triển khai → Tuỳ chọn triển khai mới → bánh răng ⚙ → Ứng dụng web
 *       Thực thi với tư cách : Tôi
 *       Ai có quyền truy cập : Bất kỳ ai
 *  6. Triển khai → cấp quyền. Màn hình "Google chưa xác minh ứng dụng này" là BÌNH
 *     THƯỜNG (mã của chính bạn, chưa gửi Google duyệt): Nâng cao → Chuyển đến ...
 *  7. Copy URL kết thúc bằng /exec, điền vào config.json của app trên máy khách:
 *       "sheet_webapp_url": "https://script.google.com/macros/s/.../exec",
 *       "sheet_token": "<đúng chuỗi TOKEN ở trên>"
 *
 *  Kiểm tra: mở URL /exec bằng trình duyệt, phải thấy "Personal Agent ... OK".
 *
 * ─── HAI ĐIỀU HAY LÀM MẤT THỜI GIAN ───────────────────────────────────────────
 *  • Sửa mã xong chỉ Ctrl+S là CHƯA ĂN. Phải Triển khai → Quản lý triển khai →
 *    sửa → Phiên bản mới, nếu không URL cũ vẫn chạy mã cũ.
 *  • URL /dev chỉ chạy cho chủ script. Agent gọi vào sẽ hỏng. Phải là /exec.
 *
 * ─── BẢO MẬT ──────────────────────────────────────────────────────────────────
 *  "Ai có quyền truy cập: Bất kỳ ai" chỉ nói về ai được GỌI web app, không phải ai
 *  đọc được sheet. Script chạy với tư cách chủ sheet, nên SHEET NÊN ĐẶT RIÊNG TƯ —
 *  dữ liệu đơn hàng có tên, số điện thoại và địa chỉ người mua. Đã kiểm chứng
 *  01-08-2026: sheet đặt "Bị hạn chế" thì người lạ đọc không được (HTTP 401) mà
 *  agent vẫn ghi được bình thường.
 *
 *  TOKEN là thứ duy nhất chặn người lạ ghi đè. Lộ URL + token thì họ ghi đè được
 *  đúng sheet này — không đọc được Gmail/Drive, không chạm được tài khoản Google.
 *  Mỗi khách một token riêng.
 */

const TOKEN = 'doi-thanh-chuoi-rieng-cua-tung-khach';

function doGet() {
  // Mở URL bằng trình duyệt sẽ thấy dòng này -> biết bản deploy còn sống.
  return ContentService.createTextOutput('Personal Agent sheet endpoint: OK');
}

function doPost(e) {
  const out = (o) => ContentService
      .createTextOutput(JSON.stringify(o))
      .setMimeType(ContentService.MimeType.JSON);
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.token !== TOKEN) return out({ok: false, error: 'sai token'});
    if (!body.csv) return out({ok: false, error: 'thieu noi dung csv'});

    // parseCsv là hàm sẵn có của Google: đọc đúng dấu phẩy và xuống dòng NẰM TRONG
    // ô có dấu ngoặc kép. Đây là lý do dùng CSV chứ không dán TSV — file đơn hàng
    // TikTok có cột Buyer Message và Detail Address, khách xuống dòng trong đó là
    // mọi cách tách chuỗi thủ công đều vỡ bảng mà không có dấu hiệu báo.
    const rows = Utilities.parseCsv(body.csv);
    if (!rows.length) return out({ok: false, error: 'csv rong'});

    // setValues đòi bảng chữ nhật; CSV thật có thể thiếu ô ở cuối dòng.
    const width = Math.max.apply(null, rows.map(r => r.length));
    const grid = rows.map(r => r.concat(new Array(width - r.length).fill('')));

    const sh = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    sh.clear();                                   // ghi đè: xoá sạch dữ liệu cũ
    sh.getRange(1, 1, grid.length, width).setValues(grid);
    sh.setFrozenRows(1);                          // ghim dòng tiêu đề

    return out({ok: true, rows: grid.length - 1, cols: width,
                sheet: sh.getName(),
                at: Utilities.formatDate(new Date(), 'Asia/Ho_Chi_Minh',
                                         'dd/MM/yyyy HH:mm:ss')});
  } catch (err) {
    return out({ok: false, error: String(err)});
  }
}
