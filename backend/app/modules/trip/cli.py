"""Lệnh tay cho trip. Chạy lại bước địa phương và tọa độ OpenStreetMap cho chuyến đã có (khi deploy):

    python -m app.modules.trip.cli geocode --trip 5
    python -m app.modules.trip.cli geocode --all

Mỗi điểm một yêu cầu Nominatim, 1 yêu cầu mỗi giây; điểm đã có tọa độ thì bỏ qua.
"""

import argparse
import json
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.trip import geocode
from app.modules.trip.models import Trip


def cmd_geocode(args: argparse.Namespace) -> int:
    with SessionLocal() as session:
        stmt = select(Trip).where(Trip.status.not_in(("importing", "failed"))).order_by(Trip.id)
        if args.trip:
            stmt = select(Trip).where(Trip.id == args.trip)
        trips = list(session.scalars(stmt))
        if not trips:
            print("Không có chuyến nào.", file=sys.stderr)
            return 1
        for trip in trips:
            result = geocode.geocode_trip(session, trip)
            session.commit()
            print(json.dumps({"trip_id": trip.id, **result}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    from app.registry import import_all_models

    import_all_models()  # chạy thẳng bằng python -m: nạp đủ model, không thì khóa ngoại tới tab_user lỗi
    parser = argparse.ArgumentParser(prog="python -m app.modules.trip.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("geocode", help="Điền địa phương, lấy tọa độ OpenStreetMap cho điểm còn thiếu")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--trip", type=int, help="Mã chuyến")
    group.add_argument("--all", action="store_true", help="Mọi chuyến đã nhập xong")
    p.set_defaults(func=cmd_geocode)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
