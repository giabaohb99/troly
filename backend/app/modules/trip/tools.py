"""Công cụ AI của lịch trình (20 mục 3.7, 41; việc 4-02).

Nhập và đánh giá chạy nền (khoảng 1 phút): công cụ trả trạng thái và nút mở màn chuyến đi, không đợi.
Dựng chuyến từ câu mô tả: dùng find_place để chọn điểm có thật, rồi import_trip với đoạn chữ có các link
`find_place` trả (link mang place_id, bộ đọc của trip lấy thẳng). Xóa chuyến luôn qua thẻ duyệt (QĐ-27).
"""

from datetime import date
from typing import Literal
from urllib.parse import quote_plus

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ApprovalDraft, ToolContext, ToolOutput, ToolSpec
from app.core.errors import AppError
from app.modules.trip import service

MAX_STOPS_PER_DAY = 25


def _strip_id(action: dict) -> dict:
    return {k: v for k, v in action.items() if k != "id"}


def _open_trip(trip_id: int, label: str = "Mở chuyến đi") -> dict:
    return act.open_screen(label, "trip_detail", {"trip_id": trip_id})


def _compact_trip(t: dict) -> dict:
    """Bản gọn cho model: đủ để trả lời, không kèm tọa độ, link."""
    days = []
    for d in t["days"]:
        stops, km = [], 0.0
        for s in d["stops"]:
            if s["role"] not in ("main", "via", None):
                continue
            km += float(s.get("leg_km") or 0)
            stops.append(
                {
                    "stop_id": s["id"],
                    "time": s["time_text"] or (s["planned_start"] or "")[11:16] or None,
                    "title": s["title"],
                    "category": s["category"],
                    "role": s["role"],
                    "optional": s["optional"],
                    "place": s["place_query"],
                    "note": s["note"],
                    # km ước tính của chặng tới điểm này và cộng dồn từ đầu ngày (có sau khi đánh giá)
                    "leg_km": s.get("leg_km"),
                    "km_tu_dau_ngay": round(km, 1) if s.get("leg_km") is not None else None,
                }
            )
        days.append(
            {
                "day_no": d["day_no"],
                "date": d["date"],
                "weekday": d["weekday_text"],
                "title": d["title"],
                "total_km": d["total_km"],
                "ride_minutes": d["ride_minutes"],
                "stops": stops[:MAX_STOPS_PER_DAY],
            }
        )
    evaluation = t.get("evaluation") or {}
    return {
        "trip_id": t["id"],
        "title": t["title"],
        "status": t["status"],
        "start_date": t["start_date"],
        "end_date": t["end_date"],
        "travel_mode": t["travel_mode"],
        "days": days,
        "facts": [{k: f[k] for k in ("kind", "day_no", "value_time", "value_text")} for f in t["facts"]],
        "risks": [
            {k: r.get(k) for k in ("code", "level", "day_no", "message", "suggestion")}
            for r in evaluation.get("risks", [])
        ],
        "options": [
            {
                k: o[k]
                for k in (
                    "id",
                    "name",
                    "summary",
                    "total_km",
                    "total_ride_minutes",
                    "red_count",
                    "yellow_count",
                    "chosen",
                )
            }
            for o in t["options"]
        ],
        "advice": t.get("advice"),
        "can_xac_nhan": len(t["needs_confirmation"]),
        "error": t.get("error"),
    }


# ---------- Đầu vào ----------


class ImportTripInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: int | None = Field(description="Tệp lịch trình người dùng đã gửi (Word, PDF, ảnh)")
    text: str | None = Field(
        description="Đoạn lịch trình hoặc câu mô tả đã dựng; điểm lấy từ find_place thì dán nguyên trường link"
    )
    url: str | None = Field(description="Link lịch trình hoặc link Google Maps người dùng dán")
    title: str | None
    start_date: date | None = Field(description="Ngày đi nếu người dùng đã nói")
    travel_mode: Literal["motorbike", "car", "walk"] | None = Field(description="null là xe máy")


class TripIdInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int


class SaveTripInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int
    option_id: int = Field(description="Phương án người dùng chọn (từ get_trip)")


class ListTripsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["importing", "draft", "evaluating", "planned", "done", "failed"] | None
    query: str | None = Field(description="Chữ trong tên chuyến, ví dụ: Trà Vinh")


class GetTripInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int | None = Field(description="Mã chuyến; null thì tìm theo query")
    query: str | None = Field(description="Tên chuyến, lấy chuyến khớp mới nhất")
    day_no: int | None = Field(description="Chỉ lấy ngày này")


class FindPlaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(description="Tên quán, điểm cần tìm, kèm tỉnh: bún nước lèo Trà Vinh")
    near: str | None = Field(description="Tìm gần đâu, ví dụ: chợ Trà Vinh")


class OpenRouteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int | None = Field(description="null là chuyến có hôm nay")
    stop_id: int | None
    place_query: str | None = Field(description="Tên điểm trong chuyến, ví dụ: chỗ ăn trưa, Chùa Âng")
    scope: Literal["stop", "day"] = Field(description="stop: dẫn đường tới một điểm; day: xem đường cả ngày")
    day_no: int | None


Category = Literal["an_uong", "nghi", "tham_quan", "pha", "di_chuyen", "khach_san", "mua_sam", "khac"]


class NewStop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_no: int = Field(description="Ngày thứ mấy của chuyến")
    title: str = Field(description="Tên điểm; điểm theo loại thì ghi kiểu: Đổ xăng ở Đất Đỏ")
    category: Category = Field(
        default="khac",
        description="di_chuyen: đổ xăng, sửa xe; nghi: nghỉ chân; an_uong; tham_quan; khac: ATM",
    )
    after_stop_id: int | None = Field(
        default=None, description="Chèn sau điểm này (stop_id); null là cuối ngày"
    )
    place_query: str | None = Field(
        default=None, description="Chuỗi tìm Google Maps, ví dụ: cây xăng gần Đất Đỏ, Bà Rịa - Vũng Tàu"
    )
    stay_minutes: int | None = Field(default=None, description="Dừng bao lâu; đổ xăng khoảng 10")
    note: str | None = None


class AddStopsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int
    stops: list[NewStop] = Field(description="1 tới 10 điểm thêm trong một lần")


class UpdateStopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int
    stop_id: int
    title: str | None = None
    category: Category | None = None
    place_query: str | None = None
    stay_minutes: int | None = None
    note: str | None = None
    day_no: int | None = Field(default=None, description="Chuyển sang ngày khác")
    after_stop_id: int | None = Field(default=None, description="Dời tới sau điểm này")


class StopRefInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int
    stop_id: int


class DeleteTripInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int
    reason: str


# ---------- Hàm chạy ----------


def _brief_import(t: dict) -> dict:
    return {
        "trip_id": t["id"],
        "status": t["status"],
        "error": t.get("error"),
        "start_date": t.get("start_date"),
        "days": len(t["days"]),
        "stops": sum(len(d["stops"]) for d in t["days"]),
        "can_xac_nhan": len(t.get("needs_confirmation") or []),
    }


def run_import(ctx: ToolContext, data: ImportTripInput) -> ToolOutput:
    out = service.import_trip(
        ctx.session,
        ctx.user,
        file_id=data.file_id,
        text=data.text,
        url=data.url,
        title=data.title,
        start_date=data.start_date,
        travel_mode=data.travel_mode,
    )
    if data.file_id:  # tệp dài: đọc nền như cũ
        return ToolOutput(
            result={
                **out,
                "ghi_chu": "Đang đọc lịch trình, khoảng 1 phút. Xong thì người dùng xem nháp trên màn chuyến đi, "
                "xác nhận điểm chưa chắc rồi đánh giá.",
            },
            actions=[_open_trip(out["trip_id"], "Xem chuyến đi")],
        )
    # Chữ, link: đọc ngay trong lượt để đánh giá luôn (QĐ-36, dựng chuyến từ câu mô tả).
    service.run_job_now(ctx.session, ctx.user, out["job_id"])
    t = service.get_trip(ctx.session, ctx.user, out["trip_id"])
    result = _brief_import(t)
    if t["status"] == "failed":
        result["ghi_chu"] = (
            "Không đọc được lịch trình (xem error). Không gọi import_trip lần nữa; báo người dùng lý do ngắn."
        )
    elif t.get("start_date"):
        result["ghi_chu"] = (
            "Đã nhập xong. Gọi evaluate_trip ngay với trip_id này trong lượt này; không tạo chuyến mới."
        )
    else:
        result["ghi_chu"] = "Đã nhập xong nhưng chưa có ngày đi: hỏi ngày đi trước khi đánh giá."
    return ToolOutput(result=result, actions=[_open_trip(out["trip_id"], "Xem chuyến đi")])


