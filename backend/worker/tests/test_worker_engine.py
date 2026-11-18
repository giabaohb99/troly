"""Chạy đúng cấu hình engine của worker trên Postgres thật, KHÔNG bọc giao dịch như fixture `db`.

Lỗi 19/11 trên VPS: kết nối LISTEN (autocommit) lọt về pool, session sau đó không có BEGIN nên
`begin_nested()` báo `SAVEPOINT can only be used in transaction blocks`.
"""

import gc
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.core import db as core_db
from app.registry import import_all_models
from worker import main as worker_main
from worker.jobs import device_events


@pytest.fixture
def waker(migrated):
    import_all_models()
    w = worker_main.Waker()
    w._connect()
    gc.collect()
    yield w
    w.close()


def test_listen_connection_never_returns_to_pool(waker):
    engine = core_db.get_engine()
    conns = [engine.raw_connection() for _ in range(engine.pool.size() + 1)]
    try:
        for c in conns:
            assert c.driver_connection is not waker.conn
            assert c.driver_connection.autocommit is False
    finally:
        for c in conns:
            c.close()


def test_process_device_events_with_real_sessions(waker):
    """Ghi dữ liệu thật rồi dọn: một chủ, một máy, một thông báo Zalo; worker xử lý xong."""
    engine = core_db.get_engine()
    email = f"worker-{uuid.uuid4().hex[:8]}@example.com"
    with engine.begin() as c:
        if c.execute(text("SELECT count(*) FROM tab_user")).scalar():
            pytest.skip("DB kiểm thử đang có người dùng của lần chạy khác")
        uid = c.execute(
            text(
                "INSERT INTO tab_user (email, name, password_hash, timezone) "
                "VALUES (:e, 'Kiểm', 'x', 'Asia/Ho_Chi_Minh') RETURNING id"
            ),
            {"e": email},
        ).scalar()
        did = c.execute(
            text(
                "INSERT INTO tab_device (user_id, name, token_hash, token_prefix) "
                "VALUES (:u, 'S25+', :h, 'dev_test') RETURNING id"
            ),
            {"u": uid, "h": uuid.uuid4().hex * 2},
        ).scalar()
        c.execute(
            text(
                "INSERT INTO tab_device_event (user_id, device_id, client_event_id, kind, app_package, "
                "posted_at, payload) VALUES (:u, :d, :cid, 'notification', 'com.zing.zalo', :at, "
                "CAST(:p AS jsonb))"
            ),
            {
                "u": uid,
                "d": did,
                "cid": uuid.uuid4(),
                "at": datetime.now(UTC),
                "p": '{"title": "Lan", "text": "Chào anh", "messages": []}',
            },
        )
    try:
        # Gọi nhiều lần để session chắc chắn đi qua mọi kết nối trong pool.
        for _ in range(3):
            device_events.process_device_events()
        with engine.connect() as c:
            status, error = c.execute(
                text("SELECT status, error FROM tab_device_event WHERE user_id = :u"), {"u": uid}
            ).one()
        assert (status, error) == ("done", None)
    finally:
        with engine.begin() as c:
            c.execute(text("DELETE FROM tab_user WHERE id = :u"), {"u": uid})
