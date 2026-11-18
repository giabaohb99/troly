"""Công cụ AI cài đặt: get_settings, update_setting (20 mục 3.7, việc 4-02).

AI chỉ đổi được người quan trọng và từ khóa gấp của hộp tin (luật nằm ở module inbox); không qua thẻ duyệt
(QĐ-27). App được nghe, kết nối Google, thiết bị, tài khoản chỉ đổi trên màn Cài đặt (60 mục 3.7).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ToolContext, ToolOutput, ToolSpec
from app.modules.inbox import service as inbox
from app.modules.setting import service

# Khóa cài đặt AI được đọc; bí mật và khóa kỹ thuật không đưa ra.
READABLE = (
    "calendar.default_remind_minutes",
    "calendar.week_start",
    "expense.default_account",
    "inbox.ai_enabled",
    "inbox.quiet_hours",
    "trip.default_travel_mode",
    "trip.night_start",
    "trip.night_end",
    "trip.ride_break_minutes",
)
RULE_KINDS = ("vip_sender", "urgent_keyword", "muted_sender", "muted_keyword", "muted_app")


class NoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdateSettingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Literal["vip_sender", "urgent_keyword"] = Field(
        description="vip_sender: người quan trọng (tin của họ lên đầu); urgent_keyword: từ khóa gấp"
    )
    op: Literal["add", "remove"]
    value: str = Field(description="Tên người như hiện trên thông báo, hoặc từ khóa")
    app: Literal["zalo", "telegram", "messenger", "sms", "gmail"] | None = Field(
        description="Chỉ áp cho app này; null là mọi app"
    )


def run_get_settings(ctx: ToolContext, data: NoInput) -> ToolOutput:
    values = service.get_all(ctx.session, ctx.user.user_id)["values"]
    rules = inbox.list_rules(ctx.session, ctx.user.user_id)
    grouped = {
        kind: [r["value"] + (f" ({r['app']})" if r["app"] else "") for r in rules if r["kind"] == kind]
        for kind in RULE_KINDS
    }
    return ToolOutput(
        result={"settings": {k: values.get(k) for k in READABLE}, "inbox_rules": grouped},
        actions=[act.open_screen("Mở Cài đặt", "settings_profile")],
    )


def run_update_setting(ctx: ToolContext, data: UpdateSettingInput) -> ToolOutput:
    value = data.value.strip()
    if not value:
        raise AiError("VALIDATION_ERROR", "Giá trị đang trống.")
    if data.op == "add":
        rule = inbox.create_rule(ctx.session, ctx.user.user_id, data.key, value, data.app)
        text = f"Đã thêm {'người quan trọng' if data.key == 'vip_sender' else 'từ khóa gấp'}: {rule['value']}"
    else:
        folded = inbox.fold(value)
        matches = [
            r
            for r in inbox.list_rules(ctx.session, ctx.user.user_id)
            if r["kind"] == data.key
            and inbox.fold(r["value"]) == folded
            and (data.app is None or r["app"] == data.app)
        ]
        if not matches:
            raise AiError("NOT_FOUND", "Không có luật này để bỏ.")
        for r in matches:
            inbox.delete_rule(ctx.session, ctx.user.user_id, r["id"])
        text = f"Đã bỏ {'người quan trọng' if data.key == 'vip_sender' else 'từ khóa gấp'}: {value}"
    return ToolOutput(
        result={"ket_qua": text}, actions=[act.open_screen("Xem luật hộp tin", "settings_profile")]
    )


TOOLS = [
    ToolSpec(
        name="get_settings",
        label="Đang xem cài đặt",
        description="Xem cài đặt hiện tại và luật hộp tin (người quan trọng, từ khóa gấp, tắt tiếng).",
        input_model=NoInput,
        run=run_get_settings,
        phase=4,
    ),
    ToolSpec(
        name="update_setting",
        label="Đang đổi cài đặt",
        description=(
            "Thêm hoặc bỏ người quan trọng, từ khóa gấp của hộp tin. Các cài đặt khác (app được nghe, Google, "
            "thiết bị) chỉ đổi trên màn Cài đặt: nói người dùng mở Cài đặt."
        ),
        input_model=UpdateSettingInput,
        run=run_update_setting,
        phase=4,
    ),
]