def run_evaluate(ctx: ToolContext, data: TripIdInput) -> ToolOutput:
    """Đánh giá ngay trong lượt và trả phương án để người dùng chọn cùng lúc."""
    out = service.evaluate_trip(ctx.session, ctx.user, data.trip_id)
    service.run_job_now(ctx.session, ctx.user, out["job_id"])
    t = service.find_trip(ctx.session, ctx.user, trip_id=data.trip_id, query=None, day_no=None)
    result = _compact_trip(t)
    if t.get("error"):
        result["ghi_chu"] = f"Đánh giá chưa xong: {t['error']}"
    else:
        result["ghi_chu"] = (
            "Đã đánh giá. Nêu ngắn 2 tới 3 phương án (tên, km, giờ chạy, rủi ro chính) và mời người dùng chọn; "
            "chọn xong thì gọi save_trip."
        )
    return ToolOutput(result=result, actions=[_open_trip(data.trip_id, "Xem đánh giá")])


def run_save(ctx: ToolContext, data: SaveTripInput) -> ToolOutput:
    t = service.choose_option(ctx.session, ctx.user, data.trip_id, data.option_id)
    chosen = next((o for o in t["options"] if o["chosen"]), None)
    return ToolOutput(
        result={"trip_id": t["id"], "status": t["status"], "phuong_an": chosen and chosen["name"]},
        actions=[_open_trip(t["id"])],
    )


def run_list(ctx: ToolContext, data: ListTripsInput) -> ToolOutput:
    items = service.list_trips(ctx.session, ctx.user, status=data.status, query=data.query)
    return ToolOutput(result={"items": items[:20]}, actions=[act.open_screen("Mở lịch trình", "trip_list")])


def run_get(ctx: ToolContext, data: GetTripInput) -> ToolOutput:
    if data.trip_id is None and not data.query:
        raise AiError("VALIDATION_ERROR", "Cần trip_id hoặc query.")
    t = service.find_trip(ctx.session, ctx.user, trip_id=data.trip_id, query=data.query, day_no=data.day_no)
    return ToolOutput(result=_compact_trip(t), actions=[_open_trip(t["id"])])


def _maps_link(p: dict) -> str:
    """Link tìm Google Maps dán được vào lịch trình; có place_id thì trỏ đúng điểm, không thì tìm theo tên."""
    if p.get("place_id"):
        query = quote_plus(p["name"] or "")
        url = f"https://www.google.com/maps/search/?api=1&query={query}&query_place_id={quote_plus(p['place_id'])}"
    elif str(p.get("link") or "").startswith("https://"):
        url = p["link"]  # service dựng sẵn khi không có khóa Maps (QĐ-36)
    else:
        query = quote_plus(", ".join(x for x in (p.get("name"), p.get("address")) if x))
        url = f"https://www.google.com/maps/search/?api=1&query={query}"
    return f"[{p['name']}]({url})"


def run_find_place(ctx: ToolContext, data: FindPlaceInput) -> ToolOutput:
    try:
        found = service.find_place(ctx.session, ctx.user, data.query, data.near)
    except AppError as exc:
        if getattr(exc, "code", None) != "MAPS_UNAVAILABLE":
            raise
        # QĐ-36: V1 không có khóa Maps; vẫn trả link tìm theo tên để dựng chuyến.
        found = [{"name": data.query.strip(), "address": data.near, "place_id": None, "verified": False}]
    if not found:
        return ToolOutput(result={"items": [], "ghi_chu": "Không tìm thấy; hỏi người dùng tên khác."})
    items = [
        {
            "name": p["name"],
            "address": p.get("address"),
            "place_id": p.get("place_id"),
            "verified": p.get("verified", bool(p.get("place_id"))),
            "link": _maps_link(p),
        }
        for p in found[:3]
    ]
    actions = [act.open_map_place(f"Xem {p['name']}", p["name"], p.get("place_id")) for p in found[:3]]
    if not any(i["verified"] for i in items):
        return ToolOutput(
            result={
                "items": items,
                "ghi_chu": "Chưa có Google Maps để xác minh: link là link tìm theo tên. Tên điểm phải lấy từ nguồn "
                "web hoặc lời người dùng, không tự nghĩ.",
            },
            actions=actions,
        )
    if len(found) > 1:
        actions.append(
            act.choices("Chọn đúng điểm", [(p["name"][:40], f"Chọn {p['name']}") for p in found[:3]])
        )
    return ToolOutput(result={"items": items}, actions=actions)


