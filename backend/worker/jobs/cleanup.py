"""Dọn dữ liệu quá hạn theo 11 mục 3.15. Bảng của phase sau được bỏ qua khi chưa có."""

import logging

from sqlalchemy import text

from app.core import storage
from app.core.config import get_settings
from app.core.db import SessionLocal

log = logging.getLogger("troly.cleanup")
BATCH = 1000

REDACTED = "[đã xóa sau 180 ngày]"


def _exists(session, table: str) -> bool:
    return session.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar() is not None


def _delete_batches(session, table: str, where: str, params: dict) -> int:
    total = 0
    while True:
        result = session.execute(
            text(f"DELETE FROM {table} WHERE ctid IN (SELECT ctid FROM {table} WHERE {where} LIMIT {BATCH})"),
            params,
        )
        session.commit()
        total += result.rowcount or 0
        if (result.rowcount or 0) < BATCH:
            return total


def _redact_third_party(session, days: int) -> int:
    """Khối tool_result có tin người khác: thay nội dung, giữ cấu trúc khối để lịch sử Claude còn hợp lệ."""
    result = session.execute(
        text(
            """
            UPDATE tab_message SET redacted_at = now(),
              content = (
                SELECT coalesce(jsonb_agg(
                  CASE WHEN b->>'type' = 'tool_result'
                       THEN jsonb_set(b, '{content}', to_jsonb(CAST(:r AS text)))
                       ELSE b END), '[]'::jsonb)
                FROM jsonb_array_elements(content) b)
            WHERE contains_third_party AND redacted_at IS NULL AND jsonb_typeof(content) = 'array'
              AND created_at < now() - make_interval(days => :d)
            """
        ),
        {"r": REDACTED, "d": days},
    )
    session.commit()
    return result.rowcount or 0


def _purge_files(session) -> int:
    """Tệp xóa mềm quá 30 ngày và tệp tải lên dở quá 24 giờ: xóa đối tượng R2 rồi xóa dòng."""
    rows = session.execute(
        text(
            "SELECT id, r2_key FROM tab_file WHERE (deleted_at < now() - interval '30 days') "
            "OR (status = 'pending_upload' AND created_at < now() - interval '24 hours') LIMIT :n"
        ),
        {"n": BATCH},
    ).all()
    bucket = get_settings().r2_bucket
    for row in rows:
        try:
            storage.delete(bucket, row.r2_key)
        except Exception:
            log.warning("Không xóa được đối tượng R2", extra={"file_id": row.id})
            continue
        session.execute(text("DELETE FROM tab_file WHERE id = :i"), {"i": row.id})
    session.commit()
    return len(rows)


def cleanup_old_data() -> tuple[int, dict]:
    s = get_settings()
    detail: dict = {}
    rules = [
        ("tab_message", "created_at < now() - make_interval(days => :d)", {"d": s.chat_retention_days}),
        (
            "tab_pending_action",
            "status <> 'pending' AND coalesce(decided_at, expires_at) < now() - interval '30 days'",
            {},
        ),
        ("tab_ai_run", "created_at < now() - interval '13 months'", {}),
        ("tab_auth_session", "coalesce(revoked_at, expires_at) < now() - interval '30 days'", {}),
        (
            "tab_job_queue",
            "(status IN ('done','cancelled') AND updated_at < now() - interval '30 days') "
            "OR (status = 'failed' AND updated_at < now() - interval '90 days')",
            {},
        ),
        ("tab_job_run", "started_at < now() - interval '30 days'", {}),
        (
            "tab_client_log",
            "created_at < now() - make_interval(days => :d)",
            {"d": s.client_log_retention_days},
        ),
        ("tab_expense", "deleted_at < now() - interval '30 days'", {}),
        ("tab_note", "deleted_at < now() - interval '30 days'", {}),
        ("tab_inbox_message", "posted_at < now() - make_interval(days => :d)", {"d": s.inbox_retention_days}),
        (
            "tab_device_event",
            "received_at < now() - make_interval(days => :d)",
            {"d": s.device_event_retention_days},
        ),
        ("tab_google_oauth_state", "expires_at < now() - interval '1 hour'", {}),
        # Phiên chat không có tin nào quá 1 ngày (luật cũ tự tạo phiên mỗi ngày; phản hồi 1.1.1).
        (
            "tab_conversation",
            "created_at < now() - interval '1 day' AND title_source IS DISTINCT FROM 'user' AND NOT pinned "
            "AND NOT EXISTS (SELECT 1 FROM tab_message m WHERE m.conversation_id = tab_conversation.id)",
            {},
        ),
        (
            "tab_google_outbox",
            "(status = 'done' AND updated_at < now() - interval '7 days') "
            "OR (status IN ('failed','conflict') AND updated_at < now() - interval '30 days')",
            {},
        ),
    ]
    with SessionLocal() as session:
        detail["redacted_messages"] = _redact_third_party(session, s.third_party_chat_retention_days)
        for table, where, params in rules:
            if _exists(session, table):
                detail[table] = _delete_batches(session, table, where, params)
        detail["tab_file"] = _purge_files(session)
        for table in ("tab_place_cache", "tab_trip_stop"):
            if _exists(session, table):
                column = "fetched_at" if table == "tab_place_cache" else "coord_fetched_at"
                extra = "" if table == "tab_place_cache" else " AND coord_source = 'google'"
                result = session.execute(
                    text(
                        f"UPDATE {table} SET lat = NULL, lng = NULL "
                        f"WHERE {column} < now() - interval '30 days' AND lat IS NOT NULL{extra}"
                    )
                )
                session.commit()
                detail[f"{table}_coords"] = result.rowcount or 0
    return sum(v for v in detail.values() if isinstance(v, int)), detail
