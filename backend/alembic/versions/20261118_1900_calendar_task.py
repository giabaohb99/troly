"""Phase 3: sự kiện lịch, việc (11 mục 3.11).

Revision ID: 0004_calendar_task
Revises: 0003_google
Create Date: 2026-11-18 19:00
"""

from alembic import op

revision = "0004_calendar_task"
down_revision = "0003_google"
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
        CREATE TABLE tab_event ({COMMON},
            title text NOT NULL,
            description text,
            location text,
            all_day boolean NOT NULL DEFAULT false,
            start_at timestamptz,
            end_at timestamptz,
            start_date date,
            end_date date,
            timezone text,
            status text NOT NULL DEFAULT 'confirmed'
                CONSTRAINT ck_tab_event_status CHECK (status IN ('confirmed','tentative','cancelled')),
            recurrence text[],
            recurring_event_id text,
            original_start_at timestamptz,
            attendees jsonb NOT NULL DEFAULT '[]',
            remind_minutes integer[] NOT NULL DEFAULT '{{}}',
            remind_source text NOT NULL DEFAULT 'app'
                CONSTRAINT ck_tab_event_remind_source CHECK (remind_source IN ('app','google')),
            is_alarm boolean NOT NULL DEFAULT false,
            is_organizer boolean NOT NULL DEFAULT true,
            source text NOT NULL DEFAULT 'app' CONSTRAINT ck_tab_event_source CHECK (source IN ('app','google')),
            task_id bigint,
            google_account_id bigint REFERENCES tab_google_account(id) ON DELETE SET NULL,
            google_calendar_id text,
            google_event_id text,
            google_etag text,
            google_updated_at timestamptz,
            google_html_link text,
            sync_status text NOT NULL DEFAULT 'local_only' CONSTRAINT ck_tab_event_sync_status
                CHECK (sync_status IN ('local_only','pending','synced','conflict','error')),
            sync_error text,
            deleted_at timestamptz,
            CONSTRAINT ck_tab_event_time_range CHECK (
                (all_day AND start_date IS NOT NULL AND end_date > start_date)
                OR (NOT all_day AND start_at IS NOT NULL AND end_at >= start_at))
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_event_user_id ON tab_event (user_id)")
    op.execute("CREATE INDEX ix_tab_event_start ON tab_event (user_id, start_at) WHERE deleted_at IS NULL")
    op.execute(
        "CREATE INDEX ix_tab_event_recurring ON tab_event (user_id) "
        "WHERE recurrence IS NOT NULL AND deleted_at IS NULL"
    )
    op.execute("CREATE INDEX ix_tab_event_recurring_event_id ON tab_event (user_id, recurring_event_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_event_google ON tab_event (user_id, google_calendar_id, google_event_id) "
        "WHERE google_event_id IS NOT NULL"
    )
    op.execute(
        f"""
        CREATE TABLE tab_task ({COMMON},
            title text NOT NULL CONSTRAINT ck_tab_task_title_len CHECK (char_length(title) <= 1024),
            note text CONSTRAINT ck_tab_task_note_len CHECK (note IS NULL OR char_length(note) <= 8000),
            status text NOT NULL DEFAULT 'todo' CONSTRAINT ck_tab_task_status CHECK (status IN ('todo','done','cancelled')),
            priority text NOT NULL DEFAULT 'normal'
                CONSTRAINT ck_tab_task_priority CHECK (priority IN ('low','normal','high')),
            due_date date,
            due_at timestamptz,
            completed_at timestamptz,
            completed_source text CONSTRAINT ck_tab_task_completed_source
                CHECK (completed_source IS NULL OR completed_source IN ('app','google')),
            event_id bigint REFERENCES tab_event(id) ON DELETE SET NULL,
            source text NOT NULL DEFAULT 'app' CONSTRAINT ck_tab_task_source CHECK (source IN ('app','chat')),
            google_account_id bigint REFERENCES tab_google_account(id) ON DELETE SET NULL,
            google_tasklist_id text,
            google_task_id text,
            google_etag text,
            google_updated_at timestamptz,
            sync_status text NOT NULL DEFAULT 'local_only' CONSTRAINT ck_tab_task_sync_status
                CHECK (sync_status IN ('local_only','pending','synced','remote_deleted','error')),
            sync_error text,
            deleted_at timestamptz,
            CONSTRAINT ck_tab_task_due_one CHECK (due_date IS NULL OR due_at IS NULL)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_task_user_id ON tab_task (user_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_task_google ON tab_task (user_id, google_task_id) WHERE google_task_id IS NOT NULL"
    )
    op.execute("CREATE INDEX ix_tab_task_open ON tab_task (user_id, status) WHERE deleted_at IS NULL")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tab_task")
    op.execute("DROP TABLE IF EXISTS tab_event")
