-- migrate:up
ALTER TYPE public.afk_type SET SCHEMA twitch;
ALTER TYPE public.permission_level SET SCHEMA twitch;
ALTER TYPE public.user_role SET SCHEMA twitch;

-- migrate:down

