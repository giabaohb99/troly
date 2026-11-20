"""Đặt chỗ đọc từ thư (QĐ-49): khách sạn, vé máy bay, xe, tàu vào Lịch và chuyến đi.

Revision ID: 0013_booking
Revises: 0012_trip_stop_area
Create Date: 2026-11-20 12:00
"""

from alembic import op

revision = "0013_booking"
down_revision = "0012_trip_stop_area"
branch_labels = None
depends_on = None

COMMON = """
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES tab_user(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE tab_booking ({COMMON},
            kind text NOT NULL CONSTRAINT ck_tab_booking_kind
                CHECK (kind IN ('hotel','flight','bus','train','other')),
            status text NOT NULL CONSTRAINT ck_tab_booking_status
                CHECK (status IN ('confirmed','changed','cancelled')),
            calendar_state text NOT NULL DEFAULT 'none' CONSTRAINT ck_tab_booking_calendar_state
                CHECK (calendar_state IN ('added','undone','none')),
            title text NOT NULL,
            provider text,
            booking_ref text,
            name text,
            address text,
            area text,
            start_at timestamptz,
            start_date date,
            end_at timestamptz,
            end_date date,
            guests smallint,
            price numeric(14,2),
            currency text,
            cancellation text,
            contact_phone text,
            confidence real,
            event_id bigint REFERENCES tab_event(id) ON DELETE SET NULL,
            end_event_id bigint REFERENCES tab_event(id) ON DELETE SET NULL,
            event_snapshot jsonb NOT NULL DEFAULT '{{}}',
            trip_id bigint REFERENCES tab_trip(id) ON DELETE SET NULL,
            trip_stop_id bigint REFERENCES tab_trip_stop(id) ON DELETE SET NULL,
            source_message_id text NOT NULL,
            source_thread_id text
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_booking_user_id ON tab_booking (user_id)")
    op.execute("CREATE INDEX ix_tab_booking_user_start ON tab_booking (user_id, start_date, start_at)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_booking_ref ON tab_booking (user_id, kind, provider, booking_ref) "
        "WHERE booking_ref IS NOT NULL"
    )
    op.execute(
        f"""
        CREATE TABLE tab_booking_mail ({COMMON},
            message_id text NOT NULL,
            outcome text NOT NULL CONSTRAINT ck_tab_booking_mail_outcome
                CHECK (outcome IN ('booking','ignored')),
            booking_id bigint REFERENCES tab_booking(id) ON DELETE SET NULL,
            CONSTRAINT uq_tab_booking_mail_user_id_message_id UNIQUE (user_id, message_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_booking_mail_user_id ON tab_booking_mail (user_id)")
    op.execute("ALTER TABLE tab_trip_stop ADD COLUMN booking jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE tab_trip_stop DROP COLUMN IF EXISTS booking")
    op.execute("DROP TABLE IF EXISTS tab_booking_mail")
    op.execute("DROP TABLE IF EXISTS tab_booking")
