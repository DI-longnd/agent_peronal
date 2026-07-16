# Personal Agent

Agent cá nhân gồm 3 phần (kiến trúc chi tiết: [PLAN.md](PLAN.md)):

- **`server/`** — "não": FastAPI trên server Linux, chạy AgentLoop + LLM (DeepSeek key ở đây), điều phối tool xuống máy khách qua WebSocket.
- **`local-agent/`** — "tay": companion app trên máy khách (Windows), thực thi browser automation (Playwright) bằng session đăng nhập của chính khách. Ghép với tài khoản bằng mã 6 số.
- **`web/`** — React SPA: khách vào bằng invite link, chat + xem tiến trình agent realtime.

`agent-framework/` là core dùng chung; `agent-framework/main.py` là CLI all-in-one (não + tay cùng máy) — công cụ debug nhanh nhất, chạy được độc lập không cần server/app/web.

## Chạy dev (không Docker)

```bash
# Server (cần .env ở root hoặc agent-framework/.env chứa DEEPSEEK_API_KEY)
agent-framework/.venv/Scripts/python -m uvicorn server.app:app --port 8000

# Tạo user + invite link
agent-framework/.venv/Scripts/python -m server.manage add-user "Tên"

# Companion app (máy khách)
agent-framework/.venv/Scripts/python local-agent/app.py

# Web: đã build sẵn vào web/dist (FastAPI serve luôn). Sửa FE thì:
cd web && npm run dev        # dev server, proxy /api + /ws sang :8000
cd web && npm run build      # build lại dist
```

## Deploy lên server Linux (Docker)

Checklist (PLAN.md mục 9):

1. Server Linux ~4GB RAM (không cần Chromium — tool chạy trên máy khách).
2. Cài docker + compose plugin; dùng user thường; tắt SSH password.
3. Trỏ DNS A record của domain → IP server. Domain nào cũng được — đổi sau chỉ cần sửa `docker/.env` + DNS + `server_url` trong config app của khách.
4. Clone repo, tạo config:
   ```bash
   cp .env.example .env                      # điền DEEPSEEK_API_KEY
   echo "DOMAIN=yourdomain.com" > docker/.env  # Caddy tự lo HTTPS
   docker compose -f docker/docker-compose.yml up -d --build
   ```
5. Firewall (ufw): chỉ mở 22, 80, 443.
6. Tạo invite link cho tester:
   ```bash
   docker compose -f docker/docker-compose.yml exec app python -m server.manage add-user "Tên"
   ```

Test local không cần domain: bỏ qua `docker/.env` → chạy ở `http://localhost`.

Dữ liệu (SQLite + notes) nằm ở `./data` trên host — backup chỉ cần copy thư mục này.

## Companion app cho khách

- Build: xem `local-agent/build.spec` (PyInstaller onedir, Windows). Build với `server_url` mặc định = `wss://yourdomain.com`.
- Exe chưa ký code → SmartScreen cảnh báo: bấm **More info → Run anyway** (chấp nhận ở quy mô tester hiện tại).
- Lần chạy đầu app tự tải Chromium (~150MB) và hiện **mã ghép 6 số** — nhập mã vào trang web (nút "Ghép máy") là xong.
- Đăng nhập trước các trang web cần thiết: `PersonalAgent.exe --login <url>` (mở browser thật, đăng nhập xong bấm Enter — session chỉ lưu trên máy khách, không bao giờ lên server).
