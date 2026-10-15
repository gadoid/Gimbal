-- 增量升级门快照(整体评审 2026-10-15):交付点 41a8b5af(alembic 0023_ext_schema_json)
-- 的 schema-only 转储 + alembic_version 行。由该提交自身的代码与依赖建库后
-- pg_dump --schema-only --no-owner --no-privileges 生成;门用 psql 恢复后
-- 以当前迁移链 upgrade head 再与当前模型比对 —— 不再执行历史代码
-- (历史代码依赖已下架的 passlib/python-jose,直接复跑会 ImportError)。
-- 随发版推进:交付后用 dev 库或交付点重建库重新转储替换本文件。

--
-- PostgreSQL database dump
--


-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activity_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_events (
    id bigint NOT NULL,
    actor_id integer,
    kind character varying(64) NOT NULL,
    resource_type character varying(32) NOT NULL,
    resource_id character varying(128) NOT NULL,
    detail jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: activity_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_events_id_seq OWNED BY public.activity_events.id;


--
-- Name: adaptation_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adaptation_batches (
    batch_id character varying(64) NOT NULL,
    kind character varying(16) NOT NULL,
    from_revisions jsonb,
    to_revision character varying(64),
    scope jsonb,
    save_mode character varying(16),
    endpoint_id character varying(255) NOT NULL,
    from_version character varying(64) NOT NULL,
    to_version character varying(64) NOT NULL,
    status character varying(16) NOT NULL,
    operator_id integer,
    operator_name character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone
);


--
-- Name: adaptation_ops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adaptation_ops (
    id integer NOT NULL,
    batch_id character varying(64) NOT NULL,
    scenario_id character varying(128),
    dataset_id character varying(128),
    op_type character varying(32) NOT NULL,
    payload jsonb NOT NULL,
    status character varying(16) NOT NULL,
    applied_at timestamp with time zone,
    note text
);


--
-- Name: adaptation_ops_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.adaptation_ops_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: adaptation_ops_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.adaptation_ops_id_seq OWNED BY public.adaptation_ops.id;


--
-- Name: adaptation_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adaptation_snapshots (
    id integer NOT NULL,
    batch_id character varying(64) NOT NULL,
    entity_type character varying(16) NOT NULL,
    entity_id character varying(128) NOT NULL,
    before_json jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: adaptation_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.adaptation_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: adaptation_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.adaptation_snapshots_id_seq OWNED BY public.adaptation_snapshots.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id bigint NOT NULL,
    actor_id integer,
    actor_name character varying(128) NOT NULL,
    action character varying(64) NOT NULL,
    resource_type character varying(32),
    resource_id character varying(128),
    detail jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: auth_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_sessions (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    alias character varying(64) NOT NULL,
    url text NOT NULL,
    username_enc text NOT NULL,
    password_enc text NOT NULL,
    token_type character varying(32) NOT NULL,
    expires_in integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: auth_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_sessions_id_seq OWNED BY public.auth_sessions.id;


--
-- Name: board_cards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.board_cards (
    id integer NOT NULL,
    subject_kind character varying(32) NOT NULL,
    subject_id character varying(255) NOT NULL,
    body text NOT NULL,
    is_root boolean NOT NULL,
    quadrant character varying(16) NOT NULL,
    annotates_node_id character varying(255),
    author_id integer,
    author_name character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: board_cards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.board_cards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: board_cards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.board_cards_id_seq OWNED BY public.board_cards.id;


--
-- Name: carry_global_defaults; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.carry_global_defaults (
    id integer NOT NULL,
    field_path character varying(255) NOT NULL,
    value text,
    updated_by_id integer,
    updated_by_name character varying(128) NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: carry_global_defaults_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.carry_global_defaults_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: carry_global_defaults_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.carry_global_defaults_id_seq OWNED BY public.carry_global_defaults.id;


--
-- Name: carry_service_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.carry_service_bindings (
    id integer NOT NULL,
    service_name character varying(128) NOT NULL,
    field_path character varying(255) NOT NULL,
    value text,
    updated_by_id integer,
    updated_by_name character varying(128) NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: carry_service_bindings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.carry_service_bindings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: carry_service_bindings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.carry_service_bindings_id_seq OWNED BY public.carry_service_bindings.id;


--
-- Name: composer_data_sets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.composer_data_sets (
    id integer NOT NULL,
    dataset_id character varying(128) NOT NULL,
    scenario_id character varying(128) NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    rows jsonb NOT NULL,
    row_count integer GENERATED ALWAYS AS (
CASE
    WHEN (jsonb_typeof(rows) = 'array'::text) THEN jsonb_array_length(rows)
    ELSE 0
END) STORED NOT NULL,
    var_unlocks jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: composer_data_sets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.composer_data_sets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: composer_data_sets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.composer_data_sets_id_seq OWNED BY public.composer_data_sets.id;


--
-- Name: composer_run_schemes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.composer_run_schemes (
    id integer NOT NULL,
    scheme_id character varying(128) NOT NULL,
    scenario_id character varying(128) NOT NULL,
    name character varying(64) NOT NULL,
    is_default boolean NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: composer_run_schemes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.composer_run_schemes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: composer_run_schemes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.composer_run_schemes_id_seq OWNED BY public.composer_run_schemes.id;


--
-- Name: composer_scenarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.composer_scenarios (
    id integer NOT NULL,
    scenario_id character varying(128) NOT NULL,
    owner_name character varying(128) NOT NULL,
    owner_id integer,
    visibility character varying(16) NOT NULL,
    forked_from_id character varying(128),
    forked_from_owner_name character varying(128),
    forked_from_at timestamp with time zone,
    payload jsonb NOT NULL,
    name character varying(64) GENERATED ALWAYS AS ((((payload -> 'definition'::text) -> 'meta'::text) ->> 'name'::text)) STORED,
    description text GENERATED ALWAYS AS ((((payload -> 'definition'::text) -> 'meta'::text) ->> 'description'::text)) STORED,
    module character varying(64) GENERATED ALWAYS AS ((((payload -> 'definition'::text) -> 'meta'::text) ->> 'module'::text)) STORED,
    author character varying(128) GENERATED ALWAYS AS ((((payload -> 'definition'::text) -> 'meta'::text) ->> 'author'::text)) STORED,
    priority smallint GENERATED ALWAYS AS (((((payload -> 'definition'::text) -> 'meta'::text) ->> 'priority'::text))::integer) STORED,
    system jsonb GENERATED ALWAYS AS ((((payload -> 'definition'::text) -> 'meta'::text) -> 'system'::text)) STORED,
    tags jsonb GENERATED ALWAYS AS ((((payload -> 'definition'::text) -> 'meta'::text) -> 'tags'::text)) STORED,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: composer_scenarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.composer_scenarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: composer_scenarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.composer_scenarios_id_seq OWNED BY public.composer_scenarios.id;


--
-- Name: constant_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.constant_entries (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    name character varying(64) NOT NULL,
    description character varying(256) NOT NULL,
    entry_kind character varying(16) NOT NULL,
    value jsonb,
    spec jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: constant_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.constant_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: constant_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.constant_entries_id_seq OWNED BY public.constant_entries.id;


--
-- Name: environments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.environments (
    id integer NOT NULL,
    name character varying(64) NOT NULL,
    description character varying(256) NOT NULL,
    owner_id integer,
    visibility character varying(16) NOT NULL,
    lines jsonb NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: environments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.environments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: environments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.environments_id_seq OWNED BY public.environments.id;


--
-- Name: execution_event_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_event_evidence (
    execution_id integer NOT NULL,
    seq integer NOT NULL,
    evidence jsonb NOT NULL
);


--
-- Name: execution_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_events (
    id integer NOT NULL,
    execution_id integer NOT NULL,
    seq integer NOT NULL,
    ts timestamp with time zone NOT NULL,
    kind character varying(8) NOT NULL,
    level character varying(16),
    category character varying(24),
    module character varying(128),
    service character varying(128),
    protocol character varying(64),
    endpoint character varying(128),
    unit character varying(255),
    attempt character varying(16),
    step character varying(64),
    event_type character varying(64),
    message text,
    payload jsonb NOT NULL
);


--
-- Name: execution_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.execution_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: execution_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.execution_events_id_seq OWNED BY public.execution_events.id;


--
-- Name: execution_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_jobs (
    id integer NOT NULL,
    execution_id integer NOT NULL,
    status character varying(16) NOT NULL,
    kind character varying(16) NOT NULL,
    payload jsonb NOT NULL,
    claimed_by character varying(64),
    claimed_at timestamp with time zone,
    heartbeat_at timestamp with time zone,
    attempts integer NOT NULL,
    cancel_requested boolean NOT NULL,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: execution_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.execution_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: execution_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.execution_jobs_id_seq OWNED BY public.execution_jobs.id;


--
-- Name: execution_rows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_rows (
    id integer NOT NULL,
    execution_id integer NOT NULL,
    seq integer NOT NULL,
    unit_id character varying(255) NOT NULL,
    branch character varying(16) NOT NULL,
    attempts integer NOT NULL,
    dataset_id character varying(128),
    injection_id character varying(128),
    row_index integer NOT NULL,
    rep integer NOT NULL,
    status character varying(24) NOT NULL,
    case_dir character varying(255) NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone
);


--
-- Name: execution_rows_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.execution_rows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: execution_rows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.execution_rows_id_seq OWNED BY public.execution_rows.id;


--
-- Name: execution_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.execution_snapshots (
    execution_id integer NOT NULL,
    snapshot jsonb NOT NULL
);


--
-- Name: executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.executions (
    plate_pins jsonb,
    m2_hash character varying(64),
    baseline_eligible boolean DEFAULT false NOT NULL,
    baseline_block character varying(16),
    baseline_evidence jsonb,
    id integer NOT NULL,
    scenario_id character varying(128) NOT NULL,
    scenario_name character varying(255) NOT NULL,
    kind character varying(32) NOT NULL,
    suite_id integer,
    owner_id integer,
    owner_name character varying(128) NOT NULL,
    status character varying(16) NOT NULL,
    batch_id character varying(64),
    total_runs integer NOT NULL,
    passed integer NOT NULL,
    failed integer NOT NULL,
    skipped integer NOT NULL,
    config_json jsonb NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: executions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.executions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: executions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.executions_id_seq OWNED BY public.executions.id;


--
-- Name: external_endpoints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.external_endpoints (
    id integer NOT NULL,
    alias_name character varying(128) NOT NULL,
    name character varying(128) NOT NULL,
    title character varying(256) NOT NULL,
    method character varying(8) NOT NULL,
    path character varying(512) NOT NULL,
    request_schema json,
    auth character varying(16) DEFAULT 'none'::character varying NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: external_endpoints_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.external_endpoints_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: external_endpoints_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.external_endpoints_id_seq OWNED BY public.external_endpoints.id;


--
-- Name: integration_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.integration_tasks (
    id integer NOT NULL,
    name character varying(128) NOT NULL,
    owner_id integer NOT NULL,
    visibility character varying(16) NOT NULL,
    identity_mode character varying(16) NOT NULL,
    target_type character varying(16) NOT NULL,
    scenario_id character varying(128),
    suite_id integer,
    scheme_id character varying(128),
    target_system character varying(64) NOT NULL,
    trigger_cron character varying(64) NOT NULL,
    result_policy character varying(16) NOT NULL,
    card_template character varying(16) NOT NULL,
    output_mapping jsonb NOT NULL,
    state_mapping jsonb NOT NULL,
    updated_by integer,
    removed_at timestamp with time zone,
    template_id integer,
    holder_id integer,
    enabled boolean NOT NULL,
    next_run_at timestamp with time zone,
    state character varying(16) NOT NULL,
    paused_reason character varying(32) NOT NULL,
    running_since timestamp with time zone,
    last_run_at timestamp with time zone,
    last_status character varying(16) NOT NULL,
    last_error text NOT NULL,
    last_outputs jsonb NOT NULL,
    state_vars jsonb NOT NULL,
    last_manual_run_at timestamp with time zone,
    fail_streak integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: integration_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.integration_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: integration_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.integration_tasks_id_seq OWNED BY public.integration_tasks.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    type character varying(32) NOT NULL,
    title character varying(255) NOT NULL,
    body text NOT NULL,
    link character varying(255),
    batch_id character varying(64),
    resource_type character varying(32),
    resource_id character varying(128),
    payload jsonb,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    read_at timestamp with time zone
);


--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: report_definitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_definitions (
    id integer NOT NULL,
    name character varying(128) NOT NULL,
    description text NOT NULL,
    definition jsonb NOT NULL,
    owner_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: report_definitions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.report_definitions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: report_definitions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.report_definitions_id_seq OWNED BY public.report_definitions.id;


--
-- Name: scenario_endpoint_refs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scenario_endpoint_refs (
    scenario_id character varying(128) NOT NULL,
    step_index integer NOT NULL,
    source character varying(16) NOT NULL,
    field_name character varying(255) NOT NULL,
    endpoint_id character varying(255) NOT NULL,
    via_var text,
    via_vars jsonb
);


--
-- Name: service_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_aliases (
    alias_name character varying(128) NOT NULL,
    base_service character varying(128) NOT NULL,
    base_url character varying(512),
    environment_id integer,
    credential_alias character varying(64),
    kind character varying(16) DEFAULT 'plate'::character varying NOT NULL,
    owner_user_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: share_refs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.share_refs (
    id integer NOT NULL,
    grantee_user_id integer NOT NULL,
    scenario_id character varying(128),
    suite_id integer,
    granted_by_name character varying(128) NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_share_refs_exactly_one CHECK (((scenario_id IS NULL) <> (suite_id IS NULL)))
);


--
-- Name: share_refs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.share_refs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: share_refs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.share_refs_id_seq OWNED BY public.share_refs.id;


--
-- Name: suite_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suite_members (
    suite_id integer NOT NULL,
    scenario_id character varying(128) NOT NULL,
    owner_id integer NOT NULL,
    role character varying(16) NOT NULL,
    sort integer NOT NULL,
    added_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: suites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suites (
    id integer NOT NULL,
    name character varying(128) NOT NULL,
    description character varying(512) NOT NULL,
    owner_id integer NOT NULL,
    visibility character varying(16) NOT NULL,
    mode character varying(32) NOT NULL,
    mode_config jsonb NOT NULL,
    rev integer NOT NULL,
    forked_from_id integer,
    forked_from_owner_name character varying(128),
    forked_from_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: suites_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.suites_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: suites_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.suites_id_seq OWNED BY public.suites.id;


--
-- Name: user_prefs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_prefs (
    user_id integer NOT NULL,
    key character varying(64) NOT NULL,
    value jsonb NOT NULL
);


--
-- Name: user_stars; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_stars (
    user_id integer NOT NULL,
    scenario_id character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(64) NOT NULL,
    display_name character varying(128) NOT NULL,
    password_hash text NOT NULL,
    role character varying(16) DEFAULT 'member'::character varying NOT NULL,
    is_active boolean NOT NULL,
    is_system boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: v_scenarios_readable; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_scenarios_readable WITH (security_invoker='true') AS
 SELECT id,
    scenario_id,
    owner_name,
    owner_id,
    visibility,
    forked_from_id,
    forked_from_owner_name,
    forked_from_at,
    payload,
    name,
    description,
    module,
    author,
    priority,
    system,
    tags,
    created_at,
    updated_at
   FROM public.composer_scenarios c
  WHERE (((visibility)::text = 'public'::text) OR (owner_id = (NULLIF(current_setting('app.uid'::text, true), ''::text))::integer) OR (current_setting('app.role'::text, true) = 'admin'::text) OR (EXISTS ( SELECT 1
           FROM public.share_refs r
          WHERE (((r.scenario_id)::text = (c.scenario_id)::text) AND (r.grantee_user_id = (NULLIF(current_setting('app.uid'::text, true), ''::text))::integer)))) OR (EXISTS ( SELECT 1
           FROM (public.share_refs r
             JOIN public.suite_members m ON ((m.suite_id = r.suite_id)))
          WHERE (((m.scenario_id)::text = (c.scenario_id)::text) AND (r.grantee_user_id = (NULLIF(current_setting('app.uid'::text, true), ''::text))::integer)))));


--
-- Name: activity_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_events ALTER COLUMN id SET DEFAULT nextval('public.activity_events_id_seq'::regclass);


--
-- Name: adaptation_ops id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adaptation_ops ALTER COLUMN id SET DEFAULT nextval('public.adaptation_ops_id_seq'::regclass);


--
-- Name: adaptation_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adaptation_snapshots ALTER COLUMN id SET DEFAULT nextval('public.adaptation_snapshots_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: auth_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_sessions ALTER COLUMN id SET DEFAULT nextval('public.auth_sessions_id_seq'::regclass);


--
-- Name: board_cards id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.board_cards ALTER COLUMN id SET DEFAULT nextval('public.board_cards_id_seq'::regclass);


--
-- Name: carry_global_defaults id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_global_defaults ALTER COLUMN id SET DEFAULT nextval('public.carry_global_defaults_id_seq'::regclass);


--
-- Name: carry_service_bindings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_service_bindings ALTER COLUMN id SET DEFAULT nextval('public.carry_service_bindings_id_seq'::regclass);


--
-- Name: composer_data_sets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_data_sets ALTER COLUMN id SET DEFAULT nextval('public.composer_data_sets_id_seq'::regclass);


--
-- Name: composer_run_schemes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_run_schemes ALTER COLUMN id SET DEFAULT nextval('public.composer_run_schemes_id_seq'::regclass);


--
-- Name: composer_scenarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_scenarios ALTER COLUMN id SET DEFAULT nextval('public.composer_scenarios_id_seq'::regclass);


--
-- Name: constant_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.constant_entries ALTER COLUMN id SET DEFAULT nextval('public.constant_entries_id_seq'::regclass);


--
-- Name: environments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environments ALTER COLUMN id SET DEFAULT nextval('public.environments_id_seq'::regclass);


--
-- Name: execution_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_events ALTER COLUMN id SET DEFAULT nextval('public.execution_events_id_seq'::regclass);


--
-- Name: execution_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_jobs ALTER COLUMN id SET DEFAULT nextval('public.execution_jobs_id_seq'::regclass);


--
-- Name: execution_rows id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_rows ALTER COLUMN id SET DEFAULT nextval('public.execution_rows_id_seq'::regclass);


--
-- Name: executions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.executions ALTER COLUMN id SET DEFAULT nextval('public.executions_id_seq'::regclass);


--
-- Name: external_endpoints id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_endpoints ALTER COLUMN id SET DEFAULT nextval('public.external_endpoints_id_seq'::regclass);


--
-- Name: integration_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_tasks ALTER COLUMN id SET DEFAULT nextval('public.integration_tasks_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: report_definitions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_definitions ALTER COLUMN id SET DEFAULT nextval('public.report_definitions_id_seq'::regclass);


--
-- Name: share_refs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.share_refs ALTER COLUMN id SET DEFAULT nextval('public.share_refs_id_seq'::regclass);


--
-- Name: suites id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suites ALTER COLUMN id SET DEFAULT nextval('public.suites_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: activity_events activity_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_events
    ADD CONSTRAINT activity_events_pkey PRIMARY KEY (id);


--
-- Name: adaptation_batches adaptation_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adaptation_batches
    ADD CONSTRAINT adaptation_batches_pkey PRIMARY KEY (batch_id);


--
-- Name: adaptation_ops adaptation_ops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adaptation_ops
    ADD CONSTRAINT adaptation_ops_pkey PRIMARY KEY (id);


--
-- Name: adaptation_snapshots adaptation_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adaptation_snapshots
    ADD CONSTRAINT adaptation_snapshots_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: auth_sessions auth_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_sessions
    ADD CONSTRAINT auth_sessions_pkey PRIMARY KEY (id);


--
-- Name: board_cards board_cards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.board_cards
    ADD CONSTRAINT board_cards_pkey PRIMARY KEY (id);


--
-- Name: carry_global_defaults carry_global_defaults_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_global_defaults
    ADD CONSTRAINT carry_global_defaults_pkey PRIMARY KEY (id);


--
-- Name: carry_service_bindings carry_service_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_service_bindings
    ADD CONSTRAINT carry_service_bindings_pkey PRIMARY KEY (id);


--
-- Name: composer_data_sets composer_data_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_data_sets
    ADD CONSTRAINT composer_data_sets_pkey PRIMARY KEY (id);


--
-- Name: composer_run_schemes composer_run_schemes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_run_schemes
    ADD CONSTRAINT composer_run_schemes_pkey PRIMARY KEY (id);


--
-- Name: composer_scenarios composer_scenarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_scenarios
    ADD CONSTRAINT composer_scenarios_pkey PRIMARY KEY (id);


--
-- Name: constant_entries constant_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.constant_entries
    ADD CONSTRAINT constant_entries_pkey PRIMARY KEY (id);


--
-- Name: environments environments_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environments
    ADD CONSTRAINT environments_name_key UNIQUE (name);


--
-- Name: environments environments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environments
    ADD CONSTRAINT environments_pkey PRIMARY KEY (id);


--
-- Name: execution_event_evidence execution_event_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_event_evidence
    ADD CONSTRAINT execution_event_evidence_pkey PRIMARY KEY (execution_id, seq);


--
-- Name: execution_events execution_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_events
    ADD CONSTRAINT execution_events_pkey PRIMARY KEY (id);


--
-- Name: execution_jobs execution_jobs_execution_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_jobs
    ADD CONSTRAINT execution_jobs_execution_id_key UNIQUE (execution_id);


--
-- Name: execution_jobs execution_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_jobs
    ADD CONSTRAINT execution_jobs_pkey PRIMARY KEY (id);


--
-- Name: execution_rows execution_rows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_rows
    ADD CONSTRAINT execution_rows_pkey PRIMARY KEY (id);


--
-- Name: execution_snapshots execution_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_snapshots
    ADD CONSTRAINT execution_snapshots_pkey PRIMARY KEY (execution_id);


--
-- Name: executions executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.executions
    ADD CONSTRAINT executions_pkey PRIMARY KEY (id);


--
-- Name: external_endpoints external_endpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_endpoints
    ADD CONSTRAINT external_endpoints_pkey PRIMARY KEY (id);


--
-- Name: integration_tasks integration_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_tasks
    ADD CONSTRAINT integration_tasks_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: report_definitions report_definitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_definitions
    ADD CONSTRAINT report_definitions_pkey PRIMARY KEY (id);


--
-- Name: scenario_endpoint_refs scenario_endpoint_refs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scenario_endpoint_refs
    ADD CONSTRAINT scenario_endpoint_refs_pkey PRIMARY KEY (scenario_id, step_index, source, field_name);


--
-- Name: service_aliases service_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_aliases
    ADD CONSTRAINT service_aliases_pkey PRIMARY KEY (alias_name);


--
-- Name: share_refs share_refs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.share_refs
    ADD CONSTRAINT share_refs_pkey PRIMARY KEY (id);


--
-- Name: suite_members suite_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suite_members
    ADD CONSTRAINT suite_members_pkey PRIMARY KEY (suite_id, scenario_id);


--
-- Name: suites suites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suites
    ADD CONSTRAINT suites_pkey PRIMARY KEY (id);


--
-- Name: auth_sessions uq_auth_owner_alias; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_sessions
    ADD CONSTRAINT uq_auth_owner_alias UNIQUE (owner_id, alias);


--
-- Name: carry_global_defaults uq_carry_default_path; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_global_defaults
    ADD CONSTRAINT uq_carry_default_path UNIQUE (field_path);


--
-- Name: carry_service_bindings uq_carry_svc_path; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_service_bindings
    ADD CONSTRAINT uq_carry_svc_path UNIQUE (service_name, field_path);


--
-- Name: constant_entries uq_constant_owner_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.constant_entries
    ADD CONSTRAINT uq_constant_owner_name UNIQUE (owner_id, name);


--
-- Name: external_endpoints uq_external_endpoint; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_endpoints
    ADD CONSTRAINT uq_external_endpoint UNIQUE (alias_name, name);


--
-- Name: share_refs uq_share_refs_user_scenario; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.share_refs
    ADD CONSTRAINT uq_share_refs_user_scenario UNIQUE (grantee_user_id, scenario_id);


--
-- Name: share_refs uq_share_refs_user_suite; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.share_refs
    ADD CONSTRAINT uq_share_refs_user_suite UNIQUE (grantee_user_id, suite_id);


--
-- Name: user_prefs user_prefs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_prefs
    ADD CONSTRAINT user_prefs_pkey PRIMARY KEY (user_id, key);


--
-- Name: user_stars user_stars_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_stars
    ADD CONSTRAINT user_stars_pkey PRIMARY KEY (user_id, scenario_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_activity_events_actor_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_activity_events_actor_created ON public.activity_events USING btree (actor_id, created_at);


--
-- Name: ix_activity_events_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_activity_events_resource ON public.activity_events USING btree (resource_type, resource_id);


--
-- Name: ix_aop_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aop_batch ON public.adaptation_ops USING btree (batch_id);


--
-- Name: ix_audit_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_action ON public.audit_logs USING btree (action, created_at);


--
-- Name: ix_audit_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_created ON public.audit_logs USING btree (created_at);


--
-- Name: ix_auth_sessions_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auth_sessions_owner_id ON public.auth_sessions USING btree (owner_id);


--
-- Name: ix_board_cards_author_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_board_cards_author_id ON public.board_cards USING btree (author_id);


--
-- Name: ix_board_cards_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_board_cards_subject ON public.board_cards USING btree (subject_kind, subject_id);


--
-- Name: ix_composer_data_sets_dataset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_composer_data_sets_dataset_id ON public.composer_data_sets USING btree (dataset_id);


--
-- Name: ix_composer_data_sets_scenario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_data_sets_scenario_id ON public.composer_data_sets USING btree (scenario_id);


--
-- Name: ix_composer_description_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_description_trgm ON public.composer_scenarios USING gin (description public.gin_trgm_ops);


--
-- Name: ix_composer_name_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_name_trgm ON public.composer_scenarios USING gin (name public.gin_trgm_ops);


--
-- Name: ix_composer_run_schemes_scheme_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_composer_run_schemes_scheme_id ON public.composer_run_schemes USING btree (scheme_id);


--
-- Name: ix_composer_scenarios_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_scenarios_owner_id ON public.composer_scenarios USING btree (owner_id);


--
-- Name: ix_composer_scenarios_scenario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_composer_scenarios_scenario_id ON public.composer_scenarios USING btree (scenario_id);


--
-- Name: ix_composer_sid_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_sid_trgm ON public.composer_scenarios USING gin (scenario_id public.gin_trgm_ops);


--
-- Name: ix_composer_system_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_system_gin ON public.composer_scenarios USING gin (system jsonb_path_ops);


--
-- Name: ix_composer_tags_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_tags_gin ON public.composer_scenarios USING gin (tags jsonb_path_ops);


--
-- Name: ix_composer_vis_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_composer_vis_updated ON public.composer_scenarios USING btree (visibility, updated_at);


--
-- Name: ix_constant_entries_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_constant_entries_owner_id ON public.constant_entries USING btree (owner_id);


--
-- Name: ix_execution_events_labels; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_execution_events_labels ON public.execution_events USING btree (execution_id, category, unit);


--
-- Name: ix_execution_events_ts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_execution_events_ts ON public.execution_events USING btree (ts);


--
-- Name: ix_execution_events_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_execution_events_type ON public.execution_events USING btree (execution_id, event_type);


--
-- Name: ix_execution_jobs_status_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_execution_jobs_status_id ON public.execution_jobs USING btree (status, id);


--
-- Name: ix_executions_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_executions_batch_id ON public.executions USING btree (batch_id);


--
-- Name: ix_executions_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_executions_owner_id ON public.executions USING btree (owner_id, id);


--
-- Name: ix_executions_scenario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_executions_scenario_id ON public.executions USING btree (scenario_id);


--
-- Name: ix_executions_suite; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_executions_suite ON public.executions USING btree (suite_id);


--
-- Name: ix_external_endpoint_alias; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_external_endpoint_alias ON public.external_endpoints USING btree (alias_name);


--
-- Name: ix_integration_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integration_due ON public.integration_tasks USING btree (state, enabled, next_run_at);


--
-- Name: ix_notifications_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user ON public.notifications USING btree (user_id, id);


--
-- Name: ix_report_definitions_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_definitions_owner ON public.report_definitions USING btree (owner_id);


--
-- Name: ix_report_definitions_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_definitions_owner_id ON public.report_definitions USING btree (owner_id);


--
-- Name: ix_ser_endpoint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ser_endpoint ON public.scenario_endpoint_refs USING btree (endpoint_id);


--
-- Name: ix_service_alias_base; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_service_alias_base ON public.service_aliases USING btree (base_service);


--
-- Name: ix_service_aliases_owner_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_service_aliases_owner_user_id ON public.service_aliases USING btree (owner_user_id);


--
-- Name: ix_share_refs_grantee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_share_refs_grantee ON public.share_refs USING btree (grantee_user_id);


--
-- Name: ix_share_refs_scenario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_share_refs_scenario ON public.share_refs USING btree (scenario_id);


--
-- Name: ix_share_refs_suite; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_share_refs_suite ON public.share_refs USING btree (suite_id);


--
-- Name: ix_snap_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_snap_batch ON public.adaptation_snapshots USING btree (batch_id);


--
-- Name: ix_suite_members_scenario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_suite_members_scenario ON public.suite_members USING btree (scenario_id);


--
-- Name: ix_suites_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_suites_owner_id ON public.suites USING btree (owner_id);


--
-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_role ON public.users USING btree (role);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: uq_board_cards_root; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_board_cards_root ON public.board_cards USING btree (subject_kind, subject_id) WHERE (is_root IS TRUE);


--
-- Name: uq_composer_sid_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_composer_sid_owner ON public.composer_scenarios USING btree (scenario_id, owner_id);


--
-- Name: uq_execution_event_seq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_execution_event_seq ON public.execution_events USING btree (execution_id, seq);


--
-- Name: uq_execution_row_seq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_execution_row_seq ON public.execution_rows USING btree (execution_id, seq);


--
-- Name: uq_integration_instance; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_integration_instance ON public.integration_tasks USING btree (template_id, holder_id);


--
-- Name: uq_notification_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_notification_batch ON public.notifications USING btree (user_id, type, batch_id) WHERE (batch_id IS NOT NULL);


--
-- Name: uq_run_scheme_default; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_run_scheme_default ON public.composer_run_schemes USING btree (scenario_id) WHERE (is_default IS TRUE);


--
-- Name: uq_run_scheme_scenario_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_run_scheme_scenario_name ON public.composer_run_schemes USING btree (scenario_id, name);


--
-- Name: uq_suites_id_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_suites_id_owner ON public.suites USING btree (id, owner_id);


--
-- Name: uq_suites_owner_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_suites_owner_name ON public.suites USING btree (owner_id, name);


--
-- Name: uq_users_display_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_display_name ON public.users USING btree (display_name) WHERE ((display_name)::text <> ''::text);


--
-- Name: activity_events activity_events_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_events
    ADD CONSTRAINT activity_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: adaptation_batches adaptation_batches_operator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adaptation_batches
    ADD CONSTRAINT adaptation_batches_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: audit_logs audit_logs_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: auth_sessions auth_sessions_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_sessions
    ADD CONSTRAINT auth_sessions_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: board_cards board_cards_author_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.board_cards
    ADD CONSTRAINT board_cards_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: carry_global_defaults carry_global_defaults_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_global_defaults
    ADD CONSTRAINT carry_global_defaults_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: carry_service_bindings carry_service_bindings_updated_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carry_service_bindings
    ADD CONSTRAINT carry_service_bindings_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: composer_data_sets composer_data_sets_scenario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_data_sets
    ADD CONSTRAINT composer_data_sets_scenario_id_fkey FOREIGN KEY (scenario_id) REFERENCES public.composer_scenarios(scenario_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: composer_run_schemes composer_run_schemes_scenario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_run_schemes
    ADD CONSTRAINT composer_run_schemes_scenario_id_fkey FOREIGN KEY (scenario_id) REFERENCES public.composer_scenarios(scenario_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: composer_scenarios composer_scenarios_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.composer_scenarios
    ADD CONSTRAINT composer_scenarios_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: constant_entries constant_entries_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.constant_entries
    ADD CONSTRAINT constant_entries_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: environments environments_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environments
    ADD CONSTRAINT environments_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: execution_event_evidence execution_event_evidence_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_event_evidence
    ADD CONSTRAINT execution_event_evidence_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.executions(id) ON DELETE CASCADE;


--
-- Name: execution_events execution_events_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_events
    ADD CONSTRAINT execution_events_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.executions(id) ON DELETE CASCADE;


--
-- Name: execution_jobs execution_jobs_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_jobs
    ADD CONSTRAINT execution_jobs_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.executions(id) ON DELETE CASCADE;


--
-- Name: execution_rows execution_rows_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_rows
    ADD CONSTRAINT execution_rows_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.executions(id) ON DELETE CASCADE;


--
-- Name: execution_snapshots execution_snapshots_execution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.execution_snapshots
    ADD CONSTRAINT execution_snapshots_execution_id_fkey FOREIGN KEY (execution_id) REFERENCES public.executions(id) ON DELETE CASCADE;


--
-- Name: executions executions_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.executions
    ADD CONSTRAINT executions_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: external_endpoints external_endpoints_alias_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_endpoints
    ADD CONSTRAINT external_endpoints_alias_name_fkey FOREIGN KEY (alias_name) REFERENCES public.service_aliases(alias_name) ON DELETE CASCADE;


--
-- Name: suite_members fk_suite_members_scenario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suite_members
    ADD CONSTRAINT fk_suite_members_scenario FOREIGN KEY (scenario_id, owner_id) REFERENCES public.composer_scenarios(scenario_id, owner_id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


--
-- Name: suite_members fk_suite_members_suite; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suite_members
    ADD CONSTRAINT fk_suite_members_suite FOREIGN KEY (suite_id, owner_id) REFERENCES public.suites(id, owner_id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


--
-- Name: integration_tasks integration_tasks_holder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_tasks
    ADD CONSTRAINT integration_tasks_holder_id_fkey FOREIGN KEY (holder_id) REFERENCES public.users(id);


--
-- Name: integration_tasks integration_tasks_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_tasks
    ADD CONSTRAINT integration_tasks_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: integration_tasks integration_tasks_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_tasks
    ADD CONSTRAINT integration_tasks_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.integration_tasks(id);


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: scenario_endpoint_refs scenario_endpoint_refs_scenario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scenario_endpoint_refs
    ADD CONSTRAINT scenario_endpoint_refs_scenario_id_fkey FOREIGN KEY (scenario_id) REFERENCES public.composer_scenarios(scenario_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: service_aliases service_aliases_environment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_aliases
    ADD CONSTRAINT service_aliases_environment_id_fkey FOREIGN KEY (environment_id) REFERENCES public.environments(id);


--
-- Name: service_aliases service_aliases_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_aliases
    ADD CONSTRAINT service_aliases_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.users(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: share_refs share_refs_grantee_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.share_refs
    ADD CONSTRAINT share_refs_grantee_user_id_fkey FOREIGN KEY (grantee_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: share_refs share_refs_scenario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.share_refs
    ADD CONSTRAINT share_refs_scenario_id_fkey FOREIGN KEY (scenario_id) REFERENCES public.composer_scenarios(scenario_id) ON DELETE CASCADE;


--
-- Name: share_refs share_refs_suite_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.share_refs
    ADD CONSTRAINT share_refs_suite_id_fkey FOREIGN KEY (suite_id) REFERENCES public.suites(id) ON DELETE CASCADE;


--
-- Name: suites suites_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suites
    ADD CONSTRAINT suites_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: user_prefs user_prefs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_prefs
    ADD CONSTRAINT user_prefs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_stars user_stars_scenario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_stars
    ADD CONSTRAINT user_stars_scenario_id_fkey FOREIGN KEY (scenario_id) REFERENCES public.composer_scenarios(scenario_id) ON DELETE CASCADE;


--
-- Name: user_stars user_stars_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_stars
    ADD CONSTRAINT user_stars_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--



INSERT INTO public.alembic_version (version_num) VALUES ('0023_ext_schema_json');
