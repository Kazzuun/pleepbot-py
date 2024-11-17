-- migrate:up
ALTER TABLE twitch.messages ADD online BOOLEAN;


-- migrate:down
ALTER TABLE twitch.messages DROP COLUMN online;
