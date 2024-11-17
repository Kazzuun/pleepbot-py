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
-- Name: twitch; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA twitch;


--
-- Name: afk_type; Type: TYPE; Schema: twitch; Owner: -
--

CREATE TYPE twitch.afk_type AS ENUM (
    'AFK',
    'GN',
    'WORK'
);


--
-- Name: permission_level; Type: TYPE; Schema: twitch; Owner: -
--

CREATE TYPE twitch.permission_level AS ENUM (
    'BROADCASTER',
    'MOD',
    'VIP',
    'SUBSCRIBER',
    'FOLLOWER',
    'EVERYONE'
);


--
-- Name: user_role; Type: TYPE; Schema: twitch; Owner: -
--

CREATE TYPE twitch.user_role AS ENUM (
    'ADMIN',
    'DEFAULT',
    'RESTRICTED',
    'BANNED'
);


--
-- Name: cancel_reminders(); Type: FUNCTION; Schema: twitch; Owner: -
--

CREATE FUNCTION twitch.cancel_reminders() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE twitch.reminders
    SET cancelled = TRUE, processed_at = CURRENT_TIMESTAMP
    WHERE
        channel_id = OLD.channel_id AND
        scheduled_at IS NOT NULL AND
        processed_at IS NULL;

    RETURN OLD;
END;
$$;


--
-- Name: delete_disposable_reminder(); Type: FUNCTION; Schema: twitch; Owner: -
--

CREATE FUNCTION twitch.delete_disposable_reminder() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF (NEW.sent IS TRUE OR NEW.cancelled IS TRUE) AND NEW.delete_after IS TRUE THEN
        DELETE FROM twitch.reminders
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: disable_timers(); Type: FUNCTION; Schema: twitch; Owner: -
--

CREATE FUNCTION twitch.disable_timers() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE twitch.timers
    SET enabled = FALSE
    WHERE channel_id = OLD.channel_id;

    RETURN OLD;
END;
$$;


--
-- Name: remove_counter(); Type: FUNCTION; Schema: twitch; Owner: -
--

CREATE FUNCTION twitch.remove_counter() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.value = 0 THEN
        DELETE FROM twitch.counters
        WHERE
            channel_id = NEW.channel_id AND
            name = NEW.name;
    END IF;

    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying(128) NOT NULL
);


--
-- Name: afks; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.afks (
    id integer NOT NULL,
    kind twitch.afk_type NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    processed_at timestamp with time zone,
    channel_id text NOT NULL,
    target_id text NOT NULL
);


--
-- Name: afks_id_seq; Type: SEQUENCE; Schema: twitch; Owner: -
--

CREATE SEQUENCE twitch.afks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: afks_id_seq; Type: SEQUENCE OWNED BY; Schema: twitch; Owner: -
--

ALTER SEQUENCE twitch.afks_id_seq OWNED BY twitch.afks.id;


--
-- Name: blocked_terms; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.blocked_terms (
    id integer NOT NULL,
    pattern text NOT NULL,
    regex boolean DEFAULT false NOT NULL
);


--
-- Name: blocked_terms_id_seq; Type: SEQUENCE; Schema: twitch; Owner: -
--

CREATE SEQUENCE twitch.blocked_terms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: blocked_terms_id_seq; Type: SEQUENCE OWNED BY; Schema: twitch; Owner: -
--

ALTER SEQUENCE twitch.blocked_terms_id_seq OWNED BY twitch.blocked_terms.id;


--
-- Name: channel_config; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.channel_config (
    channel_id text NOT NULL,
    logging boolean DEFAULT true NOT NULL,
    emote_streaks boolean DEFAULT false NOT NULL,
    commands_online boolean DEFAULT true NOT NULL,
    reminds_online boolean DEFAULT true NOT NULL,
    notifications_online boolean DEFAULT false NOT NULL,
    outside_reminds boolean DEFAULT true NOT NULL,
    disabled_commands text[] DEFAULT ARRAY[]::text[] NOT NULL,
    banned_users text[] DEFAULT ARRAY[]::text[] NOT NULL,
    prefixes text[] DEFAULT ARRAY[]::text[] NOT NULL
);


