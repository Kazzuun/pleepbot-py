-- migrate:up
CREATE TABLE twitch.locations (
    user_id         text PRIMARY KEY,
    latitude        float NOT NULL,
    longitude       float NOT NULL,
    address         text NOT NULL,
    private         boolean NOT NULL DEFAULT TRUE
);


-- migrate:down
DROP TABLE twitch.locations;