def run_open_route(ctx: ToolContext, data: OpenRouteInput) -> ToolOutput:
    found = service.route_actions(
        ctx.session,
        ctx.user,
        trip_id=data.trip_id,
        stop_id=data.stop_id,
        place_query=data.place_query,
        scope=data.scope,
        day_no=data.day_no,
    )
    actions = [_strip_id(a) for a in found if a]
    return ToolOutput(
        result={"so_nut": len(actions), "nut": [a.get("label") for a in actions]}, actions=actions
    )


def run_export(ctx: ToolContext, data: TripIdInput) -> ToolOutput:
    out = service.export_docx(ctx.session, ctx.user, data.trip_id)
    actions = []
    if out.get("download_url", "").startswith("https"):
        actions.append(act.open_link("Mở tệp Word", out["download_url"], "file"))
    return ToolOutput(result={"file_id": out["file_id"]}, actions=actions)


# ---------- Sửa điểm dừng trong chuyến có sẵn ----------

MAX_NEW_STOPS = 10
FUEL_STAY_MINUTES = 10


def _day_stops(ctx: ToolContext, trip_id: int, day_no: int) -> list[dict]:
    t = service.get_trip(ctx.session, ctx.user, trip_id)
    day = next((d for d in t["days"] if d["day_no"] == day_no), None)
    return (day or {}).get("stops", [])


def _place_after(
    ctx: ToolContext, trip_id: int, day_no: int, stop_id: int, after_stop_id: int | None
) -> None:
    if after_stop_id is None:
        return  # create_stop đã đặt cuối ngày
    order = [s["id"] for s in _day_stops(ctx, trip_id, day_no) if s["id"] != stop_id]
    if after_stop_id not in order:
        raise AiError("VALIDATION_ERROR", f"Điểm {after_stop_id} không nằm trong ngày {day_no}.")
    order.insert(order.index(after_stop_id) + 1, stop_id)
    service.reorder_stops(ctx.session, ctx.user, trip_id, day_no, order)


def _after_change(ctx: ToolContext, trip_id: int) -> dict:
    """Chuyến đã đánh giá thì đánh giá lại ngay để km, giờ, rủi ro khớp lịch mới."""
    t = service.get_trip(ctx.session, ctx.user, trip_id)
    again = bool(t.get("evaluation")) and t["status"] not in ("importing", "evaluating")
    if again:
        out = service.evaluate_trip(ctx.session, ctx.user, trip_id)
        service.run_job_now(ctx.session, ctx.user, out["job_id"])
    t = service.find_trip(ctx.session, ctx.user, trip_id=trip_id, query=None, day_no=None)
    return {**_compact_trip(t), "da_danh_gia_lai": again}


def _stop_data(item) -> dict:
    data = item.model_dump(exclude_none=True, exclude={"after_stop_id", "stop_id", "trip_id"})
    if data.get("category") == "di_chuyen" and "stay_minutes" not in data:
        data["stay_minutes"] = FUEL_STAY_MINUTES
    return data


def run_add_stops(ctx: ToolContext, data: AddStopsInput) -> ToolOutput:
    if not 1 <= len(data.stops) <= MAX_NEW_STOPS:
        raise AiError("VALIDATION_ERROR", f"Thêm từ 1 tới {MAX_NEW_STOPS} điểm mỗi lần.")
    added = []
    for item in data.stops:
        stop = service.create_stop(ctx.session, ctx.user, data.trip_id, _stop_data(item))
        _place_after(ctx, data.trip_id, item.day_no, stop["id"], item.after_stop_id)
        added.append({"stop_id": stop["id"], "day_no": item.day_no, "title": stop["title"]})
    return ToolOutput(
        result={"da_them": added, **_after_change(ctx, data.trip_id)},
        actions=[_open_trip(data.trip_id, "Xem chuyến đi")],
    )


