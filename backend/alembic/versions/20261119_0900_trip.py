"""Phase 4: lịch trình (11 mục 3.13, 41).

Revision ID: 0005_trip
Revises: 0004_calendar_task
Create Date: 2026-11-19 09:00
"""

from alembic import op

revision = "0005_trip"
down_revision = "0004_calendar_task"
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
        CREATE TABLE tab_trip ({COMMON},
            title text NOT NULL,
            start_date date,
            end_date date,
            nights smallint,
            travel_mode text NOT NULL DEFAULT 'motorbike' CONSTRAINT ck_tab_trip_travel_mode
                CHECK (travel_mode IN ('motorbike','car','walk')),
            origin_text text,
            end_text text,
            status text NOT NULL DEFAULT 'importing' CONSTRAINT ck_tab_trip_status
                CHECK (status IN ('importing','draft','evaluating','planned','done','failed')),
            source_kind text CONSTRAINT ck_tab_trip_source_kind
                CHECK (source_kind IN ('docx','pdf','image','text','link')),
            source_file_id bigint REFERENCES tab_file(id) ON DELETE SET NULL,
            source_text text,
            extract_json jsonb,
            notes jsonb NOT NULL DEFAULT '[]',
            hotels jsonb NOT NULL DEFAULT '[]',
            evaluation jsonb,
            chosen_option_id bigint,
            export_file_id bigint REFERENCES tab_file(id) ON DELETE SET NULL,
            error text,
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('troly_vn', coalesce(title,'') || ' ' || coalesce(origin_text,'') || ' '
                    || coalesce(end_text,''))
            ) STORED,
            CONSTRAINT ck_tab_trip_dates CHECK (end_date >= start_date)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_trip_user_id ON tab_trip (user_id)")
    op.execute("CREATE INDEX ix_tab_trip_user_start ON tab_trip (user_id, start_date DESC)")
    op.execute("CREATE INDEX ix_tab_trip_search ON tab_trip USING gin (search_vector)")
    op.execute(
        f"""
        CREATE TABLE tab_trip_stop ({COMMON},
            trip_id bigint NOT NULL REFERENCES tab_trip(id) ON DELETE CASCADE,
            day_no smallint NOT NULL CONSTRAINT ck_tab_trip_stop_day_no CHECK (day_no >= 1),
            seq smallint NOT NULL,
            title text NOT NULL,
            category text NOT NULL DEFAULT 'khac' CONSTRAINT ck_tab_trip_stop_category
                CHECK (category IN ('an_uong','nghi','tham_quan','pha','di_chuyen','khach_san','mua_sam','khac')),
            role text NOT NULL DEFAULT 'main' CONSTRAINT ck_tab_trip_stop_role
                CHECK (role IN ('main','alternative','backup','generic','via')),
            parent_stop_id bigint REFERENCES tab_trip_stop(id) ON DELETE CASCADE,
            time_text text,
            planned_start timestamptz,
            planned_end timestamptz,
            approx boolean NOT NULL DEFAULT false,
            fixed boolean NOT NULL DEFAULT false,
            optional boolean NOT NULL DEFAULT false,
            stay_minutes smallint,
            place_query text,
            source_url text,
            place_id text,
            lat numeric(9,6),
            lng numeric(9,6),
            coord_source text CONSTRAINT ck_tab_trip_stop_coord_source CHECK (coord_source IN ('user','google')),
            coord_fetched_at timestamptz,
            resolve_status text NOT NULL DEFAULT 'uncertain' CONSTRAINT ck_tab_trip_stop_resolve_status
                CHECK (resolve_status IN ('ok','uncertain','not_found','manual')),
            phone text,
            cost_note text,
            note text,
            alternatives jsonb NOT NULL DEFAULT '[]',
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('troly_vn', coalesce(title,'') || ' ' || coalesce(place_query,'') || ' '
                    || coalesce(note,''))
            ) STORED,
            CONSTRAINT uq_tab_trip_stop_trip_id_day_no_seq UNIQUE (trip_id, day_no, seq)
                DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_trip_stop_user_id ON tab_trip_stop (user_id)")
    op.execute("CREATE INDEX ix_tab_trip_stop_trip ON tab_trip_stop (trip_id, day_no, seq)")
    op.execute("CREATE INDEX ix_tab_trip_stop_search ON tab_trip_stop USING gin (search_vector)")
    op.execute(
        f"""
        CREATE TABLE tab_trip_option ({COMMON},
            trip_id bigint NOT NULL REFERENCES tab_trip(id) ON DELETE CASCADE,
            name text NOT NULL,
            summary text,
            plan jsonb NOT NULL,
            total_km numeric(7,1),
            total_ride_minutes integer,
            night_ride_minutes integer,
            red_count smallint NOT NULL DEFAULT 0,
            yellow_count smallint NOT NULL DEFAULT 0,
            risks jsonb NOT NULL DEFAULT '[]',
            changes jsonb NOT NULL DEFAULT '[]',
            chosen boolean NOT NULL DEFAULT false,
            evaluated_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_trip_option_user_id ON tab_trip_option (user_id)")
    op.execute("CREATE INDEX ix_tab_trip_option_trip ON tab_trip_option (trip_id)")
    op.execute(
        "ALTER TABLE tab_trip ADD CONSTRAINT fk_tab_trip_chosen_option_id "
        "FOREIGN KEY (chosen_option_id) REFERENCES tab_trip_option(id) ON DELETE SET NULL"
    )
    op.execute(
        f"""
        CREATE TABLE tab_trip_fact ({COMMON},
            trip_id bigint NOT NULL REFERENCES tab_trip(id) ON DELETE CASCADE,
            kind text NOT NULL CONSTRAINT ck_tab_trip_fact_kind
                CHECK (kind IN ('ferry_last','ferry_first','checkin','checkout','hotline','opening_hours','other')),
            stop_id bigint REFERENCES tab_trip_stop(id) ON DELETE SET NULL,
            day_no smallint,
            value_time time,
            value_text text,
            text text NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_trip_fact_user_id ON tab_trip_fact (user_id)")
    op.execute("CREATE INDEX ix_tab_trip_fact_trip ON tab_trip_fact (trip_id)")
    op.execute(
        """
        CREATE TABLE tab_place_cache (
            query_norm text NOT NULL,
            bias_key text NOT NULL,
            place_id text,
            lat numeric(9,6),
            lng numeric(9,6),
            formatted_address text,
            fetched_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_tab_place_cache PRIMARY KEY (query_norm, bias_key)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_place_cache_place_id ON tab_place_cache (place_id)")
    op.execute(
        "CREATE INDEX ix_tab_place_cache_fetched_at ON tab_place_cache (fetched_at) WHERE lat IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE tab_route_cache (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            origin_key text NOT NULL,
            destination_key text NOT NULL,
            travel_mode text NOT NULL CONSTRAINT ck_tab_route_cache_travel_mode
                CHECK (travel_mode IN ('two_wheeler','drive','walk')),
            avoid_highways boolean NOT NULL,
            distance_m integer NOT NULL,
            duration_s integer NOT NULL,
            fetched_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            CONSTRAINT uq_tab_route_cache_key
                UNIQUE (origin_key, destination_key, travel_mode, avoid_highways)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_route_cache_expires_at ON tab_route_cache (expires_at)")


def downgrade() -> None:
    op.execute("ALTER TABLE tab_trip DROP CONSTRAINT IF EXISTS fk_tab_trip_chosen_option_id")
    for table in (
        "tab_route_cache",
        "tab_place_cache",
        "tab_trip_fact",
        "tab_trip_option",
        "tab_trip_stop",
        "tab_trip",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
