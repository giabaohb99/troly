from datetime import date, time

from app.modules.trip.normalize import (
    check_extract,
    normalize,
    parse_time_text,
    suggest_start_date,
    weekday_of,
)
from app.modules.trip.reader import parse_latlng, parse_maps_url, read_docx
from app.modules.trip.tests.sample_extract import build_sample_extract, sample_bytes


def test_read_sample_docx_tables_and_links():
    doc = read_docx(sample_bytes())
    assert doc.tables == 3 and doc.table_rows == 31
    kinds = [parse_maps_url(u).kind for u in doc.links]
    assert kinds.count("dir") == 6 and kinds.count("search") == 41 and kinds.count("short") == 2
    assert "[chợ Phước Hải](https://www.google.com/maps/search/" in doc.text
    assert "# Lịch trình Phước Hải" in doc.text and "## Ngày 3 (thứ 2)" in doc.text


def test_search_link_decodes_vietnamese_query():
    link = parse_maps_url(
        "https://www.google.com/maps/search/?api=1&query=H%E1%BB%A7%20ti%E1%BA%BFu%20m%E1%BB%B1c%20b%C3%A1nh%20canh%20Vui"
    )
    assert link.kind == "search" and link.query == "Hủ tiếu mực bánh canh Vui"


def test_dir_link_reads_coordinates_and_pipe_waypoints():
    link = parse_maps_url(
        "https://www.google.com/maps/dir/?api=1&origin=10.4477939%2C107.2876573&destination=X&waypoints=A%7CB"
    )
    assert parse_latlng(link.origin) == (10.4477939, 107.2876573)
    assert link.waypoints == ["A", "B"]


def test_time_text_forms():
    assert parse_time_text("2h30").start == time(2, 30)
    approx = parse_time_text("~7h00")
    assert approx.start == time(7, 0) and approx.approx
    span = parse_time_text("10h30–12h30")
    assert span.start == time(10, 30) and span.end == time(12, 30)
    assert parse_time_text("13h00–15h30").end == time(15, 30)


def test_weekday_and_suggested_saturday():
    assert weekday_of("thứ 7") == 5 and weekday_of("chủ nhật") == 6 and weekday_of("thứ 2") == 0
    assert suggest_start_date(5, date(2026, 11, 18)) == date(2026, 11, 21)


def test_sample_extract_passes_server_checks():
    doc = read_docx(sample_bytes())
    extract = build_sample_extract(doc.text)
    assert check_extract(extract, doc.text) == []
    assert len(extract.days) == 3


def test_link_not_in_source_is_rejected():
    doc = read_docx(sample_bytes())
    extract = build_sample_extract(doc.text)
    extract.days[0].stops[0].places[0].url = "https://www.google.com/maps/search/?api=1&query=bia"
    assert any("Link không có" in e for e in check_extract(extract, doc.text))


def test_normalize_sample_three_days_and_hotel_coordinates():
    n = normalize(build_sample_extract(), "Asia/Ho_Chi_Minh", date(2026, 11, 18))
    assert n.start_date == date(2026, 11, 21) and n.date_suggested
    first = n.stops[0]
    assert first.day_no == 1 and first.planned_start.hour == 2 and first.planned_start.minute == 30
    hotel = next(s for s in n.stops if s.day_no == 1 and s.category == "khach_san")
    assert (hotel.lat, hotel.lng, hotel.coord_source) == (10.4477939, 107.2876573, "user")
    cafe = next(s for s in n.stops if "Cafe Phượng" in (s.place_query or ""))
    assert cafe.stay_minutes == 120
    ferry = next(s for s in n.stops if s.category == "pha" and s.day_no == 2)
    assert ferry.approx and not ferry.fixed  # ~13h30
    generics = {s.place_query for s in n.stops if s.role == "generic"}
    assert {"bánh giá Gò Công", "bún nước lèo Trà Vinh"} <= generics
    backups = [s for s in n.stops if s.role == "backup"]
    assert any("Cơm Nhà Tui" in s.title for s in backups) and all(s.parent is not None for s in backups)
    assert {d.day_no for d in n.stops} == {1, 2, 3}
