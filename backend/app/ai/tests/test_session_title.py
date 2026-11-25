"""Đặt tên phiên tự động (QĐ-51 bước 1): Haiku rất ngắn, không công cụ, tối đa 6 từ, không dấu chấm."""

import pytest

from app.ai.session_title import clean_title, suggest_title
from app.ai.tests.fake_claude import FakeClaude


def _text(text):
    return {"content": [{"type": "text", "text": text}]}


def test_short_haiku_call_without_tools_or_thinking(make_client):
    fake = FakeClaude([_text("Chi tiêu tháng 11.")])
    title = suggest_title(
        1,
        "tháng này anh tiêu bao nhiêu rồi em",
        "Tháng 11 đại ca đã chi 3.465.000đ, nhiều nhất là ăn uống " + "x" * 500,
        client=make_client(fake),
    )
    assert title == "Chi tiêu tháng 11"
    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5" and req["max_tokens"] == 64 and "tools" not in req
    assert req["thinking"] == {"type": "disabled"}
    sent = req["messages"][0]["content"]
    assert "x" * 201 not in sent  # chỉ 200 ký tự đầu câu trả lời


@pytest.mark.parametrize(
    "raw, want",
    [
        ('"Lịch trình Phước Hải 2 ngày cuối tuần này nhé."', "Lịch trình Phước Hải 2 ngày"),  # cắt còn 6 từ
        ("Thư xin nghỉ phép 🚀", "Thư xin nghỉ phép"),
        ("«Báo cáo chi tiêu»\nGiải thích thêm", "Báo cáo chi tiêu"),
        ("   ", None),
    ],
)
def test_clean_title(raw, want):
    assert clean_title(raw) == want


def test_secret_masked_and_failures_return_none(make_client):
    key = "AIza" + "SyD3mo0nlyFakeKeyForTests0000000000"
    fake = FakeClaude([_text("Khóa API"), {"content": [], "stop_reason": "refusal"}])
    client = make_client(fake)
    suggest_title(1, f"khóa của anh {key}", "Em không nhận khóa qua chat.", client=client)
    assert key not in str(fake.requests[0])
    assert suggest_title(1, "chào", "Chào đại ca.", client=client) is None
    assert suggest_title(1, "", "", client=client) is None
