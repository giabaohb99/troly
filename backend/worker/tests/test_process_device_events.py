"""Job process_device_events: sự kiện sang chi tiêu (ghép cặp) và hộp tin (10 mục 3.9)."""

import uuid
from datetime import datetime

import pytest
import yaml
from sqlalchemy import text

from app.core import clock
from app.modules.device.models import Device, DeviceEvent
from app.modules.expense.models import Expense
from app.modules.expense.tests.samples import sample
from app.modules.inbox.models import InboxMessage
from worker.jobs import device_events

NOW = datetime.fromisoformat("2026-12-02T12:00:00+07:00")


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)


@pytest.fixture
def device(db, user):
    d = Device(user_id=user.user_id, name="S25+", token_hash="h" * 64, token_prefix="dev_xxxx")
    db.add(d)
    db.flush()
    return d


def add_event(db, device, package, payload, posted_at, kind="notification"):
    ev = DeviceEvent(
        user_id=device.user_id,
        device_id=device.id,
        client_event_id=uuid.uuid4(),
        kind=kind,
        app_package=package,
        posted_at=posted_at,
        payload=payload,
    )
    db.add(ev)
    db.flush()
    return ev


def from_sample(db, device, sample_id):
    s = sample(sample_id)
    return add_event(db, device, s["package"], {"title": s["title"], "text": s["text"]}, s["posted_at"])


def test_bank_pair_and_inbox_and_reminder(db, device):
    vcb = from_sample(db, device, "vcb-momo-001")
    momo = from_sample(db, device, "momo-nap-001")
    promo = from_sample(db, device, "vcb-km-001")
    chat = add_event(
        db,
        device,
        "com.zing.zalo",
        {"title": "Lan", "text": "Chào anh", "messages": [{"sender": "Lan", "text": "Chào anh", "at": None}]},
        NOW,
    )
    reminder = add_event(
        db,
        device,
        None,
        {"reminder_key": "k", "source": "task", "action": "done"},
        NOW,
        kind="reminder_action",
    )

    assert device_events.process_device_events() == 5

    for ev in (vcb, momo, promo, chat, reminder):
        db.refresh(ev)
    assert (vcb.status, vcb.result_kind) == ("done", "expense")
    assert (momo.status, momo.result_kind, momo.result_id) == ("done", "transfer_merged", vcb.result_id)
    assert (promo.status, promo.result_kind, promo.error) == ("ignored", "none", "Không phải giao dịch")
    assert (chat.status, chat.result_kind) == ("done", "inbox_message")
    assert reminder.status == "ignored" and reminder.locked_at is None and reminder.processed_at is not None

    row = db.get(Expense, vcb.result_id)
    assert row.kind == "transfer" and row.device_event_id == vcb.id
    inbox = db.get(InboxMessage, chat.result_id)
    assert inbox.device_event_id == chat.id and inbox.sender == "Lan"
    assert device_events.process_device_events() == 0


def test_failure_is_retried_then_failed(db, device, monkeypatch):
    ev = from_sample(db, device, "vcb-chi-001")

    def boom(*a, **kw):
        raise RuntimeError("hỏng")

    monkeypatch.setattr(device_events, "handle_event", boom)
    device_events.process_device_events()
    db.refresh(ev)
    assert ev.status == "pending" and ev.attempts == 1 and ev.next_attempt_at > NOW
    db.execute(text("UPDATE tab_device_event SET attempts = 4, next_attempt_at = now() - interval '1 day'"))
    monkeypatch.setattr(clock, "now", lambda: datetime.fromisoformat("2027-01-01T00:00:00+07:00"))
    device_events.process_device_events()
    db.refresh(ev)
    assert ev.status == "failed"


def test_expense_source_and_export_samples(db, user, device, tmp_path):
    from app import cli
    from app.modules.expense import service as expense_service

    ev = from_sample(db, device, "vcb-chi-001")
    device_events.process_device_events()
    db.refresh(ev)
    # Gọi service vì đồng hồ giả làm JWT chưa tới hạn; route chỉ bọc hàm này.
    source = expense_service.get_expense_source(db, user, ev.result_id)
    assert source["app_package"] == "com.VCB" and "Com trua" in source["text"]

    out = tmp_path / "samples.yaml"
    assert cli.main(["export-bank-samples", "--out", str(out)]) == 0
    exported = yaml.safe_load(out.read_text(encoding="utf-8"))
    [item] = exported
    assert item["package"] == "com.VCB" and item["expect"]["amount_vnd"] == 45_000
    assert item["expect"]["account_last4"] == "9876" and item["parser"] == "regex:vcb"
    assert "2,345,000" not in item["text"]


def test_reminder_done_completes_task(db, user, device):
    from app.modules.task import service as task_service

    task = task_service.create_task(db, user, {"title": "Uống thuốc", "due_at": NOW})
    ev = add_event(
        db,
        device,
        None,
        {
            "reminder_key": f"task:{task['id']}:x:0",
            "source": "task",
            "source_id": str(task["id"]),
            "action": "done",
        },
        NOW,
        kind="reminder_action",
    )
    device_events.process_device_events()
    db.refresh(ev)
    assert (ev.status, ev.result_kind, ev.result_id) == ("done", "task_updated", task["id"])
    assert task_service.get_task(db, user, task["id"])["status"] == "done"


def test_reprocess_inbox_and_export_structure_only(db, user, device, tmp_path):
    from app import cli

    ev = add_event(
        db,
        device,
        "com.zing.zalo",
        {
            "title": "Nhóm: Bạn cũ",
            "text": "Tuấn: đi cafe",
            "messages": [{"sender": None, "text": "Tuấn: đi cafe"}],
        },
        NOW,
    )
    device_events.process_device_events()
    db.execute(text("UPDATE tab_inbox_message SET sender = 'sai', conversation_title = 'sai'"))
    assert cli.main(["reprocess-inbox"]) == 0
    [row] = db.query(InboxMessage).all()
    assert (row.sender, row.conversation_title, row.is_group, row.device_event_id) == (
        "Tuấn",
        "Bạn cũ",
        True,
        ev.id,
    )

    out = tmp_path / "inbox.yaml"
    assert cli.main(["export-inbox-samples", "--out", str(out)]) == 0
    [item] = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert item["payload"]["title"] == "Nhóm: Người 1" and item["payload"]["text"] == "Người 2: (nội dung)"
    assert "cafe" not in out.read_text(encoding="utf-8") and "Tuấn" not in out.read_text(encoding="utf-8")
