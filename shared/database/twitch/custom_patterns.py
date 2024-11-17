from asyncpg import Pool, Record

from .models import CustomPattern
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def pattern_exists(pool: Pool, channel_id: str, name: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record = await con.fetchrow(
                """
                SELECT COUNT(*) > 0 as pattern_exists
                FROM twitch.custom_patterns
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                name,
            )
            return result["pattern_exists"]


@asyncpg_error_handler
async def list_custom_patterns(pool: Pool, channel_id: str) -> list[CustomPattern]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT *
                FROM twitch.custom_patterns
                WHERE channel_id = $1;
                """,
                channel_id,
            )
            return [CustomPattern(**result) for result in results]


@asyncpg_error_handler
async def show_custom_pattern(pool: Pool, channel_id: str, name: str) -> CustomPattern:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record = await con.fetchrow(
                """
                SELECT *
                FROM twitch.custom_patterns
                WHERE channel_id = $1, name = $2;
                """,
                channel_id,
                name,
            )
            return CustomPattern(**result)


@asyncpg_error_handler
async def add_custom_pattern(
    pool: Pool, channel_id: str, name: str, pattern: str, message: str, probability: float = 1, regex: bool = False
) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.custom_patterns (channel_id, name, pattern, message, probability, regex)
                VALUES ($1, $2, $3);
                """,
                channel_id,
                name,
                pattern,
                message,
                probability,
                regex,
            )


@asyncpg_error_handler
async def delete_custom_pattern(pool: Pool, channel_id: str, name: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                DELETE FROM twitch.custom_patterns
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                name,
            )


@asyncpg_error_handler
async def enable_custom_pattern(pool: Pool, channel_id: str, name: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.custom_patterns
                SET enabled = TRUE
                WHERE channel_id = $1 AND name = $1;
                """,
                channel_id,
                name,
            )


@asyncpg_error_handler
async def disable_custom_pattern(pool: Pool, channel_id: str, name: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.custom_patterns
                SET enabled = FALSE
                WHERE channel_id = $1 AND name = $1;
                """,
                channel_id,
                name,
            )
