"""Bài kiểm dùng DB thật (db-test, tmpfs): migrate một lần, mỗi bài chạy trong giao dịch rồi rollback."""

import os
import subprocess

import pytest

url = os.environ.get("TEST_DATABASE_URL", "")
if not url.rsplit("/", 1)[-1].endswith("_test"):
    raise pytest.UsageError("TEST_DATABASE_URL phải trỏ tới DB có tên kết thúc bằng _test.")
os.environ["DATABASE_URL"] = url
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-0123456789")
os.environ.setdefault("TOKEN_ENCRYPTION_KEYS", "v1:" + "A" * 43 + "=")
os.environ.setdefault("ENV", "test")
# Bài kiểm chạy cả tính năng dở (cờ mặc định tắt trên máy thật, luật điều phối 25/11).
for _flag in ("FEATURE_GYM", "FEATURE_CONNECTORS", "FEATURE_ZALO_BRIDGE", "FEATURE_CLAUDE_WORKER"):
    os.environ.setdefault(_flag, "true")


@pytest.fixture(scope="session")
def migrated():
    """Chỉ nâng lên head dưới khóa tư vấn: hai phiên pytest chạy cùng db-test không xóa bảng của nhau.
    Chuỗi lên, xuống, lên kiểm riêng ở CI (alembic downgrade -1)."""
    import psycopg

    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://", 1), autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(42424242)")
        try:
            subprocess.run(["alembic", "upgrade", "head"], check=True, capture_output=True)
        finally:
            conn.execute("SELECT pg_advisory_unlock(42424242)")
    yield


@pytest.fixture
def db(migrated, monkeypatch):
    """Session gắn vào một giao dịch ngoài; mọi commit trong mã thành savepoint, cuối bài rollback."""
    from sqlalchemy.orm import Session

    from app.core import db as core_db
    from app.core.ratelimit import limiter
    from app.registry import import_all_models

    import_all_models()

    engine = core_db.get_engine()
    connection = engine.connect()
    outer = connection.begin()

    def make_session() -> Session:
        return Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)

    monkeypatch.setattr(core_db, "open_session", make_session)
    limiter.reset()
    session = make_session()
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def user(db):
    from app.core.auth import create_owner
    from app.core.context import UserContext

    u = create_owner(db, "dai.ca@example.com", "Gia Bảo", "matkhau-thu-123", "Asia/Ho_Chi_Minh")
    db.flush()
    return UserContext(user_id=u.id, timezone=u.timezone)


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app import main

    return TestClient(main.app)


@pytest.fixture
def auth_client(client, user):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "dai.ca@example.com", "password": "matkhau-thu-123"}
    )
    assert resp.status_code == 200, resp.text
    client.headers["Authorization"] = f"Bearer {resp.json()['data']['access_token']}"
    return client
