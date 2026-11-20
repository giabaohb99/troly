"""Luật nghiệp vụ module trip (41). Router, việc nền và công cụ AI (agent AI) gọi các hàm công khai ở đây."""

import logging
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import UserContext
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.models import JobQueue
from app.integrations.google import maps
from app.modules.trip import bridge, engine, geocode, links, places
from app.modules.trip.docx_export import DocDay, DocTrip, build_docx
from app.modules.trip.hours_text import hours_from_text
from app.modules.trip.models import CATEGORIES, RouteCache, Trip, TripFact, TripOption, TripStop
from app.modules.trip.normalize import Normalized, check_extract, fold, normalize
from app.modules.trip.reader import read_docx
from app.modules.trip.schemas import TripExtract

log = logging.getLogger("troly.trip")

ROUTED_ROLES = ("main", "via")
HOURS_CATEGORIES = ("tham_quan", "an_uong", "mua_sam")
MAX_INTERMEDIATES = 25
WEEKDAY_SHORT = ["thứ 2", "thứ 3", "thứ 4", "thứ 5", "thứ 6", "thứ 7", "chủ nhật"]
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class TripBusy(AppError):
    status = 409
    code = "CONFLICT"
    message = "Chuyến đang được xử lý, đợi xong rồi thử lại."


# ---------- Đọc ----------


def _get(session: Session, user_id: int, trip_id: int, lock: bool = False) -> Trip:
    stmt = select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    trip = session.scalar(stmt)
    if trip is None:
        raise NotFoundError("Không tìm thấy chuyến đi.")
    return trip


def _stops(session: Session, trip_id: int) -> list[TripStop]:
    return list(
        session.scalars(
            select(TripStop)
            .where(TripStop.trip_id == trip_id)
            .order_by(TripStop.day_no, TripStop.seq, TripStop.id)
        )
    )


def _num(value) -> float | None:
    return float(value) if value is not None else None


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def serialize_stop(s: TripStop, leg: dict | None = None) -> dict:
    return {
        "id": s.id,
        "day_no": s.day_no,
        "seq": s.seq,
        "title": s.title,
        "category": s.category,
        "role": s.role,
        "parent_stop_id": s.parent_stop_id,
        "time_text": s.time_text,
        "planned_start": _iso(s.planned_start),
        "planned_end": _iso(s.planned_end),
        "approx": s.approx,
        "fixed": s.fixed,
        "optional": s.optional,
        "stay_minutes": s.stay_minutes,
        "place_query": s.place_query,
        "area": s.area,
        "search_query": _link_stop(s).query,  # chuỗi tìm Google Maps khi không có tọa độ: tên kèm địa phương
        "source_url": s.source_url,
        "place_id": s.place_id,
        "lat": _num(s.lat),
        "lng": _num(s.lng),
        "resolve_status": s.resolve_status,
        "phone": s.phone,
        "cost_note": s.cost_note,
        "note": s.note,
        "booking": {k: v for k, v in s.booking.items() if k != "added_stop"} if s.booking else None,
        "leg_km": (leg or {}).get("leg_km"),
        "leg_minutes": (leg or {}).get("leg_minutes"),
    }


def _chosen(session: Session, trip: Trip) -> TripOption | None:
    return session.get(TripOption, trip.chosen_option_id) if trip.chosen_option_id else None


def _plan_index(evaluation: dict | None) -> tuple[dict[int, dict], dict[int, dict]]:
    legs: dict[int, dict] = {}
    days: dict[int, dict] = {}
    for day in (evaluation or {}).get("plan", {}).get("days", []):
        days[day["day_no"]] = day
        for item in day.get("stops", []):
            legs[item["stop_id"]] = item
    return legs, days


def serialize_trip(session: Session, trip: Trip) -> dict:
    stops = _stops(session, trip.id)
    legs, plan_days = _plan_index(trip.evaluation)
    extract_days = {d.get("day_no"): d for d in (trip.extract_json or {}).get("days", [])}
    days = []
    for day_no in sorted({s.day_no for s in stops} | set(extract_days)):
        info = extract_days.get(day_no, {})
        day_date = trip.start_date + timedelta(days=day_no - 1) if trip.start_date else None
        plan = plan_days.get(day_no, {})
        days.append(
            {
                "day_no": day_no,
                "date": _iso(day_date),
                "weekday_text": info.get("weekday_text"),
                "title": info.get("title"),
                "total_km": plan.get("km"),
                "ride_minutes": plan.get("ride_minutes"),
                "stops": [serialize_stop(s, legs.get(s.id)) for s in stops if s.day_no == day_no],
            }
        )
    facts = session.scalars(select(TripFact).where(TripFact.trip_id == trip.id).order_by(TripFact.id))
    options = session.scalars(select(TripOption).where(TripOption.trip_id == trip.id).order_by(TripOption.id))
    evaluation = trip.evaluation
    return {
        "id": trip.id,
        "title": trip.title,
        "start_date": _iso(trip.start_date),
        "end_date": _iso(trip.end_date),
        "nights": trip.nights,
        "travel_mode": trip.travel_mode,
        "origin_text": trip.origin_text,
        "status": trip.status,
        "error": trip.error,
        "archived_at": trip.archived_at,
        "is_past": is_past(trip, _local_today(session, trip.user_id)),
        "chosen_option_id": trip.chosen_option_id,
        "start_date_suggested": bool((trip.extract_json or {}).get("_start_date_suggested")),
        "advice": (evaluation or {}).get("advice"),
        "notes": trip.notes or [],
        "days": days,
        "needs_confirmation": [
            {
                "stop_id": s.id,
                "day_no": s.day_no,
                "title": s.title,
                "place_query": s.place_query,
                "candidates": s.alternatives or [],
            }
            for s in stops
            if _needs_confirmation(s)
        ],
        "facts": [
            {
                "id": f.id,
                "kind": f.kind,
                "day_no": f.day_no,
                "stop_id": f.stop_id,
                "value_time": f.value_time.strftime("%H:%M") if f.value_time else None,
                "value_text": f.value_text,
                "text": f.text,
            }
            for f in facts
        ],
        "options": [
            {
                "id": o.id,
                "name": o.name,
                "summary": o.summary,
                "total_km": _num(o.total_km),
                "total_ride_minutes": o.total_ride_minutes,
                "night_ride_minutes": o.night_ride_minutes,
                "red_count": o.red_count,
                "yellow_count": o.yellow_count,
                "changes": o.changes,
                "chosen": o.chosen,
            }
            for o in options
        ],
        "evaluation": {"evaluated_at": evaluation.get("evaluated_at"), "risks": evaluation.get("risks", [])}
        if evaluation
        else None,
    }


def _needs_confirmation(s: TripStop) -> bool:
    """Điểm cần người dùng chọn đúng chỗ. QĐ-36: không có khóa Maps thì không bao giờ có place_id;
    điểm có tên (link tìm Google Maps theo tên) đã đủ để mở bản đồ và ước tính chặng, không tính.
    Điểm không có tên lẫn link thì vốn là `manual`, không có gì để xác nhận."""
    return (
        maps.configured()
        and s.resolve_status in ("uncertain", "not_found")
        and s.role in ROUTED_ROLES
        and bool(s.place_query)
    )


def _brief(session: Session, trip: Trip) -> dict:
    chosen = _chosen(session, trip)
    ev = trip.evaluation or {}
    risks = ev.get("risks", [])
    pending = maps.configured() and session.scalar(
        select(func.count())
        .select_from(TripStop)
        .where(
            TripStop.trip_id == trip.id,
            TripStop.resolve_status.in_(("uncertain", "not_found")),
            TripStop.role.in_(ROUTED_ROLES),
            TripStop.place_query.is_not(None),
        )
    )
    return {
        "id": trip.id,
        "title": trip.title,
        "start_date": _iso(trip.start_date),
        "end_date": _iso(trip.end_date),
        "nights": trip.nights,
        "travel_mode": trip.travel_mode,
        "status": trip.status,
        "total_km": _num(chosen.total_km) if chosen else ev.get("total_km"),
        "red_count": chosen.red_count
        if chosen
        else (sum(r["level"] == "red" for r in risks) if ev else None),
        "yellow_count": chosen.yellow_count
        if chosen
        else (sum(r["level"] == "yellow" for r in risks) if ev else None),
        "needs_confirmation_count": pending or 0,
        "archived_at": trip.archived_at,
        "is_past": is_past(trip, _local_today(session, trip.user_id)),
    }


