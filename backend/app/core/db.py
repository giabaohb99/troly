"""Engine, session và lớp gốc của mọi model (10 mục 3.3, 11 mục 3.1)."""

from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache

from sqlalchemy import BigInteger, DateTime, ForeignKey, MetaData, create_engine, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserOwnedMixin(TimestampMixin):
    """Cột chung của mọi bảng nghiệp vụ: id, user_id, created_at, updated_at."""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tab_user.id", ondelete="CASCADE"), index=True
    )


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        connect_args={"options": "-c timezone=UTC"},
    )
    event.listen(engine, "connect", _register_citext)
    return engine


def _register_citext(dbapi_connection, _record) -> None:
    """psycopg không biết kiểu citext (extension) nên `citext[]` đọc về chuỗi `{a,b}`. Đăng ký kiểu để mảng
    email (tab_gmail_draft, tab_contact) đọc ra list. DB chưa có extension thì bỏ qua."""
    from psycopg.types import TypeInfo

    try:
        info = TypeInfo.fetch(dbapi_connection, "citext")
        if info is not None:
            info.register(dbapi_connection)
    finally:
        dbapi_connection.rollback()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def open_session() -> Session:
    return get_session_factory()()


def get_session() -> Iterator[Session]:
    """Dependency: một yêu cầu, một giao dịch; commit khi xong, rollback khi lỗi."""
    session = open_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def SessionLocal() -> Session:  # noqa: N802 - tên quen thuộc mà ai/ đang dùng
    """Mở session mới; dùng được với `with SessionLocal() as s:`."""
    return open_session()
