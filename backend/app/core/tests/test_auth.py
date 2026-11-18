LOGIN = "/api/v1/auth/login"
CREDS = {"email": "dai.ca@example.com", "password": "matkhau-thu-123"}


def test_wrong_password_401_without_leaking_email(client, user):
    resp = client.post(LOGIN, json={**CREDS, "password": "sai-roi"})
    assert resp.status_code == 401
    assert resp.json()["data"]["code"] == "AUTH_INVALID_CREDENTIALS"
    other = client.post(LOGIN, json={"email": "khong.co@example.com", "password": "x"})
    assert other.json()["message"] == resp.json()["message"]


def test_refresh_rotates_and_old_token_dies(client, user):
    tokens = client.post(LOGIN, json=CREDS).json()["data"]

    new = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert new.status_code == 200
    assert new.json()["data"]["refresh_token"] != tokens["refresh_token"]
    assert again.status_code == 401
    assert again.json()["data"]["code"] == "AUTH_REFRESH_INVALID"


def test_logout_revokes_refresh(client, user):
    tokens = client.post(LOGIN, json=CREDS).json()["data"]
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )


def test_device_token_scope_and_revoke(auth_client):
    reg = auth_client.post("/api/v1/devices", json={"name": "S25+"}).json()["data"]
    dev = {"Authorization": f"Device {reg['device_token']}"}

    assert auth_client.post("/api/v1/device/heartbeat", json={"queue_size": 3}).status_code == 401  # JWT
    assert (
        auth_client.post("/api/v1/device/heartbeat", json={"queue_size": 3}, headers=dev).status_code == 200
    )
    assert auth_client.get("/api/v1/expenses", headers=dev).status_code == 401
    assert auth_client.get("/api/v1/device/release", headers=dev).status_code == 200

    auth_client.delete(f"/api/v1/devices/{reg['device']['id']}")
    revoked = auth_client.post("/api/v1/device/heartbeat", json={}, headers=dev)
    assert revoked.status_code == 401
    assert revoked.json()["data"]["code"] == "DEVICE_REVOKED"


def test_validation_400_and_unknown_route_envelope(auth_client):
    bad = auth_client.post("/api/v1/expenses", json={"amount_vnd": -5})
    assert bad.status_code == 400
    body = bad.json()
    assert body["success"] is False and body["data"]["code"] == "VALIDATION_ERROR"
    assert "amount_vnd" in body["data"]["fields"]
    missing = auth_client.get("/api/v1/khong-co")
    assert missing.status_code == 404 and missing.json()["data"]["code"] == "NOT_FOUND"


def test_other_user_rows_are_404(auth_client, db):
    """Một tài khoản (QĐ-27) nhưng vẫn lọc user_id: dòng của user khác coi như không có."""
    from app.core.context import UserContext
    from app.core.models import User
    from app.modules.expense import service as expense

    u2 = User(name="Khác", email="khac@example.com", password_hash="x")
    db.add(u2)
    db.flush()
    e = expense.create_expense(db, UserContext(u2.id, "Asia/Ho_Chi_Minh"), {"amount_vnd": 1000, "note": "x"})
    db.flush()

    assert auth_client.get(f"/api/v1/expenses/{e['id']}").status_code == 404