SCOPES = ("upcoming", "past")


def _local_today(session: Session, user_id: int) -> date:
    return clock.now().astimezone(ZoneInfo(_user_tz(session, user_id))).date()


def is_past(trip: Trip, today: date) -> bool:
    """Đã đi (QĐ-42): đã lưu trữ, hoặc ngày cuối (không có thì ngày đi) trước hôm nay theo giờ người dùng."""
    last = trip.end_date or trip.start_date
    return trip.archived_at is not None or (last is not None and last < today)


def list_trips(
    session: Session,
    user: UserContext,
    status: str | None = None,
    query: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    """scope `upcoming` (sắp đi, gồm nháp chưa có ngày) hoặc `past` (Đã đi); None là tất cả."""
    if scope is not None and scope not in SCOPES:
        raise ValidationError(fields={"scope": "Chỉ nhận upcoming hoặc past."})
    stmt = select(Trip).where(Trip.user_id == user.user_id)
    if status:
        stmt = stmt.where(Trip.status == status)
    if query:
        stmt = stmt.where(
            or_(
                Trip.search_vector.op("@@")(func.plainto_tsquery("troly_vn", query)),
                Trip.title.ilike(f"%{query}%"),
            )
        )
    order = (Trip.start_date.desc().nulls_last(), Trip.id.desc())
    if scope is not None:
        last = func.coalesce(Trip.end_date, Trip.start_date)
        past = or_(
            Trip.archived_at.is_not(None),
            func.coalesce(last < _local_today(session, user.user_id), False),  # chưa có ngày: chưa đi
        )
        if scope == "past":
            stmt = stmt.where(past)
        else:
            stmt = stmt.where(~past)
            order = (Trip.start_date.asc().nulls_first(), Trip.id.desc())  # gần nhất trước, nháp lên đầu
    rows = session.scalars(stmt.order_by(*order).limit(100))
    return [_brief(session, t) for t in rows]


def archive_trip(session: Session, user: UserContext, trip_id: int) -> dict:
    """Chuyển chuyến sang Đã đi; không xóa gì. Bấm lại không đổi giờ lưu trữ."""
    trip = _get(session, user.user_id, trip_id)
    if trip.archived_at is None:
        trip.archived_at = clock.now()
        session.flush()
    return serialize_trip(session, trip)


def unarchive_trip(session: Session, user: UserContext, trip_id: int) -> dict:
    """Bỏ lưu trữ. Chuyến có ngày cuối trước hôm nay vẫn nằm ở Đã đi (is_past theo ngày)."""
    trip = _get(session, user.user_id, trip_id)
    trip.archived_at = None
    session.flush()
    return serialize_trip(session, trip)


STOP_COPY = (
    "day_no", "seq", "title", "category", "role", "time_text", "approx", "fixed", "optional", "stay_minutes",
    "place_query", "area", "source_url", "place_id", "lat", "lng", "coord_source", "coord_fetched_at",
    "resolve_status", "phone", "cost_note", "note", "alternatives",
)  # fmt: skip


def duplicate_trip(
    session: Session, user: UserContext, trip_id: int, start_date: date, title: str | None = None
) -> dict:
    """Đi lại (QĐ-42): chép ngày, điểm dừng, link, khách sạn, ghi chú, mốc giờ phà và hotline thành chuyến
    nháp mới bắt đầu từ start_date. Không chép đánh giá, phương án, tệp xuất; đánh giá lại khi được yêu cầu."""
    if start_date is None:
        raise ValidationError(fields={"start_date": "Chọn ngày đi cho chuyến mới."})
    src = _get(session, user.user_id, trip_id)
    if src.status in ("importing", "failed"):
        raise ValidationError("Chuyến này chưa đọc xong, chưa chép được.")
    shift = start_date - src.start_date if src.start_date else timedelta(0)
    extract = {k: v for k, v in (src.extract_json or {}).items() if k != "_draft"}
    extract["_start_date_suggested"] = False
    end_date = src.end_date + shift if src.end_date and src.start_date else None
    trip = Trip(
        user_id=user.user_id,
        title=((title or src.title).strip() or src.title)[:200],
        start_date=start_date,
        end_date=end_date,
        nights=src.nights,
        travel_mode=src.travel_mode,
        origin_text=src.origin_text,
        end_text=src.end_text,
        status="draft",
        source_kind=src.source_kind,
        source_file_id=src.source_file_id,
        source_text=src.source_text,
        extract_json=extract,
        notes=list(src.notes or []),
        hotels=list(src.hotels or []),
    )
    session.add(trip)
    session.flush()
    stops = _stops(session, src.id)
    new_ids: dict[int, int] = {}
    for old in stops:
        row = TripStop(user_id=user.user_id, trip_id=trip.id, **{k: getattr(old, k) for k in STOP_COPY})
        row.planned_start = old.planned_start + shift if old.planned_start else None
        row.planned_end = old.planned_end + shift if old.planned_end else None
        session.add(row)
        session.flush()
        new_ids[old.id] = row.id
    for old in stops:
        if old.parent_stop_id in new_ids:
            session.get(TripStop, new_ids[old.id]).parent_stop_id = new_ids[old.parent_stop_id]
    for f in session.scalars(select(TripFact).where(TripFact.trip_id == src.id).order_by(TripFact.id)):
        session.add(
            TripFact(
                user_id=user.user_id,
                trip_id=trip.id,
                kind=f.kind,
                stop_id=new_ids.get(f.stop_id),
                day_no=f.day_no,
                value_time=f.value_time,
                value_text=f.value_text,
                text=f.text,
            )
        )
    session.flush()
    return serialize_trip(session, trip)


def get_trip(session: Session, user: UserContext, trip_id: int) -> dict:
    return serialize_trip(session, _get(session, user.user_id, trip_id))


def find_trip(
    session: Session,
    user: UserContext,
    *,
    trip_id: int | None = None,
    query: str | None = None,
    day_no: int | None = None,
) -> dict:
    """Cho công cụ get_trip: theo id, hoặc chuyến khớp tên mới nhất; day_no thì chỉ giữ ngày đó."""
    if trip_id is None:
        hits = list_trips(session, user, query=query)
        if not hits:
            raise NotFoundError("Không tìm thấy chuyến đi nào khớp.")
        trip_id = hits[0]["id"]
    data = get_trip(session, user, trip_id)
    if day_no is not None:
        data["days"] = [d for d in data["days"] if d["day_no"] == day_no]
        if data.get("evaluation"):
            data["evaluation"]["risks"] = [
                r for r in data["evaluation"]["risks"] if r["day_no"] in (day_no, None)
            ]
    return data


# ---------- Nhập ----------


def _queue(session: Session, user_id: int, kind: str, trip_id: int, extra: dict | None = None) -> int:
    job = JobQueue(
        user_id=user_id,
        kind=kind,
        payload={"trip_id": trip_id, **(extra or {})},
        dedupe_key=f"{kind}:{trip_id}",
        max_attempts=1,
    )
    session.add(job)
    session.flush()
    session.execute(text("NOTIFY troly_wake, 'job'"))
    return job.id


def queue_geocode(session: Session, trip: Trip) -> bool:
    """Đặt việc nền lấy tọa độ OpenStreetMap khi còn điểm chưa có tọa độ (1 yêu cầu mỗi giây nên không
    chạy trong lượt chat). Đã có việc chờ thì thôi."""
    missing = session.scalar(
        select(func.count())
        .select_from(TripStop)
        .where(TripStop.trip_id == trip.id, TripStop.lat.is_(None), TripStop.role.in_(ROUTED_ROLES))
    )
    if not missing:
        return False
    stmt = (
        pg_insert(JobQueue)
        .values(
            user_id=trip.user_id,
            kind="trip_geocode",
            payload={"trip_id": trip.id},
            dedupe_key=f"trip_geocode:{trip.id}",
            max_attempts=1,
        )
        .on_conflict_do_nothing()
    )
    queued = session.execute(stmt).rowcount > 0
    if queued:
        session.execute(text("NOTIFY troly_wake, 'job'"))
    return queued


def run_geocode(session: Session, job) -> dict:
    """Việc nền trip_geocode (cũng dùng cho lệnh CLI chạy lại chuyến cũ)."""
    trip = _get(session, job.user_id, job.payload["trip_id"])
    return geocode.geocode_trip(session, trip)


def import_trip(
    session: Session,
    user: UserContext,
    *,
    file_id: int | None = None,
    text: str | None = None,
    url: str | None = None,
    draft: dict | None = None,
    title: str | None = None,
    start_date: date | None = None,
    travel_mode: str | None = None,
) -> dict:
    sources = [x for x in (file_id, text, url, draft) if x]
    if len(sources) != 1:
        raise ValidationError("Gửi đúng một trong: tệp, đoạn mô tả, link hoặc bản nháp.")
    if draft is not None:
        TripExtract.model_validate(draft)
    kind = "text" if text or draft else "link" if url else None
    trip = Trip(
        user_id=user.user_id,
        title=(title or "Chuyến đi mới")[:200],
        status="importing",
        source_kind=kind,
        source_file_id=file_id,
        source_text=text or url,
        travel_mode=travel_mode or "motorbike",
        start_date=start_date,
        extract_json={"_draft": draft} if draft else None,
    )
    session.add(trip)
    session.flush()
    return {
        "trip_id": trip.id,
        "job_id": _queue(session, user.user_id, "trip_import", trip.id),
        "status": "importing",
    }


def _content_for(session: Session, trip: Trip) -> tuple[object, str | None]:
    """Trả (nội dung đưa Claude, chữ gốc để kiểm link)."""
    if trip.source_file_id:
        data, mime, name = bridge.read_file_bytes(session, trip.user_id, trip.source_file_id)
        if mime == DOCX_MIME or (name or "").lower().endswith(".docx"):
            trip.source_kind = "docx"
            doc = read_docx(data)
            return doc.text, doc.text
        trip.source_kind = "pdf" if mime == "application/pdf" else "image"
        return bridge.claude_blocks(session, trip.user_id, [trip.source_file_id]), None
    if trip.source_kind == "link":
        return f"Lịch trình từ link Google Maps: [{trip.source_text}]({trip.source_text})", trip.source_text
    return trip.source_text or "", trip.source_text


def run_job_now(session: Session, user: UserContext, job_id: int) -> dict:
    """Chạy ngay trong giao dịch hiện tại một việc trip vừa đặt (trip_import, trip_evaluate), dùng cho
    lượt chat cần kết quả cùng lượt. Việc chưa commit nên worker chưa thấy; commit xong đã là done."""
    job = session.scalar(
        select(JobQueue)
        .where(
            JobQueue.id == job_id,
            JobQueue.user_id == user.user_id,
            JobQueue.kind.in_(("trip_import", "trip_evaluate")),
            JobQueue.status == "pending",
        )
        .with_for_update()
    )
    if job is None:
        raise NotFoundError("Không tìm thấy việc chờ của chuyến đi.")
    job.status, job.attempts, job.started_at = "processing", job.attempts + 1, clock.now()
    runner = run_import if job.kind == "trip_import" else run_evaluate
    result = runner(session, job)
    job.status, job.result, job.finished_at, job.error = "done", result, clock.now(), None
    session.flush()
    return result


def run_import(session: Session, job) -> dict:
    trip = _get(session, job.user_id, job.payload["trip_id"], lock=True)
    tz = _user_tz(session, trip.user_id)
    try:
        draft = (trip.extract_json or {}).get("_draft")
        if draft is not None:
            extract, source = TripExtract.model_validate(draft), None
        else:
            content, source = _content_for(session, trip)
            extract = bridge.extract_trip(trip.user_id, content, TripExtract, default_title=trip.title)
            errors = check_extract(extract, source) if extract else ["không đọc được"]
            if errors:
                hint = "Lỗi ở lần đọc trước, hãy sửa: " + "; ".join(errors[:10])
                extract = bridge.extract_trip(
                    trip.user_id, content, TripExtract, hint=hint, default_title=trip.title
                )
                if extract is None or check_extract(extract, source):
                    raise ValidationError("Không đọc được lịch trình từ tệp này, thử gửi lại hoặc gõ mô tả.")
        if trip.start_date:
            extract = extract.model_copy(update={"start_date": trip.start_date.isoformat()})
        normalized = normalize(extract, tz, clock.now().astimezone(ZoneInfo(tz)).date())
        _save_import(session, trip, extract, normalized)
        resolve_places(session, trip)
        geocode.fill_areas(trip, _stops(session, trip.id))
        queue_geocode(session, trip)
        trip.status, trip.error = "draft", None
    except AppError as exc:
        trip.status, trip.error = "failed", exc.message
    except Exception:
        log.exception("Nhập lịch trình lỗi", extra={"trip_id": trip.id})
        trip.status, trip.error = "failed", "Nhập lịch trình gặp lỗi, đã ghi lại."
    session.flush()
    return {"trip_id": trip.id, "status": trip.status}


def _user_tz(session: Session, user_id: int) -> str:
    return (
        session.scalar(text("SELECT timezone FROM tab_user WHERE id = :u"), {"u": user_id})
        or "Asia/Ho_Chi_Minh"
    )


def _save_import(session: Session, trip: Trip, extract: TripExtract, n: Normalized) -> None:
    session.execute(delete(TripFact).where(TripFact.trip_id == trip.id))
    session.execute(delete(TripStop).where(TripStop.trip_id == trip.id))
    trip.title = extract.title[:200] or trip.title
    trip.travel_mode = extract.travel_mode or trip.travel_mode
    trip.origin_text, trip.end_text = extract.origin_text, extract.end_text
    trip.start_date = n.start_date
    trip.end_date = n.start_date + timedelta(days=max(len(extract.days), 1) - 1)
    trip.nights = extract.nights if extract.nights is not None else max(len(extract.days) - 1, 0)
    trip.notes = extract.notes
    trip.hotels = [h.model_dump() for h in extract.hotels]
    trip.extract_json = {**extract.model_dump(), "_start_date_suggested": n.date_suggested}
    trip.evaluation, trip.chosen_option_id = None, None
    seqs: dict[int, int] = {}
    rows: list[TripStop] = []
    for d in n.stops:
        seqs[d.day_no] = seqs.get(d.day_no, 0) + 1
        row = TripStop(
            user_id=trip.user_id,
            trip_id=trip.id,
            day_no=d.day_no,
            seq=seqs[d.day_no],
            title=d.title,
            category=d.category if d.category in CATEGORIES else "khac",
            role=d.role,
            time_text=d.time_text,
            planned_start=d.planned_start,
            planned_end=d.planned_end,
            approx=d.approx,
            fixed=d.fixed,
            optional=d.optional,
            stay_minutes=d.stay_minutes,
            place_query=d.place_query,
            area=d.area,
            source_url=d.source_url,
            place_id=d.place_id,
            lat=d.lat,
            lng=d.lng,
            coord_source=d.coord_source,
            resolve_status="ok" if d.lat is not None else ("manual" if not d.place_query else "uncertain"),
            phone=d.phone,
            cost_note=d.cost_note,
            note=d.note,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    for d, row in zip(n.stops, rows, strict=True):
        if d.parent is not None:
            row.parent_stop_id = rows[d.parent].id
    for f in n.facts:
        stop = _fact_stop(rows, f)
        session.add(
            TripFact(
                user_id=trip.user_id,
                trip_id=trip.id,
                kind=f["kind"],
                day_no=f["day_no"],
                stop_id=stop.id if stop else None,
                value_time=f["value_time"],
                value_text=f["value_text"],
                text=f["text"][:1000],
            )
        )
    session.flush()


def _fact_stop(rows: list[TripStop], fact: dict) -> TripStop | None:
    wanted = {"ferry_last": "pha", "ferry_first": "pha", "checkin": "khach_san", "checkout": "khach_san"}.get(
        fact["kind"]
    )
    if not wanted:
        return None
    candidates = [
        r
        for r in rows
        if r.category == wanted
        and r.role == "main"
        and (fact["day_no"] is None or r.day_no == fact["day_no"])
    ]
    if wanted == "pha" and fact.get("text"):
        key = fold(fact["text"])
        named = [r for r in candidates if any(w in key for w in fold(r.title).split() if len(w) > 3)]
        candidates = named or candidates
    return candidates[0] if candidates else None


# ---------- Định vị ----------


def resolve_places(session: Session, trip: Trip) -> dict:
    """Định vị điểm còn thiếu theo 41 mục 4; chưa có khóa Maps thì để chờ xác nhận, không lỗi."""
    if not maps.configured():
        return {"skipped": "no_maps_key"}
    stops = _stops(session, trip.id)
    short = [s.source_url for s in stops if s.source_url and "goo.gl" in s.source_url and not s.place_id]
    resolved_short = maps.resolve_short_links(list(dict.fromkeys(short)))
    previous: dict[int, tuple[float, float] | None] = {}
    counts = {"ok": 0, "uncertain": 0, "not_found": 0}
    for s in stops:
        prev = previous.get(s.day_no)
        if s.lat is not None:
            previous[s.day_no] = (float(s.lat), float(s.lng))
            if not s.place_id and s.source_url in resolved_short:
                s.place_id = resolved_short[s.source_url]
            continue
        if not s.place_query and not s.place_id and s.source_url not in resolved_short:
            continue
        if s.role == "generic":
            s.alternatives = [_strip(c) for c in places.suggestions(session, s.place_query, prev)]
            s.resolve_status = "ok"
            continue
        place_id = s.place_id or resolved_short.get(s.source_url)
        if place_id:
            info = places.details_cached(session, place_id)
            result = places.Resolved(place_id, info.lat, info.lng, info.address, "ok", [])
        else:
            result = places.resolve(session, s.place_query, s.category, prev)
        if result.status == "ok" and result.lat is not None:
            s.place_id, s.lat, s.lng = result.place_id, result.lat, result.lng
            s.coord_source, s.coord_fetched_at = "google", clock.now()
            s.resolve_status = "ok"
            if s.role in ROUTED_ROLES:
                previous[s.day_no] = (result.lat, result.lng)
        else:
            s.resolve_status = result.status
            s.alternatives = [_strip(c) for c in result.candidates]
        counts[s.resolve_status] = counts.get(s.resolve_status, 0) + 1
    session.flush()
    return counts


def _strip(candidate: dict) -> dict:
    """alternatives chỉ giữ place_id và nhãn, không giữ tọa độ (11 mục 3.13)."""
    return {
        "place_id": candidate.get("place_id"),
        "name": candidate.get("name"),
        "address": candidate.get("address"),
    }


def refresh_google_coords(session: Session, stops: list[TripStop]) -> None:
    """Tọa độ Google quá 30 ngày thì gọi lại Place Details Essentials khi dùng (41 mục 4)."""
    for s in stops:
        stale = s.coord_source == "google" and (
            s.lat is None or s.coord_fetched_at is None or clock.now() - s.coord_fetched_at > places.COORD_TTL
        )
        if stale and s.place_id and maps.configured():
            info = places.details_cached(session, s.place_id)
            s.lat, s.lng, s.coord_fetched_at = info.lat, info.lng, clock.now()


def search_candidate(query: str, near: str | None) -> dict:
    """Không có khóa Maps (QĐ-36): một mục chưa kiểm, link tìm kiếm Google Maps theo tên.
    Dán link này vào import_trip thì bộ đọc lấy tên tìm làm điểm dừng, chặng do AI ước tính."""
    text = " ".join(x.strip() for x in (query, near or "") if x and x.strip())
    return {
        "name": query.strip(),
        "address": near,
        "place_id": None,
        "lat": None,
        "lng": None,
        "link": f"{links.MAPS_SEARCH}?api=1&query={quote_plus(text)}",
        "verified": False,
    }


def find_place(session: Session, user: UserContext, query: str, near: str | None = None) -> list[dict]:
    """Công cụ find_place: tối đa 3 điểm có tên (SKU Pro cho displayName, 41 mục 4)."""
    if not query.strip():
        raise ValidationError(fields={"query": "Nhập tên địa điểm."})
    if not maps.configured():
        return [search_candidate(query, near)]
    bias = None
    if near:
        ids = maps.text_search_ids(near, None, page_size=1)
        if ids:
            center = places.details_cached(session, ids[0])
            bias = (center.lat, center.lng) if center.lat is not None else None
    ids = maps.text_search_ids(query, bias)
    return [{**places.candidate(maps.place_with_name(pid)), "verified": True} for pid in ids[:3]]


def resolve_candidates(
    session: Session, user: UserContext, trip_id: int, stop_id: int, place_query: str
) -> dict:
    stop = _stop(session, user.user_id, trip_id, stop_id)
    if not maps.configured():
        # QĐ-36: không tra được điểm thật, ghi tên tìm để link và ước tính chặng đi theo tên.
        stop.place_query = place_query
        return {"candidates": [search_candidate(place_query, None)]}
    stops = _stops(session, trip_id)
    prev = next(
        (
            (float(s.lat), float(s.lng))
            for s in reversed(stops)
            if s.day_no == stop.day_no and s.seq < stop.seq and s.lat is not None
        ),
        None,
    )
    ids = maps.text_search_ids(place_query, prev)
    found = [places.candidate(places.details_cached(session, pid)) for pid in ids[:3]]
    stop.place_query = place_query
    stop.alternatives = [_strip(c) for c in found]
    return {"candidates": found}


# ---------- Sửa điểm ----------


def _stop(session: Session, user_id: int, trip_id: int, stop_id: int) -> TripStop:
    _get(session, user_id, trip_id)
    stop = session.scalar(select(TripStop).where(TripStop.id == stop_id, TripStop.trip_id == trip_id))
    if stop is None:
        raise NotFoundError("Không tìm thấy điểm dừng.")
    return stop


STOP_FIELDS = {"title", "category", "planned_start", "planned_end", "fixed", "optional", "stay_minutes", "place_query", "area", "note", "phone", "cost_note", "day_no", "seq"}  # fmt: skip


def _apply_stop(stop: TripStop, data: dict) -> None:
    moved = ("area" in data and data["area"] != stop.area) or (
        "place_query" in data and data["place_query"] != stop.place_query
    )
    for key in STOP_FIELDS & data.keys():
        setattr(stop, key, data[key])
    if moved and stop.coord_source == "osm":
        # Tọa độ OpenStreetMap lấy theo tên và địa phương cũ: bỏ để lần đánh giá sau tìm lại.
        stop.lat = stop.lng = stop.coord_source = stop.coord_fetched_at = None
    if stop.category not in CATEGORIES:
        raise ValidationError(fields={"category": "Loại điểm không hợp lệ."})
    if "lat" in data or "place_id" in data:
        lat, lng = data.get("lat"), data.get("lng")
        if (lat is None) != (lng is None):
            raise ValidationError(fields={"lat": "Cần cả vĩ độ và kinh độ."})
        stop.place_id = data.get("place_id", stop.place_id)
        stop.lat, stop.lng = lat, lng
        stop.coord_source = "google" if data.get("place_id") else "user"
        stop.coord_fetched_at = clock.now()
        stop.resolve_status = "manual"
        stop.alternatives = []
    if data.get("resolve_status") == "manual":
        stop.resolve_status = "manual"


def create_stop(session: Session, user: UserContext, trip_id: int, data: dict) -> dict:
    trip = _get(session, user.user_id, trip_id)
    if not (data.get("title") or "").strip():
        raise ValidationError(fields={"title": "Nhập tên điểm."})
    day_no = int(data.get("day_no") or 1)
    last = (
        session.scalar(
            select(func.max(TripStop.seq)).where(TripStop.trip_id == trip_id, TripStop.day_no == day_no)
        )
        or 0
    )
    stop = TripStop(
        user_id=user.user_id,
        trip_id=trip.id,
        day_no=day_no,
        seq=last + 1,
        title=data["title"],
        resolve_status="uncertain",
    )
    _apply_stop(stop, {**data, "day_no": day_no, "seq": data.get("seq") or last + 1})
    if not stop.place_query:
        stop.resolve_status = "manual"
    session.add(stop)
    session.flush()
    return serialize_stop(stop)


def update_stop(session: Session, user: UserContext, trip_id: int, stop_id: int, data: dict) -> dict:
    stop = _stop(session, user.user_id, trip_id, stop_id)
    if data.get("place_id") and data.get("lat") is None and maps.configured():
        # Gợi ý lưu trong chuyến không giữ tọa độ (11 mục 3.13): chọn bằng place_id thì máy chủ tự tra.
        info = places.details_cached(session, data["place_id"])
        data = {**data, "lat": info.lat, "lng": info.lng}
    _apply_stop(stop, data)
    session.flush()
    return serialize_stop(stop)


def delete_stop(session: Session, user: UserContext, trip_id: int, stop_id: int) -> None:
    session.delete(_stop(session, user.user_id, trip_id, stop_id))
    session.flush()


def reorder_stops(
    session: Session, user: UserContext, trip_id: int, day_no: int, stop_ids: list[int]
) -> list[dict]:
    _get(session, user.user_id, trip_id)
    rows = {s.id: s for s in _stops(session, trip_id) if s.day_no == day_no}
    if set(stop_ids) != set(rows):
        raise ValidationError("Danh sách điểm không khớp với ngày này.")
    for i, sid in enumerate(stop_ids, start=1):
        rows[sid].seq = i  # UQ DEFERRABLE nên đổi chỗ trong một giao dịch được
    session.flush()
    return [serialize_stop(rows[sid]) for sid in stop_ids]


def update_trip(session: Session, user: UserContext, trip_id: int, data: dict) -> dict:
    trip = _get(session, user.user_id, trip_id)
    if "start_date" in data and data["start_date"]:
        new_start = data["start_date"]
        shift = (new_start - trip.start_date) if trip.start_date else timedelta(0)
        trip.start_date = new_start
        if trip.end_date:
            trip.end_date += shift
        for s in _stops(session, trip_id):
            if s.planned_start:
                s.planned_start += shift
            if s.planned_end:
                s.planned_end += shift
        if trip.extract_json:
            trip.extract_json = {**trip.extract_json, "_start_date_suggested": False}
    for key in ("title", "travel_mode", "origin_text"):
        if data.get(key):
            setattr(trip, key, data[key])
    if data.get("status") in ("draft", "planned", "done"):
        trip.status = data["status"]
    session.flush()
    return serialize_trip(session, trip)


def delete_trip(session: Session, user: UserContext, trip_id: int) -> None:
    session.delete(_get(session, user.user_id, trip_id))
    session.flush()


# ---------- Đánh giá ----------


def evaluate_trip(session: Session, user: UserContext, trip_id: int, mode: str = "normal") -> dict:
    """mode `think` (người dùng bấm nghĩ kỹ): AI tìm thêm giờ mở cửa trên web (QĐ-36)."""
    if mode not in ("normal", "think"):
        raise ValidationError(fields={"mode": "Chỉ nhận normal hoặc think."})
    trip = _get(session, user.user_id, trip_id, lock=True)
    if trip.status in ("importing", "evaluating"):
        raise TripBusy()
    trip.status = "evaluating"
    job_id = _queue(session, user.user_id, "trip_evaluate", trip.id, {"mode": mode})
    queue_geocode(session, trip)
    return {"job_id": job_id, "status": "evaluating"}


def _settings(session: Session, user_id: int, tz: str) -> engine.Settings:
    values = bridge.setting_values(session, user_id).get("values", {})

    def hhmm(value, default):
        try:
            return time.fromisoformat(value)
        except (TypeError, ValueError):
            return default

    return engine.Settings(
        tz=tz,
        night_start=hhmm(values.get("trip.night_start"), time(18, 0)),
        night_end=hhmm(values.get("trip.night_end"), time(5, 30)),
        ride_break_minutes=int(values.get("trip.ride_break_minutes") or 90),
        speed_factor=float(values.get("trip.speed_factor") or 1.2),
        ferries=list(values.get("trip.ferries") or []),
    )


def _pdays(trip: Trip, stops: list[TripStop]) -> list[engine.PDay]:
    weekday = {d.get("day_no"): d.get("weekday_text") for d in (trip.extract_json or {}).get("days", [])}
    out = []
    for day_no in sorted({s.day_no for s in stops}):
        out.append(
            engine.PDay(
                day_no,
                trip.start_date + timedelta(days=day_no - 1),
                weekday.get(day_no),
                [
                    engine.PStop(
                        id=s.id,
                        day_no=s.day_no,
                        title=s.title,
                        category=s.category,
                        role=s.role,
                        fixed=s.fixed,
                        optional=s.optional,
                        approx=s.approx,
                        planned_start=s.planned_start,
                        stay_minutes=s.stay_minutes or 0,
                        lat=_num(s.lat),
                        lng=_num(s.lng),
                        place_query=s.place_query,
                        place_id=s.place_id,
                    )
                    for s in stops
                    if s.day_no == day_no and s.role in ROUTED_ROLES
                ],
            )
        )
    return out


def _route_legs(session: Session, days: list[engine.PDay]) -> dict[engine.LegKey, engine.PLeg]:
    """Một lời gọi Compute Routes cho mỗi đoạn tối đa 27 điểm; chặng đã lưu đệm thì không gọi."""
    legs: dict[engine.LegKey, engine.PLeg] = {}
    now = clock.now()
    for day in days:
        points = [s for s in day.stops if s.located]
        for start in range(0, max(len(points) - 1, 0), MAX_INTERMEDIATES + 1):
            chunk = points[start : start + MAX_INTERMEDIATES + 2]
            pairs = list(zip(chunk, chunk[1:], strict=False))
            cached = {}
            for a, b in pairs:
                (ok_, dk_) = engine.leg_key(a, b)
                row = session.scalar(
                    select(RouteCache).where(
                        RouteCache.origin_key == f"{ok_[0]},{ok_[1]}",
                        RouteCache.destination_key == f"{dk_[0]},{dk_[1]}",
                        RouteCache.travel_mode == "two_wheeler",
                        RouteCache.avoid_highways.is_(True),
                        RouteCache.expires_at > now,
                    )
                )
                if row is not None:
                    cached[engine.leg_key(a, b)] = engine.PLeg(row.duration_s / 60, row.distance_m / 1000)
            if len(cached) == len(pairs):
                legs.update(cached)
                continue
            departure = (
                chunk[0].planned_start if chunk[0].planned_start and chunk[0].planned_start > now else None
            )
            result = maps.compute_route([p.point for p in chunk], departure)
            for (a, b), leg in zip(pairs, result.legs, strict=False):
                key = engine.leg_key(a, b)
                legs[key] = engine.PLeg(leg.duration_s / 60, leg.distance_m / 1000, leg.instructions)
                if result.travel_mode == "two_wheeler":
                    _cache_leg(session, key, leg)
    return legs


def _cache_leg(session: Session, key: engine.LegKey, leg: maps.Leg) -> None:
    session.execute(
        text(
            "INSERT INTO tab_route_cache (origin_key, destination_key, travel_mode, avoid_highways, distance_m, "
            "duration_s, fetched_at, expires_at) VALUES (:o, :d, 'two_wheeler', true, :m, :s, now(), "
            "now() + interval '30 days') ON CONFLICT ON CONSTRAINT uq_tab_route_cache_key DO UPDATE SET "
            "distance_m = EXCLUDED.distance_m, duration_s = EXCLUDED.duration_s, fetched_at = now(), "
            "expires_at = EXCLUDED.expires_at"
        ),
        {
            "o": f"{key[0][0]},{key[0][1]}",
            "d": f"{key[1][0]},{key[1][1]}",
            "m": leg.distance_m,
            "s": leg.duration_s,
        },
    )


def _reorder(days: list[engine.PDay]) -> tuple[list[engine.PDay], list[str]]:
    out, changes = [], []
    for day in days:
        flexible = [s for s in day.stops if s.located and not s.fixed and s.role == "main"]
        if len(flexible) < 3:
            out.append(day)
            continue
        located = [s for s in day.stops if s.located][:25]
        index = {s.id: i for i, s in enumerate(located)}
        try:
            matrix = maps.route_matrix([s.point for s in located])
        except maps.MapsUnavailable:
            out.append(day)
            continue

        def minutes(a, b, matrix=matrix, index=index):
            if a.id not in index or b.id not in index:
                return None
            value = matrix[index[a.id]][index[b.id]]
            return value / 60 if value is not None else None

        new_day, day_changes = engine.reorder_day(day, minutes)
        out.append(new_day)
        changes.extend(day_changes)
    return out, changes


def _fetch_hours(days: list[engine.PDay]) -> None:
    """Giờ mở cửa (SKU Enterprise) chỉ cho điểm tham quan, ăn uống, mua sắm có place_id; không lưu."""
    for day in days:
        for s in day.stops:
            if s.category in HOURS_CATEGORIES and s.role == "main" and s.place_id:
                s.hours_checked = True
                try:
                    s.hours = maps.opening_hours(s.place_id)
                except maps.MapsUnavailable:
                    s.hours = None


def _evaluate_days(days, legs, facts, cfg, now_iso):
    results = [engine.simulate(d, legs, cfg) for d in days]
    risks = [
        r for d, res in zip(days, results, strict=True) for r in engine.check_day(d, res, facts, cfg, now_iso)
    ]
    return results, risks


def _plan_json(results: list[engine.DayResult]) -> dict:
    return {
        "days": [
            {
                "day_no": r.day_no,
                "km": round(r.km, 1),
                "ride_minutes": round(r.ride_minutes),
                "stops": [
                    {
                        "stop_id": t.stop.id,
                        "planned_start": t.begin.isoformat(),
                        "planned_end": t.depart.isoformat(),
                        "stay_minutes": t.stop.stay_minutes,
                        "leg_minutes": t.leg_minutes,
                        "leg_km": t.leg_km,
                    }
                    for t in r.timed
                ],
            }
            for r in results
        ]
    }


def _night_minutes(results: list[engine.DayResult], cfg: engine.Settings) -> int:
    return round(sum(engine._night_windows(r, cfg)[0] for res in results for r in res.rides))


def _template_summary(o: dict) -> str:
    h, m = divmod(o["total_ride_minutes"] or 0, 60)
    return (
        f"Tổng khoảng {o['total_km']} km, chạy xe khoảng {h} giờ {m} phút. "
        f"Còn {o['red_count']} rủi ro đỏ, {o['yellow_count']} rủi ro vàng."
    )


def _allowed_numbers(data: dict) -> set[str]:
    h, m = divmod(data["total_ride_minutes"], 60)
    values = (
        data["total_km"],
        data["total_ride_minutes"],
        data["night_ride_minutes"],
        data["red_count"],
        data["yellow_count"],
    )
    return {str(v) for v in values} | {str(h), str(m), str(round(data["total_km"]))}


def _numbers_ok(summary: str, allowed: set[str]) -> bool:
    return all(n.replace(",", ".") in allowed for n in re.findall(r"\d+(?:[.,]\d+)?", summary))


def _hour_sentences(row: TripStop | None, stops: list[TripStop]) -> list[str]:
    """Câu về giờ mở cửa của đúng điểm này: hàng có nhiều điểm thì chỉ lấy câu nhắc tên điểm."""
    if row is None or not row.note:
        return [row.title] if row else []
    sentences = [x for x in re.split(r"(?<=[.;!?])\s+", row.note) if x.strip()]
    words = fold(row.title).split()[:3]
    key = " ".join(words)
    own = [x for x in sentences if key and key in fold(x)]
    shared = sum(1 for s in stops if s.day_no == row.day_no and s.note == row.note and s.role == "main") > 1
    return [row.title, *(own if own or shared else sentences)]


def _estimate_legs(
    session: Session,
    trip: Trip,
    stops: list[TripStop],
    days: list[engine.PDay],
    cfg: engine.Settings,
    web: bool,
) -> tuple[dict, list[engine.Fact], list[str]]:
    """Chặng do AI ước tính (app.ai.trip_legs.estimate_legs); thiếu thì tạm tính theo khoảng cách chim bay.

    Trả (chặng, mốc phà cuối AI tìm được khi nghĩ kỹ). Giờ mở cửa gắn thẳng vào PStop.hours.
    """
    zone = ZoneInfo(cfg.tz)
    by_id = {s.id: s for s in stops}
    pairs: list[tuple[engine.PStop, engine.PStop]] = []
    payload_stops: list[dict] = []
    for d in days:
        points = [p for p in d.stops if engine.routable(p, cfg)]
        pairs += list(zip(points, points[1:], strict=False))
        for p in points:
            payload_stops.append(
                {
                    "stop_id": p.id,
                    "day_no": d.day_no,
                    "title": p.title,
                    "category": p.category,
                    "address": by_id[p.id].area
                    if p.id in by_id
                    else None,  # địa phương giúp AI ước tính đúng chỗ
                    "place_query": p.place_query,
                    "lat": p.lat,
                    "lng": p.lng,
                    "planned_time": p.planned_start.astimezone(zone).strftime("%H:%M")
                    if p.planned_start
                    else None,
                    "visit_date": d.date.isoformat(),
                }
            )
    estimate = (
        bridge.estimate_legs(
            trip.user_id,
            trip.title,
            trip.end_text or trip.origin_text,
            payload_stops,
            [{"from_stop_id": a.id, "to_stop_id": b.id} for a, b in pairs],
            web,
            trip.travel_mode,
        )
        or {}
    )
    legs: dict = {}
    for leg in estimate.get("legs") or []:
        try:
            ferry = float(leg.get("ferry_minutes") or 0)
            minutes = max(float(leg["minutes"]) - ferry, 0)
            legs[(int(leg["from_stop_id"]), int(leg["to_stop_id"]))] = engine.PLeg(
                minutes,
                float(leg["km"]),
                [leg.get("note") or "", *(leg.get("roads") or [])],
                wait_minutes=ferry,
            )
        except (KeyError, TypeError, ValueError):
            continue
    for a, b in pairs:
        if (a.id, b.id) not in legs and a.located and b.located:
            km = places.distance_km(a.point, b.point) * 1.3
            legs[(a.id, b.id)] = engine.PLeg(km / 35 * 60, km, [])
    fact_texts: dict[int, list[str]] = {}
    for f in session.scalars(
        select(TripFact).where(TripFact.trip_id == trip.id, TripFact.kind == "opening_hours")
    ):
        if f.stop_id:
            fact_texts.setdefault(f.stop_id, []).append(f"{f.text} {f.value_text or ''}")
    checks = {(int(c["stop_id"]), c.get("kind")): c for c in estimate.get("checks") or [] if c.get("stop_id")}
    new_facts: list[engine.Fact] = []
    web_notes: list[str] = []
    for check in estimate.get("checks") or []:
        if not check.get("hours") and not check.get("last_time") and check.get("text"):
            name = by_id[int(check["stop_id"])].title if int(check["stop_id"]) in by_id else "Một điểm"
            web_notes.append(f"{name}: {check['text']}"[:300])  # tìm web không ra: hiện lý do cho người dùng
    for d in days:
        for p in d.stops:
            p.hours = hours_from_text(*_hour_sentences(by_id.get(p.id), stops), *fact_texts.get(p.id, []))
            web_hours = checks.get((p.id, "opening_hours"))
            if web_hours and web_hours.get("hours"):
                p.hours = web_hours["hours"]  # không có thì để None: R2 không báo (QĐ-36)
            ferry = checks.get((p.id, "ferry_last"))
            last = ferry.get("last_time") if ferry else None
            if isinstance(last, str) and last:
                last = time.fromisoformat(last)
            already = last and session.scalar(
                select(TripFact.id).where(
                    TripFact.trip_id == trip.id,
                    TripFact.stop_id == p.id,
                    TripFact.kind == "ferry_last",
                    TripFact.value_time == (last if not isinstance(last, str) else time.fromisoformat(last)),
                )
            )
            if last and already:
                new_facts.append(engine.Fact("ferry_last", d.day_no, last, p.id, ""))
            elif last:
                text_ = (ferry.get("text") or "Chuyến phà cuối (tìm trên web)")[:900]
                if ferry.get("source_url"):
                    text_ += f" ({ferry['source_url']})"
                session.add(
                    TripFact(
                        user_id=trip.user_id,
                        trip_id=trip.id,
                        kind="ferry_last",
                        stop_id=p.id,
                        day_no=d.day_no,
                        value_time=last,
                        text=text_,
                    )
                )
                new_facts.append(engine.Fact("ferry_last", d.day_no, last, p.id, text_))
    return legs, new_facts, web_notes


def run_evaluate(session: Session, job) -> dict:
    trip = _get(session, job.user_id, job.payload["trip_id"], lock=True)
    previous_status = "planned" if trip.chosen_option_id else "draft"
    tz = _user_tz(session, trip.user_id)
    try:
        if trip.start_date is None:
            raise ValidationError("Chọn ngày đi trước khi đánh giá.")
        stops = _stops(session, trip.id)
        refresh_google_coords(session, stops)
        cfg = _settings(session, trip.user_id, tz)
        facts = [
            engine.Fact(f.kind, f.day_no, f.value_time, f.stop_id, f.text)
            for f in session.scalars(select(TripFact).where(TripFact.trip_id == trip.id))
        ]
        now_iso = clock.now().isoformat()
        days = _pdays(trip, stops)
        if maps.configured():
            days, order_changes = _reorder(days)
            legs = _route_legs(session, days)
            _fetch_hours(days)
            web_notes = []
        else:
            # QĐ-36: không có Maps Platform; AI ước tính chặng, giờ mở cửa đọc từ chữ (và tìm web khi nghĩ kỹ).
            cfg.by_stop_id = cfg.estimated = True
            order_changes = []
            legs, web_facts, web_notes = _estimate_legs(
                session, trip, stops, days, cfg, web=job.payload.get("mode") == "think"
            )
            facts = web_facts + facts  # mốc tìm trên web đứng trước mốc cũ cùng điểm
        base_results, base_risks = _evaluate_days(days, legs, facts, cfg, now_iso)
        options = engine.build_options(days, base_risks, order_changes)
        session.execute(delete(TripOption).where(TripOption.trip_id == trip.id))
        trip.chosen_option_id = None
        created: list[tuple[TripOption, dict]] = []
        for opt in options:
            opt_legs = engine.bridge_legs(opt.days, legs, days, cfg)
            results, risks = _evaluate_days(opt.days, opt_legs, facts, cfg, now_iso)
            data = {
                "name": opt.name,
                "total_km": round(sum(r.km for r in results), 1),
                "total_ride_minutes": round(sum(r.ride_minutes for r in results)),
                "night_ride_minutes": _night_minutes(results, cfg),
                "red_count": sum(r["level"] == "red" for r in risks),
                "yellow_count": sum(r["level"] == "yellow" for r in risks),
                "changes": opt.changes,
                "risks": risks,
            }
            row = TripOption(
                user_id=trip.user_id,
                trip_id=trip.id,
                name=data["name"],
                summary=_template_summary(data),
                plan=_plan_json(results),
                total_km=Decimal(str(data["total_km"])),
                total_ride_minutes=data["total_ride_minutes"],
                night_ride_minutes=data["night_ride_minutes"],
                red_count=data["red_count"],
                yellow_count=data["yellow_count"],
                risks=risks,
                changes=data["changes"],
                evaluated_at=clock.now(),
            )
            session.add(row)
            created.append((row, data))
        session.flush()
        # Sonnet viết tóm tắt và lời khuyên (app.ai.trip_ai.summarize_options); thiếu thì giữ câu mẫu.
        ai = bridge.summarize_options(
            trip.user_id,
            trip.title,
            [
                {k: v for k, v in data.items() if k != "risks"}
                | {
                    "option_id": row.id,
                    "risks": [
                        {k: r[k] for k in ("code", "level", "day_no", "message", "suggestion")}
                        for r in data["risks"]
                    ],
                }
                for row, data in created
            ],
        )
        tips: list[str] = []
        for row, data in created:
            item = ai.get(row.id)
            if item and item.get("summary") and _numbers_ok(item["summary"], _allowed_numbers(data)):
                row.summary = item["summary"]
            for tip in (item or {}).get("tips", []):
                if tip not in tips:
                    tips.append(str(tip)[:300])
        trip.evaluation = {
            "evaluated_at": now_iso,
            "risks": base_risks,
            "advice": (tips[:8] + web_notes[:8]) or None,
            "plan": _plan_json(base_results),
            "estimated": cfg.estimated,
            "total_km": round(sum(r.km for r in base_results), 1),
        }
        trip.status, trip.error = "draft", None
    except AppError as exc:
        trip.status, trip.error = previous_status, exc.message
    except Exception:
        log.exception("Đánh giá lịch trình lỗi", extra={"trip_id": trip.id})
        trip.status, trip.error = previous_status, "Đánh giá gặp lỗi, đã ghi lại."
    session.flush()
    return {"trip_id": trip.id, "status": trip.status}


def choose_option(session: Session, user: UserContext, trip_id: int, option_id: int) -> dict:
    trip = _get(session, user.user_id, trip_id, lock=True)
    option = session.scalar(
        select(TripOption).where(TripOption.id == option_id, TripOption.trip_id == trip.id)
    )
    if option is None:
        raise NotFoundError("Không tìm thấy phương án.")
    keep: dict[int, dict] = {}
    for day in option.plan.get("days", []):
        for i, item in enumerate(day.get("stops", []), start=1):
            keep[item["stop_id"]] = {**item, "seq": i}
    for s in _stops(session, trip.id):
        if s.role not in ROUTED_ROLES:
            continue
        item = keep.get(s.id)
        if item is None:
            session.delete(s)  # phương án bỏ điểm này (điểm phụ đi theo CASCADE)
            continue
        s.seq = item["seq"]
        s.planned_start = datetime.fromisoformat(item["planned_start"])
        s.planned_end = datetime.fromisoformat(item["planned_end"])
        s.stay_minutes = item.get("stay_minutes")
    for o in session.scalars(select(TripOption).where(TripOption.trip_id == trip.id)):
        o.chosen = o.id == option.id
    trip.chosen_option_id = option.id
    trip.status = "planned"
    trip.evaluation = {
        **(trip.evaluation or {}),
        "risks": option.risks,
        "plan": option.plan,
        "total_km": _num(option.total_km),
    }
    session.flush()
    return serialize_trip(session, trip)


# ---------- Bản đồ ----------


def _link_stop(s: TripStop) -> links.LinkStop:
    return links.LinkStop(
        s.id,
        s.title,
        s.category,
        s.stay_minutes or 0,
        _num(s.lat),
        _num(s.lng),
        s.place_query,
        s.place_id,
        s.area,
    )


def _link_stops(stops: list[TripStop]) -> list[links.LinkStop]:
    return [_link_stop(s) for s in stops if s.role in ROUTED_ROLES]


def map_links(
    session: Session, user: UserContext, trip_id: int, day_no: int | None, max_waypoints: int = 9
) -> dict:
    if max_waypoints not in (3, 9):
        raise ValidationError(fields={"max_waypoints": "Chỉ nhận 9 hoặc 3."})
    trip = _get(session, user.user_id, trip_id)
    stops = _stops(session, trip.id)
    days = sorted({s.day_no for s in stops} if day_no is None else {day_no})
    return {
        "days": [
            links.day_actions(d, _link_stops([s for s in stops if s.day_no == d]), max_waypoints)
            for d in days
        ]
    }


def route_actions(
    session: Session,
    user: UserContext,
    *,
    trip_id: int | None = None,
    stop_id: int | None = None,
    place_query: str | None = None,
    scope: str = "stop",
    day_no: int | None = None,
) -> list[dict]:
    """Công cụ open_route: nút dẫn đường tới một điểm hoặc các đoạn cả ngày (41 mục 7)."""
    if trip_id is None:
        today = clock.now().astimezone(ZoneInfo(user.timezone)).date()
        trip = session.scalar(
            select(Trip)
            .where(Trip.user_id == user.user_id, Trip.start_date <= today, Trip.end_date >= today)
            .limit(1)
        )
        if trip is None:
            raise NotFoundError("Hôm nay không có chuyến đi nào.")
        trip_id = trip.id
        day_no = day_no or (today - trip.start_date).days + 1
    data = map_links(session, user, trip_id, day_no)
    if scope == "day":
        return [a for d in data["days"] for a in d["segments"]]
    for d in data["days"]:
        for s in d["stops"]:
            if stop_id is not None and s["stop_id"] != stop_id:
                continue
            if stop_id is None and place_query:
                row = session.get(TripStop, s["stop_id"])
                if fold(place_query) not in fold(f"{row.title} {row.place_query or ''}"):
                    continue
            return [s["navigation"] or s["place"]]
    raise NotFoundError("Không tìm thấy điểm cần chỉ đường.")


# ---------- Xuất Word, đưa vào lịch ----------


def _weekday_short(d: date) -> str:
    return WEEKDAY_SHORT[d.weekday()]


def build_doc(session: Session, trip: Trip, tz: str) -> DocTrip:
    stops = _stops(session, trip.id)
    zone = ZoneInfo(tz)
    children: dict[int, list[TripStop]] = {}
    for s in stops:
        if s.parent_stop_id:
            children.setdefault(s.parent_stop_id, []).append(s)
    extract_days = {d.get("day_no"): d for d in (trip.extract_json or {}).get("days", [])}
    link_days = {d["day_no"]: d for d in map_links_for(stops)}
    legs, plan_days = _plan_index(trip.evaluation)
    days = []
    for day_no in sorted({s.day_no for s in stops}):
        info = extract_days.get(day_no, {})
        day_date = trip.start_date + timedelta(days=day_no - 1)
        mains = [s for s in stops if s.day_no == day_no and not s.parent_stop_id]
        located = [s for s in mains if s.lat is not None]
        span = f"{located[0].title} → {located[-1].title}" if len(located) >= 2 else (info.get("title") or "")
        rows = []
        for s in mains:
            when = s.time_text or (
                s.planned_start.astimezone(zone).strftime("%Hh%M") if s.planned_start else ""
            )
            runs: list = [
                (s.title, links.place_url(_link_stop(s)) if s.place_query or s.lat is not None else None)
            ]
            for c in children.get(s.id, []):
                runs += [
                    (" Dự phòng: " if c.role == "backup" else " hoặc ", None),
                    (c.title, links.place_url(_link_stop(c)) if c.place_query else None),
                ]
            extra = "; ".join(x for x in (s.cost_note, s.phone and f"SĐT {s.phone}", s.note) if x)
            if extra:
                runs.append((f". {extra}", None))
            rows.append((when, runs))
        plan = plan_days.get(day_no, {})
        route = info.get("route_text") or ""
        if plan:
            h, m = divmod(plan.get("ride_minutes") or 0, 60)
            route = f"{route} (khoảng {plan.get('km')} km, chạy {h} giờ {m} phút)".strip()
        days.append(
            DocDay(
                day_no=day_no,
                heading=f"Ngày {day_no} ({_weekday_short(day_date)}, {day_date:%d/%m}): {span}".rstrip(": "),
                route_line=route or None,
                rows=rows,
                map_links=[
                    (seg["label"], seg["urls"][0]) for seg in link_days.get(day_no, {}).get("segments", [])
                ],
            )
        )
    hotels = []
    for h in trip.hotels or []:
        runs = [(f"Đêm {h.get('night_no')}: ", None), (h.get("label", ""), h.get("url"))]
        runs.append((" (đã đặt)" if h.get("booked") else " (chưa đặt)", None))
        for b in h.get("backups") or []:
            runs += [(". Dự phòng: ", None), (b.get("label", ""), b.get("url"))]
        hotels.append(runs)
    risks = [r["message"] for r in (trip.evaluation or {}).get("risks", [])]
    nights = trip.nights or 0
    summary = f"{len(days)} ngày {nights} đêm, đi {'xe máy' if trip.travel_mode == 'motorbike' else 'ô tô' if trip.travel_mode == 'car' else 'bộ'}"
    if trip.origin_text:
        summary += f", xuất phát từ {trip.origin_text}"
    return DocTrip(trip.title, summary + ".", days, hotels, risks + list(trip.notes or []))


def map_links_for(stops: list[TripStop], max_waypoints: int = 9) -> list[dict]:
    return [
        links.day_actions(d, _link_stops([s for s in stops if s.day_no == d]), max_waypoints)
        for d in sorted({s.day_no for s in stops})
    ]


def export_docx(session: Session, user: UserContext, trip_id: int, save_to_drive: bool = False) -> dict:
    trip = _get(session, user.user_id, trip_id)
    if trip.start_date is None:
        raise ValidationError("Chọn ngày đi trước khi xuất.")
    data = build_docx(build_doc(session, trip, user.timezone))
    name = re.sub(r"[^\w\s-]", "", fold(trip.title)).strip().replace(" ", "-")[:60] or "lich-trinh"
    stored = bridge.store_generated_file(
        session, user.user_id, data, DOCX_MIME, f"{name}.docx", "trip_export"
    )
    trip.export_file_id = stored.get("id") or stored.get("file_id")
    session.flush()
    drive_queued = bool(
        save_to_drive and bridge.request_drive_upload(session, user.user_id, trip.export_file_id)
    )
    return {
        "file_id": trip.export_file_id,
        "download_url": stored.get("url") or stored.get("download_url"),
        "drive_queued": drive_queued,
    }


def to_calendar(session: Session, user: UserContext, trip_id: int) -> dict:
    """Mỗi ngày một sự kiện cả ngày, cộng sự kiện có giờ cho mốc cứng; phà, trả phòng là báo thức (12 mục 5.7)."""
    trip = _get(session, user.user_id, trip_id)
    if trip.start_date is None:
        raise ValidationError("Chọn ngày đi trước khi đưa vào lịch.")
    stops = _stops(session, trip.id)
    checkout_ids = set(
        session.scalars(
            select(TripFact.stop_id).where(TripFact.trip_id == trip.id, TripFact.kind == "checkout")
        )
    )
    event_ids = []
    for day_no in sorted({s.day_no for s in stops}):
        day_date = trip.start_date + timedelta(days=day_no - 1)
        made = bridge.create_calendar_event(
            session,
            user,
            {
                "title": f"{trip.title}: ngày {day_no}",
                "all_day": True,
                "start_date": day_date,
                "end_date": day_date + timedelta(days=1),
            },
        )
        event_ids.append(made["event"]["id"])
        for s in stops:
            if s.day_no != day_no or not s.fixed or not s.planned_start or s.role not in ROUTED_ROLES:
                continue
            alarm = s.category == "pha" or s.id in checkout_ids
            made = bridge.create_calendar_event(
                session,
                user,
                {
                    "title": s.title,
                    "start_at": s.planned_start,
                    "end_at": s.planned_end or s.planned_start + timedelta(minutes=s.stay_minutes or 30),
                    "location": s.place_query,
                    "is_alarm": alarm,
                },
            )
            event_ids.append(made["event"]["id"])
    return {"event_ids": event_ids}


# ---------- Đặt phòng từ thư (QĐ-49, module booking gọi) ----------


def _same_place(a: str | None, b: str | None) -> bool:
    fa, fb = fold(a or ""), fold(b or "")
    return bool(fa and fb) and (fa in fb or fb in fa)


def attach_booking(
    session: Session,
    user: UserContext,
    *,
    night: date,
    name: str,
    area: str | None,
    address: str | None,
    phone: str | None,
    booking: dict,
) -> tuple[int, int] | None:
    """Gắn đặt phòng vào chuyến có đêm `night`: vào điểm khách sạn trùng tên (hoặc điểm khách sạn duy nhất)
    của ngày đó; không có thì thêm điểm khách sạn cuối ngày. Trả (trip_id, stop_id) hoặc None."""
    trip = session.scalar(
        select(Trip)
        .where(
            Trip.user_id == user.user_id,
            Trip.archived_at.is_(None),
            Trip.start_date <= night,
            func.coalesce(Trip.end_date, Trip.start_date) >= night,
            Trip.status.not_in(("importing", "failed")),
        )
        .order_by(Trip.start_date.desc())
        .limit(1)
    )
    if trip is None:
        return None
    day_no = (night - trip.start_date).days + 1
    day = [s for s in _stops(session, trip.id) if s.day_no == day_no]
    hotels = [s for s in day if s.category == "khach_san" and s.role == "main" and not s.booking]
    stop = next((s for s in hotels if _same_place(s.title, name) or _same_place(s.place_query, name)), None)
    if stop is None and len(hotels) == 1:
        stop = hotels[0]
    added = stop is None
    if added:
        stop = TripStop(
            user_id=user.user_id,
            trip_id=trip.id,
            day_no=day_no,
            seq=max((s.seq for s in day), default=0) + 1,
            title=name[:500],
            category="khach_san",
            role="main",
            place_query=", ".join(x for x in (name, address) if x)[:500] or name,
            area=area,
            resolve_status="uncertain",
        )
        session.add(stop)
    if phone and not stop.phone:
        stop.phone = phone
    if area and not stop.area:
        stop.area = area
    stop.booking = {**booking, "added_stop": added}
    session.flush()
    return trip.id, stop.id


def update_stop_booking(session: Session, user: UserContext, stop_id: int, booking: dict) -> None:
    stop = session.scalar(select(TripStop).where(TripStop.id == stop_id, TripStop.user_id == user.user_id))
    if stop is not None and stop.booking:
        stop.booking = {**booking, "added_stop": stop.booking.get("added_stop", False)}
        session.flush()


def detach_booking(session: Session, user: UserContext, stop_id: int) -> None:
    """Hoàn tác: điểm do đặt phòng thêm vào thì xóa; điểm có sẵn thì chỉ bỏ thông tin đặt phòng."""
    stop = session.scalar(select(TripStop).where(TripStop.id == stop_id, TripStop.user_id == user.user_id))
    if stop is None:
        return
    if (stop.booking or {}).get("added_stop"):
        session.delete(stop)
    else:
        stop.booking = None
    session.flush()
