"""Kết nối MCP chung như Claude (QĐ-56): client đăng ký động, kết nối theo người dùng, state OAuth.

Revision ID: 0018_connectors
Revises: 0017_ai_session_title
Create Date: 2026-11-25 15:00
"""

from alembic import op

revision = "0018_connectors"
down_revision = "0017_ai_session_title"
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
        """
        CREATE TABLE tab_connector_client (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            issuer text NOT NULL,
            redirect_uri text NOT NULL,
            client_id text NOT NULL,
            client_secret_enc bytea,
            key_version smallint,
            auth_method text NOT NULL,
            registered_at timestamptz NOT NULL,
            CONSTRAINT uq_tab_connector_client_issuer_redirect_uri UNIQUE (issuer, redirect_uri)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tab_connector ({COMMON},
            name text NOT NULL,
            url text NOT NULL,
            auth text NOT NULL CONSTRAINT ck_tab_connector_auth CHECK (auth IN ('oauth','api_key','none')),
            status text NOT NULL DEFAULT 'not_connected' CONSTRAINT ck_tab_connector_status
                CHECK (status IN ('not_connected','connected','reauth_required','error')),
            account_label text,
            last_error text,
            write_tools_enabled text[] NOT NULL DEFAULT '{{}}',
            tools_count integer,
            issuer text,
            as_metadata jsonb NOT NULL DEFAULT '{{}}',
            client_row_id bigint REFERENCES tab_connector_client(id) ON DELETE SET NULL,
            scope text,
            access_token_enc bytea,
            refresh_token_enc bytea,
            api_key_enc bytea,
            key_version smallint,
            access_expires_at timestamptz,
            connected_at timestamptz,
            CONSTRAINT uq_tab_connector_user_id_url UNIQUE (user_id, url)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_connector_user_id ON tab_connector (user_id)")
    op.execute(
        f"""
        CREATE TABLE tab_connector_oauth_state ({COMMON},
            connector_id bigint NOT NULL REFERENCES tab_connector(id) ON DELETE CASCADE,
            state_hash text NOT NULL CONSTRAINT uq_tab_connector_oauth_state_state_hash UNIQUE,
            code_verifier_enc bytea NOT NULL,
            key_version smallint NOT NULL,
            expires_at timestamptz NOT NULL,
            used_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_connector_oauth_state_user_id ON tab_connector_oauth_state (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tab_connector_oauth_state")
    op.execute("DROP TABLE IF EXISTS tab_connector")
    op.execute("DROP TABLE IF EXISTS tab_connector_client")