--
-- Name: command_usage_log; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.command_usage_log (
    id integer NOT NULL,
    command text NOT NULL,
    message text NOT NULL,
    use_time_ms double precision NOT NULL,
    used_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    channel_id text NOT NULL,
    user_id text NOT NULL
);


--
-- Name: command_usage_log_log_id_seq; Type: SEQUENCE; Schema: twitch; Owner: -
--

CREATE SEQUENCE twitch.command_usage_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: command_usage_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: twitch; Owner: -
--

ALTER SEQUENCE twitch.command_usage_log_log_id_seq OWNED BY twitch.command_usage_log.id;


--
-- Name: counters; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.counters (
    channel_id text NOT NULL,
    name text NOT NULL,
    value integer DEFAULT 0 NOT NULL
);


--
-- Name: custom_commands; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.custom_commands (
    channel_id text NOT NULL,
    name text NOT NULL,
    message text NOT NULL,
    level twitch.permission_level DEFAULT 'EVERYONE'::twitch.permission_level NOT NULL,
    enabled boolean DEFAULT true NOT NULL
);


--
-- Name: custom_patterns; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.custom_patterns (
    channel_id text NOT NULL,
    name text NOT NULL,
    message text NOT NULL,
    pattern text NOT NULL,
    regex boolean DEFAULT false NOT NULL,
    probability double precision DEFAULT 1 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    CONSTRAINT non_zero CHECK (((probability > (0)::double precision) AND (probability <= (1)::double precision)))
);


--
-- Name: fights; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.fights (
    user_id_1 text NOT NULL,
    user_id_2 text NOT NULL,
    user_1_wins integer DEFAULT 0 NOT NULL,
    user_2_wins integer DEFAULT 0 NOT NULL,
    CONSTRAINT fights_check CHECK ((user_id_1 < user_id_2))
);


--
-- Name: fortunes; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.fortunes (
    id integer NOT NULL,
    fortune text NOT NULL
);


--
-- Name: fortunes_id_seq; Type: SEQUENCE; Schema: twitch; Owner: -
--

CREATE SEQUENCE twitch.fortunes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fortunes_id_seq; Type: SEQUENCE OWNED BY; Schema: twitch; Owner: -
--

ALTER SEQUENCE twitch.fortunes_id_seq OWNED BY twitch.fortunes.id;


