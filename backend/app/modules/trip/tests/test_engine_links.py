from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.modules.trip import engine, links

VN = ZoneInfo("Asia/Ho_Chi_Minh")
DAY = date(2026, 11, 23)  # thứ Hai
NOW = "2026-11-18T00:00:00+00:00"


def stop(i, lat, lng, **kw):
    return engine.PStop(
        id=i,
        day_no=1,
        title=kw.pop("title", f"Điểm {i}"),
        category=kw.pop("category", "tham_quan"),
        lat=lat,
        lng=lng,
        **kw,
    )


def at(h, m=0):
    return datetime.combine(DAY, time(h, m), VN)


def legs_for(stops, minutes):
    out = {}
    located = [s for s in stops if s.located]
    for a, b in zip(located, located[1:], strict=False):
        out[engine.leg_key(a, b)] = engine.PLeg(minutes, minutes * 0.6, ["Đi theo đường tỉnh"])
    return out


def run(stops, minutes=30, facts=None, cfg=None, weekday="thứ 2"):
    cfg = cfg or engine.Settings(speed_factor=1.0)
    day = engine.PDay(1, DAY, weekday, stops)
    result = engine.simulate(day, legs_for(stops, minutes), cfg)
    return result, engine.check_day(day, result, facts or [], cfg, NOW)


def codes(risks, level=None):
    return [r["code"] for r in risks if level is None or r["level"] == level]


def test_late_arrival_r1_levels():
    stops = [
        stop(1, 10.0, 106.0, planned_start=at(8)),
        stop(2, 10.1, 106.1, planned_start=at(8, 40), stay_minutes=0),
    ]
    stops[0].stay_minutes = 0
    _, risks = run(stops, minutes=60)
    assert "R1" in codes(risks, "yellow")  # trễ 20 phút
    _, risks = run(stops, minutes=90)
    assert "R1" in codes(risks, "red")


def test_closed_monday_r2_red_and_24h_ok():
    hours = {
        "regular": {
            "periods": [
                {"open": {"day": d, "hour": 8}, "close": {"day": d, "hour": 17}} for d in (0, 2, 3, 4, 5, 6)
            ]
        }
    }
    museum = stop(1, 10.0, 106.0, planned_start=at(10), hours=hours, hours_checked=True)
    _, risks = run([museum])
    assert any(r["code"] == "R2" and r["level"] == "red" and "thứ Hai" in r["message"] for r in risks)
    always = stop(
        2,
        10.0,
        106.0,
        planned_start=at(10),
        hours={"regular": {"periods": [{"open": {"day": 0, "hour": 0}}]}},
        hours_checked=True,
    )
    assert "R2" not in codes(run([always])[1])
    unknown = stop(3, 10.0, 106.0, planned_start=at(10), hours_checked=True)
    assert "R2" in codes(run([unknown])[1], "yellow")


def test_ferry_last_r3():
    ferry = stop(2, 10.1, 106.1, category="pha")
    start = stop(1, 10.0, 106.0, planned_start=at(15, 50), stay_minutes=0)
    fact = engine.Fact("ferry_last", 1, time(17, 0))
    _, risks = run([start, ferry], minutes=60, facts=[fact])  # tới 16:50, dư 10 phút
    assert "R3" in codes(risks, "red")
    _, risks = run([start, ferry], minutes=20, facts=[fact])  # dư 50 phút
    assert "R3" in codes(risks, "yellow")
    _, risks = run([start, ferry], minutes=20)
    assert any(r["code"] == "R3" and "hotline" in r["suggestion"] for r in risks)


def test_ferry_last_from_settings_table():
    cfg = engine.Settings(speed_factor=1.0, ferries=[{"name": "Bình Khánh", "last_time": "16:00"}])
    start = stop(1, 10.0, 106.0, planned_start=at(15, 0), stay_minutes=0)
    ferry = stop(2, 10.1, 106.1, category="pha", title="Phà Bình Khánh")
    assert "R3" in codes(run([start, ferry], minutes=50, cfg=cfg)[1], "red")


def test_continuous_ride_and_daily_total():
    s = [stop(i, 10 + i / 10, 106.0, stay_minutes=5) for i in range(4)]
    s[0].planned_start = at(6)
    _, risks = run(s, minutes=45)  # 135 phút liền, nghỉ dưới 15 phút không tính
    assert "R4" in codes(risks, "red")
    long_day = [stop(i, 10 + i / 10, 106.0, stay_minutes=20) for i in range(6)]
    long_day[0].planned_start = at(5, 30)
    _, risks = run(long_day, minutes=100)
    assert "R6" in codes(risks, "red")


def test_night_ride_r5():
    s = [stop(1, 10.0, 106.0, planned_start=at(2, 30), stay_minutes=0), stop(2, 10.5, 106.5)]
    _, risks = run(s, minutes=120)
    assert any(r["code"] == "R5" and r["level"] == "red" and "03:00" in r["message"] for r in risks)
    evening = [stop(1, 10.0, 106.0, planned_start=at(17, 50), stay_minutes=0), stop(2, 10.5, 106.5)]
    assert "R5" in codes(run(evening, minutes=40)[1], "yellow")


