"""Phase 2: app được nghe, sự kiện thiết bị, hộp tin (11 mục 3.5, 3.10).

Revision ID: 0002_device_inbox
Revises: 0001_core_init
Create Date: 2026-11-18 15:00
"""

from alembic import op

revision = "0002_device_inbox"
down_revision = "0001_core_init"
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
        CREATE TABLE tab_listened_app ({COMMON},
            package_name text NOT NULL,
            label text NOT NULL,
            purpose text NOT NULL CONSTRAINT ck_tab_listened_app_purpose CHECK (purpose IN ('expense','inbox')),
            parser text NOT NULL CONSTRAINT ck_tab_listened_app_parser
                CHECK (parser IN ('vcb','tcb','momo','zalo','telegram','messenger','sms','generic')),
            enabled boolean NOT NULL DEFAULT true,
            is_default boolean NOT NULL DEFAULT false,
            CONSTRAINT uq_tab_listened_app_user_id_package_name UNIQUE (user_id, package_name)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_listened_app_user_id ON tab_listened_app (user_id)")
    op.execute(
        f"""
        CREATE TABLE tab_device_event ({COMMON},
            device_id bigint NOT NULL REFERENCES tab_device(id) ON DELETE CASCADE,
            client_event_id uuid NOT NULL,
            kind text NOT NULL CONSTRAINT ck_tab_device_event_kind CHECK (kind IN ('notification','reminder_action')),
            app_package text,
            posted_at timestamptz NOT NULL,
            payload jsonb NOT NULL,
            received_at timestamptz NOT NULL DEFAULT now(),
            status text NOT NULL DEFAULT 'pending' CONSTRAINT ck_tab_device_event_status
                CHECK (status IN ('pending','processing','done','ignored','failed')),
            attempts smallint NOT NULL DEFAULT 0,
            next_attempt_at timestamptz NOT NULL DEFAULT now(),
            locked_at timestamptz,
            processed_at timestamptz,
            result_kind text CONSTRAINT ck_tab_device_event_result_kind
                CHECK (result_kind IN ('expense','inbox_message','transfer_merged','task_updated','none')),
            result_id bigint,
            error text,
            CONSTRAINT uq_tab_device_event_device_id_client_event_id UNIQUE (device_id, client_event_id),
            CONSTRAINT ck_tab_device_event_app_package CHECK (kind <> 'notification' OR app_package IS NOT NULL)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_device_event_user_id ON tab_device_event (user_id)")
    op.execute(
        "CREATE INDEX ix_tab_device_event_pending ON tab_device_event (status, next_attempt_at) WHERE status = 'pending'"
    )
    op.execute("CREATE INDEX ix_tab_device_event_received ON tab_device_event (user_id, received_at DESC)")
    op.execute(
        "ALTER TABLE tab_expense ADD CONSTRAINT fk_tab_expense_device_event_id_tab_device_event "
        "FOREIGN KEY (device_event_id) REFERENCES tab_device_event(id) ON DELETE SET NULL"
    )
    op.execute(
        f"""
        CREATE TABLE tab_inbox_message ({COMMON},
            source text NOT NULL CONSTRAINT ck_tab_inbox_message_source CHECK (source IN ('notification','gmail')),
            app text NOT NULL CONSTRAINT ck_tab_inbox_message_app
                CHECK (app IN ('zalo','telegram','messenger','sms','gmail','other')),
            app_package text,
            device_id bigint REFERENCES tab_device(id) ON DELETE SET NULL,
            device_event_id bigint REFERENCES tab_device_event(id) ON DELETE SET NULL,
            sender text,
            sender_key text NOT NULL,
            conversation_key text NOT NULL,
            conversation_title text,
            is_group boolean NOT NULL DEFAULT false,
            subject text,
            text text NOT NULL CONSTRAINT ck_tab_inbox_message_text_len CHECK (char_length(text) <= 4000),
            hidden_content boolean NOT NULL DEFAULT false,
            posted_at timestamptz NOT NULL,
            status text NOT NULL DEFAULT 'new' CONSTRAINT ck_tab_inbox_message_status CHECK (status IN ('new','seen','done')),
            importance text NOT NULL DEFAULT 'normal'
                CONSTRAINT ck_tab_inbox_message_importance CHECK (importance IN ('normal','important')),
            importance_reason text,
            external_id text,
            thread_ref text,
            labels text[] NOT NULL DEFAULT '{{}}',
            dedupe_hash text NOT NULL,
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('troly_vn', coalesce(sender,'') || ' ' || coalesce(conversation_title,'') || ' '
                    || coalesce(subject,'') || ' ' || text)
            ) STORED
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_inbox_message_user_id ON tab_inbox_message (user_id)")
    op.execute("CREATE UNIQUE INDEX uq_tab_inbox_message_dedupe ON tab_inbox_message (user_id, dedupe_hash)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_inbox_message_external ON tab_inbox_message (user_id, external_id) "
        "WHERE source = 'gmail'"
    )
    op.execute(
        "CREATE INDEX ix_tab_inbox_message_conversation ON tab_inbox_message (user_id, conversation_key, posted_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_tab_inbox_message_status ON tab_inbox_message (user_id, status, importance, posted_at DESC)"
    )
    op.execute("CREATE INDEX ix_tab_inbox_message_search ON tab_inbox_message USING gin (search_vector)")
    op.execute(
        f"""
        CREATE TABLE tab_inbox_rule ({COMMON},
            kind text NOT NULL CONSTRAINT ck_tab_inbox_rule_kind CHECK (kind IN
                ('vip_sender','urgent_keyword','muted_sender','muted_keyword','muted_app','private_conversation')),
            value text NOT NULL,
            app text
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_inbox_rule_user_id ON tab_inbox_rule (user_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_inbox_rule_value ON tab_inbox_rule (user_id, kind, lower(value), coalesce(app, ''))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tab_inbox_rule")
    op.execute("DROP TABLE IF EXISTS tab_inbox_message")
    op.execute(
        "ALTER TABLE tab_expense DROP CONSTRAINT IF EXISTS fk_tab_expense_device_event_id_tab_device_event"
    )
    op.execute("DROP TABLE IF EXISTS tab_device_event")
    op.execute("DROP TABLE IF EXISTS tab_listened_app")
