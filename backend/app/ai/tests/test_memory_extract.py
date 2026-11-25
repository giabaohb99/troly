"""QĐ-59: rút trí nhớ sau mỗi câu trả lời (Haiku, không công cụ, chạy nền) rồi cập nhật hồ sơ lõi."""

import json

from app.ai.memory_extract import extract_changes, is_trivial
from app.ai.tests.fake_claude import FakeClaude


def _json(data):
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}


def test_extracts_add_and_remove_changes(make_client):
    fake = FakeClaude([_json({"changes": [
        {"op": "add", "section": "Mục tiêu", "fact": "Đang vay mua nhà 2 tỷ, lãi 9%, còn 15 năm"},
        {"op": "remove", "match": "Ở Cần Thơ"},
        {"op": "add", "section": "Không có mục này", "fact": "x"},
        {"op": "add", "section": "Công việc", "fact": ""},
    ]})])  # fmt: skip
    changes = extract_changes(
        1, "## Thông tin cơ bản\n- Ở Cần Thơ\n", "anh vay nhà 2 tỷ lãi 9% còn 15 năm, giờ anh chuyển lên Sài Gòn rồi",
        "Dạ em ghi nhận.", client=make_client(fake),
    )  # fmt: skip
    assert changes == [
        {"op": "add", "section": "Mục tiêu", "fact": "Đang vay mua nhà 2 tỷ, lãi 9%, còn 15 năm"},
        {"op": "remove", "match": "Ở Cần Thơ"},
        {"op": "add", "section": "Ghi nhớ khác", "fact": "x"},  # mục lạ về Ghi nhớ khác; dòng rỗng bỏ
    ]
    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5" and "tools" not in req
    assert "Ở Cần Thơ" in req["messages"][0]["content"]


def test_bad_output_gives_no_changes(make_client):
    fake = FakeClaude([{"content": [{"type": "text", "text": "không phải JSON"}]}])
    assert extract_changes(1, "", "anh làm ở DEGO", "Dạ.", client=make_client(fake)) == []


def test_trivial_messages_skipped():
    assert is_trivial("ok") and is_trivial("cảm ơn em") and is_trivial("  ")
    assert not is_trivial("anh làm ở DEGO") and not is_trivial("vay 2 tỷ")