def test_checkout_and_unlocated_and_weekday():
    hotel = stop(1, 10.0, 106.0, category="khach_san", planned_start=at(9), stay_minutes=180)
    fact = engine.Fact("checkout", 1, time(10, 45), stop_id=1)
    assert "R7" in codes(run([hotel], facts=[fact])[1], "red")
    lost = engine.PStop(id=5, day_no=1, title="Quán lạ", category="an_uong", place_query="Quán lạ")
    assert "R8" in codes(run([lost])[1], "yellow")
    assert "R9" in codes(run([hotel], weekday="thứ 7")[1], "red")


def test_reorder_window_between_fixed_stops():
    a = stop(1, 10.0, 106.0, fixed=True, planned_start=at(8))
    far, near, mid = stop(2, 10.0, 106.9), stop(3, 10.0, 106.1), stop(4, 10.0, 106.5)
    b = stop(5, 10.0, 107.0, fixed=True)
    day = engine.PDay(1, DAY, None, [a, far, near, mid, b])
    new_day, changes = engine.reorder_day(day, lambda x, y: abs(x.lng - y.lng) * 100)
    assert [s.id for s in new_day.stops] == [1, 3, 4, 2, 5]
    assert changes


def test_options_drop_optional_before_red_ferry_and_dedupe():
    s1 = stop(1, 10.0, 106.0, planned_start=at(14))
    opt = stop(2, 10.1, 106.1, optional=True, title="Đồng lúa")
    ferry = stop(3, 10.2, 106.2, category="pha", title="Phà")
    base = [engine.PDay(1, DAY, None, [s1, opt, ferry])]
    risks = [{"code": "R3", "level": "red", "day_no": 1, "stop_id": 3, "message": "x", "suggestion": "y"}]
    options = engine.build_options(base, risks, [])
    names = [o.name for o in options]
    assert names[0] == "Nhiều điểm" and "Đúng giờ, ít rủi ro" in names
    safe = next(o for o in options if o.name == "Đúng giờ, ít rủi ro")
    assert [s.id for s in safe.days[0].stops] == [1, 3]
    assert any("Đồng lúa" in c for c in safe.changes)
    legs = legs_for([s1, opt, ferry], 30)
    bridged = engine.bridge_legs(safe.days, legs, base)
    assert bridged[engine.leg_key(s1, ferry)].minutes == 60


def _ls(i, lat, lng, category="tham_quan", stay=30):
    return links.LinkStop(i, f"Điểm {i}", category, stay, lat, lng, f"Điểm {i}", None)


def test_split_segments_cut_at_hotel_and_respect_limits():
    pts = (
        [_ls(i, 10 + i / 100, 106.0) for i in range(5)]
        + [_ls(5, 10.05, 106.0, "khach_san")]
        + [_ls(i, 10 + i / 100, 106.0) for i in range(6, 20)]
    )
    segments = links.split_segments(pts, 9)
    assert segments[0][-1].id == 5 and segments[1][0].id == 5
    assert all(len(s) <= 11 for s in segments)
    for a, b in zip(segments, segments[1:], strict=False):
        assert a[-1].id == b[0].id
    small = links.split_segments(pts, 3)
    assert all(len(s) <= 5 for s in small)
    assert all(len(links.directions_url(s)) <= 2048 for s in segments)


def test_day_actions_shape():
    stops = [
        _ls(1, 10.1, 106.1),
        _ls(2, 10.2, 106.2),
        links.LinkStop(3, "Chưa định vị", "an_uong", 30, None, None, "Quán", None),
    ]
    data = links.day_actions(1, stops, 9)
    seg = data["segments"][0]
    assert (
        seg["type"] == "open_map_directions"
        and "travelmode=two-wheeler" in seg["urls"][0]
        and "avoid=highways" in seg["urls"][0]
    )
    nav = data["stops"][0]["navigation"]
    assert nav["type"] == "open_map_navigation" and nav["mode"] == "l" and nav["avoid"] == "h"
    assert "dir_action=navigate" in nav["fallback_url"]
    assert data["stops"][2]["navigation"] is None and data["stops"][2]["place"]["type"] == "open_map_place"
    assert links.navigation_uri(10.1, 106.1) == "google.navigation:q=10.1,106.1&mode=l&avoid=h"


def test_simulate_waits_for_planned_time():
    s = [
        stop(1, 10.0, 106.0, planned_start=at(8), stay_minutes=10),
        stop(2, 10.1, 106.1, planned_start=at(10)),
    ]
    result, _ = run(s, minutes=30)
    assert result.timed[1].arrive == at(8, 40) and result.timed[1].begin == at(10)
    assert result.timed[1].leg_minutes == 30 and abs(result.ride_minutes - 30) < 1e-6
    assert result.timed[1].depart - result.timed[1].begin == timedelta(minutes=30)
