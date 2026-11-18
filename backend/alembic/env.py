"""Alembic: một lịch sử thẳng; nạp model của core, ai và mọi module bật (11 mục 3.16)."""

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.core.db import Base
from app.registry import import_all_models

import_all_models()

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata

# Đối tượng chỉ có ở migration viết tay (cấu hình tìm kiếm, hàm), bỏ qua khi so model.
IGNORED_TABLES = {"alembic_version"}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name in IGNORED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
