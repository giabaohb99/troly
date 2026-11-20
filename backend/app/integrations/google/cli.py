"""Lệnh tay cho Google. Khi deploy sửa lọc mục Gmail: quét lại hộp thư đến 7 ngày qua.

python -m app.integrations.google.cli rescan-inbox --days 7
"""

import argparse
import json

from sqlalchemy import select


def cmd_rescan_inbox(args: argparse.Namespace) -> int:
    from app.core.db import SessionLocal
    from app.integrations.google import gmail, service
    from app.integrations.google.models import GoogleAccount

    with SessionLocal() as session:
        accounts = list(
            session.scalars(
                select(GoogleAccount).where(
                    GoogleAccount.status == "active", GoogleAccount.enabled_packs.any("gmail")
                )
            )
        )
        for account in accounts:
            gmail.rescan_inbox(session, account.user_id, args.days)
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
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_rescan_inbox)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
