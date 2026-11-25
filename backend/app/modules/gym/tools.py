"""Công cụ AI của module gym (QĐ-54, agent AI): đọc báo cáo tập luyện từ app gym, chỉ đọc.

Dữ liệu từ `integrations.gym.client.fetch_summary` (hình dạng theo `getIntegrationSummary` của app gym):
`workouts[].exercises[] = {name, sets_done, top_set: {weight_kg, reps}, volume_kg}`, `progress[] = {name, first,
last}`, `nutrition.days[]` tính theo bữa đã tick. Phần tóm chung (số buổi, cân nặng, hôm nay, mai) dùng
`service.summarize` như thẻ Báo cáo.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import ToolContext, ToolOutput, ToolSpec
from app.integrations.gym import client
from app.modules.gym import service

MAX_WORKOUTS = 14
MAX_LIFTS = 15
NUTRITION_NOTE = "kcal và đạm tính theo bữa đã tick trong app gym, không phải đo thật."


class GymReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_date: date | None = Field(
        default=None, description="Ngày đầu YYYY-MM-DD; bỏ trống thì 7 ngày tới hôm nay"
    )
    to_date: date | None = Field(
        default=None, description="Ngày cuối YYYY-MM-DD, tối đa 92 ngày tính từ ngày đầu"
    )


def _set_text(top: dict | None) -> str | None:
    top = top or {}
    weight, reps = top.get("weight_kg"), top.get("reps")
    if reps is None:
        return None
    return f"{weight:g}kg x {reps}" if weight is not None else f"{reps} lần (không tạ)"


def _workouts(raw: dict) -> list[dict]:
    out = []
    for w in (raw.get("workouts") or [])[-MAX_WORKOUTS:]:
        out.append(
            {
                "ngay": w.get("date"),
                "buoi": w.get("day_name") or "Ngoài lịch",
                "du_bai": bool(w.get("done")),
                "bai": [
                    {
                        "ten": e.get("name"),
                        "so_set": e.get("sets_done"),
                        "top_set": _set_text(e.get("top_set")),
                        "khoi_luong_kg": e.get("volume_kg"),
                    }
                    for e in w.get("exercises") or []
                ],
            }
        )
    return out


def _lifts(raw: dict) -> list[dict]:
    out = []
    for p in raw.get("progress") or []:
        first, last = p.get("first") or {}, p.get("last") or {}
        fw, lw = first.get("weight_kg"), last.get("weight_kg")
        out.append(
            {
                "bai": p.get("name"),
                "dau": _set_text(first),
                "cuoi": _set_text(last),
                "tang_kg": round(lw - fw, 2) if fw is not None and lw is not None else None,
            }
        )
    out.sort(key=lambda x: x["tang_kg"] if x["tang_kg"] is not None else -1e9, reverse=True)
    return out[:MAX_LIFTS]


def _nutrition(raw: dict) -> dict:
    nutrition = raw.get("nutrition") or {}
    targets = nutrition.get("targets") or {}
    train_days = {p.get("date") for p in raw.get("planned") or []} | {
        w.get("date") for w in raw.get("workouts") or []
    }
    days = []
    for d in nutrition.get("days") or []:
        train = d.get("date") in train_days
        days.append(
            {
                "ngay": d.get("date"),
                "ngay_tap": train,
                "so_bua_tick": d.get("meals_checked"),
                "kcal": d.get("kcal"),
                "kcal_muc_tieu": targets.get("kcal_train") if train else targets.get("kcal_rest"),
                "dam_g": d.get("protein_g"),
                "dam_muc_tieu_g": targets.get("protein_g"),
                "nuoc_coc": d.get("water_cups"),
            }
        )
    return {"ghi_chu": NUTRITION_NOTE, "muc_tieu": targets, "ngay": days}


def run_gym_report(ctx: ToolContext, data: GymReportInput) -> ToolOutput:
    raw = client.fetch_summary(
        data.from_date, data.to_date
    )  # lỗi có code: GYM_NOT_CONNECTED, GYM_UNAVAILABLE
    s = service.summarize(raw)
    result = {
        "tu": s["from"],
        "den": s["to"],
        "buoi_da_tap": s["sessions_done"],
        "buoi_du_bai": s["sessions_complete"],
        "buoi_theo_lich": s["sessions_planned"],
        "buoi_tap": _workouts(raw),
        "tien_bo_ta": _lifts(raw),
        "can_nang": s["weight"],
        "dinh_duong": _nutrition(raw),
        "hom_nay": s["today"],
        "ngay_mai": s["tomorrow"],
        "ghi_chu": "Chỉ đọc. Người dùng muốn sửa lịch tập, bữa ăn thì bảo mở app gym (nút bên dưới).",
    }
    return ToolOutput(result=result, actions=[act.open_link("Mở app gym", service.APP_URL, "web")])


TOOLS = [
    ToolSpec(
        name="get_gym_report",
        label="Đang xem số liệu tập luyện",
        description=(
            "Báo cáo tập luyện từ app gym, chỉ đọc: số buổi đã tập so với lịch, từng buổi (bài, top set, khối "
            "lượng), bài tăng tạ đầu và cuối khoảng, cân nặng, kcal và đạm theo ngày so mục tiêu (theo bữa đã "
            "tick), buổi hôm nay và mai. Hỏi về tập, ăn, cân nặng thì dùng công cụ này, không đoán. Không sửa "
            "được dữ liệu gym."
        ),
        input_model=GymReportInput,
        run=run_gym_report,
        phase=4,
    ),
]
