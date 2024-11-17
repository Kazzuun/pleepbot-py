-- migrate:up
ALTER TABLE twitch.command_usage_log
RENAME COLUMN log_id TO id;


ALTER TABLE twitch.watchtime
DROP CONSTRAINT watchtime_pkey;

ALTER TABLE twitch.watchtime
ADD PRIMARY KEY (channel_id, username);

ALTER TABLE twitch.watchtime
DROP COLUMN channel;


ALTER TABLE twitch.user_config
DROP COLUMN username;

ALTER TABLE twitch.old_fish
DROP COLUMN username;

ALTER TABLE twitch.afks
DROP COLUMN channel;

ALTER TABLE twitch.afks
DROP COLUMN target;

ALTER TABLE twitch.command_usage_log
DROP COLUMN channel;

ALTER TABLE twitch.command_usage_log
DROP COLUMN username;

ALTER TABLE twitch.messages
DROP COLUMN channel;

ALTER TABLE twitch.reminders
DROP COLUMN channel;

ALTER TABLE twitch.reminders
DROP COLUMN sender;

ALTER TABLE twitch.reminders
DROP COLUMN target;


ALTER TABLE twitch.afks
ALTER COLUMN channel_id SET NOT NULL;

ALTER TABLE twitch.afks
ALTER COLUMN target_id SET NOT NULL;

ALTER TABLE twitch.command_usage_log
ALTER COLUMN channel_id SET NOT NULL;

ALTER TABLE twitch.command_usage_log
ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE twitch.messages
ALTER COLUMN channel_id SET NOT NULL;

ALTER TABLE twitch.reminders
ALTER COLUMN channel_id SET NOT NULL;

ALTER TABLE twitch.reminders
ALTER COLUMN sender_id SET NOT NULL;

ALTER TABLE twitch.reminders
ALTER COLUMN target_id SET NOT NULL;


-- migrate:down
ALTER TABLE twitch.command_usage_log
RENAME COLUMN id TO log_id;


ALTER TABLE twitch.watchtime
DROP CONSTRAINT watchtime_pkey;

ALTER TABLE twitch.watchtime
ADD COLUMN channel text;

UPDATE twitch.watchtime
SET channel = channel_id

ALTER TABLE twitch.watchtime
ADD PRIMARY KEY (channel, username)


ALTER TABLE twitch.user_config
ADD COLUMN username text NOT NULL;

ALTER TABLE twitch.old_fish
ADD COLUMN username text UNIQUE NOT NULL;

ALTER TABLE twitch.afks
ADD COLUMN channel text NOT NULL;

ALTER TABLE twitch.afks
ADD COLUMN target text NOT NULL;

ALTER TABLE twitch.command_usage_log
ADD COLUMN channel text NOT NULL;

ALTER TABLE twitch.command_usage_log
ADD COLUMN username text NOT NULL;

ALTER TABLE twitch.messages
ADD COLUMN channel text NOT NULL;

ALTER TABLE twitch.reminders
ADD COLUMN channel text NOT NULL;

ALTER TABLE twitch.reminders
ADD COLUMN sender text NOT NULL;

ALTER TABLE twitch.reminders
ADD COLUMN target text NOT NULL;


ALTER TABLE twitch.afks
ALTER COLUMN channel_id DROP NOT NULL;

ALTER TABLE twitch.afks
ALTER COLUMN target_id DROP NOT NULL;

ALTER TABLE twitch.command_usage_log
ALTER COLUMN channel_id DROP NOT NULL;

ALTER TABLE twitch.command_usage_log
ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE twitch.messages
ALTER COLUMN channel_id DROP NOT NULL;

ALTER TABLE twitch.reminders
ALTER COLUMN channel_id DROP NOT NULL;

ALTER TABLE twitch.reminders
ALTER COLUMN sender_id DROP NOT NULL;

ALTER TABLE twitch.reminders
ALTER COLUMN target_id DROP NOT NULL;
