# PLAN.md — Personal Agent: Web UI + Server (não) + Companion App (tay)

> Tài liệu này là **nguồn sự thật duy nhất** cho việc phát triển product.
> Nó viết cho cả NGƯỜI và AGENT (Claude Code, v.v.) đọc để code chính xác:
> mọi quyết định kiến trúc, contract, dependency đã được CHỐT ở đây.
> Agent thực hiện task trong plan này KHÔNG được tự ý đổi contract/dependency —
> nếu thấy contract có vấn đề, dừng lại và hỏi người dùng trước.
>
> **v2 (2026-07-15)**: đổi kiến trúc so với v1 — tool thực thi (browser automation)
> chạy trên MÁY KHÁCH qua companion app, KHÔNG chạy trên VPS nữa. Khách vào web
> bằng invite link (không nhập key), ghép máy bằng pairing code 6 số.

---

## 0. Cách dùng tài liệu này

- **Mục 1-4** là bộ khung đã chốt (kiến trúc, dependencies, contracts, luồng chạy) — đọc TRƯỚC KHI code bất kỳ phase nào.
- **Mục 5-9** là hướng dẫn từng phase, làm theo thứ tự. Mỗi phase có: mục tiêu, file tạo/sửa, các bước, Definition of Done, cách verify.
- **Mục 10** là backlog — KHÔNG làm trước khi Phase 0-4 xong.
- **Mục 11** là quy ước code + danh sách "cấm làm" (chống over-engineering) — bắt buộc tuân thủ.
- Khi hoàn thành 1 đầu việc, tick checkbox `[x]` trong phase tương ứng và commit.

---

## 1. Mục tiêu sản phẩm & phạm vi

### Mục tiêu
Biến agent framework hiện tại (CLI one-shot trong `agent-framework/`) thành sản phẩm gồm 3 phần:
1. **Web UI (React)**: khách mở bằng invite link, gõ yêu cầu, thấy tiến trình agent realtime. KHÔNG nhập key/không cần biết kỹ thuật.
2. **Server (FastAPI, chạy trên server Linux có sẵn của chủ dự án — 4GB RAM)**: chạy "não" — AgentLoop, LLM (DeepSeek key nằm ở đây), lịch sử hội thoại, điều phối subagent.
3. **Companion app (máy khách, Windows trước)**: chạy "tay" — browser automation (Playwright) thực thi NGAY TRÊN máy khách, dùng session đăng nhập của chính khách. Cài 1 lần, ghép với tài khoản bằng mã 6 số.

### Vì sao tool chạy trên máy khách (quyết định nền tảng của v2)
- Mật khẩu / cookie / session đăng nhập của khách **không bao giờ rời máy khách** — login làm local, server không giữ credential.
- Website thuần KHÔNG THỂ điều khiển máy khách (browser sandbox) → bắt buộc có app cài 1 lần. Đã cân nhắc browser extension nhưng chọn companion app vì tái dùng ~90% code Playwright hiện có.
- Server nhẹ đi hẳn: không Chromium trên server, chỉ FastAPI + SQLite (~200-400MB RAM).

### Quy mô đã chốt (giai đoạn này)
- **Cá nhân + vài người thử** (< 10 người). Mỗi khách = 1 invite link (chủ dự án tạo tay bằng CLI). KHÔNG có đăng ký tài khoản.
- Mỗi user tối đa **1 device** và **1 run tại 1 thời điểm**.

### Non-goals (KHÔNG làm ở giai đoạn này)
- Đăng ký/đăng nhập tự do, billing, phân quyền, nhiều device/user.
- Token-level streaming (chữ hiện dần) — chỉ stream theo EVENT.
- macOS/Linux build của companion app (Windows trước; code viết portable nhưng chỉ đóng gói Windows).
- Auto-update companion app (tester tải bản mới thủ công).
- Mobile, i18n, theme.

---

## 2. Quyết định kiến trúc đã CHỐT

