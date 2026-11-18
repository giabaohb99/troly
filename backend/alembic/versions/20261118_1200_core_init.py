"""Khởi tạo Phase 1: phần mở rộng, cấu hình tìm kiếm troly_vn, bảng V1.0 và V1.1 (11).

Viết tay vì có cột sinh tsvector, chỉ mục một phần, hàm IMMUTABLE. Downgrade xóa hết dữ liệu.

Revision ID: 0001_core_init
Revises:
Create Date: 2026-11-18 12:00
"""

from alembic import op

revision = "0001_core_init"
down_revision = None
branch_labels = None
depends_on = None

COMMON = """
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES tab_user(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'troly_vn') THEN
            CREATE TEXT SEARCH CONFIGURATION troly_vn (COPY = simple);
            ALTER TEXT SEARCH CONFIGURATION troly_vn
              ALTER MAPPING FOR hword, hword_part, word WITH unaccent, simple;
          END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION troly_join_tags(text[]) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT coalesce(array_to_string($1, ' '), '') $$"
    )

    # ---------- core ----------
    op.execute(
        """
        CREATE TABLE tab_user (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name text NOT NULL,
            email citext NOT NULL CONSTRAINT uq_tab_user_email UNIQUE,
            password_hash text NOT NULL,
            timezone text NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
            last_login_at timestamptz,
            password_changed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tab_auth_session ({COMMON},
            refresh_token_hash text NOT NULL CONSTRAINT uq_tab_auth_session_refresh_token_hash UNIQUE,
            label text,
            last_used_at timestamptz,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_auth_session_user_id ON tab_auth_session (user_id)")
    op.execute(
        f"""
        CREATE TABLE tab_job_queue ({COMMON},
            kind text NOT NULL,
            payload jsonb NOT NULL DEFAULT '{{}}',
            status text NOT NULL DEFAULT 'pending'
                CONSTRAINT ck_tab_job_queue_status CHECK (status IN ('pending','processing','done','failed','cancelled')),
            attempts smallint NOT NULL DEFAULT 0,
            max_attempts smallint NOT NULL DEFAULT 3,
            next_attempt_at timestamptz NOT NULL DEFAULT now(),
            locked_at timestamptz,
            started_at timestamptz,
            finished_at timestamptz,
            result jsonb,
            error text,
            dedupe_key text
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_job_queue_user_id ON tab_job_queue (user_id)")
    op.execute(
        "CREATE INDEX ix_tab_job_queue_pending ON tab_job_queue (status, next_attempt_at) WHERE status = 'pending'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_job_queue_dedupe ON tab_job_queue (user_id, dedupe_key) "
        "WHERE status IN ('pending','processing')"
    )
    op.execute(
        """
        CREATE TABLE tab_job_schedule (
            name text PRIMARY KEY,
            next_run_at timestamptz NOT NULL,
            last_started_at timestamptz,
            last_finished_at timestamptz,
            last_status text CONSTRAINT ck_tab_job_schedule_last_status CHECK (last_status IN ('ok','error','skipped')),
            last_error text,
            last_duration_ms integer,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tab_job_run (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            job_name text NOT NULL,
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            status text NOT NULL CONSTRAINT ck_tab_job_run_status CHECK (status IN ('running','ok','error')),
            items_processed integer NOT NULL DEFAULT 0,
            detail jsonb,
            error text
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_job_run_name_started ON tab_job_run (job_name, started_at DESC)")
    op.execute(
        """
        CREATE TABLE tab_client_log (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id bigint REFERENCES tab_user(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            device_id bigint,
            level text NOT NULL CONSTRAINT ck_tab_client_log_level CHECK (level IN ('error','warn','info')),
            kind text NOT NULL,
            screen text,
            message text NOT NULL,
            detail jsonb,
            app_version text,
            occurred_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_client_log_created ON tab_client_log (created_at)")

    # ---------- setting ----------
    op.execute(
        """
        CREATE TABLE tab_setting (
            user_id bigint NOT NULL REFERENCES tab_user(id) ON DELETE CASCADE,
            key text NOT NULL,
            value jsonb NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_tab_setting PRIMARY KEY (user_id, key)
        )
        """
    )

    # ---------- memory ----------
    op.execute(
        f"""
        CREATE TABLE tab_profile_memory ({COMMON},
            content text NOT NULL DEFAULT '' CONSTRAINT ck_tab_profile_memory_content_len CHECK (char_length(content) <= 8000),
            version integer NOT NULL DEFAULT 1,
            updated_by text NOT NULL DEFAULT 'user'
                CONSTRAINT ck_tab_profile_memory_updated_by CHECK (updated_by IN ('user','ai')),
            CONSTRAINT uq_tab_profile_memory_user_id UNIQUE (user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_profile_memory_user_id ON tab_profile_memory (user_id)")
    op.execute(
        """
        CREATE TABLE tab_profile_memory_revision (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id bigint NOT NULL REFERENCES tab_user(id) ON DELETE CASCADE,
            version integer NOT NULL,
            content text NOT NULL,
            changed_by text NOT NULL CONSTRAINT ck_tab_profile_memory_revision_changed_by CHECK (changed_by IN ('user','ai')),
            reason text,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_tab_profile_memory_revision_user_id_version UNIQUE (user_id, version)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE tab_note ({COMMON},
            title text NOT NULL CONSTRAINT ck_tab_note_title_len CHECK (char_length(title) BETWEEN 1 AND 200),
            body text NOT NULL DEFAULT '' CONSTRAINT ck_tab_note_body_len CHECK (char_length(body) <= 20000),
            tags text[] NOT NULL DEFAULT '{{}}',
            source text NOT NULL DEFAULT 'user' CONSTRAINT ck_tab_note_source CHECK (source IN ('user','ai')),
            deleted_at timestamptz,
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('troly_vn', coalesce(title,'') || ' ' || coalesce(body,'') || ' ' || troly_join_tags(tags))
            ) STORED
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_note_user_id ON tab_note (user_id)")
    op.execute("CREATE INDEX ix_tab_note_search ON tab_note USING gin (search_vector)")
    op.execute("CREATE INDEX ix_tab_note_tags ON tab_note USING gin (tags)")

    # ---------- chat ----------
    op.execute(
        f"""
        CREATE TABLE tab_conversation ({COMMON},
            local_date date NOT NULL,
            started_at timestamptz NOT NULL,
            last_message_at timestamptz,
            summary text,
            summary_upto_id bigint,
            last_prompt_tokens integer,
            compacted_count integer NOT NULL DEFAULT 0,
            day_summary_done boolean NOT NULL DEFAULT false,
            message_count integer NOT NULL DEFAULT 0,
            CONSTRAINT uq_tab_conversation_user_id_local_date UNIQUE (user_id, local_date)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_conversation_user_id ON tab_conversation (user_id)")
    # ---------- ai (bảng của agent AI, cột theo 11 mục 3.7 và bang-viec mục 4) ----------
    op.execute(
        """
        CREATE TABLE tab_ai_run (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id bigint REFERENCES tab_user(id) ON DELETE CASCADE,
            purpose text NOT NULL CONSTRAINT ck_tab_ai_run_purpose CHECK (purpose IN
                ('chat','compaction','bank_extract','file_extract','trip_extract','trip_evaluate','eval')),
            mode text CONSTRAINT ck_tab_ai_run_mode CHECK (mode IN ('chat','think','research','summary')),
            model text NOT NULL,
            effort text,
            conversation_id bigint REFERENCES tab_conversation(id) ON DELETE SET NULL,
            input_tokens integer NOT NULL DEFAULT 0,
            cache_write_5m_tokens integer NOT NULL DEFAULT 0,
            cache_write_1h_tokens integer NOT NULL DEFAULT 0,
            cache_read_tokens integer NOT NULL DEFAULT 0,
            output_tokens integer NOT NULL DEFAULT 0,
            web_search_requests integer NOT NULL DEFAULT 0,
            fallback_used boolean NOT NULL DEFAULT false,
            cost_usd numeric(12,6) NOT NULL,
            rate_card text CONSTRAINT ck_tab_ai_run_rate_card CHECK (rate_card IN ('le_100k','gt_100k')),
            stop_reason text,
            refusal_category text,
            request_id text,
            error_code text,
            latency_ms integer,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_ai_run_user_created ON tab_ai_run (user_id, created_at)")
    op.execute("CREATE INDEX ix_tab_ai_run_created ON tab_ai_run (created_at)")

    op.execute(
        f"""
        CREATE TABLE tab_message ({COMMON},
            conversation_id bigint NOT NULL REFERENCES tab_conversation(id) ON DELETE CASCADE,
            turn_id uuid NOT NULL,
            role text NOT NULL CONSTRAINT ck_tab_message_role CHECK (role IN ('user','assistant','system')),
            content jsonb NOT NULL,
            text text,
            hidden boolean NOT NULL DEFAULT false,
            model text,
            citations jsonb,
            status text NOT NULL DEFAULT 'complete' CONSTRAINT ck_tab_message_status CHECK (status IN ('complete','failed')),
            client_message_id uuid,
            attachment_file_ids bigint[] NOT NULL DEFAULT '{{}}',
            actions jsonb,
            contains_third_party boolean NOT NULL DEFAULT false,
            redacted_at timestamptz,
            ai_run_id bigint REFERENCES tab_ai_run(id) ON DELETE SET NULL,
            input_tokens integer,
            output_tokens integer,
            search_vector tsvector GENERATED ALWAYS AS (to_tsvector('troly_vn', coalesce(text,''))) STORED
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_message_user_id ON tab_message (user_id)")
    op.execute("CREATE INDEX ix_tab_message_conversation ON tab_message (conversation_id, id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_message_client_id ON tab_message (user_id, client_message_id) "
        "WHERE client_message_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_tab_message_search ON tab_message USING gin (search_vector) WHERE hidden = false"
    )
    op.execute(
        "CREATE INDEX ix_tab_message_third_party ON tab_message (created_at) "
        "WHERE contains_third_party AND redacted_at IS NULL"
    )
    op.execute(
        f"""
        CREATE TABLE tab_pending_action ({COMMON},
            conversation_id bigint REFERENCES tab_conversation(id) ON DELETE SET NULL,
            message_id bigint REFERENCES tab_message(id) ON DELETE SET NULL,
            tool_name text NOT NULL,
            input jsonb NOT NULL,
            payload_hash text NOT NULL,
            title text NOT NULL,
            summary text NOT NULL,
            details jsonb NOT NULL DEFAULT '[]',
            danger boolean NOT NULL DEFAULT false,
            status text NOT NULL DEFAULT 'pending'
                CONSTRAINT ck_tab_pending_action_status CHECK (status IN ('pending','done','failed','rejected','expired')),
            expires_at timestamptz NOT NULL,
            decided_at timestamptz,
            result jsonb,
            error text
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_pending_action_user_id ON tab_pending_action (user_id)")
    op.execute(
        "CREATE INDEX ix_tab_pending_action_user_status ON tab_pending_action (user_id, status, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_tab_pending_action_expiring ON tab_pending_action (expires_at) WHERE status = 'pending'"
    )

    # ---------- file ----------
    op.execute(
        f"""
        CREATE TABLE tab_file ({COMMON},
            r2_key text NOT NULL CONSTRAINT uq_tab_file_r2_key UNIQUE,
            original_name text,
            mime text NOT NULL,
            size_bytes bigint NOT NULL CONSTRAINT ck_tab_file_size_positive CHECK (size_bytes > 0),
            sha256 text,
            purpose text NOT NULL CONSTRAINT ck_tab_file_purpose CHECK (purpose IN
                ('chat_attachment','voice','document','trip_source','trip_export','report_export','other')),
            status text NOT NULL DEFAULT 'pending_upload'
                CONSTRAINT ck_tab_file_status CHECK (status IN ('pending_upload','ready','deleted')),
            extract_status text NOT NULL DEFAULT 'none'
                CONSTRAINT ck_tab_file_extract_status CHECK (extract_status IN ('none','pending','done','failed','skipped')),
            drive_file_id text,
            deleted_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_file_user_id ON tab_file (user_id)")
    op.execute(
        "CREATE INDEX ix_tab_file_ready ON tab_file (user_id, purpose, created_at DESC) WHERE status = 'ready'"
    )
    op.execute(
        "CREATE INDEX ix_tab_file_extract_pending ON tab_file (extract_status) WHERE extract_status = 'pending'"
    )
    op.execute(
        """
        CREATE TABLE tab_file_text (
            file_id bigint PRIMARY KEY REFERENCES tab_file(id) ON DELETE CASCADE,
            user_id bigint NOT NULL REFERENCES tab_user(id) ON DELETE CASCADE,
            content text NOT NULL,
            method text NOT NULL CONSTRAINT ck_tab_file_text_method CHECK (method IN ('docx','pdf_text','ai_ocr','plain')),
            page_count integer,
            extracted_at timestamptz NOT NULL,
            search_vector tsvector GENERATED ALWAYS AS (to_tsvector('troly_vn', content)) STORED
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_file_text_user_id ON tab_file_text (user_id)")
    op.execute("CREATE INDEX ix_tab_file_text_search ON tab_file_text USING gin (search_vector)")

    # ---------- device ----------
    op.execute(
        f"""
        CREATE TABLE tab_device ({COMMON},
            name text NOT NULL,
            platform text NOT NULL DEFAULT 'android' CONSTRAINT ck_tab_device_platform CHECK (platform IN ('android')),
            manufacturer text,
            model text,
            os_version text,
            token_hash text NOT NULL CONSTRAINT uq_tab_device_token_hash UNIQUE,
            token_prefix text NOT NULL,
            app_version_code integer,
            app_version_name text,
            default_sms_package text,
            notification_access boolean,
            listener_connected boolean,
            notifications_enabled boolean,
            exact_alarm_allowed boolean,
            battery_optimization_ignored boolean,
            queue_size integer,
            otp_blocked_today integer,
            last_seen_at timestamptz,
            last_event_at timestamptz,
            silent_warned_at timestamptz,
            revoked_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_device_user_id ON tab_device (user_id)")

    # ---------- expense ----------
    op.execute(
        f"""
        CREATE TABLE tab_expense_category ({COMMON},
            name text NOT NULL,
            keywords text[] NOT NULL DEFAULT '{{}}',
            kind text NOT NULL DEFAULT 'expense' CONSTRAINT ck_tab_expense_category_kind CHECK (kind IN ('expense','income')),
            sort_order smallint NOT NULL DEFAULT 0,
            is_archived boolean NOT NULL DEFAULT false
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_expense_category_user_id ON tab_expense_category (user_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_expense_category_name ON tab_expense_category (user_id, lower(name))"
    )
    accounts = "('vcb','tcb','momo','cash','card','other')"
    op.execute(
        f"""
        CREATE TABLE tab_expense ({COMMON},
            amount_vnd bigint NOT NULL CONSTRAINT ck_tab_expense_amount_positive CHECK (amount_vnd > 0),
            kind text NOT NULL CONSTRAINT ck_tab_expense_kind CHECK (kind IN ('expense','income','transfer')),
            account text NOT NULL CONSTRAINT ck_tab_expense_account CHECK (account IN {accounts}),
            account_last4 text CONSTRAINT ck_tab_expense_account_last4 CHECK (account_last4 IS NULL OR account_last4 ~ '^[0-9]{{4}}$'),
            to_account text CONSTRAINT ck_tab_expense_to_account CHECK (to_account IS NULL OR to_account IN {accounts}),
            to_account_last4 text CONSTRAINT ck_tab_expense_to_account_last4
                CHECK (to_account_last4 IS NULL OR to_account_last4 ~ '^[0-9]{{4}}$'),
            category_id bigint REFERENCES tab_expense_category(id) ON DELETE SET NULL,
            merchant text,
            place text,
            note text,
            spent_at timestamptz NOT NULL,
            source text NOT NULL CONSTRAINT ck_tab_expense_source CHECK (source IN ('chat','bank_notification','manual')),
            source_ref text,
            transfer_peer_ref text,
            device_event_id bigint,
            parser text,
            parse_confidence numeric(3,2) CONSTRAINT ck_tab_expense_confidence
                CHECK (parse_confidence IS NULL OR parse_confidence BETWEEN 0 AND 1),
            needs_review boolean NOT NULL DEFAULT false,
            deleted_at timestamptz,
            CONSTRAINT ck_tab_expense_transfer_target CHECK (kind <> 'transfer' OR to_account IS NOT NULL)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_expense_user_id ON tab_expense (user_id)")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_expense_source_ref ON tab_expense (user_id, source_ref) WHERE source_ref IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_expense_peer_ref ON tab_expense (user_id, transfer_peer_ref) "
        "WHERE transfer_peer_ref IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_tab_expense_spent ON tab_expense (user_id, spent_at DESC) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_tab_expense_review ON tab_expense (user_id) WHERE needs_review AND deleted_at IS NULL"
    )


def downgrade() -> None:
    for table in (
        "tab_expense",
        "tab_expense_category",
        "tab_device",
        "tab_file_text",
        "tab_file",
        "tab_pending_action",
        "tab_message",
        "tab_conversation",
        "tab_note",
        "tab_profile_memory_revision",
        "tab_profile_memory",
        "tab_setting",
        "tab_ai_run",
        "tab_client_log",
        "tab_job_run",
        "tab_job_schedule",
        "tab_job_queue",
        "tab_auth_session",
        "tab_user",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS troly_join_tags(text[])")
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS troly_vn")
