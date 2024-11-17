from typing import Literal

from asyncpg import Pool, Record

from .models import FightStats, LastIq, RpsStats
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def random_fortune(pool: Pool) -> str | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT fortune 
                FROM twitch.fortunes
                ORDER BY RANDOM()
                LIMIT 1;
                """
            )
            if result is None:
                return None
            return result["fortune"]


@asyncpg_error_handler
async def last_iq(pool: Pool, user_id: str) -> LastIq | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT user_id, last_iq, last_updated
                FROM twitch.last_iqs
                WHERE user_id = $1;
                """,
                user_id,
            )
            if result is None:
                return None
            return LastIq(**result)


@asyncpg_error_handler
async def update_last_iq(pool: Pool, user_id: str, new_iq: int) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.last_iqs (user_id, last_iq, last_updated)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET 
                    last_iq = EXCLUDED.last_iq, 
                    last_updated = EXCLUDED.last_updated;
                """,
                user_id,
                new_iq,
            )


@asyncpg_error_handler
async def list_iqs(pool: Pool, top: bool = True) -> list[LastIq]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                f"""
                SELECT user_id, last_iq, last_updated
                FROM twitch.last_iqs
                ORDER BY last_iq {"DESC" if top else "ASC"};
                """
            )
            return [LastIq(**result) for result in results]


@asyncpg_error_handler
async def rps(pool: Pool, user_id: str, outcome: Literal["win", "draw", "loss"]) -> RpsStats:
    async with pool.acquire() as con:
        async with con.transaction():
            match outcome:
                case "win":
                    result: Record = await con.fetchrow(
                        """
                        INSERT INTO twitch.rps (user_id, wins)
                        VALUES ($1, 1)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET wins = twitch.rps.wins + 1
                        RETURNING user_id, wins, draws, losses;
                        """,
                        user_id,
                    )
                case "draw":
                    result: Record = await con.fetchrow(
                        """
                        INSERT INTO twitch.rps (user_id, draws)
                        VALUES ($1, 1)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET draws = twitch.rps.draws + 1
                        RETURNING user_id, wins, draws, losses;
                        """,
                        user_id,
                    )
                case "loss":
                    result: Record = await con.fetchrow(
                        """
                        INSERT INTO twitch.rps (user_id, losses)
                        VALUES ($1, 1)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET losses = twitch.rps.losses + 1
                        RETURNING user_id, wins, draws, losses;
                        """,
                        user_id,
                    )
            return RpsStats(**result)


@asyncpg_error_handler
async def fight(pool: Pool, user_id_1: str, user_id_2: str, winner_id: str) -> FightStats:
    async with pool.acquire() as con:
        async with con.transaction():
            users = sorted([user_id_1, user_id_2])

            if users[0] == winner_id:
                result: Record = await con.fetchrow(
                    """
                    INSERT INTO twitch.fights (user_id_1, user_id_2, user_1_wins)
                    VALUES ($1, $2, 1) 
                    ON CONFLICT (user_id_1, user_id_2) 
                    DO UPDATE SET user_1_wins = twitch.fights.user_1_wins + 1
                    RETURNING user_id_1, user_id_2, user_1_wins, user_2_wins;
                    """,
                    users[0],
                    users[1],
                )
            else:
                result: Record = await con.fetchrow(
                    """
                    INSERT INTO twitch.fights (user_id_1, user_id_2, user_2_wins)
                    VALUES ($1, $2, 1) 
                    ON CONFLICT (user_id_1, user_id_2) 
                    DO UPDATE SET user_2_wins = twitch.fights.user_2_wins + 1
                    RETURNING user_id_1, user_id_2, user_1_wins, user_2_wins;
                    """,
                    users[0],
                    users[1],
                )
            return FightStats(**result)