def run_update_stop(ctx: ToolContext, data: UpdateStopInput) -> ToolOutput:
    changes = _stop_data(data)
    if not changes and data.after_stop_id is None:
        raise AiError("VALIDATION_ERROR", "Không có gì để sửa.")
    if "day_no" in changes:
        changes["seq"] = (
            1000 + data.stop_id
        )  # tạm cuối ngày mới cho khỏi trùng thứ tự; reorder bên dưới xếp lại
    stop = (
        service.update_stop(ctx.session, ctx.user, data.trip_id, data.stop_id, changes) if changes else None
    )
    if data.after_stop_id is not None:
        day_no = data.day_no or (stop or {}).get("day_no")
        if day_no is None:
            t = service.get_trip(ctx.session, ctx.user, data.trip_id)
            day_no = next(d["day_no"] for d in t["days"] if any(s["id"] == data.stop_id for s in d["stops"]))
        _place_after(ctx, data.trip_id, day_no, data.stop_id, data.after_stop_id)
    elif "day_no" in changes:
        order = [s["id"] for s in _day_stops(ctx, data.trip_id, changes["day_no"])]
        service.reorder_stops(ctx.session, ctx.user, data.trip_id, changes["day_no"], order)
    return ToolOutput(
        result={"da_sua": data.stop_id, **_after_change(ctx, data.trip_id)},
        actions=[_open_trip(data.trip_id, "Xem chuyến đi")],
    )


def run_delete_stop(ctx: ToolContext, data: StopRefInput) -> ToolOutput:
    t = service.get_trip(ctx.session, ctx.user, data.trip_id)
    day = next((d for d in t["days"] if any(s["id"] == data.stop_id for s in d["stops"])), None)
    if day is None:
        raise AiError("NOT_FOUND", "Điểm này không còn trong chuyến (đã xóa trước đó).")
    stops = day["stops"]
    idx = next(i for i, s in enumerate(stops) if s["id"] == data.stop_id)
    stop, prev = stops[idx], (stops[idx - 1] if idx > 0 else None)
    service.delete_stop(ctx.session, ctx.user, data.trip_id, data.stop_id)
    # Xóa điểm là xóa hẳn (không có đường khôi phục): nút Hoàn tác gửi lại câu thêm điểm qua chat.
    where = f" sau {prev['title']}" if prev else " ở đầu ngày"
    again = f"Thêm lại điểm {stop['title']} vào ngày {day['day_no']}{where}"
    if stop.get("place_query"):
        again += f", tìm theo: {stop['place_query']}"
    return ToolOutput(
        result={
            "da_xoa": {"stop_id": data.stop_id, "title": stop["title"]},
            **_after_change(ctx, data.trip_id),
        },
        actions=[act.choices("Hoàn tác", [("Hoàn tác", again)]), _open_trip(data.trip_id, "Xem chuyến đi")],
    )


def prepare_delete(ctx: ToolContext, data: DeleteTripInput) -> ApprovalDraft:
    t = service.get_trip(ctx.session, ctx.user, data.trip_id)
    when = f"{t['start_date'] or 'chưa chọn ngày'}, {len(t['days'])} ngày"
    return ApprovalDraft(
        title=f"Xóa chuyến {t['title']}",
        summary=f"Xóa hẳn chuyến đi và mọi điểm dừng. Lý do: {data.reason}",
        input={"trip_id": data.trip_id},
        details=[{"label": "Chuyến", "value": t["title"]}, {"label": "Thời gian", "value": when}],
        danger=True,
    )


def execute_delete(ctx: ToolContext, tool_input: dict) -> ToolOutput:
    service.delete_trip(ctx.session, ctx.user, int(tool_input["trip_id"]))
    return ToolOutput(result={"da_xoa": int(tool_input["trip_id"])})


STOP_KIND_RULE = (
    "Điểm theo loại (đổ xăng, ATM, nghỉ chân, sửa xe) không cần tên cơ sở: title kiểu Đổ xăng ở <thị trấn trên "
    "tuyến>, place_query kiểu cây xăng gần <thị trấn>; không bịa tên trạm, không bắt người dùng gửi tên. Xin đổ "
    "xăng mỗi khoảng N km thì xem get_trip (km_tu_dau_ngay, leg_km) để chọn thị trấn trên tuyến gần mốc N km, "
    "không cần tìm web từng trạm."
)

