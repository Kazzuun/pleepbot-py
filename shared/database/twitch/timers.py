from datetime import datetime, timedelta

from asyncpg import Pool, Record

from .models import Timer
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def sendable_timers(pool: Pool) -> list[Timer]:
    async with pool.acquire() as con:
        async with con.transaction():
            results: list[Record] = await con.fetch(
                """
                SELECT t.channel_id, j.username, name, message, next_time, time_between, enabled
                FROM twitch.timers t JOIN twitch.joined_channels j ON t.channel_id = j.channel_id
                WHERE next_time < CURRENT_TIMESTAMP AND enabled IS TRUE;
                """
            )
            timers = [Timer(**result) for result in results]
            await con.executemany(
                """
                UPDATE twitch.timers
                SET next_time = next_time + time_between
                WHERE channel_id = $1 AND name = $2;
                """,
                [(timer.channel_id, timer.name) for timer in timers],
            )
            return timers


@asyncpg_error_handler
async def timer_exists(pool: Pool, channel_id: str, cmd_name: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: bool = await con.fetchval(
                """
                SELECT COUNT(*) > 0
                FROM twitch.timers
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                cmd_name,
            )
            return result


@asyncpg_error_handler
async def list_timers(pool: Pool, channel_id: str) -> list[Timer]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT t.channel_id, j.username, name, message, next_time, time_between, enabled
                FROM twitch.timers t JOIN twitch.joined_channels j ON t.channel_id = j.channel_id
                WHERE t.channel_id = $1;
                """,
                channel_id,
            )
            return [Timer(**result) for result in results]


@asyncpg_error_handler
async def show_timer(pool: Pool, channel_id: str, timer_name: str) -> Timer | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT t.channel_id, j.username, name, message, next_time, time_between, enabled
                FROM twitch.timers t JOIN twitch.joined_channels j ON t.channel_id = j.channel_id
                WHERE channel_id = $1, name = $2;
                """,
                channel_id,
                timer_name,
            )
            if result is None:
                return None
            return Timer(**result)


@asyncpg_error_handler
async def add_timer(
    pool: Pool, channel_id: str, timer_name: str, message: str, first_time: datetime, time_between: timedelta
) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.timers (channel_id, name, message, next_time, time_between)
                VALUES ($1, $2, $3, $4, $5);
                """,
                channel_id,
                timer_name,
                message,
                first_time,
                time_between,
            )


@asyncpg_error_handler
async def delete_timer(pool: Pool, channel_id: str, timer_name: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                DELETE FROM twitch.timers
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                timer_name,
            )


# TODO: make this
# @asyncpg_error_handler
# async def edit_timer(pool: Pool, channel_id: str, timer_name: str, message: str, first_time: datetime, time_between: timedelta) -> None:
#     async with pool.acquire() as con:
#         async with con.transaction():
#             await con.execute(
#                 '''
#                 UPDATE twitch.timers
#                 SET message = $1,
#                 WHERE channel_id = $2 AND name = $3;
#                 ''',
#                 channel_id, timer_name, message, first_time, time_between
#             )


@asyncpg_error_handler
async def enable_timer(pool: Pool, channel_id: str, timer_name: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.timers
                SET enabled = TRUE
                WHERE channel_id = $1 AND name = $1;
                """,
                channel_id,
                timer_name,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def disable_timer(pool: Pool, channel_id: str, timer_name: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.timers
                SET enabled = FALSE
                WHERE channel_id = $1 AND name = $1;
                """,
                channel_id,
                timer_name,
            )
            return int(result.split()[-1]) > 0
