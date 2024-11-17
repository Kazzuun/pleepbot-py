from asyncpg import Pool, Record

from .models import Counter
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def list_counters(pool: Pool, channel_id: str) -> list[Counter]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT channel_id, name, value 
                FROM twitch.counters
                WHERE channel_id = $1;
                """,
                channel_id,
            )
            return [Counter(**result) for result in results]


@asyncpg_error_handler
async def show_counter(pool: Pool, channel_id: str, name: str) -> Counter:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT channel_id, name, value 
                FROM twitch.counters
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                name,
            )
            if result is None:
                return Counter(channel_id=channel_id, name=name)
            return Counter(**result)


@asyncpg_error_handler
async def change_counter(pool: Pool, channel_id: str, name: str, change: int) -> Counter:
    async with pool.acquire() as con:
        async with con.transaction():
            result: Record = await con.fetchrow(
                """
                INSERT INTO twitch.counters (channel_id, name, value)
                VALUES ($1, $2, $3)
                ON CONFLICT (channel_id, name)
                DO UPDATE SET value = twitch.counters.value + $3
                RETURNING channel_id, name, value;
                """,
                channel_id,
                name,
                change,
            )
            return Counter(**result)


@asyncpg_error_handler
async def set_counter(pool: Pool, channel_id: str, name: str, value: int) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.counters
                VALUES ($1, $2, $3)
                ON CONFLICT (channel_id, name)
                DO UPDATE SET value = $3;
                """,
                channel_id,
                name,
                value,
            )


async def reset_counter(pool: Pool, channel_id: str, name: str) -> None:
    await set_counter(pool, channel_id, name, 0)
