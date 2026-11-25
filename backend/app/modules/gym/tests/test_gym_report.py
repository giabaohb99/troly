"""QĐ-54: thẻ Tập luyện đọc app gym qua cửa chỉ đọc (gym giả bằng httpx.MockTransport)."""

from datetime import UTC, date, datetime

import httpx
import pytest

from app.core.config import get_settings
from app.integrations.gym import client

KEY = "khoa-gym-gia-123"

SAMPLE = {
    "username": "giabao",
    "range": {"from": "2026-11-19", "to": "2026-11-25"},
    "workouts": [
        {"date": "2026-11-20", "day_name": "Ngực tay sau", "done": True, "exercises": []},
        {"date": "2026-11-22", "day_name": "Lưng tay trước", "done": False, "exercises": []},
        {"date": "2026-11-25", "day_name": "Chân", "done": True, "exercises": []},
    ],
    "planned": [
        {"date": "2026-11-20", "day_name": "Ngực tay sau"},
        {"date": "2026-11-22", "day_name": "Lưng tay trước"},
        {"date": "2026-11-23", "day_name": "Vai"},
        {"date": "2026-11-25", "day_name": "Chân"},
    ],
    "body": [
        {"date": "2026-11-24", "weight_kg": 71.2, "waist_cm": None},
        {"date": "2026-11-19", "weight_kg": 72.0, "waist_cm": 82},
        {"date": "2026-11-21", "weight_kg": None, "waist_cm": 81},
    ],
    "nutrition": {
        "days": [
            {"date": "2026-11-20", "meals_checked": 4, "kcal": 2400, "protein_g": 140, "water_cups": 8, "creatine": True},
            {"date": "2026-11-21", "meals_checked": 3, "kcal": 2100, "protein_g": 121, "water_cups": 6, "creatine": False},
            {"date": "2026-11-22", "meals_checked": 0, "kcal": None, "protein_g": None, "water_cups": 5, "creatine": True},
        ],
        "targets": {"kcal_train": 2500, "kcal_rest": 2200, "protein_g": 150, "carb_g": 280, "fat_g": 70, "water_cups": 8},
    },
    "progress": [
        {"name": "Đẩy ngực", "first": {"date": "2026-11-20", "weight_kg": 60, "reps": 8},
         "last": {"date": "2026-11-25", "weight_kg": 65, "reps": 8}},
        {"name": "Squat", "first": {"date": "2026-11-20", "weight_kg": 80, "reps": 5},
         "last": {"date": "2026-11-25", "weight_kg": 82.5, "reps": 5}},
        {"name": "Kéo xà", "first": {"date": "2026-11-22", "weight_kg": None, "reps": 6},
         "last": {"date": "2026-11-25", "weight_kg": None, "reps": 8}},
        {"name": "Cuốn tay", "first": {"date": "2026-11-20", "weight_kg": 12, "reps": 10},
         "last": {"date": "2026-11-25", "weight_kg": 12, "reps": 12}},
    ],
    "today": [
        {"date": "2026-11-25", "day_name": "Chân", "exercises": ["Squat", "Đạp đùi"]},
        {"date": "2026-11-26", "day_name": None, "exercises": []},
    ],
}  # fmt: skip


@pytest.fixture
def gym(monkeypatch):
    calls: list[httpx.Request] = []
    state = {"status": 200}

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.headers.get("x-integration-key") != KEY:
            return httpx.Response(401, json={"success": False, "message": "Sai khóa", "data": None})
        if state["status"] != 200:
            return httpx.Response(state["status"])
        return httpx.Response(200, json={"success": True, "message": "", "data": SAMPLE})

    monkeypatch.setenv("GYM_BASE_URL", "https://gym.fake")
    monkeypatch.setenv("GYM_API_KEY", KEY)
    monkeypatch.setenv("GYM_USERNAME", "giabao")
    get_settings.cache_clear()
    client.set_transport(httpx.MockTransport(handle))
    yield calls, state
    client.set_transport(None)
    get_settings.cache_clear()