TOOLS = [
    ToolSpec(
        name="import_trip",
        label="Đang đọc lịch trình",
        description=(
            "Nhập lịch trình từ tệp người dùng gửi (file_id), đoạn chữ, link, hoặc câu mô tả chuyến đi. "
            "Từ câu mô tả: thiếu ngày đi hoặc nơi xuất phát thì hỏi (tối đa 2 câu một lần); dùng web_search tìm "
            "điểm có thật trong vùng (tên đúng, khu vực, giờ mở cửa nếu nguồn ghi), find_place lấy link từng điểm, "
            "soạn xong đủ mọi ngày rồi mới gọi một lần, text dạng Ngày 1, giờ, việc, kèm nguyên link. Không có "
            "nguồn thì không đưa tên quán. Đầu vào chữ được đọc ngay; xong thì gọi evaluate_trip."
        ),
        input_model=ImportTripInput,
        run=run_import,
        phase=4,
    ),
    ToolSpec(
        name="add_trip_stops",
        label="Đang thêm điểm vào chuyến",
        description=(
            "Thêm 1 tới 10 điểm dừng vào chuyến đã có (theo ngày, chèn sau điểm nào). Chuyến đã đánh giá thì tự "
            "đánh giá lại, kết quả có km và phương án mới. " + STOP_KIND_RULE
        ),
        input_model=AddStopsInput,
        run=run_add_stops,
        phase=4,
    ),
    ToolSpec(
        name="update_trip_stop",
        label="Đang sửa điểm trong chuyến",
        description=(
            "Sửa hoặc dời một điểm dừng (tên, loại, chuỗi tìm, thời gian dừng, ngày, sau điểm nào). "
            "Chuyến đã đánh giá thì tự đánh giá lại."
        ),
        input_model=UpdateStopInput,
        run=run_update_stop,
        phase=4,
    ),
    ToolSpec(
        name="delete_trip_stop",
        label="Đang bỏ điểm khỏi chuyến",
        description="Bỏ một điểm dừng khỏi chuyến; làm ngay, có nút Hoàn tác. Chuyến đã đánh giá thì tự đánh giá lại.",
        input_model=StopRefInput,
        run=run_delete_stop,
        phase=4,
    ),
    ToolSpec(
        name="evaluate_trip",
        label="Đang đánh giá lịch trình",
        description=(
            "Kiểm thời gian chạy, giờ mở cửa, giờ phà, chạy đêm và đề xuất phương án cho một chuyến. Chạy xong "
            "trong lượt (khoảng nửa phút), kết quả có phương án để người dùng chọn."
        ),
        input_model=TripIdInput,
        run=run_evaluate,
        phase=4,
    ),
    ToolSpec(
        name="save_trip",
        label="Đang chốt phương án",
        description="Chốt phương án người dùng chọn cho chuyến đi.",
        input_model=SaveTripInput,
        run=run_save,
        phase=4,
    ),
    ToolSpec(
        name="list_trips",
        label="Đang xem các chuyến",
        description="Liệt kê các chuyến đi đã lưu, lọc theo trạng thái hoặc tên.",
        input_model=ListTripsInput,
        run=run_list,
        phase=4,
    ),
    ToolSpec(
        name="get_trip",
        label="Đang lấy lịch trình",
        description=(
            "Lấy một chuyến theo mã hoặc tên (lấy lịch trình Trà Vinh), có thể chỉ một ngày; gồm điểm dừng, "
            "rủi ro đã tính, phương án. Số liệu và rủi ro do máy tính, không tự đổi."
        ),
        input_model=GetTripInput,
        run=run_get,
        phase=4,
    ),
    ToolSpec(
        name="find_place",
        label="Đang tìm địa điểm",
        description=(
            "Lấy link Google Maps cho một điểm có thật (tối đa 3). Có Maps thì xác minh (verified true); không có thì "
            "trả link tìm theo tên (verified false), tên phải lấy từ kết quả web_search hoặc lời người dùng. "
            "Không chắc điểm nào đúng thì hỏi người dùng."
        ),
        input_model=FindPlaceInput,
        run=run_find_place,
        phase=4,
    ),
    ToolSpec(
        name="open_route",
        label="Đang dựng nút bản đồ",
        description=(
            "Tạo nút dẫn đường xe máy tới một điểm trong chuyến (chỉ đường tới chỗ ăn trưa) hoặc nút xem đường "
            "cả ngày. Không chép link ra chữ."
        ),
        input_model=OpenRouteInput,
        run=run_open_route,
        phase=4,
    ),
    ToolSpec(
        name="export_trip_docx",
        label="Đang xuất Word",
        description="Xuất lịch trình ra tệp Word kiểu tệp mẫu để chia sẻ.",
        input_model=TripIdInput,
        run=run_export,
        phase=4,
    ),
    ToolSpec(
        name="delete_trip",
        label="Đang xóa chuyến",
        description="Xóa cả chuyến đi: chỉ tạo thẻ xác nhận, chưa xóa tới khi người dùng bấm Duyệt.",
        input_model=DeleteTripInput,
        needs_approval=lambda data: True,
        prepare=prepare_delete,
        execute=execute_delete,
        phase=4,
    ),
]
