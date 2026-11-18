"""Phase 3: bảng Google (11 mục 3.12, 40 mục 3 tới 5).

Revision ID: 0003_google
Revises: 0002_device_inbox
Create Date: 2026-11-18 17:00
"""

from alembic import op

revision = "0003_google"
down_revision = "0002_device_inbox"
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
        CREATE TABLE tab_google_account ({COMMON},
            google_sub text NOT NULL,
            email citext NOT NULL,
            granted_scopes text[] NOT NULL,
            enabled_packs text[] NOT NULL DEFAULT '{{base}}',
            refresh_token_enc bytea NOT NULL,
            access_token_enc bytea,
            access_expires_at timestamptz,
            key_version smallint NOT NULL,
            status text NOT NULL DEFAULT 'active' CONSTRAINT ck_tab_google_account_status
                CHECK (status IN ('active','reauth_required','revoked')),
            last_error text,
            invalid_grant_count integer NOT NULL DEFAULT 0,
            connected_at timestamptz NOT NULL,
            CONSTRAINT uq_tab_google_account_google_sub UNIQUE (google_sub),
            CONSTRAINT uq_tab_google_account_user_id UNIQUE (user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_google_account_user_id ON tab_google_account (user_id)")
    op.execute(
        f"""
        CREATE TABLE tab_google_oauth_state ({COMMON},
            state_hash text NOT NULL,
            packs text[] NOT NULL,
            code_verifier_enc bytea NOT NULL,
            key_version smallint NOT NULL,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            CONSTRAINT uq_tab_google_oauth_state_state_hash UNIQUE (state_hash)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_google_oauth_state_user_id ON tab_google_oauth_state (user_id)")
    op.execute(
        f"""
        CREATE TABLE tab_google_sync_state ({COMMON},
            google_account_id bigint NOT NULL REFERENCES tab_google_account(id) ON DELETE CASCADE,
            service text NOT NULL CONSTRAINT ck_tab_google_sync_state_service
                CHECK (service IN ('calendar','tasks','gmail','contacts','drive','sheets')),
            resource_id text NOT NULL,
            sync_token text,
            history_id text,
            updated_min timestamptz,
            needs_sync boolean NOT NULL DEFAULT true,
            last_sync_at timestamptz,
            last_full_sync_at timestamptz,
            next_sync_at timestamptz,
            initial_sync_state text CONSTRAINT ck_tab_google_sync_state_initial_sync_state
                CHECK (initial_sync_state IN ('pending','running','done','failed')),
            status text NOT NULL DEFAULT 'ok' CONSTRAINT ck_tab_google_sync_state_status
                CHECK (status IN ('ok','error','disabled')),
            last_error text,
            channel_id uuid,
            channel_resource_id text,
            channel_token_hash text,
            channel_expires_at timestamptz,
            CONSTRAINT uq_tab_google_sync_state_channel_id UNIQUE (channel_id),
            CONSTRAINT uq_tab_google_sync_state_google_account_id_service_resource_id
                UNIQUE (google_account_id, service, resource_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_google_sync_state_user_id ON tab_google_sync_state (user_id)")
    op.execute("CREATE INDEX ix_tab_google_sync_state_next_sync_at ON tab_google_sync_state (next_sync_at)")
    op.execute(
        "CREATE INDEX ix_tab_google_sync_state_channel_expires_at ON tab_google_sync_state (channel_expires_at)"
    )
    op.execute(
        f"""
        CREATE TABLE tab_google_outbox ({COMMON},
            google_account_id bigint NOT NULL REFERENCES tab_google_account(id) ON DELETE CASCADE,
            service text NOT NULL CONSTRAINT ck_tab_google_outbox_service
                CHECK (service IN ('calendar','tasks','gmail','drive','sheets')),
            op text NOT NULL CONSTRAINT ck_tab_google_outbox_op
                CHECK (op IN ('insert','patch','delete','draft_create','draft_send','file_upload','sheet_write')),
            local_type text NOT NULL CONSTRAINT ck_tab_google_outbox_local_type
                CHECK (local_type IN ('event','task','gmail_draft','file','export')),
            local_id bigint NOT NULL,
            payload jsonb NOT NULL DEFAULT '{{}}',
            status text NOT NULL DEFAULT 'pending' CONSTRAINT ck_tab_google_outbox_status
                CHECK (status IN ('pending','processing','done','failed','conflict')),
            attempts smallint NOT NULL DEFAULT 0,
            next_attempt_at timestamptz NOT NULL DEFAULT now(),
            locked_at timestamptz,
            last_error text
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_google_outbox_user_id ON tab_google_outbox (user_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_google_outbox_waiting ON tab_google_outbox (local_type, local_id, op) "
        "WHERE status IN ('pending','processing')"
    )
    op.execute(
        "CREATE INDEX ix_tab_google_outbox_pending ON tab_google_outbox (status, next_attempt_at) "
        "WHERE status = 'pending'"
    )


def downgrade() -> None:
    for table in (
        "tab_google_outbox",
        "tab_google_sync_state",
        "tab_google_oauth_state",
        "tab_google_account",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
