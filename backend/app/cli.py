"""Lệnh quản trị (10 mục 3.15): docker compose run --rm api python -m app.cli <lệnh>."""

import argparse
import getpass
import pathlib
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


def cmd_export_bank_samples(args: argparse.Namespace) -> int:
    """Xuất thông báo ngân hàng, ví thật đã che thành tệp mẫu đúng định dạng testdata/ (QĐ-35, 70 mục 3.3).

    Tự che số tài khoản, thẻ (xxxx + 4 số cuối), số điện thoại, số dư, cụm tên viết hoa; `expect` điền
    sẵn theo kết quả hiện tại để người duyệt sửa. Ghi YAML bằng chuỗi JSON để ảnh chạy không cần pyyaml.
    """
    import json
    from datetime import timedelta

    from sqlalchemy import text

    from app.modules.expense.bank import mask_for_ai, mask_names

    since = clock.now() - timedelta(days=args.days)
    with SessionLocal() as session:
        rows = session.execute(
            text(
                "SELECT e.id, e.app_package, e.payload->>'title' AS title, e.payload->>'text' AS text, "
                "e.posted_at, e.status, x.kind, x.amount_vnd, x.account, x.account_last4, x.to_account, "
                "x.spent_at, x.parser "
                "FROM tab_device_event e "
                "JOIN tab_listened_app a ON a.user_id = e.user_id AND a.package_name = e.app_package "
                "LEFT JOIN tab_expense x ON x.device_event_id = e.id "
                "WHERE a.purpose = 'expense' AND e.kind = 'notification' AND e.received_at >= :since "
                "AND e.error IS DISTINCT FROM 'OTP_DETECTED' ORDER BY e.app_package, e.posted_at"
            ),
            {"since": since},
        ).all()

    def clean(value: str | None) -> str:
        return json.dumps(mask_names(mask_for_ai(value or "")), ensure_ascii=False)

    lines = ["# Mẫu thật đã che tự động. Rà lại tên, mã tham chiếu và expect trước khi chép vào testdata/."]
    for r in rows:
        if r.kind is None:
            expect = {"kind": "ignore"} if r.status == "ignored" else {}
        else:
            expect = {
                k: v
                for k, v in {
                    "kind": r.kind,
                    "amount_vnd": r.amount_vnd,
                    "account": r.account,
                    "account_last4": r.account_last4,
                    "to_account": r.to_account,
                    "spent_at": r.spent_at.isoformat() if r.spent_at else None,
                }.items()
                if v is not None
            }
        lines += [
            f"- id: real-{r.app_package.rsplit('.', 1)[-1].lower()}-{r.id}",
            f"  package: {json.dumps(r.app_package)}",
            f"  title: {clean(r.title)}",
            f"  text: {clean(r.text)}",
            f"  posted_at: {json.dumps(r.posted_at.isoformat())}",
            f"  parser: {json.dumps(r.parser)}",
            f"  expect: {json.dumps(expect, ensure_ascii=False)}",
            "",
        ]
    pathlib.Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"Đã xuất {len(rows)} thông báo vào {args.out}.")
    return 0


