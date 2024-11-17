from asyncpg import Pool, Record

from .models import UserConfig, Watchtime
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def user_config(pool: Pool, user_id: str) -> UserConfig:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT user_id, role, no_replies, optouts
                FROM twitch.user_config
                WHERE user_id = $1;
                """,
                user_id,
            )
            if result is None:
                return UserConfig(user_id=user_id)
            return UserConfig(**result)


@asyncpg_error_handler
async def create_user_config(pool: Pool, user_id: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.user_config (user_id)
                VALUES ($1)
                ON CONFLICT (user_id)
                DO NOTHING;
                """,
                user_id,
            )


@asyncpg_error_handler
async def replies_on(pool: Pool, user_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.user_config
                SET no_replies = FALSE
                WHERE user_id = $1;
                """,
                user_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def replies_off(pool: Pool, user_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.user_config
                SET no_replies = TRUE
                WHERE user_id = $1;
                """,
                user_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def ban_globally(pool: Pool, user_id: str, notes: str | None = None) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                INSERT INTO twitch.user_config (user_id, role, notes)
                VALUES ($1, 'BANNED', $2)
                ON CONFLICT (user_id)
                DO UPDATE SET role = 'BANNED';
                """,
                user_id,
                notes,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def unban_globally(pool: Pool, user_id: str, notes: str | None = None) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.user_config
                SET role = 'DEFAULT', notes = $2
                WHERE user_id = $1;
                """,
                user_id,
                notes,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def optin(pool: Pool, user_id: str, commands: list[str]) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                UPDATE twitch.user_config
                SET optouts = array_remove(optouts, $2)
                WHERE user_id = $1 AND $2 = ANY(optouts);
                """,
                [(user_id, command) for command in commands],
            )


@asyncpg_error_handler
async def optout(pool: Pool, user_id: str, commands: list[str]) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                UPDATE twitch.user_config
                SET optouts = array_append(optouts, $2)
                WHERE user_id = $1 AND NOT $2 = ANY(optouts);
                """,
                [(user_id, command) for command in commands],
            )


@asyncpg_error_handler
async def watchtime(pool: Pool, channel_id: str, username: str) -> Watchtime:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT channel_id, username, total_time, online_time
                FROM twitch.watchtime
                WHERE channel_id = $1 AND username = $2;
                """,
                channel_id,
                username,
            )
            if result is None:
                return Watchtime(channel_id=channel_id, username=username)
            return Watchtime(**result)


@asyncpg_error_handler
async def add_offline_time(pool: Pool, channel_id: str, users: list[str], interval: int) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                INSERT INTO twitch.watchtime (channel_id, username, total_time)
                VALUES ($1, $2, $3)
                ON CONFLICT (channel_id, username)
                DO UPDATE SET total_time = twitch.watchtime.total_time + EXCLUDED.total_time;
                """,
                [(channel_id, user, interval) for user in users],
            )


@asyncpg_error_handler
async def add_online_time(pool: Pool, channel_id: str, users: list[str], interval: int) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                INSERT INTO twitch.watchtime (channel_id, username, online_time, total_time)
                VALUES ($1, $2, $3, $3)
                ON CONFLICT (channel_id, username)
                DO UPDATE SET 
                    online_time = twitch.watchtime.online_time + EXCLUDED.online_time,
                    total_time = twitch.watchtime.total_time + EXCLUDED.total_time;
                """,
                [(channel_id, user, interval) for user in users],
            )


@asyncpg_error_handler
async def rename_user(pool: Pool, old_name: str, new_name: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.messages
                SET sender = $2
                WHERE sender = $1;
                """,
                old_name,
                new_name,
            )

            watchtimes: list[Record] = await con.fetch(
                """
                SELECT channel_id, username, online_time, total_time
                FROM twitch.watchtime
                WHERE username = $1;
                """,
                old_name,
            )

            await con.executemany(
                """
                INSERT INTO twitch.watchtime (channel_id, username, online_time, total_time)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (channel_id, username)
                DO UPDATE SET 
                    online_time = twitch.watchtime.online_time + EXCLUDED.online_time, 
                    total_time = twitch.watchtime.total_time + EXCLUDED.total_time;
                """,
                [(r["channel_id"], new_name, r["online_time"], r["total_time"]) for r in watchtimes]
            )

            await con.execute(
                """
                DELETE FROM twitch.watchtime
                WHERE username = $1;
                """,
                old_name,
            )
