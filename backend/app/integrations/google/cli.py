"""Lệnh tay cho Google. Khi deploy sửa lọc mục Gmail: quét lại hộp thư đến 7 ngày qua.

python -m app.integrations.google.cli rescan-inbox --days 30 [--account x@gmail.com]
"""

import argparse
import json

from sqlalchemy import select


def cmd_rescan_inbox(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal
    from app.integrations.google import gmail, service
    from app.integrations.google.models import GoogleAccount

    with SessionLocal() as session:
        stmt = select(GoogleAccount).where(
            GoogleAccount.status == "active", GoogleAccount.enabled_packs.any("gmail")
        )
        if args.account:
            stmt = stmt.where(GoogleAccount.email == args.account.strip())
        accounts = list(session.scalars(stmt))
        if args.account and not accounts:
            print(json.dumps({"error": f"Không có tài khoản Gmail {args.account}"}, ensure_ascii=False))
            return 1
        for account in accounts:
            gmail.rescan_inbox(session, account.user_id, args.days, account_id=account.id)
            session.commit()
        count = service.sync_due(session, "gmail", 0)
        session.commit()
        print(json.dumps({"accounts": len(accounts), "saved": count}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    from app.registry import import_all_models, register_integrations

    import_all_models()
    register_integrations()
    parser = argparse.ArgumentParser(prog="python -m app.integrations.google.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("rescan-inbox", help="Quét lại hộp thư đến Gmail n ngày qua")
    p.add_argument("--days", type=int, default=30, help="Tối đa 30 ngày, 300 thư")
    p.add_argument("--account", help="Chỉ một tài khoản, theo email")
    p.set_defaults(func=cmd_rescan_inbox)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
