from datetime import datetime
from typing import Literal

from asyncpg import Pool, Record

from .models import Reminder, AfkStatus
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def set_reminder(
    pool: Pool,
    channel_id: str,
    sender_id: str,
    target_id: str,
    message: str | None,
    scheduled_at: datetime | None,
    delete_after: bool = False,
) -> int | None:
    async with pool.acquire() as con:
        async with con.transaction():
            if delete_after:
                await con.execute(
                    """
                    DELETE FROM twitch.reminders
                    WHERE
                        channel_id = $1 AND
                        sender_id = $2 AND
                        message = $3 AND
                        processed_at IS NULL AND
                        delete_after IS TRUE;
                    """,
                    channel_id,
                    sender_id,
                    message,
                )

            id: int | None = await con.fetchval(
                """
                INSERT INTO twitch.reminders (channel_id, sender_id, target_id, message, scheduled_at, delete_after)
                SELECT $1, $2, $3, $4, $5, $6
                WHERE (
                    SELECT COUNT(*)
                    FROM twitch.reminders
                    WHERE
                        target_id = $3 AND
                        scheduled_at IS NULL AND
                        processed_at IS NULL
                ) < 10
                RETURNING id;
                """,
                channel_id,
                sender_id,
                target_id,
                message,
                scheduled_at,
                delete_after,
            )
            return id


@asyncpg_error_handler
async def cancel_reminder(pool: Pool, reminder_id: int) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.reminders
                SET cancelled = TRUE, processed_at = CURRENT_TIMESTAMP
                WHERE id = $1 AND processed_at IS NULL;
                """,
                reminder_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def cancel_reminder_check_sender(pool: Pool, reminder_id: int, sender_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.reminders
                SET cancelled = TRUE, processed_at = CURRENT_TIMESTAMP
                WHERE id = $1 AND sender_id = $2 AND processed_at IS NULL;
                """,
                reminder_id,
                sender_id,
            )
            return int(result.split()[-1]) > 0


# @asyncpg_error_handler
# async def cancel_all_reminders_by(pool: Pool, sender_id: str) -> int:
#     async with pool.acquire() as con:
#         async with con.transaction():
#             result: str = await con.execute(
#                 """
#                 UPDATE twitch.reminders
#                 SET cancelled = TRUE, processed_at = CURRENT_TIMESTAMP
#                 WHERE sender_id = $1 AND processed_at IS NULL;
#                 """,
#                 sender_id,
#             )
#             return int(result.split()[-1])


# @asyncpg_error_handler
# async def cancel_all_reminders_to(pool: Pool, target_id: str) -> int:
#     async with pool.acquire() as con:
#         async with con.transaction():
#             result: str = await con.execute(
#                 """
#                 UPDATE twitch.reminders
#                 SET cancelled = TRUE, processed_at = CURRENT_TIMESTAMP
#                 WHERE target_id = $1 AND processed_at IS NULL;
#                 """,
#                 target_id,
#             )
#             return int(result.split()[-1])


@asyncpg_error_handler
async def uncancel_reminder(pool: Pool, reminder_id: int) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.reminders
                SET cancelled = FALSE, processed_at = NULL
                WHERE id = $1;
                """,
                reminder_id,
            )


@asyncpg_error_handler
async def set_reminder_as_sent(pool: Pool, reminder_id: int) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.reminders
                SET sent = TRUE, processed_at = CURRENT_TIMESTAMP
                WHERE id = $1 AND processed_at IS NULL;
                """,
                reminder_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def sendable_timed_reminders(pool: Pool) -> list[Reminder]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT 
                    id,
                    channel_id,
                    sender_id,
                    target_id,
                    message,
                    created_at,
                    scheduled_at
                FROM twitch.reminders
                WHERE 
                    scheduled_at IS NOT NULL AND
                    scheduled_at < CURRENT_TIMESTAMP AND
                    processed_at IS NULL;
                """
            )
            return [Reminder(**result) for result in results]


@asyncpg_error_handler
async def sendable_not_timed_reminders(pool: Pool, target_id: str) -> list[Reminder]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT
                    id,
                    channel_id,
                    sender_id,
                    target_id,
                    message,
                    created_at,
                    scheduled_at
                FROM twitch.reminders
                WHERE
                    target_id = $1 AND
                    created_at < CURRENT_TIMESTAMP - INTERVAL '5 seconds' AND
                    scheduled_at IS NULL AND
                    processed_at IS NULL;
                """,
                target_id,
            )
            return [Reminder(**result) for result in results]


@asyncpg_error_handler
async def set_afk(pool: Pool, channel_id: str, target_id: str, afk_type: Literal["AFK", "GN", "WORK"]) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.afks (channel_id, target_id, kind)
                SELECT $1, $2, $3
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM twitch.afks
                    WHERE
                        channel_id = $1 AND
                        target_id = $2 AND
                        processed_at IS NULL
                );
                """,
                channel_id,
                target_id,
                afk_type,
            )


@asyncpg_error_handler
async def afk_status(pool: Pool, channel_id: str, target_id: str) -> AfkStatus | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT
                    id,
                    channel_id,
                    target_id,
                    kind,
                    created_at
                FROM twitch.afks
                WHERE
                    channel_id = $1 AND
                    target_id = $2 AND
                    created_at < CURRENT_TIMESTAMP - INTERVAL '5 seconds' AND
                    processed_at IS NULL;
                """,
                channel_id,
                target_id,
            )
            if result is None:
                return None
            return AfkStatus(**result)


@asyncpg_error_handler
async def set_afk_as_sent(pool: Pool, afk_id: int) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.afks
                SET processed_at = CURRENT_TIMESTAMP
                WHERE id = $1 AND processed_at IS NULL;
                """,
                afk_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def continue_afk(pool: Pool, channel_id: str, target_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.afks
                SET processed_at = NULL
                WHERE id = (
                    SELECT id
                    FROM twitch.afks
                    WHERE
                        channel_id = $1 AND
                        target_id = $2 AND
                        processed_at > CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                    ORDER BY processed_at DESC
                    LIMIT 1
                ) AND (
                    SELECT COUNT(*)
                    FROM twitch.afks 
                    WHERE
                        channel_id = $1 AND
                        target_id = $2 AND
                        processed_at IS NULL
                ) = 0;
                """,
                channel_id,
                target_id,
            )
            return int(result.split()[-1]) > 0
