#!/usr/bin/env python3
"""Đổi khoảng ngày -> URL trang đơn hàng TikTok Shop đã kèm bộ lọc.

Vì sao là script chứ không để LLM tự tính: đo ngày 01-08-2026, agent được yêu cầu
"đến 01/08/2026" nhưng lại chép mốc `1785517199999` (31/07) từ ví dụ trong SKILL.md,
xuất thiếu một ngày, rồi tự bịa lý do "giới hạn kỹ thuật của TikTok Shop". Main agent
bắt được và giao lại — nhưng lần chạy đó tốn 427k token, gấp 2.4 lần bình thường.
Phép tính này tất định; đưa cho máy làm thì không có lớp lỗi đó nữa.

Múi giờ CỐ ĐỊNH GMT+7: TikTok Shop VN neo theo giờ Việt Nam, không theo giờ của máy
chạy server. Đây cũng là lý do không dùng datetime.now() trần.

Dùng:
    daterange.py 01/12/2025 31/07/2026     # hai mốc cụ thể (DD/MM/YYYY)
    daterange.py --last-days 7             # 7 ngày qua, tính cả hôm nay
    daterange.py --last-months 3           # 3 tháng gần nhất
    daterange.py --this-month              # từ mùng 1 tháng này tới hôm nay
    daterange.py --last-month              # trọn tháng trước
    daterange.py --today
"""
from __future__ import annotations

import sys
from datetime import datetime, date, timedelta, timezone

VN = timezone(timedelta(hours=7))
BASE = "https://seller-vn.tiktok.com/order"


def _today() -> date:
    return datetime.now(VN).date()


def _parse(s: str) -> date:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise SystemExit(f"Không đọc được ngày {s!r}. Dùng DD/MM/YYYY, vd 01/05/2026.")


def _ms(d: date, end: bool) -> int:
    t = (datetime(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=VN) if end
         else datetime(d.year, d.month, d.day, tzinfo=VN))
    return int(t.timestamp() * 1000)


def _resolve(argv: list[str]) -> tuple[date, date, str]:
    today = _today()
    flag = argv[0] if argv and argv[0].startswith("--") else ""

    if flag == "--today":
        return today, today, "hôm nay"
    if flag == "--this-month":
        return today.replace(day=1), today, "từ đầu tháng này tới hôm nay"
    if flag == "--last-month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev, "trọn tháng trước"
    if flag == "--last-days":
        n = int(argv[1])
        return today - timedelta(days=n - 1), today, f"{n} ngày qua (tính cả hôm nay)"
    if flag == "--last-months":
        n = int(argv[1])
        m = today.month - n
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        day = min(today.day, [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28,
                              31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
        return date(y, m, day), today, f"{n} tháng gần nhất"
    if flag:
        raise SystemExit(f"Không hiểu tuỳ chọn {flag!r}. Xem phần đầu file.")

    if len(argv) < 2:
        raise SystemExit("Cần 2 ngày, vd: daterange.py 01/05/2026 01/08/2026")
    return _parse(argv[0]), _parse(argv[1]), "khoảng chỉ định"


def main() -> None:
    start, end, label = _resolve(sys.argv[1:])
    if end < start:
        raise SystemExit(f"Ngày cuối ({end:%d/%m/%Y}) trước ngày đầu ({start:%d/%m/%Y}).")

    s_ms, e_ms = _ms(start, False), _ms(end, True)
    days = (e_ms - s_ms + 1) // 86_400_000
    url = f"{BASE}?tab=all&time_order_created[]={s_ms}&time_order_created[]={e_ms}"

    print(f"Khoảng   : {start:%d/%m/%Y} - {end:%d/%m/%Y}  ({label}, giờ VN GMT+7)")
    print(f"Số ngày  : {days}")
    print(f"Chip phải hiện đúng: {start:%d/%m/%Y}-{end:%d/%m/%Y}")
    print(f"URL:\n{url}")


if __name__ == "__main__":
    main()
