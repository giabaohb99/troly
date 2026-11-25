"""Công cụ get_gym_report (QĐ-54, agent AI): app gym giả bằng httpx.MockTransport, Claude giả bằng FakeClaude."""

import copy
import json
import uuid
from datetime import date

import httpx
import pytest

from app.ai import client as ai_client
from app.ai.registry import get_tool, register_tools
from app.ai.schemas import ToolContext
from app.ai.tests.fake_claude import FakeClaude, text_reply, tool_call
from app.core.config import get_settings
from app.integrations.gym import client
from app.modules.gym import tools
from app.modules.gym.tests.test_gym_report import KEY, SAMPLE

RAW = copy.deepcopy(SAMPLE)
RAW["workouts"][0]["exercises"] = [
    {"name": "Đẩy ngực", "sets_done": 4, "top_set": {"weight_kg": 60, "reps": 8}, "volume_kg": 1840},
    {"name": "Kéo xà", "sets_done": 3, "top_set": {"weight_kg": None, "reps": 8}, "volume_kg": 0},
]


@pytest.fixture
def gym(monkeypatch):
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.headers.get("x-integration-key") != KEY:
            return httpx.Response(401)
        return httpx.Response(200, json={"success": True, "message": "", "data": RAW})

    monkeypatch.setenv("GYM_BASE_URL", "https://gym.fake")
    monkeypatch.setenv("GYM_API_KEY", KEY)
    monkeypatch.setenv("GYM_USERNAME", "giabao")
    get_settings.cache_clear()
    client.set_transport(httpx.MockTransport(handle))
    yield calls
    client.set_transport(None)
    get_settings.cache_clear()


def _run(user, **data):
    spec = tools.TOOLS[0]
    ctx = ToolContext(session=None, user=user, conversation_id=None, now=None)
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_report_is_compact_and_read_only(gym, user):
    out = _run(user, from_date="2026-11-19", to_date="2026-11-25")
    assert dict(gym[0].url.params) == {"username": "giabao", "from": "2026-11-19", "to": "2026-11-25"}
    r = out.result
    assert (r["buoi_da_tap"], r["buoi_du_bai"], r["buoi_theo_lich"]) == (3, 2, 4)
    assert r["buoi_tap"][0]["bai"] == [
        {"ten": "Đẩy ngực", "so_set": 4, "top_set": "60kg x 8", "khoi_luong_kg": 1840},
        {"ten": "Kéo xà", "so_set": 3, "top_set": "8 lần (không tạ)", "khoi_luong_kg": 0},
    ]
    lifts = {x["bai"]: x for x in r["tien_bo_ta"]}
    assert lifts["Đẩy ngực"] == {"bai": "Đẩy ngực", "dau": "60kg x 8", "cuoi": "65kg x 8", "tang_kg": 5}
    assert r["tien_bo_ta"][0]["bai"] == "Đẩy ngực" and lifts["Kéo xà"]["tang_kg"] is None
    assert r["can_nang"]["first_kg"] == 72.0 and r["can_nang"]["last_kg"] == 71.2
    nut = r["dinh_duong"]
    assert "bữa đã tick" in nut["ghi_chu"] and "không phải đo" in nut["ghi_chu"]
    day20, day21 = nut["ngay"][0], nut["ngay"][1]
    assert (day20["ngay_tap"], day20["kcal_muc_tieu"], day20["dam_g"], day20["dam_muc_tieu_g"]) == (
        True,
        2500,
        140,
        150,
    )
    assert (day21["ngay_tap"], day21["kcal_muc_tieu"]) == (False, 2200)  # ngày nghỉ theo mục tiêu ngày nghỉ
    assert r["hom_nay"]["title"] == "Chân" and r["ngay_mai"]["rest"] is True
    assert out.actions == [{"type": "open_link", "label": "Mở app gym", "url": "https://gym.baohuynh.io.vn",
                            "kind": "web"}]  # fmt: skip


def test_not_connected_raises_coded_error(monkeypatch, user):
    monkeypatch.setenv("GYM_API_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(client.GymNotConnected) as exc:
            _run(user)
        assert exc.value.code == "GYM_NOT_CONNECTED"
    finally:
        get_settings.cache_clear()


def test_range_over_92_days_rejected_before_call(gym, user):
    with pytest.raises(Exception) as exc:
        _run(user, from_date=date(2026, 8, 1), to_date=date(2026, 11, 30))
    assert getattr(exc.value, "code", "") == "VALIDATION_ERROR" and gym == []


def test_chat_turn_uses_gym_report(auth_client, gym, monkeypatch):
    """Câu hỏi tập luyện -> Claude giả gọi get_gym_report -> kết quả tới Claude -> trả lời theo số."""
    if get_tool("get_gym_report") is None:
        register_tools(tools.TOOLS)
    fake = FakeClaude(
        [
            tool_call("get_gym_report", {"from_date": None, "to_date": None}),
            text_reply("Tuần này anh tập 3/4 buổi, đẩy ngực tăng 5kg."),
        ]
    )
    from app.ai.models import DbRunRecorder

    monkeypatch.setattr(ai_client, "_client", ai_client.ClaudeClient(sdk=fake, recorder=DbRunRecorder()))
    resp = auth_client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid.uuid4()), "text": "tuần này anh tập thế nào"},
    )
    assert resp.status_code == 200, resp.text
    msg = resp.json()["data"]["assistant_message"]
    assert msg["text"].startswith("Tuần này anh tập 3/4 buổi")
    assert any(a["type"] == "open_link" for a in msg["actions"])
    first, second = fake.requests
    assert any(t.get("name") == "get_gym_report" for t in first["tools"])
    static = "".join(b["text"] for b in first["system"])
    assert "get_gym_report" not in static  # lời nhắc tĩnh không nhắc công cụ sau cờ; mô tả công cụ đủ
    result = next(
        b
        for m in second["messages"]
        if isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result"
    )
    data = json.loads(result["content"])
    assert data["buoi_da_tap"] == 3 and "không phải đo" in data["dinh_duong"]["ghi_chu"]