def test_card_summarizes_week_and_caches(auth_client, gym, monkeypatch):
    from app.core import clock

    calls, _ = gym
    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 11, 25, 3, tzinfo=UTC))
    card = auth_client.get("/api/v1/reports/gym").json()["data"]
    assert card["status"] == "ok"
    d = card["data"]
    req = calls[0]
    assert req.url.path == "/api/integration/summary"
    assert dict(req.url.params) == {"username": "giabao", "from": "2026-11-19", "to": "2026-11-25"}
    assert req.headers["user-agent"].startswith("troly-tro-ly-ca-nhan/")
    assert (d["period"], d["sessions_done"], d["sessions_complete"], d["sessions_planned"]) == (
        "week",
        3,
        2,
        4,
    )
    assert d["lift_highlights"] == [
        {"exercise": "Đẩy ngực", "from_kg": 60, "to_kg": 65, "delta_kg": 5},
        {"exercise": "Squat", "from_kg": 80, "to_kg": 82.5, "delta_kg": 2.5},
    ]  # bài không tạ, bài không tăng thì bỏ
    assert d["weight"] == {
        "first_kg": 72.0,
        "last_kg": 71.2,
        "first_date": "2026-11-19",
        "last_date": "2026-11-24",
    }
    assert d["protein"] == {"avg_g": 130, "target_g": 150, "days_logged": 2}
    assert d["today"] == {"date": "2026-11-25", "title": "Chân", "rest": False,
                          "exercises": ["Squat", "Đạp đùi"], "done": True}  # fmt: skip
    assert d["tomorrow"] == {"date": "2026-11-26", "title": "Ngày nghỉ", "rest": True, "exercises": []}
    assert d["app_url"] == "https://gym.baohuynh.io.vn"
    auth_client.get("/api/v1/reports/gym")
    assert len(calls) == 1  # đệm 5 phút
    month = auth_client.get("/api/v1/reports/gym", params={"period": "month"}).json()["data"]
    assert month["data"]["period"] == "month" and dict(calls[-1].url.params)["from"] == "2026-10-27"


def test_card_custom_range_and_limits(auth_client, gym):
    calls, _ = gym
    ok = auth_client.get("/api/v1/reports/gym", params={"from": "2026-09-01", "to": "2026-11-30"})
    assert ok.json()["data"]["status"] == "ok"
    assert dict(calls[-1].url.params)["from"] == "2026-09-01"
    too_long = auth_client.get("/api/v1/reports/gym", params={"from": "2026-08-01", "to": "2026-11-30"})
    assert too_long.status_code == 400


def test_card_disabled_without_env_or_bad_key(auth_client, gym, monkeypatch):
    monkeypatch.setenv("GYM_API_KEY", "")
    get_settings.cache_clear()
    card = auth_client.get("/api/v1/reports/gym").json()["data"]
    assert card == {"status": "disabled", "message": "Chưa nối app gym.", "data": None}
    monkeypatch.setenv("GYM_API_KEY", "khoa-sai")
    get_settings.cache_clear()
    bad = auth_client.get("/api/v1/reports/gym").json()["data"]
    assert bad["status"] == "disabled" and "từ chối" in bad["message"]


def test_card_error_when_gym_down_does_not_raise(auth_client, gym):
    _, state = gym
    state["status"] = 503
    card = auth_client.get("/api/v1/reports/gym").json()["data"]
    assert card["status"] == "error" and card["data"] is None

    def boom(request):
        raise httpx.ConnectTimeout("hết giờ")

    client.set_transport(httpx.MockTransport(boom))
    with pytest.raises(client.GymUnavailable):
        client.fetch_summary(date(2026, 11, 1), date(2026, 11, 7))


def test_feature_flag_hides_gym_parts(monkeypatch):
    from app import registry

    assert registry.feature_enabled("gym") and registry.features()["gym"] is True  # bài kiểm bật cờ
    monkeypatch.setenv("FEATURE_GYM", "false")
    get_settings.cache_clear()
    try:
        assert not registry.feature_enabled("gym")
        assert "gym" not in [name for name, _ in registry.iter_module_parts("router")]
        assert registry.feature_enabled("chat")  # module không có cờ luôn bật
    finally:
        get_settings.cache_clear()
