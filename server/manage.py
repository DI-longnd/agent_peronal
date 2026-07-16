"""
CLI quản trị (chạy trên server): tạo user + invite link, xem danh sách, thu hồi.

    python -m server.manage add-user "Tên Khách"
    python -m server.manage list-users
    python -m server.manage revoke-user <tên hoặc invite_token>
"""

from __future__ import annotations
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from server.config import load_config
from server.sessions import SessionStore


def _find_user(store: SessionStore, key: str) -> dict | None:
    """Tìm theo invite_token trước (không nhầm được), rồi theo tên (phải duy nhất)."""
    user = store.get_user_by_invite(key)
    if user:
        return user
    matches = [u for u in store.list_users() if u["name"] == key]
    if len(matches) > 1:
        print(f"Có {len(matches)} user cùng tên '{key}' — dùng invite_token để chỉ đích danh (xem list-users).")
        sys.exit(1)
    return matches[0] if matches else None


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("add-user", "list-users", "revoke-user"):
        print(__doc__)
        sys.exit(1)

    config = load_config()
    store = SessionStore(config.data_dir / "app.db")

    if args[0] == "add-user":
        if len(args) < 2:
            print("Thiếu tên user: python -m server.manage add-user \"Tên Khách\"")
            sys.exit(1)
        user = store.create_user(args[1])
        print(f"Đã tạo user: {user['name']} (id {user['id']})")
        # PUBLIC_URL đặt trong .env (vd https://ecomerceagnet.duckdns.org) để in
        # link gửi thẳng cho khách — tránh ghép link tay dễ copy thiếu/thừa ký tự.
        public_url = os.environ.get("PUBLIC_URL", "").rstrip("/")
        if public_url:
            print(f"Invite link (gửi cho khách): {public_url}/?invite={user['invite_token']}")
        else:
            print(f"Invite link (local): http://localhost:{config.port}/?invite={user['invite_token']}")
            print(f"Invite link (prod):  https://<domain>/?invite={user['invite_token']}")
    elif args[0] == "revoke-user":
        if len(args) < 2:
            print("Thiếu đối số: python -m server.manage revoke-user <tên hoặc invite_token>")
            sys.exit(1)
        user = _find_user(store, args[1])
        if not user:
            print(f"Không tìm thấy user '{args[1]}' — xem danh sách bằng list-users.")
            sys.exit(1)
        store.delete_user(user["id"])
        print(f"Đã thu hồi user: {user['name']} — invite link + device token vô hiệu, lịch sử chat đã xóa.")
        print("Lưu ý: kết nối WS đang mở (nếu có) chỉ đứt khi restart app:")
        print("  docker compose -f docker/docker-compose.yml restart app")
    else:
        users = store.list_users()
        if not users:
            print("(chưa có user nào — tạo bằng: python -m server.manage add-user \"Tên\")")
        for u in users:
            print(f"- {u['name']}  |  invite={u['invite_token']}  |  tạo lúc {u['created_at']}")


if __name__ == "__main__":
    main()
