"""Lệnh tay cho đặt chỗ. Khi deploy QĐ-49: đọc lại thư đặt chỗ 60 ngày qua (bắt thư đã đến trước đó):

python -m app.modules.booking.cli rescan --days 60
"""

import argparse
import json

from sqlalchemy import select

from app.core.db import SessionLocal
from app.integrations.google import gmail, stores
from app.integrations.google.models import GoogleAccount


def cmd_rescan(args: argparse.Namespace) -> int:
    from app.modules.booking.google_store import STORE

    if stores.booking_store() is None:
        stores.register_booking_store(STORE)
    with SessionLocal() as session:
        accounts = list(
            session.scalars(
                select(GoogleAccount).where(
                    GoogleAccount.status == "active", GoogleAccount.enabled_packs.any("gmail")
                )
            )
        )
        for account in accounts:
            gmail.reset_booking_scan(session, account.user_id, args.days)
            found = 0
            for _ in range(20):  # mỗi lượt tối đa 50 thư; lượt đầy thì đọc tiếp
                before = gmail._booking_state(session, account).updated_min
                found += gmail.scan_bookings(session, account)
                session.commit()
                if gmail._booking_state(session, account).updated_min != before:
                    break
            print(json.dumps({"user_id": account.user_id, "bookings": found}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.modules.booking.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("rescan", help="Đọc lại thư đặt chỗ trong n ngày qua")
    p.add_argument("--days", type=int, default=60)
    p.set_defaults(func=cmd_rescan)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
