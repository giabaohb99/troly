from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.core import clock
from app.core.models import JobQueue
from app.core.security import sha256_hex
from app.integrations.google import oauth
from app.integrations.google.errors import GoogleReauthRequired
from app.integrations.google.models import GoogleOAuthState, GoogleSyncState
from app.integrations.google.tests.conftest import connect_account


def test_start_connect_builds_pkce_url_and_hashed_state(db, user, fake):
    url = oauth.start_connect(db, user.user_id, ["calendar"])
    query = parse_qs(urlparse(url).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["access_type"] == ["offline"] and query["prompt"] == ["consent"]
    assert query["include_granted_scopes"] == ["true"]
    assert query["redirect_uri"] == ["https://assistant.example.test/api/v1/google/oauth/callback"]
    assert "calendar.events" in query["scope"][0] and "openid" in query["scope"][0]
    row = db.scalar(select(GoogleOAuthState))
    assert row.state_hash == sha256_hex(query["state"][0])
    assert row.packs == ["base", "calendar"]


def test_callback_connects_enables_packs_and_queues_initial_sync(db, user, fake, account):
    assert account.enabled_packs == ["base", "calendar", "tasks"]
    assert account.status == "active"
    services = set(db.scalars(select(GoogleSyncState.service)))
    assert services == {"calendar", "tasks"}
    job = db.scalar(select(JobQueue).where(JobQueue.kind == "google_initial_sync"))
    assert job is not None and job.user_id == user.user_id
    token = fake.calls("POST", r"oauth2\.googleapis\.com/token")[0]
    assert "code_verifier=" in token.content.decode()


def test_state_is_single_use(db, user, fake):
    url = oauth.start_connect(db, user.user_id, ["calendar"])
    state = parse_qs(urlparse(url).query)["state"][0]
    assert oauth.finish_connect(db, fake.issue_code(), state, None).ket_qua == "ok"
    assert oauth.finish_connect(db, fake.issue_code(), state, None).ket_qua == "loi"


def test_expired_state_rejected(db, user, fake):
    url = oauth.start_connect(db, user.user_id, ["calendar"])
    state = parse_qs(urlparse(url).query)["state"][0]
    row = db.scalar(select(GoogleOAuthState))
    row.expires_at = clock.now() - timedelta(seconds=1)
    assert oauth.finish_connect(db, fake.issue_code(), state, None).ket_qua == "loi"


def test_access_denied_maps_to_huy(db, user, fake):
    url = oauth.start_connect(db, user.user_id, ["calendar"])
    state = parse_qs(urlparse(url).query)["state"][0]
    assert oauth.finish_connect(db, None, state, "access_denied").ket_qua == "huy"


def test_missing_scope_reports_thieu_quyen_and_keeps_pack_off(db, user, fake):
    scope = "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"
    acc, result = connect_account(
        db, user, fake, packs=("calendar",), scope=scope + " https://www.googleapis.com/auth/tasks"
    )
    assert result.ket_qua == "thieu-quyen" and result.missing_packs == ["calendar"]
    assert "calendar" not in acc.enabled_packs


def test_reconnect_revokes_previous_refresh_token(db, user, fake, account):
    old = oauth._decrypt(account, account.refresh_token_enc)
    _, result = connect_account(db, user, fake)
    assert result.ket_qua == "ok"
    assert old in fake.revoked


def test_other_google_account_is_not_overwritten(db, user, fake, account):
    url = oauth.start_connect(db, user.user_id, ["calendar"])
    state = parse_qs(urlparse(url).query)["state"][0]
    result = oauth.finish_connect(db, fake.issue_code(sub="sub-khac"), state, None)
    assert result.ket_qua == "loi"
    assert oauth.get_account(db, user.user_id).google_sub == "sub-1"


def test_access_token_refreshes_when_near_expiry(db, fake, account):
    account.access_expires_at = clock.now() + timedelta(minutes=2)
    token = oauth.access_token(db, account)
    assert token in fake.access_tokens
    assert account.access_expires_at > clock.now() + timedelta(minutes=30)
    assert len(fake.calls("POST", r"/token")) == 2  # đổi mã lúc nối, làm mới lúc này


def test_invalid_grant_marks_reauth_required(db, fake, account):
    fake.refresh_tokens.clear()
    with pytest.raises(GoogleReauthRequired):
        oauth.access_token(db, account, force_refresh=True)
    assert account.status == "reauth_required"
    assert account.invalid_grant_count == 1


def test_token_ciphertext_is_bound_to_owner(db, fake, account):
    from app.core.security import decrypt_bound

    with pytest.raises(ValueError):
        decrypt_bound(account.user_id + 1, "google", bytes(account.refresh_token_enc), account.key_version)
