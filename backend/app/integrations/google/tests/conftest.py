import pytest

from app.integrations.google import http, stores
from app.integrations.google.settings import get_google_settings
from app.integrations.google.tests.fake_google import CLIENT_ID, FakeGoogle
from app.integrations.google.tests.memory_stores import MemoryCalendarStore, MemoryFileStore, MemoryTaskStore

ALL_SCOPES = (
    "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile "
    "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/tasks"
)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret-test")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://assistant.example.test")
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    get_google_settings.cache_clear()
    google = FakeGoogle()
    google.granted_scope = ALL_SCOPES
    http.set_transport(google.transport())
    sleeps: list[float] = []
    monkeypatch.setattr(http, "_sleep", sleeps.append)
    google.sleeps = sleeps
    yield google
    http.set_transport(None)
    get_google_settings.cache_clear()


@pytest.fixture
def cal_store():
    store = MemoryCalendarStore()
    stores.register_calendar_store(store)
    yield store
    stores.register_calendar_store(None)


@pytest.fixture
def task_store():
    store = MemoryTaskStore()
    stores.register_task_store(store)
    yield store
    stores.register_task_store(None)


def connect_account(db, user, fake, packs=("calendar", "tasks"), scope=None):
    """Chạy luồng nối thật qua Google giả; trả (account, CallbackResult)."""
    from urllib.parse import parse_qs, urlparse

    from app.integrations.google import oauth

    url = oauth.start_connect(db, user.user_id, list(packs))
    state = parse_qs(urlparse(url).query)["state"][0]
    code = fake.issue_code(scope=scope)
    result = oauth.finish_connect(db, code, state, None)
    db.flush()
    return oauth.get_account(db, user.user_id), result


@pytest.fixture
def account(db, user, fake):
    acc, result = connect_account(db, user, fake)
    assert result.ket_qua == "ok", result.message
    return acc


@pytest.fixture
def file_store():
    store = MemoryFileStore()
    stores.register_file_store(store)
    yield store
    stores.register_file_store(None)


DRIVE_SCOPES = ALL_SCOPES + " https://www.googleapis.com/auth/drive.file"