| # | Quyết định | Lựa chọn | Lý do (tóm tắt) |
|---|---|---|---|
| 1 | Backend framework | **FastAPI + uvicorn** | Async native cho WebSocket, nhẹ |
| 2 | Realtime channel | **WebSocket** cho cả web client lẫn device | Chat 2 chiều; device cần kênh lệnh 2 chiều thường trực |
| 3 | Core agent giữ sync | **AgentLoop chạy sync trong thread riêng** mỗi run (trên server) | LLM client sync; async-hóa core là đập code không cần thiết |
| 4 | Bridge thread→async | **`queue.Queue` + sentinel** (event ra WS); **`concurrent.futures.Future`** (RPC tool call chờ kết quả từ device) | Stdlib, không thêm dependency |
| 5 | Thực thi tool local | **Companion app Python** (đóng gói PyInstaller), kết nối **RA** server qua WSS (không mở port trên máy khách) | Tái dùng nguyên bộ `tools/browser/`; NAT/firewall không cản kết nối chiều ra |
| 6 | Định tuyến tool | Tool `browser__*` trên server là **RPC stub**: gửi lệnh xuống device của đúng user, chờ kết quả (timeout 120s) | AgentLoop không biết tool chạy ở đâu — cùng interface `handler(**args) -> str` |
| 7 | Danh sách tool device | **Whitelist cố định** khai báo 1 nơi (spec-driven, mục 4.6). Server KHÔNG BAO GIỜ gửi lệnh shell/code tùy ý xuống device | An toàn: server bị chiếm cũng chỉ đẩy được tool trong whitelist |
| 8 | `browser__extract` | **Tách 2 nửa**: device trả markdown thô của trang (`browser__page_markdown`), server chạy LLM extraction | LLM key không được nằm trên máy khách |
| 9 | Browser trên máy khách | Khởi động **lazy** khi có tool call đầu tiên, **hiện cửa sổ (headless=false mặc định)** để khách thấy agent đang làm gì, tự đóng sau 5 phút idle | Minh bạch = niềm tin; tiết kiệm RAM máy khách |
| 10 | Login web của khách | Khách tự đăng nhập **local** qua chức năng "Đăng nhập trang web" của app (mở cửa sổ browser thật) — storage state lưu trên máy khách | Credential không bao giờ lên server; không bị web đánh dấu IP lạ |
| 11 | Auth web | **Invite link** chứa token (`/?invite=<token>`), FE lưu localStorage — khách không gõ gì | Người dùng phổ thông; đổi sang account thật sau không phá kiến trúc |
| 12 | Ghép app ↔ user | **Pairing code 6 số**: app hiện mã, khách nhập vào web. App nhận `device_token` lưu local, dùng cho mọi kết nối sau | Giống pairing TV/Zalo PC — quen thuộc |
| 13 | Frontend | **React + Vite + TypeScript + Tailwind**, build static, FastAPI serve luôn | 1 container, không CORS |
| 14 | State FE | useState/useReducer thuần. CẤM redux/zustand/react-query/router | Quy mô nhỏ |
| 15 | Database | **SQLite (stdlib `sqlite3`, WAL)** 1 file trong `DATA_DIR`. CẤM ORM/Postgres | Vài user |
| 16 | Persist | Chỉ persist messages cuối (user + assistant). Progress event ephemeral, không replay sau refresh | Chống over-engineering |
| 17 | Per-run isolation | `ToolRegistry`, `SubagentDispatcher`, `ContextManager`, `LLMClient` build MỚI mỗi run. Shared: `SkillLoader`, `DeviceHub`, `SessionStore` | Registry có state `_activated` mutable |
| 18 | Giới hạn | `MAX_CONCURRENT_RUNS=3` (toàn server), 1 run/user, `RUN_TIMEOUT_SECONDS=300`, `TOOL_CALL_TIMEOUT_SECONDS=120` | LLM-bound, không còn browser trên server |
| 19 | Deploy | **Server Linux có sẵn (4GB RAM) + Docker Compose**: `app` (python:3.12-slim — KHÔNG cần image Playwright) + `caddy` (HTTPS tự động). Cần 1 domain trỏ về server — domain nào cũng được (kể cả xấu/tạm), đổi sau dễ (xem 9.4) | Đã có server; không Chromium nên 4GB dư dả |
| 20 | `main.py` CLI | Giữ chế độ **all-in-one** (não + tay cùng máy) chạy được sau mọi phase | Công cụ debug nhanh nhất, không cần dựng server/app |

---

## 3. Bộ khung hệ thống

### 3.1 Sơ đồ kiến trúc

```
┌───────────────┐   WS /ws (JSON events)   ┌──────────────────────────────────┐
│  Web UI React │ ◄───────────────────────►│  SERVER (FastAPI, Linux 4GB)     │
│  - invite link│      GET /api/* (REST)   │  ├─ auth: invite_token /          │
│  - chat + xem │                          │  │        device_token            │
│    tiến trình │                          │  ├─ SessionStore (SQLite)         │
│  - nhập mã 6  │                          │  ├─ AgentRunner                   │
│    số pairing │                          │  │   thread(AgentLoop) → queue    │
└───────────────┘                          │  │   → WS. LLM key ở ĐÂY.         │
                                           │  └─ DeviceHub: định tuyến RPC     │
        ▲ HTTPS/WSS :443                   │      tool_call ↔ device           │
   ┌────┴────┐                             └───────────────┬──────────────────┘
   │  Caddy  │                                             │ WS /ws/device
   └─────────┘                                             │ (app kết nối RA)
                                           ┌───────────────▼──────────────────┐
                                           │  MÁY KHÁCH — Companion App        │
                                           │  (local-agent/, PyInstaller)      │
                                           │  ├─ WS client + device_token      │
                                           │  ├─ Executor: SyncBrowserTool     │
                                           │  │   (Playwright, code sẵn có)    │
                                           │  ├─ Login local (storage state)   │
                                           │  └─ BROWSER_SECRET_* local        │
                                           └──────────────────────────────────┘
                                                           │ import chung
                                           ┌───────────────▼──────────────────┐
                                           │ agent-framework/ (core hiện tại)  │
                                           └──────────────────────────────────┘
```

### 3.2 Cấu trúc repo đích

```
personal_agent/
├── PLAN.md                     # file này
├── agent-framework/            # core — sửa TỐI THIỂU (chỉ theo Phase 0)
│   ├── core/                   #   agent_loop.py, context_manager.py, llm_client.py
│   ├── tools/                  #   registry.py, tool_search.py, skill_loader.py, browser/
│   ├── subagents/              #   dispatcher.py, *.md
│   ├── skills/
│   ├── scripts/setup_browser_login.py
│   └── main.py                 # CLI all-in-one — PHẢI chạy được sau mọi phase
├── server/                     # Phase 1 — "não"
│   ├── app.py                  #   FastAPI, mount static, WS /ws + /ws/device, REST
│   ├── runner.py               #   AgentRunner: wiring per-run + thread + queue bridge
│   ├── device_hub.py           #   DeviceHub: presence + RPC tool call (mục 4.6)
│   ├── remote_tools.py         #   build ToolRegistry stub (RPC) từ BROWSER_TOOL_SPECS
│   ├── sessions.py             #   SessionStore: SQLite (users, devices, sessions, messages, runs)
│   ├── pairing.py              #   pairing code in-memory (TTL 10 phút)
│   │                           #   (auth check invite/device token gộp trong app.py — không có auth.py riêng)
│   ├── config.py               #   env vars (bảng 3.4)
│   ├── manage.py               #   CLI: add-user "Tên" → in invite link
│   ├── test_client.py          #   script test WS chat bằng tay
│   └── fake_device.py          #   device giả lập (test RPC không cần app thật)
├── local-agent/                # Phase 2 — "tay" (companion app)
│   ├── app.py                  #   entry: load config → pairing nếu chưa có token → WS loop
│   ├── executor.py             #   nhận tool_call → gọi SyncBrowserTool → trả tool_result
│   ├── pairing.py              #   flow lấy pairing code + poll device_token
│   ├── config.py               #   đọc/ghi %APPDATA%/PersonalAgent/config.json
│   ├── login_setup.py          #   menu "Đăng nhập trang web" (tái dùng logic setup_browser_login)
│   └── build.spec              #   PyInstaller spec (Windows)
├── web/                        # Phase 3 — React SPA
│   ├── src/
│   │   ├── App.tsx             #   useReducer trung tâm xử lý mọi WS event
│   │   ├── api/ws.ts           #   WS client + reconnect
│   │   ├── api/rest.ts         #   REST client + invite token (localStorage)
│   │   ├── components/         #   InviteGate, PairingPanel, DeviceBadge, Sidebar,
│   │   │                       #   ChatView (kèm MessageBubble inline), Composer,
│   │   │                       #   ProgressGroup (kèm ToolCallRow inline)
│   │   └── types.ts            #   TS types mirror event schema (4.1)
│   ├── package.json
│   └── vite.config.ts
├── docker/                     # Phase 4
│   ├── Dockerfile              #   node build web → python:3.12-slim (KHÔNG playwright)
│   ├── docker-compose.yml      #   app + caddy
│   └── Caddyfile
└── data/                       # runtime trên server, KHÔNG commit (.gitignore)
    ├── app.db
    └── memory/notes/<session_id>/
```

