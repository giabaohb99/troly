"""Thẻ *Tập luyện* của màn Báo cáo (QĐ-54): tóm dữ liệu chỉ đọc từ app gym.

Thẻ cùng dạng thẻ dashboard `{status, message, data}`: `disabled` khi chưa nối app gym, `error` khi gym không trả
lời (lượt khác không hỏng). `summarize(raw)` thuần dữ liệu, công cụ AI của agent AI dùng chung được.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from app.core import clock
from app.integrations.gym import client

APP_URL = "https://gym.baohuynh.io.vn"
PERIOD_DAYS = {"week": 7, "month": 30}
TOP_LIFTS = 3


def period_range(period: str, tz: str) -> tuple[date, date]:
    """`week`: 7 ngày tới hôm nay; `month`: 30 ngày tới hôm nay (giờ người dùng)."""
    today = clock.now().astimezone(ZoneInfo(tz)).date()
    return today - timedelta(days=PERIOD_DAYS.get(period, 7) - 1), today


def _lift_highlights(progress: list[dict]) -> list[dict]:
    out = []
    for p in progress or []:
        first, last = (p.get("first") or {}).get("weight_kg"), (p.get("last") or {}).get("weight_kg")
        if last is None:
            continue
        delta = round(last - first, 2) if first is not None else None
        if delta is not None and delta <= 0:
            continue
        out.append({"exercise": p.get("name"), "from_kg": first, "to_kg": last, "delta_kg": delta})
    out.sort(key=lambda x: (x["delta_kg"] is not None, x["delta_kg"] or 0), reverse=True)
    return out[:TOP_LIFTS]


def _weight(body: list[dict]) -> dict | None:
    rows = sorted((b for b in body or [] if b.get("weight_kg") is not None), key=lambda b: b["date"])
    if not rows:
        return None
    return {
        "first_kg": rows[0]["weight_kg"],
        "last_kg": rows[-1]["weight_kg"],
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
    }


def _protein(nutrition: dict | None) -> dict | None:
    nutrition = nutrition or {}
    days = [d["protein_g"] for d in nutrition.get("days") or [] if d.get("protein_g") is not None]
    if not days:
        return None
    return {
        "avg_g": round(sum(days) / len(days)),
        "target_g": (nutrition.get("targets") or {}).get("protein_g"),
        "days_logged": len(days),
    }


def _day(item: dict | None, workouts: list[dict]) -> dict | None:
    if not item:
        return None
    done = next((w.get("done") for w in workouts or [] if w.get("date") == item.get("date")), False)
    rest = not item.get("day_name")
    return {
        "date": item.get("date"),
        "title": item.get("day_name") or "Ngày nghỉ",
        "rest": rest,
        "exercises": list(item.get("exercises") or []),
        "done": bool(done),
    }


def summarize(raw: dict, period: str | None = None) -> dict:
    workouts = raw.get("workouts") or []
    today = raw.get("today") or []
    rng = raw.get("range") or {}
    tomorrow = _day(today[1] if len(today) > 1 else None, workouts)
    if tomorrow is not None:
        tomorrow.pop("done")
    return {
        "period": period,
        "from": rng.get("from"),
        "to": rng.get("to"),
        "sessions_done": len(workouts),
        "sessions_complete": sum(1 for w in workouts if w.get("done")),
        "sessions_planned": len(raw.get("planned") or []),
        "lift_highlights": _lift_highlights(raw.get("progress") or []),
        "weight": _weight(raw.get("body") or []),
        "protein": _protein(raw.get("nutrition")),
        "today": _day(today[0] if today else None, workouts),
        "tomorrow": tomorrow,
        "app_url": APP_URL,
    }


def gym_card(tz: str, period: str | None = None, from_: date | None = None, to: date | None = None) -> dict:
    if from_ is None and to is None:
        period = period or "week"
        from_, to = period_range(period, tz)
    try:
        raw = client.fetch_summary(from_, to)
    except client.GymNotConnected as exc:
        return {"status": "disabled", "message": exc.message, "data": None}
    except client.GymUnavailable as exc:
        return {"status": "error", "message": exc.message, "data": None}
    return {"status": "ok", "message": None, "data": summarize(raw, period)}
