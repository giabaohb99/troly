"""Chạy bộ mẫu ước tính chặng xe máy với Claude thật (QĐ-36). Chỉ chạy tay: pytest -m ai_eval.

Không cần DB. Ghi kết quả vào results/<ngày>-legs.json. Mỗi mẫu khoảng 0,005 USD; mẫu nghĩ kỹ khoảng 0,05 USD.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

HERE = Path(__file__).parent
_RESULTS: list[dict] = []

pytestmark = pytest.mark.ai_eval


def _load() -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []
    return yaml.safe_load((HERE / "leg_cases.yaml").read_text(encoding="utf-8"))


CASES = _load()


@pytest.fixture(scope="module", autouse=True)
def write_results():
    yield
    if not _RESULTS:
        return
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    summary = {"passed": sum(r["ok"] for r in _RESULTS), "total": len(_RESULTS), "cases": _RESULTS}
    path = out / f"{datetime.now(UTC):%Y-%m-%d}-legs.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _errors(case: dict, result) -> list[str]:
    exp = case["expect"]
    if result is None:
        return ["không có kết quả"]
    errors: list[str] = []
    legs = {(g.from_stop_id, g.to_stop_id): g for g in result.legs}
    tol = exp.get("tolerance", 0.35)
    for i, (a, b) in enumerate(case["legs"]):
        g = legs.get((a, b))
        if g is None:
            errors.append(f"thiếu chặng {a}-{b}")
            continue
        want = (exp.get("km") or [None] * len(case["legs"]))[i]
        if want is not None and abs(g.km - want) > want * tol:
            errors.append(f"chặng {a}-{b}: {g.km} km, chuẩn {want}")
        lo, hi = exp["minutes_range"][i]
        if not lo <= g.minutes <= hi:
            errors.append(f"chặng {a}-{b}: {g.minutes} phút, ngoài {lo}-{hi}")
    if "total_km_range" in exp:
        lo, hi = exp["total_km_range"]
        total = sum(g.km for g in result.legs)
        if not lo <= total <= hi:
            errors.append(f"tổng {total} km ngoài {lo}-{hi}")
    checks = {c.stop_id: c for c in result.checks}
    for stop_id in exp.get("checks", []):
        if stop_id not in checks or not checks[stop_id].text:
            errors.append(f"điểm {stop_id}: không có dòng kiểm")
    for stop_id in exp.get("found", []):
        c = checks.get(stop_id)
        if c is None or (c.hours is None and c.last_time is None):
            errors.append(f"điểm {stop_id}: không tìm được giờ")
    for stop_id, weekday in (exp.get("closed_weekday") or {}).items():
        c = checks.get(stop_id)
        days = (
            {p["open"]["day"] for p in ((c.hours or {}).get("regular") or {}).get("periods", [])}
            if c
            else set()
        )
        if weekday in days:
            errors.append(f"điểm {stop_id}: lẽ ra nghỉ ngày {weekday}")
    return errors


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_leg_case(case):
    from app.ai.client import ClaudeClient, NullRecorder
    from app.ai.trip_legs import estimate_legs

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("Chưa có ANTHROPIC_API_KEY")
    recorder = NullRecorder()
    client = ClaudeClient(recorder=recorder)
    stops = [{**s, "day_no": 1} for s in case["stops"]]
    legs = [{"from_stop_id": a, "to_stop_id": b} for a, b in case["legs"]]
    result = estimate_legs(
        1,
        trip_title="Chuyến xe máy miền Tây và Bà Rịa",
        region="Nam Bộ",
        stops=stops,
        legs=legs,
        think=bool(case.get("think")),
        client=client,
    )
    errors = _errors(case, result)
    _RESULTS.append(
        {
            "id": case["id"],
            "ok": not errors,
            "errors": errors,
            "cost_usd": round(sum(float(r.cost_usd) for r in recorder.records), 6),
            "legs": [vars(g) for g in result.legs] if result else None,
            "checks": [vars(c) for c in result.checks] if result else None,
        }
    )
    assert not errors, errors