### 3.3 Dependencies đã chốt

**Server** (thêm vào môi trường chạy server):

| Package | Vì sao |
|---|---|
| `openai`, `pyyaml`, `python-dotenv`, `markdownify` | đã có (markdownify giờ chỉ server dùng cho extract? KHÔNG — device dùng, xem dưới) |
| `fastapi`, `uvicorn[standard]` | MỚI — web framework + ASGI (kèm websockets) |

**Companion app (`local-agent/`)**:

| Package | Vì sao |
|---|---|
| `playwright` | browser automation (code sẵn có) |
| `markdownify` | HTML → markdown ngay trên device (nửa dưới của extract) |
| `websockets` | WS client kết nối server |
| `pyinstaller` | build exe (dev-dependency) |

Lưu ý: **server KHÔNG cần playwright/markdownify** để chạy (chỉ import specs từ `registration.py` — file này phải import được mà không cần playwright, xem Phase 0.5). CLI `main.py` all-in-one thì cần đủ cả.

**CẤM thêm**: sqlalchemy/sqlmodel, celery, redis, langchain, pydantic-settings, janus, electron. Stdlib dùng: `sqlite3`, `queue`, `threading`, `asyncio`, `secrets`, `uuid`.

**Frontend (`web/package.json`)**: `react`, `react-dom`, `vite`, `typescript`, `@vitejs/plugin-react`, `tailwindcss`, `react-markdown`. **CẤM**: router, redux/zustand, react-query/swr, axios, UI kit (MUI/AntD).

### 3.4 Cấu hình

**Server — `.env` ở root:**

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DEEPSEEK_API_KEY` | (bắt buộc) | LLM key — CHỈ tồn tại trên server |
| `LLM_BASE_URL` | `https://api.deepseek.com` | |
| `LLM_MODEL` | `deepseek-chat` | |
| `DATA_DIR` | `./data` | app.db + memory/ |
| `MAX_CONCURRENT_RUNS` | `3` | semaphore toàn server |
| `RUN_TIMEOUT_SECONDS` | `300` | timeout 1 run |
| `TOOL_CALL_TIMEOUT_SECONDS` | `120` | timeout chờ device trả kết quả 1 tool call |
| `PORT` | `8000` | |

**Companion app — `%APPDATA%/PersonalAgent/config.json`** (app tự tạo lần đầu):

```jsonc
{
  "server_url": "wss://yourdomain.com",   // nhập lần đầu (hoặc hardcode default khi build)
  "device_token": "...",                   // nhận sau pairing, app tự ghi
  "device_name": "PC-cua-Long",
  "headless": false,                       // mặc định HIỆN cửa sổ browser
  "storage_state_path": "<APPDATA>/PersonalAgent/state.json",
  "secrets": {"site_password": "..."}      // thay cho BROWSER_SECRET_* env — chỉ nằm máy khách
}
```

---

## 4. Contracts cốt lõi — PHẢI tuân thủ chính xác

### 4.1 Event schema (AgentLoop phát ra, WS forward cho web FE)

Mọi event là JSON có field `type`. Field `agent` = `"main"` hoặc tên subagent. Preview cắt **tối đa 500 ký tự** (thêm `…` nếu cắt).

```jsonc
{"type": "run_started",       "run_id": "<uuid4>", "session_id": "..."}
{"type": "tool_call",         "agent": "main", "tool": "dispatch_subagent", "args_preview": "..."}
{"type": "tool_result",       "agent": "main", "tool": "dispatch_subagent", "result_preview": "..."}
{"type": "subagent_started",  "name": "browser-agent", "task": "..."}
{"type": "subagent_finished", "name": "browser-agent", "result_preview": "..."}
{"type": "llm_usage",         "agent": "main", "prompt_tokens": 123, "completion_tokens": 45}
{"type": "final_answer",      "content": "<markdown đầy đủ, KHÔNG cắt>"}
{"type": "error",             "message": "..."}
{"type": "run_finished",      "run_id": "...", "status": "ok|error|cancelled|timeout",
                              "total_prompt_tokens": 0, "total_completion_tokens": 0}
```

Quy tắc:
- `run_finished` LUÔN là event cuối của 1 run (kể cả lỗi) — sentinel đóng vòng đọc queue.
- Event trong subagent phát ra ngoài với `agent` = tên subagent — FE nhóm vào block subagent.
- `final_answer` phát TRƯỚC `run_finished`.
- Tool call browser chạy trên device vẫn phát `tool_call`/`tool_result` như thường (từ góc nhìn AgentLoop, RPC stub là 1 tool bình thường).

### 4.2 Web WebSocket protocol (`WS /ws`)

**Client → Server:**

```jsonc
{"type": "auth", "invite_token": "..."}                          // BẮT BUỘC message đầu tiên
{"type": "chat", "session_id": "<uuid>|null", "message": "..."}  // null = tạo session mới
{"type": "cancel", "run_id": "..."}
```

