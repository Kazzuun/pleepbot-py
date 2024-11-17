from asyncpg import Pool, Record

from .models import Location


async def set_location(pool: Pool, user_id: str, latitude: float, longitude: float, address: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.locations (user_id, latitude, longitude, address)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    address = EXCLUDED.address
                """,
                user_id,
                latitude,
                longitude,
                address,
            )


async def user_location(pool: Pool, user_id: str) -> Location | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT user_id, latitude, longitude, address, private
                FROM twitch.locations
                WHERE user_id = $1;
                """,
                user_id,
            )
            if result is None:
                return None
            return Location(**result)


async def delete(pool: Pool, user_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                DELETE FROM twitch.locations
                WHERE user_id = $1;
                """,
                user_id,
            )
            return int(result.split()[-1]) > 0


async def set_location_private(pool: Pool, user_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.locations
                SET private = TRUE
                WHERE user_id = $1;
                """,
                user_id,
            )
            return int(result.split()[-1]) > 0


async def set_location_public(pool: Pool, user_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.locations
                SET private = FALSE
                WHERE user_id = $1;
                """,
                user_id,
            )
            return int(result.split()[-1]) > 0
