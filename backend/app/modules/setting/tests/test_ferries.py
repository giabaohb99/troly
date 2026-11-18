import pytest

from app.core.errors import ValidationError
from app.modules.setting import service


def test_trip_ferries_default_and_validation(db, user):
    assert service.get_value(db, user.user_id, "trip.ferries") == []
    ferry = {
        "name": "Phà Cát Lái",
        "place_query": "Bến phà Cát Lái",
        "first_time": "04:00",
        "last_time": "23:30",
        "hotline": None,
        "note": None,
        "updated_at": "2026-11-19",
    }
    service.update(db, user.user_id, {"trip.ferries": [ferry]})
    assert service.get_value(db, user.user_id, "trip.ferries")[0]["name"] == "Phà Cát Lái"
    for bad in ([{**ferry, "first_time": "25:00"}], [{**ferry, "lạ": 1}], [ferry] * 11, [{"name": ""}]):
        with pytest.raises(ValidationError):
            service.update(db, user.user_id, {"trip.ferries": bad})