--
-- Name: joined_channels; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.joined_channels (
    channel_id text NOT NULL,
    username text NOT NULL,
    currently_online boolean DEFAULT false NOT NULL,
    joined_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: last_iqs; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.last_iqs (
    user_id text NOT NULL,
    last_iq integer NOT NULL,
    last_updated timestamp with time zone NOT NULL
);


--
-- Name: live_notifications; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.live_notifications (
    channel_id text NOT NULL,
    target_id text NOT NULL,
    pings text[] DEFAULT ARRAY[]::text[] NOT NULL
);


--
-- Name: locations; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.locations (
    user_id text NOT NULL,
    latitude double precision NOT NULL,
    longitude double precision NOT NULL,
    address text NOT NULL,
    private boolean DEFAULT true NOT NULL
);


--
-- Name: messages; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.messages (
    id integer NOT NULL,
    sender text NOT NULL,
    message text NOT NULL,
    sent_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    channel_id text NOT NULL,
    online boolean
);


--
-- Name: messages_id_seq; Type: SEQUENCE; Schema: twitch; Owner: -
--

CREATE SEQUENCE twitch.messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: messages_id_seq; Type: SEQUENCE OWNED BY; Schema: twitch; Owner: -
--

ALTER SEQUENCE twitch.messages_id_seq OWNED BY twitch.messages.id;


--
-- Name: old_fish; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.old_fish (
    user_id text NOT NULL,
    fish_count integer DEFAULT 0 NOT NULL,
    exp integer DEFAULT 0 NOT NULL,
    last_fished timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    equipment integer DEFAULT 0 NOT NULL
);


--
-- Name: reminders; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.reminders (
    id integer NOT NULL,
    message text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    scheduled_at timestamp with time zone,
    processed_at timestamp with time zone,
    sent boolean DEFAULT false,
    cancelled boolean DEFAULT false,
    delete_after boolean DEFAULT false,
    channel_id text NOT NULL,
    sender_id text NOT NULL,
    target_id text NOT NULL,
    CONSTRAINT reminders_check CHECK (((sent IS FALSE) OR (cancelled IS FALSE))),
    CONSTRAINT reminders_check1 CHECK (((processed_at IS NULL) OR ((processed_at IS NOT NULL) AND ((sent IS TRUE) OR (cancelled IS TRUE)))))
);


--
-- Name: reminders_id_seq; Type: SEQUENCE; Schema: twitch; Owner: -
--

CREATE SEQUENCE twitch.reminders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reminders_id_seq; Type: SEQUENCE OWNED BY; Schema: twitch; Owner: -
--

ALTER SEQUENCE twitch.reminders_id_seq OWNED BY twitch.reminders.id;


--
-- Name: rps; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.rps (
    user_id text NOT NULL,
    wins integer DEFAULT 0 NOT NULL,
    draws integer DEFAULT 0 NOT NULL,
    losses integer DEFAULT 0 NOT NULL
);


--
-- Name: timers; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.timers (
    channel_id text NOT NULL,
    name text NOT NULL,
    message text NOT NULL,
    next_time timestamp with time zone NOT NULL,
    time_between interval NOT NULL,
    enabled boolean DEFAULT true NOT NULL
);


--
-- Name: user_config; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.user_config (
    user_id text NOT NULL,
    role twitch.user_role DEFAULT 'DEFAULT'::twitch.user_role NOT NULL,
    no_replies boolean DEFAULT false NOT NULL,
    optouts text[] DEFAULT ARRAY[]::text[] NOT NULL,
    notes text
);


--
-- Name: watchtime; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.watchtime (
    username text NOT NULL,
    online_time integer DEFAULT 0 NOT NULL,
    total_time integer DEFAULT 0 NOT NULL,
    channel_id text NOT NULL
);


--
-- Name: yt_upload_notifications; Type: TABLE; Schema: twitch; Owner: -
--

CREATE TABLE twitch.yt_upload_notifications (
    channel_id text NOT NULL,
    playlist_id text NOT NULL,
    pings text[] DEFAULT ARRAY[]::text[] NOT NULL
);


--
-- Name: afks id; Type: DEFAULT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.afks ALTER COLUMN id SET DEFAULT nextval('twitch.afks_id_seq'::regclass);


--
-- Name: blocked_terms id; Type: DEFAULT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.blocked_terms ALTER COLUMN id SET DEFAULT nextval('twitch.blocked_terms_id_seq'::regclass);


--
-- Name: command_usage_log id; Type: DEFAULT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.command_usage_log ALTER COLUMN id SET DEFAULT nextval('twitch.command_usage_log_log_id_seq'::regclass);


--
-- Name: fortunes id; Type: DEFAULT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.fortunes ALTER COLUMN id SET DEFAULT nextval('twitch.fortunes_id_seq'::regclass);


--
-- Name: messages id; Type: DEFAULT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.messages ALTER COLUMN id SET DEFAULT nextval('twitch.messages_id_seq'::regclass);


--
-- Name: reminders id; Type: DEFAULT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.reminders ALTER COLUMN id SET DEFAULT nextval('twitch.reminders_id_seq'::regclass);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: afks afks_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.afks
    ADD CONSTRAINT afks_pkey PRIMARY KEY (id);


--
-- Name: blocked_terms blocked_terms_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.blocked_terms
    ADD CONSTRAINT blocked_terms_pkey PRIMARY KEY (id);


--
-- Name: channel_config channel_config_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.channel_config
    ADD CONSTRAINT channel_config_pkey PRIMARY KEY (channel_id);


--
-- Name: command_usage_log command_usage_log_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.command_usage_log
    ADD CONSTRAINT command_usage_log_pkey PRIMARY KEY (id);


--
-- Name: counters counters_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.counters
    ADD CONSTRAINT counters_pkey PRIMARY KEY (channel_id, name);


--
-- Name: custom_commands custom_commands_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.custom_commands
    ADD CONSTRAINT custom_commands_pkey PRIMARY KEY (channel_id, name);


--
-- Name: custom_patterns custom_patterns_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.custom_patterns
    ADD CONSTRAINT custom_patterns_pkey PRIMARY KEY (channel_id, name);


--
-- Name: fights fights_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.fights
    ADD CONSTRAINT fights_pkey PRIMARY KEY (user_id_1, user_id_2);


--
-- Name: fortunes fortunes_fortune_key; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.fortunes
    ADD CONSTRAINT fortunes_fortune_key UNIQUE (fortune);


--
-- Name: fortunes fortunes_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.fortunes
    ADD CONSTRAINT fortunes_pkey PRIMARY KEY (id);


--
-- Name: joined_channels joined_channels_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.joined_channels
    ADD CONSTRAINT joined_channels_pkey PRIMARY KEY (channel_id);


--
-- Name: joined_channels joined_channels_username_key; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.joined_channels
    ADD CONSTRAINT joined_channels_username_key UNIQUE (username);


--
-- Name: last_iqs last_iqs_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.last_iqs
    ADD CONSTRAINT last_iqs_pkey PRIMARY KEY (user_id);


--
-- Name: live_notifications live_notifications_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.live_notifications
    ADD CONSTRAINT live_notifications_pkey PRIMARY KEY (channel_id, target_id);


--
-- Name: locations locations_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.locations
    ADD CONSTRAINT locations_pkey PRIMARY KEY (user_id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: old_fish old_fish_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.old_fish
    ADD CONSTRAINT old_fish_pkey PRIMARY KEY (user_id);


--
-- Name: reminders reminders_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.reminders
    ADD CONSTRAINT reminders_pkey PRIMARY KEY (id);


--
-- Name: rps rps_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.rps
    ADD CONSTRAINT rps_pkey PRIMARY KEY (user_id);


--
-- Name: timers timers_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.timers
    ADD CONSTRAINT timers_pkey PRIMARY KEY (channel_id, name);


--
-- Name: user_config user_config_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.user_config
    ADD CONSTRAINT user_config_pkey PRIMARY KEY (user_id);


--
-- Name: watchtime watchtime_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.watchtime
    ADD CONSTRAINT watchtime_pkey PRIMARY KEY (channel_id, username);


--
-- Name: yt_upload_notifications yt_upload_notifications_pkey; Type: CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.yt_upload_notifications
    ADD CONSTRAINT yt_upload_notifications_pkey PRIMARY KEY (channel_id, playlist_id);


--
-- Name: messages_search_idx; Type: INDEX; Schema: twitch; Owner: -
--

CREATE INDEX messages_search_idx ON twitch.messages USING gin (to_tsvector('english'::regconfig, message));


--
-- Name: joined_channels cancel_reminders_on_part; Type: TRIGGER; Schema: twitch; Owner: -
--

CREATE TRIGGER cancel_reminders_on_part AFTER DELETE ON twitch.joined_channels FOR EACH ROW EXECUTE FUNCTION twitch.cancel_reminders();


--
-- Name: reminders delete_disposable_reminder_after_complete; Type: TRIGGER; Schema: twitch; Owner: -
--

CREATE TRIGGER delete_disposable_reminder_after_complete AFTER UPDATE OF sent, cancelled ON twitch.reminders FOR EACH ROW EXECUTE FUNCTION twitch.delete_disposable_reminder();


--
-- Name: joined_channels disable_timers_on_part; Type: TRIGGER; Schema: twitch; Owner: -
--

CREATE TRIGGER disable_timers_on_part AFTER DELETE ON twitch.joined_channels FOR EACH ROW EXECUTE FUNCTION twitch.disable_timers();


--
-- Name: counters remove_counter_on_reset; Type: TRIGGER; Schema: twitch; Owner: -
--

CREATE TRIGGER remove_counter_on_reset AFTER UPDATE OF value ON twitch.counters FOR EACH ROW EXECUTE FUNCTION twitch.remove_counter();


--
-- Name: live_notifications live_notifications_channel_id_fkey; Type: FK CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.live_notifications
    ADD CONSTRAINT live_notifications_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES twitch.joined_channels(channel_id) ON DELETE CASCADE;


--
-- Name: yt_upload_notifications yt_upload_notifications_channel_id_fkey; Type: FK CONSTRAINT; Schema: twitch; Owner: -
--

ALTER TABLE ONLY twitch.yt_upload_notifications
    ADD CONSTRAINT yt_upload_notifications_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES twitch.joined_channels(channel_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20240717224825'),
    ('20240811154021'),
    ('20240831210348'),
    ('20240831210655'),
    ('20240923122022'),
    ('20240926234316'),
    ('20241112072924');
