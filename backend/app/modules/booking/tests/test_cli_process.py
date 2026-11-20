"""Lỗi thật 20/11: chạy thẳng `python -m app.modules.<module>.cli` bị NoReferencedTableError (tab_user) vì
không nạp đủ model. Chạy trong tiến trình con như trên VPS."""

import os
import subprocess
import sys

import pytest


def _run(*args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", "")),
    }
    return subprocess.run(
        [sys.executable, "-m", *args], capture_output=True, text=True, timeout=120, env=env, cwd=os.getcwd()
    )


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (
            ("app.modules.trip.cli", "geocode", "--trip", "987654321"),
            1,
        ),  # không có chuyến: báo, không lỗi model
        (("app.modules.trip.cli", "geocode", "--all"), None),
        (("app.modules.booking.cli", "rescan", "--days", "1"), 0),
        (("app.integrations.google.cli", "rescan-inbox", "--days", "7"), 0),
        (
            (
                "app.integrations.google.cli",
                "rescan-inbox",
                "--account",
                "khong-co@gmail.com",
                "--days",
                "30",
            ),
            1,
        ),
    ],
)
def test_cli_runs_in_fresh_process(args, code):
    out = _run(*args)
    assert "NoReferencedTableError" not in out.stderr and "Traceback" not in out.stderr, out.stderr[-2000:]
    if code is not None:
        assert out.returncode == code, out.stderr[-2000:]


@pytest.fixture
def committed_trip():
    """Dữ liệu thật đã commit để tiến trình con thấy: một điểm cần điền địa phương (ghi xuống DB)."""
    import uuid
    from datetime import date

    from app.core.auth import create_owner
    from app.core.db import SessionLocal
    from app.modules.trip.models import Trip, TripStop
    from app.registry import import_all_models

    import_all_models()
    with SessionLocal() as s:
        u = create_owner(
            s, f"cli-{uuid.uuid4().hex[:8]}@example.com", "CLI", "matkhau-thu-123", "Asia/Ho_Chi_Minh"
        )
        s.flush()
        trip = Trip(user_id=u.id, title="CLI", status="draft", start_date=date(2026, 11, 21),
                    extract_json={"days": [{"day_no": 1, "route_text": "Cần Thơ → Phước Hải"}]})  # fmt: skip
        s.add(trip)
        s.flush()
        # Vai generic: không tìm tọa độ (không gọi mạng) nhưng vẫn được điền địa phương.
        s.add(TripStop(user_id=u.id, trip_id=trip.id, day_no=1, seq=1, title="Quán ăn", role="generic"))
        s.commit()
        trip_id, user_id = trip.id, u.id
    yield trip_id
    with SessionLocal() as s:
        s.execute(__import__("sqlalchemy").text("DELETE FROM tab_user WHERE id = :u"), {"u": user_id})
        s.commit()


def test_trip_cli_writes_in_fresh_process(committed_trip):
    out = _run("app.modules.trip.cli", "geocode", "--trip", str(committed_trip))
    assert out.returncode == 0, out.stderr[-2000:]
    assert f'"trip_id": {committed_trip}' in out.stdout
