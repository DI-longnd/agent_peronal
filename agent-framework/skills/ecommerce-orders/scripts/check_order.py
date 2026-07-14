#!/usr/bin/env python3
"""Mock: trong thực tế sẽ gọi API sàn TMĐT. Đây là dữ liệu giả để demo framework."""
import sys
import json

def main():
    order_id = sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN"
    # TODO (bạn): thay bằng call API thật của sàn bạn đang tích hợp
    mock_db = {
        "SA-00123": {"status": "pending", "amount_thousand_vnd": 450, "customer": "Nguyen Van A"},
        "SA-00456": {"status": "disputed", "amount_thousand_vnd": 200, "customer": "Tran Thi B"},
    }
    result = mock_db.get(order_id, {"status": "not_found", "amount_thousand_vnd": 0, "customer": None})
    print(json.dumps({"order_id": order_id, **result}, ensure_ascii=False))

if __name__ == "__main__":
    main()
