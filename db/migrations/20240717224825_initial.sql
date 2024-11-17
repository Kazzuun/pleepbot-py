-- migrate:up
CREATE SCHEMA twitch;

CREATE TYPE user_role AS ENUM ('ADMIN', 'DEFAULT', 'RESTRICTED', 'BANNED');

CREATE TABLE twitch.user_config (
    user_id     text PRIMARY KEY,
    username    text UNIQUE NOT NULL,
    role        user_role NOT NULL DEFAULT 'DEFAULT',
    no_replies  boolean NOT NULL DEFAULT FALSE,
    optouts     text[] NOT NULL DEFAULT array[]::text[],
    notes       text DEFAULT NULL
);

CREATE TABLE twitch.joined_channels (
    channel_id          text PRIMARY KEY ,
    username            text UNIQUE NOT NULL,
    currently_online    boolean NOT NULL DEFAULT FALSE,
    joined_at           timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE twitch.channel_config (
    channel_id              text PRIMARY KEY,
    logging                 boolean NOT NULL DEFAULT TRUE,
    emote_streaks           boolean NOT NULL DEFAULT FALSE,
    commands_online         boolean NOT NULL DEFAULT TRUE,
    reminds_online          boolean NOT NULL DEFAULT TRUE,
    notifications_online    boolean NOT NULL DEFAULT FALSE,
    outside_reminds         boolean NOT NULL DEFAULT TRUE,
    disabled_commands       text[] NOT NULL DEFAULT array[]::text[],
    banned_users            text[] NOT NULL DEFAULT array[]::text[],
    prefixes                text[] NOT NULL DEFAULT array[]::text[]
);

CREATE TABLE twitch.messages (
    id          serial PRIMARY KEY,
    channel     text NOT NULL,
    sender      text NOT NULL,
    message     text NOT NULL,
    sent_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX messages_search_idx ON twitch.messages USING GIN (to_tsvector('english', message));

CREATE TYPE afk_type AS ENUM ('AFK', 'GN', 'WORK');

CREATE TABLE twitch.afks (
    id              serial PRIMARY KEY,
    channel         text NOT NULL,
    target          text NOT NULL,
    kind            afk_type NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at    timestamptz DEFAULT NULL
);

CREATE TABLE twitch.reminders (
    id              serial PRIMARY KEY,
    channel         text NOT NULL,
    sender          text NOT NULL,
    target          text NOT NULL,
    message         text,
    created_at      timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scheduled_at    timestamptz,
    processed_at    timestamptz DEFAULT NULL,
    sent            boolean DEFAULT FALSE,
    cancelled       boolean DEFAULT FALSE,
    delete_after    boolean DEFAULT FALSE,
    CHECK (sent IS FALSE OR cancelled IS FALSE),
    CHECK (processed_at IS NULL OR (processed_at IS NOT NULL AND (sent IS TRUE OR cancelled IS TRUE)))
);

CREATE FUNCTION twitch.cancel_reminders()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE twitch.reminders
    SET cancelled = TRUE, processed_at = CURRENT_TIMESTAMP
    WHERE 
        channel = OLD.username AND
        scheduled_at IS NOT NULL AND
        processed_at IS NULL;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER cancel_reminders_on_part
AFTER DELETE ON twitch.joined_channels
FOR EACH ROW
EXECUTE FUNCTION twitch.cancel_reminders();

CREATE OR REPLACE FUNCTION twitch.delete_disposable_reminder()
RETURNS TRIGGER AS $$
BEGIN
    IF (NEW.sent IS TRUE OR NEW.cancelled IS TRUE) AND NEW.delete_after IS TRUE THEN
        DELETE FROM twitch.reminders
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER delete_disposable_reminder_after_complete
AFTER UPDATE OF sent, cancelled ON twitch.reminders
FOR EACH ROW
EXECUTE FUNCTION twitch.delete_disposable_reminder();

CREATE TABLE twitch.live_notifications (
    channel_id      text NOT NULL,
    target_id       text NOT NULL,
    pings           text[] NOT NULL DEFAULT array[]::text[],
    PRIMARY KEY (channel_id, target_id),
    FOREIGN KEY (channel_id)
        REFERENCES twitch.joined_channels (channel_id)
        ON DELETE CASCADE
);

CREATE TABLE twitch.yt_upload_notifications (
    channel_id      text NOT NULL,
    playlist_id     text NOT NULL,
    pings           text[] NOT NULL DEFAULT array[]::text[],
    PRIMARY KEY (channel_id, playlist_id),
    FOREIGN KEY (channel_id)
        REFERENCES twitch.joined_channels (channel_id)
        ON DELETE CASCADE
);

CREATE TABLE twitch.fortunes (
    id          serial PRIMARY KEY,
    fortune     text UNIQUE NOT NULL
);

CREATE TABLE twitch.blocked_terms (
    id          serial PRIMARY KEY,
    pattern     text NOT NULL,
    regex       boolean NOT NULL DEFAULT FALSE
);

CREATE TABLE twitch.old_fish (
    user_id     text PRIMARY KEY,
    username    text UNIQUE NOT NULL,
    fish_count  int NOT NULL DEFAULT 0,
    exp         int NOT NULL DEFAULT 0,
    last_fished timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    equipment   int NOT NULL DEFAULT 0
);

CREATE TYPE permission_level AS ENUM ('BROADCASTER', 'MOD', 'VIP', 'SUBSCRIBER', 'FOLLOWER', 'EVERYONE');

CREATE TABLE twitch.custom_commands (
    channel_id  text,
    name        text,
    message     text NOT NULL,
    level       permission_level NOT NULL DEFAULT 'EVERYONE',
    enabled     boolean NOT NULL DEFAULT TRUE,
    PRIMARY KEY (channel_id, name)
);

CREATE TABLE twitch.custom_patterns (
    channel_id  text,
    name        text,
    message     text NOT NULL,
    pattern     text NOT NULL,
    regex       boolean NOT NULL DEFAULT FALSE,
    probability float NOT NULL DEFAULT 1 CONSTRAINT non_zero CHECK (probability > 0 AND probability <= 1),
    enabled     boolean NOT NULL DEFAULT TRUE,
    PRIMARY KEY (channel_id, name)
);

CREATE TABLE twitch.counters (
    channel_id  text,
    name        text,
    value       int NOT NULL DEFAULT 0,
    PRIMARY KEY (channel_id, name)
);

CREATE FUNCTION twitch.remove_counter()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.value = 0 THEN
        DELETE FROM twitch.counters
        WHERE 
            channel_id = NEW.channel_id AND 
            name = NEW.name;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER remove_counter_on_reset
AFTER UPDATE OF value ON twitch.counters
FOR EACH ROW
EXECUTE FUNCTION twitch.remove_counter();

CREATE TABLE twitch.timers (
    channel_id      text,
    name            text,
    message         text NOT NULL,
    next_time       timestamptz NOT NULL,
    time_between    interval NOT NULL,
    enabled         boolean NOT NULL DEFAULT TRUE,
    PRIMARY KEY (channel_id, name)
);

CREATE FUNCTION twitch.disable_timers()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE twitch.timers
    SET enabled = FALSE
    WHERE channel_id = OLD.channel_id;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER disable_timers_on_part
AFTER DELETE ON twitch.joined_channels
FOR EACH ROW
EXECUTE FUNCTION twitch.disable_timers();

CREATE TABLE twitch.watchtime (
    channel     text,
    username    text,
    online_time int NOT NULL DEFAULT 0,
    total_time  int NOT NULL DEFAULT 0,
    PRIMARY KEY (channel, username)
);

CREATE TABLE twitch.rps (
    user_id     text PRIMARY KEY,
    wins        int NOT NULL DEFAULT 0,
    draws       int NOT NULL DEFAULT 0,
    losses      int NOT NULL DEFAULT 0
);

CREATE TABLE twitch.last_iqs (
    user_id         text PRIMARY KEY,
    last_iq         int NOT NULL,
    last_updated    timestamptz NOT NULL
);

CREATE TABLE twitch.fights (
    user_id_1   text,
    user_id_2   text,
    user_1_wins int NOT NULL DEFAULT 0,
    user_2_wins int NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id_1, user_id_2),
    CHECK (user_id_1 < user_id_2)
);

CREATE TABLE twitch.command_usage_log (
    log_id      serial PRIMARY KEY,
    channel     text NOT NULL,
    username    text NOT NULL,
    command     text NOT NULL,
    message     text NOT NULL,
    use_time_ms float NOT NULL,
    used_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- migrate:down
