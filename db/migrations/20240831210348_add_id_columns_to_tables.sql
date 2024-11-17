-- migrate:up
ALTER TABLE twitch.watchtime
ADD COLUMN channel_id text;

ALTER TABLE twitch.afks
ADD COLUMN channel_id text;

ALTER TABLE twitch.afks
ADD COLUMN target_id text;

ALTER TABLE twitch.command_usage_log
ADD COLUMN channel_id text;

ALTER TABLE twitch.command_usage_log
ADD COLUMN user_id text;

ALTER TABLE twitch.messages
ADD COLUMN channel_id text;

ALTER TABLE twitch.reminders
ADD COLUMN channel_id text;

ALTER TABLE twitch.reminders
ADD COLUMN sender_id text;

ALTER TABLE twitch.reminders
ADD COLUMN target_id text;

-- migrate:down
ALTER TABLE twitch.watchtime
DROP COLUMN channel_id;

ALTER TABLE twitch.afks
DROP COLUMN channel_id;

ALTER TABLE twitch.afks
DROP COLUMN target_id;

ALTER TABLE twitch.command_usage_log
DROP COLUMN channel_id;

ALTER TABLE twitch.command_usage_log
DROP COLUMN user_id;

ALTER TABLE twitch.messages
DROP COLUMN channel_id;

ALTER TABLE twitch.reminders
DROP COLUMN channel_id;

ALTER TABLE twitch.reminders
DROP COLUMN sender_id;

ALTER TABLE twitch.reminders
DROP COLUMN target_id;
