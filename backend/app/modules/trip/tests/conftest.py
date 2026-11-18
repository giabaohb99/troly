import uuid

import pytest

from app.integrations.google import http
from app.integrations.google.settings import get_google_settings
from app.modules.trip import bridge
from app.modules.trip.tests.fake_maps import FakeMaps, area_of, km
from app.modules.trip.tests.sample_extract import build_sample_extract, sample_bytes

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def maps_fake(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "maps-test-key")
    get_google_settings.cache_clear()
    fake = FakeMaps()
    http.set_transport(fake.transport())
    monkeypatch.setattr(http, "_sleep", lambda s: None)
    yield fake
    http.set_transport(None)
    get_google_settings.cache_clear()


@pytest.fixture
def no_maps(monkeypatch):
    """Đường chính V1 (QĐ-36): không có khóa Maps; mọi lời gọi HTTP ra Google đều là lỗi."""
    import httpx

    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    get_google_settings.cache_clear()
    seen: list = []

    def refuse(request):
        seen.append(request)
        raise AssertionError(f"Không được gọi Maps khi chưa có khóa: {request.url}")

    http.set_transport(httpx.MockTransport(refuse))
    yield seen
    http.set_transport(None)
    get_google_settings.cache_clear()


@pytest.fixture
def stored_files(db, monkeypatch):
    """Thay hàm tệp của module file (agent kiến trúc thêm sau) bằng bản ghi tab_file thật."""
    from app.modules.file.models import File

    saved: dict[int, bytes] = {}

    def store(session, user_id, data, mime, filename, purpose):
        f = File(
            user_id=user_id,
            r2_key=f"u/{user_id}/test/{uuid.uuid4()}",
            original_name=filename,
            mime=mime,
            size_bytes=len(data),
            purpose=purpose,
            status="ready",
        )
        session.add(f)
        session.flush()
        saved[f.id] = data
        return {"id": f.id, "url": f"https://r2.example.test/{f.r2_key}"}

    def read(session, user_id, file_id):
        if file_id in saved:
            return saved[file_id], DOCX, "tep.docx"
        raise AssertionError("tệp lạ")

    monkeypatch.setattr(bridge, "store_generated_file", store)
    monkeypatch.setattr(bridge, "read_file_bytes", read)
    return saved


@pytest.fixture
def sample_file(db, user, stored_files) -> int:
    from app.modules.trip import bridge as b

    made = b.store_generated_file(
        db, user.user_id, sample_bytes(), DOCX, "Lich-trinh-Phuoc-Hai-Tra-Vinh.docx", "trip_source"
    )
    return made["id"]


@pytest.fixture
def fake_ai(monkeypatch):
    calls = {"extract": 0, "summaries": []}

    def extract(user_id, content, output_model, hint=None):
        calls["extract"] += 1
        assert isinstance(content, str) and "[chợ Phước Hải](" in content
        return build_sample_extract(content)

    def summaries(user_id, trip_title, options):
        calls["summaries"].append(options)
        return {
            o["option_id"]: {
                "summary": f"Chạy {o['total_km']} km, còn {o['red_count']} rủi ro đỏ.",
                "tips": ["Gọi hotline phà trước 1 ngày.", "Mặc áo phản quang khi chạy đêm."],
            }
            for o in options
        }

    def estimate(user_id, trip_title, region, stops, legs, think, travel_mode="motorbike"):
        """Ước tính giả theo vùng trong tên (như AI đoán): chim bay nhân 1,3, xe máy 35 km/giờ."""
        calls.setdefault("estimate", []).append({"web": think, "stops": stops, "legs": legs})
        by_id = {st["stop_id"]: st for st in stops}
        out = []
        for pair in legs:
            a, b = by_id[pair["from_stop_id"]], by_id[pair["to_stop_id"]]
            pa = (a["lat"], a["lng"]) if a["lat"] is not None else area_of(a["place_query"] or a["title"])
            pb = (b["lat"], b["lng"]) if b["lat"] is not None else area_of(b["place_query"] or b["title"])
            d = km(pa, pb) * 1.3
            ferry = 30 if b["category"] == "pha" else 0
            note = "theo QL1A" if pa[1] < 106.5 and pb[1] < 106.9 else ""
            out.append(
                {
                    "from_stop_id": a["stop_id"],
                    "to_stop_id": b["stop_id"],
                    "km": round(d, 1),
                    "minutes": round(d / 35 * 60) + ferry,
                    "ferry_minutes": ferry,
                    "estimated": True,
                    "adjusted": False,
                    "note": note,
                }
            )
        checks = []
        if think:
            for st in stops:
                if "Chùa Hang" in st["title"]:
                    periods = [
                        {
                            "open": {"day": dd, "hour": 7, "minute": 0},
                            "close": {"day": dd, "hour": 17, "minute": 0},
                        }
                        for dd in range(7)
                        if dd != 1
                    ]
                    checks.append(
                        {
                            "stop_id": st["stop_id"],
                            "kind": "opening_hours",
                            "hours": {"regular": {"periods": periods}},
                            "last_time": None,
                            "text": "Nghỉ thứ Hai",
                            "source_url": "https://example.test",
                        }
                    )
                if st["category"] == "pha" and "Bình Khánh" in st["title"]:
                    checks.append(
                        {
                            "stop_id": st["stop_id"],
                            "kind": "ferry_last",
                            "hours": None,
                            "last_time": "16:00",
                            "text": "Phà Bình Khánh chuyến cuối 16:00",
                            "source_url": "https://example.test/pha",
                        }
                    )
        if think:
            hang = next((st for st in stops if "Ao Bà Om" in st["title"]), None)
            if hang:
                checks.append(
                    {
                        "stop_id": hang["stop_id"],
                        "kind": "opening_hours",
                        "hours": None,
                        "last_time": None,
                        "text": "Không tìm được giờ mở cửa trên web",
                        "source_url": None,
                    }
                )
        return {"legs": out, "checks": checks, "sources": []}

    monkeypatch.setattr(bridge, "extract_trip", extract)
    monkeypatch.setattr(bridge, "summarize_options", summaries)
    monkeypatch.setattr(bridge, "estimate_legs", estimate)
    return calls


def run_job(db, kind: str, trip_id: int):
    from sqlalchemy import select

    from app.core.models import JobQueue
    from app.modules.trip import jobs

    job = db.scalar(
        select(JobQueue).where(JobQueue.kind == kind, JobQueue.payload["trip_id"].as_integer() == trip_id)
    )
    handler = jobs.run_import if kind == "trip_import" else jobs.run_evaluate
    return handler(db, job)
