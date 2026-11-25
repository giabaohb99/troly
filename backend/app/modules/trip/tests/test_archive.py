"""QĐ-42: chuyến đã đi nằm ở mục Đã đi; Đi lại chép thành chuyến nháp mới với ngày mới."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import clock
from app.core.errors import ValidationError
from app.modules.trip import service
from app.modules.trip.models import Trip, TripFact, TripOption, TripStop
from app.modules.trip.tests.conftest import run_job

# 17h00 giờ UTC ngày 19/11 là 0h00 ngày 20/11 giờ Việt Nam.
NOW = datetime(2026, 11, 19, 17, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen(request, monkeypatch):
    if "auth_client" not in request.fixturenames:  # token đăng nhập dùng giờ thật
        monkeypatch.setattr(clock, "now", lambda: NOW)


@pytest.fixture
def trip(db, user, no_maps, fake_ai, sample_file):
    data = service.import_trip(db, user, file_id=sample_file, start_date=date(2026, 11, 21))
    run_job(db, "trip_import", data["trip_id"])
    return db.get(Trip, data["trip_id"])


def _ids(db, user, scope):
    return [t["id"] for t in service.list_trips(db, user, scope=scope)]


def _stops(db, trip_id):
    return list(
        db.scalars(
            select(TripStop).where(TripStop.trip_id == trip_id).order_by(TripStop.day_no, TripStop.seq)
        )
    )


def test_past_by_end_date_uses_user_timezone(db, user, trip):
    service.update_trip(db, user, trip.id, {"start_date": date(2026, 11, 17)})  # cuối 19/11
    # Theo UTC vẫn là 19/11, nhưng giờ Việt Nam đã sang 20/11: chuyến đã đi.
    assert _ids(db, user, "past") == [trip.id] and _ids(db, user, "upcoming") == []
    assert service.get_trip(db, user, trip.id)["is_past"] is True


def test_upcoming_lists_future_and_undated_drafts(db, user, trip):
    draft = Trip(user_id=user.user_id, title="Chưa có ngày", status="draft")
    db.add(draft)
    db.flush()
    assert _ids(db, user, "upcoming") == [draft.id, trip.id]
    assert _ids(db, user, "past") == []
    assert {t["id"] for t in service.list_trips(db, user)} == {draft.id, trip.id}  # không scope là tất cả


def test_archive_and_unarchive(db, user, trip):
    brief = service.archive_trip(db, user, trip.id)
    assert brief["is_past"] is True and brief["archived_at"] == NOW
    assert service.archive_trip(db, user, trip.id)["archived_at"] == NOW  # bấm lại không đổi
    assert _ids(db, user, "past") == [trip.id]
    assert db.get(Trip, trip.id) is not None and _stops(db, trip.id)  # không xóa gì

    brief = service.unarchive_trip(db, user, trip.id)
    assert brief["archived_at"] is None and brief["is_past"] is False
    assert _ids(db, user, "upcoming") == [trip.id]


def test_bad_scope_rejected(db, user):
    with pytest.raises(ValidationError):
        service.list_trips(db, user, scope="all")


def test_duplicate_copies_plan_to_new_dates_without_evaluation(db, user, trip, fake_ai):
    service.evaluate_trip(db, user, trip.id)
    run_job(db, "trip_evaluate", trip.id)
    service.archive_trip(db, user, trip.id)
    old_stops = _stops(db, trip.id)

    out = service.duplicate_trip(db, user, trip.id, date(2027, 1, 2), "Phước Hải lần 2")
    new = db.get(Trip, out["id"])
    assert new.id != trip.id and new.title == "Phước Hải lần 2" and new.status == "draft"
    assert (
        new.start_date == date(2027, 1, 2)
        and new.end_date - new.start_date == trip.end_date - trip.start_date
    )
    assert new.evaluation is None and new.chosen_option_id is None and new.archived_at is None
    assert db.scalars(select(TripOption).where(TripOption.trip_id == new.id)).first() is None
    assert new.hotels == trip.hotels and new.notes == trip.notes

    new_stops = _stops(db, new.id)
    shift = date(2027, 1, 2) - date(2026, 11, 21)
    assert len(new_stops) == len(old_stops)
    for a, b in zip(old_stops, new_stops, strict=True):
        assert (b.title, b.source_url, b.place_query, b.day_no, b.seq) == (
            a.title,
            a.source_url,
            a.place_query,
            a.day_no,
            a.seq,
        )
        if a.planned_start:
            assert b.planned_start - a.planned_start == timedelta(days=shift.days)
    children = [s for s in new_stops if s.parent_stop_id]
    assert all(db.get(TripStop, s.parent_stop_id).trip_id == new.id for s in children)
    old_facts = db.scalars(select(TripFact).where(TripFact.trip_id == trip.id)).all()
    new_facts = db.scalars(select(TripFact).where(TripFact.trip_id == new.id)).all()
    assert len(new_facts) == len(old_facts)
    assert all(f.stop_id is None or db.get(TripStop, f.stop_id).trip_id == new.id for f in new_facts)

    assert out["id"] in _ids(db, user, "upcoming") and trip.id in _ids(db, user, "past")
    service.evaluate_trip(db, user, new.id)  # đánh giá lại khi được yêu cầu
    run_job(db, "trip_evaluate", new.id)
    db.refresh(new)
    assert new.evaluation is not None


def test_duplicate_keeps_title_when_not_given(db, user, trip):
    out = service.duplicate_trip(db, user, trip.id, date(2027, 1, 2))
    assert out["title"] == trip.title


def test_api_scope_archive_duplicate(auth_client, db, user, trip):
    service.update_trip(
        db, user, trip.id, {"start_date": date(2099, 11, 21)}
    )  # giờ thật: chuyến phải còn sắp tới
    r = auth_client.get("/api/v1/trips")
    assert r.status_code == 200 and [t["id"] for t in r.json()["data"]["items"]] == [trip.id]
    r = auth_client.post(f"/api/v1/trips/{trip.id}/archive")
    assert r.status_code == 200 and r.json()["data"]["is_past"] is True
    assert auth_client.get("/api/v1/trips").json()["data"]["items"] == []
    past = auth_client.get("/api/v1/trips?scope=past").json()["data"]["items"]
    assert [t["id"] for t in past] == [trip.id]
    r = auth_client.post(f"/api/v1/trips/{trip.id}/duplicate", json={"start_date": "2027-01-02"})
    assert r.status_code == 201 and r.json()["data"]["status"] == "draft"
    assert auth_client.get("/api/v1/trips?scope=bad").status_code == 400
    r = auth_client.post(f"/api/v1/trips/{trip.id}/unarchive")
    assert r.status_code == 200 and r.json()["data"]["archived_at"] is None
