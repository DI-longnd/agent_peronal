"""
CLI quản trị (chạy trên server): tạo user + invite link, xem danh sách user.

    python -m server.manage add-user "Tên Khách"
    python -m server.manage list-users
"""

from __future__ import annotations
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from server.config import load_config
from server.sessions import SessionStore


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("add-user", "list-users"):
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
        print(f"Invite link (local): http://localhost:{config.port}/?invite={user['invite_token']}")
        print(f"Invite link (prod):  https://<domain>/?invite={user['invite_token']}")
    else:
        users = store.list_users()
        if not users:
            print("(chưa có user nào — tạo bằng: python -m server.manage add-user \"Tên\")")
        for u in users:
            print(f"- {u['name']}  |  invite={u['invite_token']}  |  tạo lúc {u['created_at']}")


if __name__ == "__main__":
    main()
