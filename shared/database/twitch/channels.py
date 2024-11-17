from asyncpg import Pool, Record

from .models import ChannelConfig
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def initial_channels(pool: Pool) -> list[str]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT username 
                FROM twitch.joined_channels;
                """
            )
            return [result["username"] for result in results]


@asyncpg_error_handler
async def initial_channel_ids(pool: Pool) -> set[str]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT channel_id 
                FROM twitch.joined_channels;
                """
            )
            return set(result["channel_id"] for result in results)


@asyncpg_error_handler
async def channel_config(pool: Pool, channel: str) -> ChannelConfig:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT 
                    j.channel_id, 
                    username,
                    currently_online,
                    joined_at,
                    logging,
                    emote_streaks,
                    commands_online,
                    reminds_online,
                    notifications_online,
                    outside_reminds,
                    disabled_commands,
                    banned_users,
                    prefixes
                FROM twitch.joined_channels j JOIN twitch.channel_config c ON j.channel_id = c.channel_id
                WHERE username = $1;
                """,
                channel,
            )
            assert result is not None
            return ChannelConfig(**result)


@asyncpg_error_handler
async def channel_config_from_id(pool: Pool, channel_id: str) -> ChannelConfig:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT 
                    j.channel_id, 
                    username,
                    currently_online,
                    joined_at,
                    logging,
                    emote_streaks,
                    commands_online,
                    reminds_online,
                    notifications_online,
                    outside_reminds,
                    disabled_commands,
                    banned_users,
                    prefixes
                FROM twitch.joined_channels j JOIN twitch.channel_config c ON j.channel_id = c.channel_id
                WHERE j.channel_id = $1;
                """,
                channel_id,
            )
            assert result is not None
            return ChannelConfig(**result)


@asyncpg_error_handler
async def channel_id(pool: Pool, channel: str) -> str:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: str | None = await con.fetchval(
                """
                SELECT channel_id
                FROM twitch.joined_channels
                WHERE username = $1;
                """,
                channel,
            )
            assert result is not None
            return result


@asyncpg_error_handler
async def join_channel(pool: Pool, channel_id: str, channel_name: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.joined_channels (channel_id, username) 
                VALUES ($1, $2)
                ON CONFLICT (channel_id)
                DO UPDATE SET username = EXCLUDED.username;
                """,
                channel_id,
                channel_name,
            )
            await con.execute(
                """
                INSERT INTO twitch.channel_config (channel_id)
                VALUES ($1)
                ON CONFLICT (channel_id)
                DO NOTHING;
                """,
                channel_id,
            )


@asyncpg_error_handler
async def part_channel(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                DELETE FROM twitch.joined_channels
                WHERE channel_id = $1;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def set_online(pool: Pool, channel_id: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.joined_channels
                SET currently_online = TRUE
                WHERE channel_id = $1;
                """,
                channel_id,
            )


@asyncpg_error_handler
async def set_offline(pool: Pool, channel_id: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.joined_channels
                SET currently_online = FALSE
                WHERE channel_id = $1;
                """,
                channel_id,
            )


@asyncpg_error_handler
async def enable_commands(pool: Pool, channel_id: str, commands: list[str]) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                UPDATE twitch.channel_config
                SET disabled_commands = array_remove(disabled_commands, $2)
                WHERE channel_id = $1 AND $2 = ANY(disabled_commands);
                """,
                [(channel_id, command) for command in commands],
            )


@asyncpg_error_handler
async def disable_commands(pool: Pool, channel_id: str, commands: list[str]) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                UPDATE twitch.channel_config
                SET disabled_commands = array_append(disabled_commands, $2)
                WHERE channel_id = $1 AND NOT $2 = ANY(disabled_commands);
                """,
                [(channel_id, command) for command in commands],
            )


@asyncpg_error_handler
async def ban_in_channel(pool: Pool, channel_id: str, user_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET banned_users = array_append(banned_users, $2)
                WHERE channel_id = $1 AND NOT $2 = ANY(banned_users);
                """,
                channel_id,
                user_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def unban_in_channel(pool: Pool, channel_id: str, user_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET banned_users = array_remove(banned_users, $2)
                WHERE channel_id = $1 AND $2 = ANY(banned_users);
                """,
                channel_id,
                user_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def add_prefixes(pool: Pool, channel_id: str, prefixes: list[str]) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                UPDATE twitch.channel_config
                SET prefixes = array_append(prefixes, $2)
                WHERE channel_id = $1 AND NOT $2 = ANY(prefixes);
                """,
                [(channel_id, prefix) for prefix in prefixes],
            )


@asyncpg_error_handler
async def remove_prefixes(pool: Pool, channel_id: str, prefixes: list[str]) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(
                """
                UPDATE twitch.channel_config
                SET prefixes = array_remove(prefixes, $2)
                WHERE channel_id = $1 AND $2 = ANY(prefixes);
                """,
                [(channel_id, prefix) for prefix in prefixes],
            )


@asyncpg_error_handler
async def logging_on(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET logging = TRUE
                WHERE channel_id = $1 AND logging IS FALSE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def logging_off(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET logging = FALSE
                WHERE channel_id = $1 AND logging IS TRUE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def emote_streaks_on(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET emote_streaks = TRUE
                WHERE channel_id = $1 AND emote_streaks IS FALSE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def emote_streaks_off(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET emote_streaks = FALSE
                WHERE channel_id = $1 AND emote_streaks IS TRUE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def commands_online_on(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET commands_online = TRUE
                WHERE channel_id = $1 AND commands_online IS FALSE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def commands_online_off(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET commands_online = FALSE
                WHERE channel_id = $1 AND commands_online IS TRUE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def reminds_online_on(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET reminds_online = TRUE
                WHERE channel_id = $1 AND reminds_online IS FALSE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def reminds_online_off(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET reminds_online = FALSE
                WHERE channel_id = $1 AND reminds_online IS TRUE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def outside_reminds_on(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET outside_reminds = TRUE
                WHERE channel_id = $1 AND outside_reminds IS FALSE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def outside_reminds_off(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET outside_reminds = FALSE
                WHERE channel_id = $1 AND outside_reminds IS TRUE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0

@asyncpg_error_handler
async def notifications_online_on(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET notifications_online = TRUE
                WHERE channel_id = $1 AND notifications_online IS FALSE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def notifications_online_off(pool: Pool, channel_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.channel_config
                SET notifications_online = FALSE
                WHERE channel_id = $1 AND notifications_online IS TRUE;
                """,
                channel_id,
            )
            return int(result.split()[-1]) > 0
