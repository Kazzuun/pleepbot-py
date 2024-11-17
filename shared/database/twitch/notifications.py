from asyncpg import Pool, Record

from .models import LiveNotification, YoutubeUploadNotification
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def twitch_notifications(pool: Pool) -> set[str]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT DISTINCT target_id 
                FROM twitch.live_notifications;
                """
            )
            return set(result["target_id"] for result in results)


@asyncpg_error_handler
async def twitch_notifications_to_target(pool: Pool, target_id: str) -> list[LiveNotification]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT channel_id, target_id, pings 
                FROM twitch.live_notifications
                WHERE target_id = $1;
                """,
                target_id,
            )
            return [LiveNotification(**result) for result in results]


@asyncpg_error_handler
async def sub_to_twitch_notifications(pool: Pool, channel_id: str, target_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                INSERT INTO twitch.live_notifications (channel_id, target_id)
                VALUES ($1, $2)
                ON CONFLICT (channel_id, target_id)
                DO NOTHING;
                """,
                channel_id,
                target_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def unsub_to_twitch_notifications(pool: Pool, channel_id: str, target_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                DELETE FROM twitch.live_notifications
                WHERE channel_id = $1 AND target_id = $2;
                """,
                channel_id,
                target_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def ping(pool: Pool, user_id: str, channel_id: str, target_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.live_notifications
                SET pings = array_append(pings, $1)
                WHERE channel_id = $2 AND target_id = $3 AND NOT $1 = ANY(pings);
                """,
                user_id,
                channel_id,
                target_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def unping(pool: Pool, user_id: str, channel_id: str, target_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.live_notifications
                SET pings = array_remove(pings, $1)
                WHERE channel_id = $2 AND target_id = $3 AND $1 = ANY(pings);
                """,
                user_id,
                channel_id,
                target_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def youtube_notifications(pool: Pool) -> list[YoutubeUploadNotification]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT channel_id, playlist_id, pings 
                FROM twitch.yt_upload_notifications;
                """
            )
            return [YoutubeUploadNotification(**result) for result in results]


@asyncpg_error_handler
async def sub_to_youtube_notifications(pool: Pool, channel_id: str, playlist_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                INSERT INTO twitch.yt_upload_notifications (channel_id, playlist_id)
                VALUES ($1, $2)
                ON CONFLICT (channel_id, playlist_id)
                DO NOTHING;
                """,
                channel_id,
                playlist_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def unsub_to_youtube_notifications(pool: Pool, channel_id: str, playlist_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                DELETE FROM twitch.yt_upload_notifications
                WHERE channel_id = $1 AND playlist_id = $2;
                """,
                channel_id,
                playlist_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def ytping(pool: Pool, user_id: str, channel_id: str, playlist_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.yt_upload_notifications
                SET pings = array_append(pings, $1)
                WHERE channel_id = $2 AND playlist_id = $3 AND NOT $1 = ANY(pings);
                """,
                user_id,
                channel_id,
                playlist_id,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def ytunping(pool: Pool, user_id: str, channel_id: str, playlist_id: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.yt_upload_notifications
                SET pings = array_remove(pings, $1)
                WHERE channel_id = $2 AND playlist_id = $3 AND $1 = ANY(pings);
                """,
                user_id,
                channel_id,
                playlist_id,
            )
            return int(result.split()[-1]) > 0
