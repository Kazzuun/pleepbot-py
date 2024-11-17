-- migrate:up
CREATE OR REPLACE FUNCTION twitch.cancel_reminders() RETURNS trigger
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


-- migrate:down
CREATE OR REPLACE FUNCTION twitch.cancel_reminders() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE twitch.reminders
    SET cancelled = TRUE, processed_at = CURRENT_TIMESTAMP
    WHERE
        channel = OLD.username AND
        scheduled_at IS NOT NULL AND
        processed_at IS NULL;

    RETURN OLD;
END;
$$;