def cmd_export_inbox_samples(args: argparse.Namespace) -> int:
    """Xuất dạng thông báo tin nhắn thật để rút luật (70 mục 3.3), KHÔNG giữ nội dung tin người khác.

    Mọi tên thay bằng `Người N` (cùng tên cùng số), mọi nội dung thay bằng `(nội dung)`; chỉ giữ tiền tố
    tiêu đề (`Nhóm:`, `Group:`), dạng `Tên: nội dung`, cờ, số tin trong messages[]. Ghi YAML bằng chuỗi JSON.
    """
    import json
    import re
    from datetime import timedelta

    from sqlalchemy import text

    since = clock.now() - timedelta(days=args.days)
    with SessionLocal() as session:
        rows = session.execute(
            text(
                "SELECT e.id, e.app_package, e.payload, e.posted_at FROM tab_device_event e "
                "JOIN tab_listened_app a ON a.user_id = e.user_id AND a.package_name = e.app_package "
                "WHERE a.purpose = 'inbox' AND e.kind = 'notification' AND e.received_at >= :since "
                "ORDER BY e.app_package, e.posted_at"
            ),
            {"since": since},
        ).all()
    names: dict[str, str] = {}
    prefix = re.compile(r"^\s*((?:Nhóm|Nhom|Group)\s*:\s*)(.+)$", re.IGNORECASE)
    named = re.compile(r"^([^:\n]{1,60}?):\s+.+$", re.DOTALL)

    def alias(value: str | None) -> str | None:
        if not value:
            return value
        m = prefix.match(value)
        if m:
            return m.group(1) + alias(m.group(2))
        if value.strip().lower() in ("zalo", "telegram", "messenger", "facebook"):
            return value
        return names.setdefault(value.strip(), f"Người {len(names) + 1}")

    def body(value: str | None) -> str | None:
        if not value:
            return value
        m = named.match(value)
        return f"{alias(m.group(1))}: (nội dung)" if m else "(nội dung)"

    lines = [
        "# Dạng thông báo tin nhắn thật, đã thay hết tên và nội dung. Điền expect trước khi chép vào testdata/."
    ]
    for r in rows:
        p = r.payload or {}
        payload = {
            "title": alias(p.get("title")),
            "text": body(p.get("text")),
            "conversation_title": alias(p.get("conversation_title")),
            "is_group_conversation": bool(p.get("is_group_conversation")),
            "hidden_content": bool(p.get("hidden_content")),
            "category": p.get("category"),
            "messages": [
                {"sender": alias(m.get("sender")), "text": body(m.get("text")), "at": m.get("at")}
                for m in p.get("messages") or []
            ],
        }
        lines += [
            f"- id: real-{r.app_package.rsplit('.', 1)[-1].lower()}-{r.id}",
            f"  package: {json.dumps(r.app_package)}",
            f"  payload: {json.dumps(payload, ensure_ascii=False)}",
            "  expect: {}",
            "",
        ]
    pathlib.Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"Đã xuất {len(rows)} thông báo vào {args.out}.")
    return 0


def cmd_reprocess_inbox(args: argparse.Namespace) -> int:
    """Đọc lại tin trong hộp tin từ tab_device_event sau khi sửa luật bóc tách (tin cũ bị xóa, tạo lại;
    trạng thái đã xem, xong của các tin đó mất). Chỉ tin đến từ thông báo, trong `--days` ngày."""
    from datetime import timedelta

    from sqlalchemy import delete, select

    from app.core.context import UserContext
    from app.core.models import User
    from app.modules.device import service as device_service
    from app.modules.device.models import DeviceEvent
    from app.modules.inbox import service as inbox_service
    from app.modules.inbox.models import InboxMessage

    since = clock.now() - timedelta(days=args.days)
    with SessionLocal() as session:
        event_ids = sorted(
            set(
                session.scalars(
                    select(InboxMessage.device_event_id).where(
                        InboxMessage.device_event_id.is_not(None), InboxMessage.posted_at >= since
                    )
                )
            )
        )
        removed = session.execute(
            delete(InboxMessage).where(InboxMessage.device_event_id.in_(event_ids))
        ).rowcount
        created = 0
        for ev in session.scalars(
            select(DeviceEvent).where(DeviceEvent.id.in_(event_ids)).order_by(DeviceEvent.id)
        ):
            tz = session.scalar(select(User.timezone).where(User.id == ev.user_id))
            app = device_service.resolve_listened_app(session, ev.user_id, ev.device_id, ev.app_package)
            if app is None or app.purpose != "inbox":
                continue
            out = inbox_service.ingest_notification(
                session,
                UserContext(user_id=ev.user_id, timezone=tz),
                parser=app.parser,
                app_package=ev.app_package,
                payload=ev.payload,
                posted_at=ev.posted_at,
                device_id=ev.device_id,
                device_event_id=ev.id,
            )
            device_service.finish_event(
                ev,
                out["status"],
                out["result_kind"],
                out.get("result_id"),
                None if out["status"] == "done" else out.get("reason"),
            )
            created += out.get("created", 0)
        session.commit()
    print(f"Đã đọc lại {len(event_ids)} thông báo: xóa {removed} tin cũ, tạo {created} tin.")
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

    p = sub.add_parser("export-bank-samples", help="Xuất thông báo ngân hàng thật đã che làm mẫu")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--out", default="bank-samples.yaml")
    p.set_defaults(func=cmd_export_bank_samples)

    p = sub.add_parser(
        "export-inbox-samples", help="Xuất dạng thông báo tin nhắn thật, đã thay tên và nội dung"
    )
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--out", default="inbox-samples.yaml")
    p.set_defaults(func=cmd_export_inbox_samples)

    p = sub.add_parser("reprocess-inbox", help="Đọc lại hộp tin từ sự kiện thiết bị sau khi sửa luật")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_reprocess_inbox)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
