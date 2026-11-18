"""Lược đồ bóc tách lịch trình, lược đồ duy nhất (41 mục 3.2). Agent AI dùng làm output_model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["an_uong", "nghi", "tham_quan", "pha", "di_chuyen", "khach_san", "mua_sam", "khac"]
Role = Literal["main", "alternative", "backup", "generic", "via"]
FactKind = Literal["ferry_last", "ferry_first", "checkin", "checkout", "hotline", "opening_hours", "other"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractPlace(_Strict):
    label: str = Field(description="Tên điểm như trong tệp")
    url: str | None = Field(
        None, description="Link Google Maps gắn với chữ này, nguyên văn; không có thì null"
    )
    role: Role = Field(
        "main", description="main, alternative (sau chữ hoặc), backup (sau Dự phòng), generic, via"
    )


class ExtractStop(_Strict):
    time_text: str | None = Field(None, description="Giờ nguyên văn: 2h30, ~7h00, 10h30–12h30")
    title: str = Field(description="Một câu ngắn mô tả việc ở điểm này")
    category: Category = "khac"
    places: list[ExtractPlace] = Field(default_factory=list)
    cost_note: str | None = None
    phone: str | None = None
    note: str | None = None
    optional: bool = Field(False, description="true khi có: nếu còn đói, nếu còn lúa, có thể")


class ExtractDay(_Strict):
    day_no: int
    weekday_text: str | None = Field(None, description="thứ 7, chủ nhật, thứ 2...")
    date: str | None = Field(None, description="YYYY-MM-DD nếu tệp ghi ngày; không thì null")
    title: str | None = None
    route_text: str | None = Field(None, description="Dòng Đường đi: ... nguyên văn")
    stops: list[ExtractStop] = Field(default_factory=list)


class ExtractHotel(_Strict):
    night_no: int
    label: str
    url: str | None = None
    booked: bool = False
    backups: list[ExtractPlace] = Field(default_factory=list)


class ExtractMapLink(_Strict):
    day_no: int
    label: str
    url: str


class ExtractFact(_Strict):
    kind: FactKind
    day_no: int | None = None
    value_time: str | None = Field(None, description="HH:MM")
    value_text: str | None = None
    text: str = Field(description="Câu nguyên văn trong tệp")


class TripExtract(_Strict):
    title: str
    travel_mode: Literal["motorbike", "car", "walk"] = "motorbike"
    origin_text: str | None = None
    end_text: str | None = None
    start_date: str | None = Field(None, description="YYYY-MM-DD nếu tệp ghi; không thì null")
    nights: int | None = None
    days: list[ExtractDay] = Field(default_factory=list)
    hotels: list[ExtractHotel] = Field(default_factory=list)
    map_links: list[ExtractMapLink] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    facts: list[ExtractFact] = Field(default_factory=list)
