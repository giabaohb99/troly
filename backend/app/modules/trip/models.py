"""Bảng module trip (11 mục 3.13, 41 mục 3 tới 6). Migration 0005_trip."""

from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

CATEGORIES = ("an_uong", "nghi", "tham_quan", "pha", "di_chuyen", "khach_san", "mua_sam", "khac")
ROLES = ("main", "alternative", "backup", "generic", "via")
FACT_KINDS = ("ferry_last", "ferry_first", "checkin", "checkout", "hotline", "opening_hours", "other")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")"


class Trip(UserOwnedMixin, Base):
    __tablename__ = "tab_trip"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="dates"),
        CheckConstraint(_in("travel_mode", ("motorbike", "car", "walk")), name="travel_mode"),
        CheckConstraint(
            _in("status", ("importing", "draft", "evaluating", "planned", "done", "failed")), name="status"
        ),
        CheckConstraint(_in("source_kind", ("docx", "pdf", "image", "text", "link")), name="source_kind"),
        Index("ix_tab_trip_user_start", "user_id", text("start_date DESC")),
        Index("ix_tab_trip_search", "search_vector", postgresql_using="gin"),
    )

    title: Mapped[str] = mapped_column(Text)
    start_date: Mapped[datetime | None] = mapped_column(Date)
    end_date: Mapped[datetime | None] = mapped_column(Date)
    nights: Mapped[int | None] = mapped_column(SmallInteger)
    travel_mode: Mapped[str] = mapped_column(Text, server_default="motorbike")
    origin_text: Mapped[str | None] = mapped_column(Text)
    end_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="importing")
    source_kind: Mapped[str | None] = mapped_column(Text)
    source_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_file.id", ondelete="SET NULL")
    )
    source_text: Mapped[str | None] = mapped_column(Text)
    extract_json: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[list] = mapped_column(JSONB, server_default="[]")
    hotels: Mapped[list] = mapped_column(JSONB, server_default="[]")
    evaluation: Mapped[dict | None] = mapped_column(JSONB)
    chosen_option_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "tab_trip_option.id", ondelete="SET NULL", use_alter=True, name="fk_tab_trip_chosen_option_id"
        ),
    )
    export_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_file.id", ondelete="SET NULL")
    )
    error: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('troly_vn', coalesce(title,'') || ' ' || coalesce(origin_text,'') || ' ' "
            "|| coalesce(end_text,''))",
            persisted=True,
        ),
    )


class TripStop(UserOwnedMixin, Base):
    __tablename__ = "tab_trip_stop"
    __table_args__ = (
        UniqueConstraint("trip_id", "day_no", "seq", deferrable=True, initially="DEFERRED"),
        CheckConstraint("day_no >= 1", name="day_no"),
        CheckConstraint(_in("category", CATEGORIES), name="category"),
        CheckConstraint(_in("role", ROLES), name="role"),
        CheckConstraint(_in("coord_source", ("user", "google")), name="coord_source"),
        CheckConstraint(
            _in("resolve_status", ("ok", "uncertain", "not_found", "manual")), name="resolve_status"
        ),
        Index("ix_tab_trip_stop_trip", "trip_id", "day_no", "seq"),
        Index("ix_tab_trip_stop_search", "search_vector", postgresql_using="gin"),
    )

    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tab_trip.id", ondelete="CASCADE"))
    day_no: Mapped[int] = mapped_column(SmallInteger)
    seq: Mapped[int] = mapped_column(SmallInteger)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, server_default="khac")
    role: Mapped[str] = mapped_column(Text, server_default="main")
    parent_stop_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_trip_stop.id", ondelete="CASCADE")
    )
    time_text: Mapped[str | None] = mapped_column(Text)
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approx: Mapped[bool] = mapped_column(Boolean, server_default="false")
    fixed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    optional: Mapped[bool] = mapped_column(Boolean, server_default="false")
    stay_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    place_query: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    place_id: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    coord_source: Mapped[str | None] = mapped_column(Text)
    coord_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolve_status: Mapped[str] = mapped_column(Text, server_default="uncertain")
    phone: Mapped[str | None] = mapped_column(Text)
    cost_note: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    alternatives: Mapped[list] = mapped_column(JSONB, server_default="[]")
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('troly_vn', coalesce(title,'') || ' ' || coalesce(place_query,'') || ' ' "
            "|| coalesce(note,''))",
            persisted=True,
        ),
    )


class TripOption(UserOwnedMixin, Base):
    __tablename__ = "tab_trip_option"
    __table_args__ = (Index("ix_tab_trip_option_trip", "trip_id"),)

    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tab_trip.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[dict] = mapped_column(JSONB)
    total_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 1))
    total_ride_minutes: Mapped[int | None] = mapped_column(Integer)
    night_ride_minutes: Mapped[int | None] = mapped_column(Integer)
    red_count: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    yellow_count: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    risks: Mapped[list] = mapped_column(JSONB, server_default="[]")
    changes: Mapped[list] = mapped_column(JSONB, server_default="[]")
    chosen: Mapped[bool] = mapped_column(Boolean, server_default="false")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TripFact(UserOwnedMixin, Base):
    __tablename__ = "tab_trip_fact"
    __table_args__ = (
        CheckConstraint(_in("kind", FACT_KINDS), name="kind"),
        Index("ix_tab_trip_fact_trip", "trip_id"),
    )

    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tab_trip.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    stop_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_trip_stop.id", ondelete="SET NULL")
    )
    day_no: Mapped[int | None] = mapped_column(SmallInteger)
    value_time: Mapped[time | None] = mapped_column(Time)
    value_text: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)


class PlaceCache(Base):
    """Bảng hệ thống dùng chung, không dữ liệu cá nhân. place_id giữ mãi; tọa độ, địa chỉ tối đa 30 ngày."""

    __tablename__ = "tab_place_cache"
    __table_args__ = (
        Index("ix_tab_place_cache_place_id", "place_id"),
        Index("ix_tab_place_cache_fetched_at", "fetched_at", postgresql_where=text("lat IS NOT NULL")),
    )

    query_norm: Mapped[str] = mapped_column(Text, primary_key=True)
    bias_key: Mapped[str] = mapped_column(Text, primary_key=True)
    place_id: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    formatted_address: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class RouteCache(Base):
    __tablename__ = "tab_route_cache"
    __table_args__ = (
        UniqueConstraint(
            "origin_key", "destination_key", "travel_mode", "avoid_highways", name="uq_tab_route_cache_key"
        ),
        CheckConstraint(_in("travel_mode", ("two_wheeler", "drive", "walk")), name="travel_mode"),
        Index("ix_tab_route_cache_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    origin_key: Mapped[str] = mapped_column(Text)
    destination_key: Mapped[str] = mapped_column(Text)
    travel_mode: Mapped[str] = mapped_column(Text)
    avoid_highways: Mapped[bool] = mapped_column(Boolean)
    distance_m: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
