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
        stops = [
            {
                "stop_id": s["id"],
                "time": s["time_text"] or (s["planned_start"] or "")[11:16] or None,
                "title": s["title"],
                "category": s["category"],
                "role": s["role"],
                "optional": s["optional"],
                "place": s["place_query"],
                "note": s["note"],
            }
            for s in d["stops"]
            if s["role"] in ("main", "via", None)
        ]
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


class DeleteTripInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int
    reason: str


# ---------- Hàm chạy ----------


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
    return ToolOutput(
        result={
            **out,
            "ghi_chu": "Đang đọc lịch trình, khoảng 1 phút. Xong thì người dùng xem nháp trên màn chuyến đi, "
            "xác nhận điểm chưa chắc rồi đánh giá.",
        },
        actions=[_open_trip(out["trip_id"], "Xem chuyến đi")],
    )


def run_evaluate(ctx: ToolContext, data: TripIdInput) -> ToolOutput:
    out = service.evaluate_trip(ctx.session, ctx.user, data.trip_id)
    return ToolOutput(
        result={
            **out,
            "ghi_chu": "Đang tính đường, giờ mở cửa và rủi ro, khoảng 1 phút; xong có 2 tới 3 phương án.",
        },
        actions=[_open_trip(data.trip_id, "Xem đánh giá")],
    )


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
    url = (
        "https://www.google.com/maps/search/?api=1"
        f"&query={quote_plus(p['name'] or '')}&query_place_id={quote_plus(p['place_id'])}"
    )
    return f"[{p['name']}]({url})"


def run_find_place(ctx: ToolContext, data: FindPlaceInput) -> ToolOutput:
    found = service.find_place(ctx.session, ctx.user, data.query, data.near)
    if not found:
        return ToolOutput(result={"items": [], "ghi_chu": "Không tìm thấy; hỏi người dùng tên khác."})
    items = [
        {"name": p["name"], "address": p.get("address"), "place_id": p["place_id"], "link": _maps_link(p)}
        for p in found[:3]
    ]
    actions = [act.open_map_place(f"Xem {p['name']}", p["name"], p["place_id"]) for p in found[:3]]
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


TOOLS = [
    ToolSpec(
        name="import_trip",
        label="Đang đọc lịch trình",
        description=(
            "Nhập lịch trình từ tệp người dùng gửi (file_id), đoạn chữ, link, hoặc câu mô tả chuyến đi. "
            "Từ câu mô tả: hỏi tối đa 2 câu (ngày đi, nơi xuất phát), dùng find_place chọn điểm có thật, rồi gửi "
            "text dạng Ngày 1, giờ, việc, kèm nguyên link find_place trả. Không tự nghĩ tên quán."
        ),
        input_model=ImportTripInput,
        run=run_import,
        phase=4,
    ),
    ToolSpec(
        name="evaluate_trip",
        label="Đang đánh giá lịch trình",
        description="Kiểm thời gian chạy, giờ mở cửa, giờ phà, chạy đêm và đề xuất phương án cho một chuyến.",
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
        description="Tìm địa điểm có thật trên Google Maps (tối đa 3). Không chắc điểm nào đúng thì hỏi người dùng.",
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
