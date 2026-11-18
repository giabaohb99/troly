"""Bộ mẫu thông báo tin nhắn ở testdata/inbox-notifications (dạng thật thấy trên Galaxy S25+)."""

import os
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from app.modules.inbox import service
from app.modules.inbox.models import InboxMessage

POSTED = datetime.fromisoformat("2026-11-18T21:30:00+07:00")
PARSER = {"com.zing.zalo": "zalo", "org.telegram.messenger": "telegram", "com.facebook.orca": "messenger"}


def _samples() -> list[dict]:
    root = Path(os.environ.get("TESTDATA_DIR") or Path(__file__).resolve().parents[5] / "testdata")
    files = sorted((root / "inbox-notifications").glob("*.yaml"))
    assert files, "Thiếu testdata/inbox-notifications"
    return [s for f in files for s in yaml.safe_load(f.read_text(encoding="utf-8"))]


@pytest.mark.parametrize("s", _samples(), ids=lambda s: s["id"])
def test_sample(db, user, s):
    out = service.ingest_notification(
        db,
        user,
        parser=PARSER[s["package"]],
        app_package=s["package"],
        payload=s["payload"],
        posted_at=POSTED,
    )
    rows = db.query(InboxMessage).filter(InboxMessage.user_id == user.user_id).order_by(InboxMessage.id).all()
    if s["expect"].get("ignored"):
        assert out["status"] == "ignored" and rows == []
        return
    got = [
        {
            "sender": r.sender,
            "text": r.text,
            "conversation_title": r.conversation_title,
            "is_group": r.is_group,
        }
        for r in rows
    ]
    assert got == s["expect"]["messages"]
    assert len({r.conversation_key for r in rows}) == 1


def test_group_key_is_stable_across_notifications(db, user):
    first = {"title": "Nhóm: Gia đình", "messages": [{"sender": None, "text": "Lan: a", "at": None}]}
    second = {"title": "Nhóm: Gia đình", "messages": [{"sender": "Minh", "text": "b", "at": None}]}
    for payload in (first, second):
        service.ingest_notification(
            db, user, parser="zalo", app_package="com.zing.zalo", payload=payload, posted_at=POSTED
        )
    [conv] = service.list_conversations(db, user.user_id, {}, None)["items"]
    assert conv["title"] == "Gia đình" and conv["is_group"] and conv["unread_count"] == 2
