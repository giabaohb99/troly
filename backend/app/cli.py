"""Lệnh quản trị (10 mục 3.15): docker compose run --rm api python -m app.cli <lệnh>."""

import argparse
import getpass
import sys

from app.core import clock
from app.core.auth import create_owner
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.registry import import_all_models


def cmd_create_owner(args: argparse.Namespace) -> int:
    password = args.password or getpass.getpass("Mật khẩu (từ 8 ký tự): ")
    if not args.password:
        again = getpass.getpass("Nhập lại: ")
        if again != password:
            print("Hai lần nhập không khớp.")
            return 1
    if len(password) < 8 or len(password.encode()) > 72:
        print("Mật khẩu từ 8 ký tự tới 72 byte.")
        return 1
    with SessionLocal() as session:
        user = create_owner(
            session, args.email, args.name, password, args.timezone or get_settings().app_timezone
        )
        from app.modules.expense import service as expense_service

        expense_service.ensure_default_categories(session, user.id)
        session.commit()
        print(f"Đã tạo tài khoản #{user.id} ({user.email}).")
    return 0


def cmd_revoke_device(args: argparse.Namespace) -> int:
    from sqlalchemy import text

    with SessionLocal() as session:
        result = session.execute(
            text("UPDATE tab_device SET revoked_at = :n WHERE id = :i AND revoked_at IS NULL"),
            {"n": clock.now(), "i": args.device_id},
        )
        session.commit()
    print("Đã thu hồi." if result.rowcount else "Không có thiết bị đang dùng với mã này.")
    return 0


def cmd_reencrypt_tokens(args: argparse.Namespace) -> int:
    """Mã hóa lại bí mật bằng khóa đầu vòng TOKEN_ENCRYPTION_KEYS (sau khi thêm khóa mới)."""
    from sqlalchemy import text

    from app.core.security import decrypt_bound, encrypt_bound

    count = 0
    with SessionLocal() as session:
        exists = session.execute(text("SELECT to_regclass('tab_google_account')")).scalar()
        if exists is None:
            print("Chưa có bảng tab_google_account, không có gì để mã hóa lại.")
            return 0
        rows = session.execute(
            text(
                "SELECT id, user_id, refresh_token_enc, access_token_enc, key_version FROM tab_google_account"
            )
        ).all()
        for row in rows:
            refresh = decrypt_bound(row.user_id, "google", bytes(row.refresh_token_enc), row.key_version)
            new_refresh, version = encrypt_bound(row.user_id, "google", refresh)
            new_access = None
            if row.access_token_enc is not None:
                access = decrypt_bound(row.user_id, "google", bytes(row.access_token_enc), row.key_version)
                new_access, _ = encrypt_bound(row.user_id, "google", access)
            session.execute(
                text(
                    "UPDATE tab_google_account SET refresh_token_enc = :r, access_token_enc = :a, key_version = :v "
                    "WHERE id = :i"
                ),
                {"r": new_refresh, "a": new_access, "v": version, "i": row.id},
            )
            count += 1
        session.commit()
    print(f"Đã mã hóa lại {count} tài khoản Google.")
    return 0


def main(argv: list[str] | None = None) -> int:
    import_all_models()
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-owner", help="Tạo tài khoản duy nhất")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--timezone")
    p.add_argument("--password", help="Chỉ dùng khi chạy tự động; bỏ trống thì hỏi")
    p.set_defaults(func=cmd_create_owner)

    p = sub.add_parser("revoke-device", help="Thu hồi một thiết bị")
    p.add_argument("device_id", type=int)
    p.set_defaults(func=cmd_revoke_device)

    p = sub.add_parser("reencrypt-tokens", help="Mã hóa lại token bằng khóa mới nhất")
    p.set_defaults(func=cmd_reencrypt_tokens)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