**Server → Client:**

```jsonc
{"type": "auth_ok", "user_name": "..."}
{"type": "auth_failed"}                                          // sau đó server ĐÓNG kết nối
{"type": "device_status", "online": true, "device_name": "..."}  // gửi ngay sau auth_ok + mỗi khi đổi
{"type": "session_created", "session_id": "...", "title": "..."}
{"type": "busy", "session_id": "..."}                            // user này đang có run chạy
// ... + toàn bộ event mục 4.1 forward nguyên văn
```

Quy tắc:
- Chưa `auth_ok` mà gửi `chat` → đóng kết nối.
- **1 user 1 run** tại 1 thời điểm (không phải chỉ per-session — vì device chỉ có 1 browser).
- `title` session = 60 ký tự đầu message đầu tiên.
- Web client rớt giữa chừng: run VẪN chạy tiếp đến xong, lưu DB. Refresh thấy kết quả cuối, mất progress (quyết định #16).

**REST** (header `X-Invite-Token`):

```
GET    /api/me                          → {user_name, device: {online, name} | null}
GET    /api/sessions                    → [{id, title, created_at}]
GET    /api/sessions/{id}/messages      → [{role, content, created_at}]
DELETE /api/sessions/{id}
POST   /api/pair/complete  {code}       → {ok, device_name}      // khách nhập mã 6 số
GET    /healthz                         → {"ok": true}            // không cần token
```

### 4.3 Pairing flow + Device WebSocket protocol

**Pairing (REST, phía app — không cần auth vì chưa có token):**

```
POST /api/device/pair/start {device_name}
     → {pairing_code: "483920", poll_token: "<uuid>"}      // code TTL 10 phút, lưu in-memory
GET  /api/device/pair/poll?poll_token=...
     → {"status": "pending"} | {"status": "paired", "device_token": "..."}
     // app poll mỗi 2s. Khi user nhập đúng code trên web (POST /api/pair/complete),
     // server tạo device gắn user đó, sinh device_token. 1 user 1 device: pair mới
     // GHI ĐÈ device cũ (token cũ vô hiệu).
```

**Device WS (`WS /ws/device`)** — app kết nối RA, giữ thường trực, reconnect backoff (2s→4s→8s, max 30s):

```jsonc
// App → Server
{"type": "hello", "device_token": "..."}                 // BẮT BUỘC message đầu tiên
{"type": "tool_result", "call_id": "...", "result": "<string>"}
{"type": "pong"}

// Server → App
{"type": "hello_ok"} | {"type": "hello_failed"}          // failed → app xóa token, quay lại pairing
{"type": "tool_call", "call_id": "<uuid>", "tool": "browser__navigate", "args": {...}}
{"type": "ping"}                                         // mỗi 30s; 2 lần không pong → coi như offline
```

Quy tắc:
- `result` LUÔN là string (đúng contract `Tool.handler -> str` sẵn có). App bắt mọi exception, trả string lỗi actionable — KHÔNG bao giờ để WS chết vì 1 tool lỗi.
- Device disconnect giữa chừng → server fail toàn bộ RPC đang chờ của device đó với message rõ ràng ("app trên máy khách mất kết nối").
- Server CHỈ gửi tool nằm trong whitelist `BROWSER_TOOL_SPECS` (mục 4.6). App cũng validate lại tên tool trước khi thực thi (defense in depth).

### 4.4 DB schema (SQLite, `CREATE TABLE IF NOT EXISTS` khi khởi động, WAL mode)

```sql
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,            -- uuid4
    name         TEXT NOT NULL,
    invite_token TEXT NOT NULL UNIQUE,        -- secrets.token_urlsafe(24)
    created_at   TEXT NOT NULL                -- ISO 8601 UTC
);
CREATE TABLE IF NOT EXISTS devices (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL UNIQUE REFERENCES users(id),   -- 1 user 1 device
    device_token TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    last_seen    TEXT,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL,                 -- 'user' | 'assistant'
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id                      TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL,
    status                  TEXT NOT NULL,    -- ok|error|cancelled|timeout
    total_prompt_tokens     INTEGER DEFAULT 0,
    total_completion_tokens INTEGER DEFAULT 0,
    created_at              TEXT NOT NULL
);
```

- sqlite3 mở `check_same_thread=False` + 1 `threading.Lock` quanh mọi write.
- Pairing code KHÔNG lưu DB — dict in-memory với TTL (mất khi restart server là chấp nhận được).

### 4.5 Luồng chạy chính end-to-end (mỗi chat message)

```
1. FE gửi {"type":"chat", session_id, message} qua WS (đã auth_ok)
2. app.py: session_id null → SessionStore.create(user_id) → gửi session_created
3. Check user không có run đang active (dict in-RAM) — có → busy
4. SessionStore.add_message(session_id, "user", message)
5. runner.start_run(user, session_id, message):
   a. history = SessionStore.get_messages(session_id)[:-1]   (KHÔNG gồm system)
   b. Tạo run_id, queue.Queue, threading.Event (cancel), deadline = now + RUN_TIMEOUT
   c. Spawn thread (acquire semaphore RUNS bên trong thread):
      - build per-run: LLMClient, ToolRegistry (ecom + framework), ContextManager
        (notes = DATA_DIR/memory/notes/<session_id>/main.md),
        SubagentDispatcher(local_tools_factory = lambda: remote_tools.build(device_hub, user_id))
      - AgentLoop(...).run(message, history=history, on_event=q.put, should_stop=...)
      - q.put(final_answer) → q.put(run_finished sentinel)
   d. Async task: while True: ev = await asyncio.to_thread(q.get) → ws.send_json(ev)
      → ev.type == "run_finished" → break
      (web WS đã đóng thì bỏ qua send, vẫn đọc queue đến sentinel)
6. final_answer → SessionStore.add_message(session_id, "assistant", content)
7. run_finished → ghi bảng runs, xóa khỏi active dict
8. cancel: set Event → should_stop() True ở đầu iteration → dừng lịch sự
9. timeout: should_stop bao cả time.monotonic() > deadline
```

### 4.6 Luồng tool local (RPC qua device) — thay thế "browser trên server"

**Spec-driven tool list** — 1 nguồn khai báo duy nhất trong `tools/browser/registration.py`:

```python
# BROWSER_TOOL_SPECS: list[dict] — mỗi entry:
# {"name": "browser__navigate", "description": "...", "parameters": {...json schema...},
#  "method": "navigate",          # tên method trên SyncBrowserTool
#  "defer_loading": False}
# Tool list (giữ nguyên mô tả/schema hiện có):
#   browser__navigate, browser__get_state, browser__click, browser__type,
#   browser__extract,                    ← đặc biệt, xem dưới
#   browser__search, browser__go_back, browser__scroll, browser__press_key,
#   browser__wait, browser__type_sensitive
# + tool NỘI BỘ device (không cho agent thấy): browser__page_markdown
```

- **CLI all-in-one** (`main.py`): `build_browser_registry(sync_browser, secrets)` loop specs, bind handler = method local. Như hiện tại.
- **Server**: `server/remote_tools.py` loop CÙNG specs, bind handler = RPC stub:
  ```
  handler(**args) → device_hub.call_tool(user_id, tool_name, args, timeout=TOOL_CALL_TIMEOUT)
  ```
  Riêng `browser__extract` handler server-side là composite:
  ```
  1. md_json = device_hub.call_tool(user_id, "browser__page_markdown", {start_from_char})
     → JSON string {"url", "markdown" (≤100k chars), "truncated", "next_start"}
  2. return extract_from_markdown(md_json, query, llm)   # LLM chạy trên server
  ```
- **`extract_action.py` tách 2 hàm** (Phase 0): `page_to_markdown(page, start_from_char) -> dict`
  (device, không cần LLM) và `extract_from_markdown(payload, query, llm) -> str` (server).
  `SyncBrowserTool.extract()` cũ = ghép 2 hàm in-process (CLI vẫn chạy).
- **DeviceHub (server)**: giữ `{user_id: DeviceConnection}`. `call_tool()` là method SYNC
  (gọi từ agent thread): tạo `concurrent.futures.Future` theo `call_id`, schedule send qua
  `asyncio.run_coroutine_threadsafe(ws.send_json(...), main_loop)`, `future.result(timeout)`.
  WS receive loop của device resolve future theo `call_id`. Device offline/disconnect →
  future fail → handler trả string lỗi actionable cho LLM.
- **Dispatcher**: subagent có `needs_device: true` (frontmatter, thay `needs_browser`) →
  trước khi dispatch, gọi `local_tools_factory()`; factory raise `RuntimeError` nếu device
  offline → dispatcher TRẢ NGAY string: "Máy của khách đang offline — yêu cầu khách mở
  app Personal Agent rồi thử lại." (không tốn LLM call nào).
- **Device app**: nhận `tool_call` → `executor.py` map tool name → method của SyncBrowserTool
  local (khởi động browser lazy ở call đầu, idle 5 phút tự đóng — `threading.Timer` reset
  mỗi call). `browser__type_sensitive` đọc secrets từ config.json local.

### 4.7 Chữ ký hàm đã chốt (Phase 0 — thay đổi core DUY NHẤT được phép)

```python
# core/agent_loop.py
class AgentLoop:
    def run(
        self,
        user_message: str,
        history: list[dict] | None = None,        # messages cũ [{"role","content"},...], KHÔNG gồm system
        on_event: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        agent_name: str = "main",                  # gắn vào field "agent" của mọi event
    ) -> str: ...

# subagents/dispatcher.py
@dataclass
class SubagentConfig:
    ...                                            # field cũ giữ nguyên
    needs_device: bool = False                     # frontmatter, mặc định False

class SubagentDispatcher:
    def __init__(self, llm, full_registry, skills, notes_dir,
                 local_tools_factory: Callable[[], ToolRegistry] | None = None): ...
                 # factory trả registry tool local (browser). CLI: bind SyncBrowserTool local.
                 # Server: bind RPC stubs. Raise RuntimeError nếu device offline.
    def dispatch(self, subagent_name: str, task: str,
                 on_event: Callable[[dict], None] | None = None,
                 should_stop: Callable[[], bool] | None = None) -> str: ...

# tools/browser/registration.py
BROWSER_TOOL_SPECS: list[dict]                     # nguồn khai báo duy nhất (4.6)
def build_browser_registry(sync_browser, sensitive_data) -> ToolRegistry   # giữ nguyên hành vi

# tools/browser/extract_action.py
def page_to_markdown(page, start_from_char: int = 0) -> dict               # async, chạy device
def extract_from_markdown(payload: dict, query: str, llm) -> str           # sync, chạy server
```

---

## 5. Phase 0 — Refactor core cho chế độ phân tán

**Mục tiêu**: core phát event, multi-turn, cancel/timeout, tool spec-driven, extract tách 2 nửa. `main.py` CLI all-in-one vẫn chạy như cũ.

**File sửa**: `core/agent_loop.py`, `subagents/dispatcher.py`, `tools/browser/registration.py`, `tools/browser/extract_action.py`, `tools/browser/browser_tool.py` (thêm method `page_markdown`), `subagents/browser-agent.md`, `main.py`.

### Các bước

- [x] **0.1** `AgentLoop.run()` theo chữ ký 4.7:
  - `history` chèn giữa system prompt và user message mới.
  - `on_event` mặc định no-op. Phát: `tool_call` (trước execute), `tool_result` (sau), `llm_usage` (sau mỗi lần gọi LLM, đọc `response.raw.usage`, bỏ qua nếu None). `run_started`/`run_finished`/`final_answer`/`error` do RUNNER phát, KHÔNG phải AgentLoop.
  - `should_stop` check ĐẦU mỗi iteration → True thì return `"(run đã dừng: hủy hoặc quá thời gian)"`.
  - Helper `_preview(text) -> str` cắt 500 ký tự, đặt trong file này.
- [x] **0.2** `SubagentDispatcher` theo 4.7: đọc `needs_device` từ frontmatter; `dispatch()` phát `subagent_started/finished`, truyền `on_event` + `should_stop` xuống sub_loop (`agent_name=subagent_name`); luồng `local_tools_factory` đúng 4.6 (bắt RuntimeError → trả message offline).
- [x] **0.3** `registration.py`: refactor thành `BROWSER_TOOL_SPECS` + `build_browser_registry` loop specs. **File phải import được khi KHÔNG cài playwright** (không import playwright ở module level — specs là dict thuần; chỉ type hint dạng string).
- [x] **0.4** `extract_action.py`: tách `page_to_markdown` / `extract_from_markdown` (4.7). `ExtractAction.extract` cũ giữ lại = ghép 2 hàm (backward compat cho CLI).
- [x] **0.5** `browser_tool.py`: thêm method `page_markdown(start_from_char=0) -> str` (JSON string của `page_to_markdown`) vào `BrowserTool` + `SyncBrowserTool`.
- [x] **0.6** `browser-agent.md`: frontmatter thêm `needs_device: true`.
- [x] **0.7** `main.py`: wiring theo API mới — dispatcher nhận `local_tools_factory` bind SyncBrowserTool local; in event ra console dạng `[event] {...}` để CLI làm công cụ debug event stream.

### Definition of Done
- `python agent-framework/main.py`: task "Kiểm tra đơn SA-00123" chạy, console in event stream đầy đủ (tool_call → subagent_started → ... → kết quả).
- Gọi `run()` lần 2 với `history` → agent nhớ ngữ cảnh lượt trước.
- Task browser demo qua CLI chạy được; `browser__extract` vẫn hoạt động (đường ghép 2 hàm).
- `python -c "from tools.browser.registration import BROWSER_TOOL_SPECS"` chạy được trong venv KHÔNG có playwright.

---

## 6. Phase 1 — Server (não)

**Mục tiêu**: WS web + WS device + pairing + RPC routing chạy đúng contract mục 4, test được bằng script (chưa cần FE/app đóng gói).

**File tạo**: toàn bộ `server/` (mục 3.2).

### Các bước

- [x] **1.1** `config.py`: dataclass đọc env bảng 3.4, fail sớm nếu thiếu biến bắt buộc.
- [x] **1.2** `sessions.py`: `SessionStore` theo schema 4.4 — method: `create_user(name)`, `get_user_by_invite(token)`, `upsert_device(user_id, name) -> device_token`, `get_device(user_id)`, `get_user_by_device_token(token)`, `create_session/list/get_messages/add_message/delete`, `record_run`.
- [x] **1.3** `manage.py`: `python -m server.manage add-user "Tên"` → tạo user, in `https://<domain>/?invite=<token>`. Thêm `list-users`.
- [x] **1.4** `pairing.py`: dict in-memory `{code: {device_name, poll_token, expires, user_id|None, device_token|None}}`, TTL 10 phút, code = 6 chữ số `secrets.randbelow`.
- [x] **1.5** `device_hub.py`: `DeviceHub` theo 4.6 — `register/unregister/is_online/call_tool` + ping 30s + fail pending futures khi disconnect + callback `on_presence_change(user_id)` để app.py đẩy `device_status` cho web WS của user đó.
- [x] **1.6** `remote_tools.py`: build ToolRegistry stub từ `BROWSER_TOOL_SPECS` (trừ `page_markdown` không expose cho agent; `extract` là composite theo 4.6).
- [x] **1.7** `runner.py`: `AgentRunner` theo 4.5 — active dict theo `user_id`, semaphore, timeout, cancel.
- [x] **1.8** `app.py`: lifespan (config, store, hub, skills); `WS /ws` (protocol 4.2); `WS /ws/device` (protocol 4.3); REST 4.2 + pairing 4.3; mount `web/dist` nếu tồn tại; import path fix: `sys.path.insert(0, str(ROOT / "agent-framework"))` (KHÔNG đổi tên thư mục, KHÔNG làm package).
- [x] **1.9** `test_client.py`: connect, auth bằng invite token, gửi chat, in mọi event đến `run_finished`. (Được phép cài `websockets` làm dev-dependency.)

### Definition of Done
- `uvicorn server.app:app` chạy; `manage.py add-user` tạo được user.
- `test_client.py "Kiểm tra đơn SA-00123"` (task KHÔNG cần device) in đủ event + kết quả; câu 2 cùng session nhớ ngữ cảnh; 2 client cùng user → client 2 nhận `busy`.
- Task cần browser khi CHƯA có device online → agent trả lời "máy khách offline, mở app..." (không crash, không tốn tool call).
- Pairing flow test bằng curl/httpie: start → complete (invite token) → poll trả device_token.
- Cancel + timeout hoạt động; sai invite token → `auth_failed`.

---

## 7. Phase 2 — Companion app (tay)

**Mục tiêu**: app Python chạy trên máy khách: pairing lần đầu, kết nối WS thường trực, thực thi tool browser local, login local. Cuối phase đóng gói PyInstaller.

**File tạo**: toàn bộ `local-agent/` (mục 3.2).

### Các bước

- [x] **2.1** `config.py`: đọc/ghi `%APPDATA%/PersonalAgent/config.json` theo 3.4 (dùng `os.environ["APPDATA"]`, fallback `~/.personal-agent/` cho non-Windows).
- [x] **2.2** `pairing.py`: chưa có `device_token` → hỏi `server_url` (input console, default hardcode), POST pair/start, **in mã 6 số to rõ** + hướng dẫn "Nhập mã này vào trang web", poll 2s tới khi paired → lưu token.
- [x] **2.3** `executor.py`: map `tool_name → method` từ `BROWSER_TOOL_SPECS` + `browser__page_markdown`; SyncBrowserTool khởi động **lazy** call đầu (llm=None, headless theo config, storage_state theo config), idle timer 5 phút tự `stop()`; mọi exception → trả string lỗi actionable; validate tool name thuộc whitelist.
- [x] **2.4** `app.py`: vòng đời chính — config → pairing nếu cần → WS connect (`hello`) → loop nhận `tool_call`/`ping` → chạy tool trong thread pool size 1 (tool browser tuần tự) → gửi `tool_result`. Reconnect backoff 2s→4s→8s (max 30s). `hello_failed` → xóa token → quay lại pairing. Console in log thân thiện ("Đã kết nối", "Đang chạy: mở trang X...").
- [x] **2.5** `login_setup.py`: menu console khi chạy `app.py --login <url>`: mở browser visible (dùng SyncBrowserTool + storage_state config), khách tự đăng nhập, Enter để lưu state. (Tái dùng logic `scripts/setup_browser_login.py`, đổi đường dẫn theo config app.)
- [x] **2.6** Import chung: `local-agent/` import `agent-framework/` bằng `sys.path.insert` (giống server). PyInstaller spec phải gom cả 2 thư mục.
- [x] **2.7** `build.spec` + hướng dẫn build: PyInstaller onedir (KHÔNG onefile — Playwright cần cấu trúc thư mục), console app. Lần chạy đầu app tự chạy `playwright install chromium` nếu chưa có (check `~/AppData/Local/ms-playwright`). Ghi rõ README: exe chưa ký → SmartScreen cảnh báo, tester bấm "Run anyway" (chấp nhận ở quy mô này).

### Definition of Done
- Máy dev: chạy `python local-agent/app.py` (chưa đóng gói) + server local + test_client: task "vào duckduckgo tìm giá bitcoin" chạy **end-to-end xuyên 3 tiến trình** (test_client → server → app → browser bật lên → kết quả về test_client).
- `browser__extract` end-to-end: device trả markdown, server LLM extract, agent dùng được kết quả.
- Tắt app giữa run → tool call fail với message rõ ràng, agent trả lời tử tế, server không crash. Mở lại app → tự reconnect, `device_status online` đẩy về web WS.
- Browser tự đóng sau 5 phút idle. Bản build PyInstaller chạy được trên máy Windows sạch (không cài Python).

---

## 8. Phase 3 — Web UI (React)

**Mục tiêu**: giao diện khách dùng: vào bằng invite link, pairing device, chat + tiến trình realtime.

**File tạo**: toàn bộ `web/`.

### Các bước

- [x] **3.1** Scaffold: `npm create vite@latest web -- --template react-ts` + Tailwind + `react-markdown`. KHÔNG thêm gì khác.
- [x] **3.2** `types.ts`: mirror event schema 4.1 + protocol 4.2 thành TS types.
- [x] **3.3** `api/ws.ts`: WS client — đọc `?invite=` từ URL → lưu localStorage → xóa khỏi URL (`history.replaceState`); auth khi open; auto-reconnect backoff (1s→2s→4s, max 10s); expose `onEvent`. *(Thực tế: phần đọc `?invite=`/localStorage nằm trong `api/rest.ts` — `resolveInviteToken()`; `ws.ts` chỉ lo WS + auth + reconnect.)*
- [x] **3.4** Components (Tailwind tự viết): *(Thực tế: `MessageBubble` inline trong `ChatView.tsx`, `ToolCallRow` inline trong `ProgressGroup.tsx` — không tách file riêng.)*
  - `InviteGate`: không có token trong localStorage lẫn URL → màn hình "Liên hệ để nhận link mời" (+ ô dán link dự phòng). Token sai (`auth_failed`) → xóa token, hiện lại màn này.
  - `DeviceBadge`: góc màn hình — chấm xanh "Máy đã kết nối: <tên>" / đỏ "Máy chưa kết nối" (từ `device_status`).
  - `PairingPanel`: hiện khi user chưa có device hoặc bấm "Ghép máy mới": hướng dẫn tải app + ô nhập mã 6 số → POST `/api/pair/complete` → cập nhật badge.
  - `Sidebar`: list sessions (REST), New chat, xóa session.
  - `ChatView`: 3 loại item — user message, assistant message (react-markdown), `ProgressGroup`.
  - `ProgressGroup`: gom event 1 run — mỗi `tool_call` 1 dòng `ToolCallRow` (spinner → ✓ khi có `tool_result`; click mở args/result preview); event `agent != "main"` nhóm vào sub-block `🤖 <subagent>`; có `final_answer` → group tự thu gọn.
  - `Composer`: textarea, Enter gửi / Shift+Enter xuống dòng, disable khi đang chạy, nút "Dừng" (gửi `cancel`).
- [x] **3.5** State: 1 `useReducer` trong `App.tsx` xử lý mọi WS event. Không context lồng nhau.
- [x] **3.6** UX bắt buộc: auto-scroll khi có event mới (trừ khi user đang cuộn lên); chỉ báo kết nối WS; khi task cần device mà badge đỏ → banner nhắc mở app.
- [x] **3.7** Build: `npm run build` → `web/dist`; xác nhận FastAPI serve, WS cùng origin OK.

### Definition of Done
- Flow trọn vẹn trên máy dev: mở link invite → pairing với app → chat "tìm giá bitcoin" → thấy từng tool call hiện realtime trong block browser-agent, cửa sổ Chrome bật lên trên máy, kết quả markdown hiện ra.
- Refresh: history load từ REST, progress cũ mất (đúng thiết kế). `npm run build` + mở qua port 8000: chạy không cần dev server.

---

## 9. Phase 4 — Docker hóa + deploy lên server Linux có sẵn

**Mục tiêu**: `docker compose up -d` trên server Linux có sẵn (4GB RAM) → product chạy trên domain HTTPS. Server KHÔNG cần Chromium → image nhẹ.

**File tạo**: `docker/Dockerfile`, `docker/docker-compose.yml`, `docker/Caddyfile`, `.env.example` root, `.dockerignore` root (chặn secret/.venv/node_modules lọt vào image), cập nhật `.gitignore` (`data/` đã có sẵn, thêm `docker/.env`).

### Các bước

- [x] **4.1** `Dockerfile` multi-stage:
  ```dockerfile
  FROM node:20-slim AS web
  WORKDIR /build
  COPY web/package*.json ./
  RUN npm ci
  COPY web/ ./
  RUN npm run build

  FROM python:3.12-slim
  WORKDIR /app
  COPY agent-framework/ agent-framework/
  COPY server/ server/
  COPY --from=web /build/dist web/dist
  RUN pip install --no-cache-dir fastapi "uvicorn[standard]" openai pyyaml python-dotenv markdownify
  CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
  (KHÔNG cài playwright trên server — Phase 0.3 đã đảm bảo import specs không cần nó.)
- [x] **4.2** `docker-compose.yml`: `app` (build, env_file `.env`, volume `./data:/app/data`, restart unless-stopped) + `caddy` (caddy:2, ports 80/443, volume Caddyfile + caddy_data). *(Đường dẫn trong compose viết tương đối thư mục `docker/` — `../.env`, `../data`.)*
- [x] **4.3** `Caddyfile`: `{$DOMAIN} { reverse_proxy app:8000 }` — domain truyền qua env `DOMAIN` (đặt trong `docker/.env` khi deploy, mặc định `http://localhost` để test local không cần cấu hình). Caddy tự lo Let's Encrypt (WS proxy tự động).
- [x] **4.4** Checklist server (ghi vào README):
  1. Dùng server Linux có sẵn (4GB RAM — dư dả vì không còn Chromium trên server).
  2. Cài docker + compose plugin; user thường; tắt SSH password.
  3. Trỏ DNS A record của domain → IP server. **Domain nào cũng được** (kể cả domain xấu/tạm — chốt sau). Đổi domain về sau chỉ cần: sửa `Caddyfile` + DNS + `server_url` trong config app của khách (hoặc build lại app với default mới) — không đụng code.
  4. Clone repo, tạo `.env`, `docker compose -f docker/docker-compose.yml up -d --build`.
  5. ufw: chỉ mở 22, 80, 443.
  6. `docker compose exec app python -m server.manage add-user "Tên"` → gửi invite link cho tester.
- [ ] **4.5** Companion app build trỏ `server_url` mặc định = `wss://<domain>`; smoke test: pairing + 1 task browser end-to-end từ máy khách thật qua Internet.
  - *Hiện trạng 2026-07-16: server đã deploy tại VPS `103.72.56.204` (Ubuntu 24.04), CHƯA có domain — đang chạy HTTP qua IP (`DOMAIN=http://103.72.56.204` trong `docker/.env` trên server). Smoke test pairing + task browser qua Internet đã PASS (app chạy từ source trỏ `ws://103.72.56.204`). Còn lại khi có domain: trỏ DNS → sửa `docker/.env` → restart caddy (HTTPS tự động) → build exe với default `wss://<domain>`.*

### Definition of Done
- Local: `docker compose up -d` → `http://localhost` đầy đủ chức năng (trừ pairing cần app).
- Trên server thật: `https://<domain>` chat được; app trên máy Windows khác pairing + chạy task browser thành công qua Internet; container tự restart khi reboot.

---

## 10. Phase 5 — Backlog (CHỈ làm sau khi Phase 4 xong, có người dùng thật)

Theo thứ tự ưu tiên:
1. **Xác nhận trên app cho hành động nhạy cảm** (type_sensitive, thanh toán...): app hiện prompt Yes/No trước khi thực thi — tăng trần an toàn của kênh server→device.
2. Rate limit theo user (đếm bảng `runs`); giới hạn token/ngày.
3. Tray app (pystray) thay console; auto-start cùng Windows; auto-update.
4. Trang admin `/admin`: usage theo user/ngày, danh sách device online.
5. Token streaming câu trả lời cuối.
6. Replay progress sau refresh (persist events).
7. Nhiều device/user; chọn device khi chat.
8. macOS build; ký code (code signing) để hết cảnh báo SmartScreen.
9. Tài khoản email thật thay invite link.

---

## 11. Quy ước code & danh sách CẤM (chống over-engineering)

### Quy ước
- **Style theo code hiện có**: docstring/comment tiếng Việt giải thích "vì sao", type hints đầy đủ, `from __future__ import annotations`.
- Core `agent-framework/` sửa **tối thiểu** — chỉ những gì Phase 0 liệt kê. Logic server trong `server/`, logic app trong `local-agent/`.
- `main.py` CLI all-in-one phải chạy được sau MỌI phase (công cụ debug nhanh nhất — não + tay cùng tiến trình, không cần server/app/web).
- Lỗi trả về cho LLM/user phải **actionable** (triết lý sẵn có trong `registry.py`).
- **Phân giới secrets** (bất di bất dịch):
  - Server giữ: `DEEPSEEK_API_KEY`, invite tokens, device tokens.
  - Máy khách giữ: mật khẩu web (storage state), `secrets` trong config.json.
  - KHÔNG BAO GIỜ: credential khách lên server; LLM key xuống máy khách; secret xuất hiện trong event/log/DB/response.
- Mỗi phase = chuỗi commit rõ ràng, message tiếng Việt ngắn gọn.

### CẤM (nếu thấy "cần", dừng lại hỏi người dùng trước)
- ❌ Thêm dependency ngoài danh sách mục 3.3.
- ❌ ORM, Postgres, Redis, Celery, message queue, Electron.
- ❌ Async-hóa `AgentLoop`/`LLMClient` (giữ sync + thread).
- ❌ Gửi lệnh shell/code tùy ý từ server xuống device — CHỈ tool trong `BROWSER_TOOL_SPECS`.
- ❌ Đưa LLM key / gọi LLM trực tiếp từ companion app.
- ❌ Router/state-library/UI-kit phía React.
- ❌ Auth framework (OAuth, JWT) — invite token + device token là đủ giai đoạn này.
- ❌ Abstract hóa "cho tương lai" (plugin system, multi-tenant...) khi chưa có nhu cầu thật.
- ❌ Đổi tên thư mục `agent-framework/` hay biến nó thành package cài đặt được.
- ❌ Tự đổi event schema / WS protocol / DB schema / tool specs — 4 contract này cố định; muốn đổi = sửa PLAN.md trước, code sau.
