from asyncpg import Pool, Record
from typing import Literal

from .models import CustomCommand
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def command_exists(pool: Pool, channel_id: str, cmd_name: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: bool = await con.fetchval(
                """
                SELECT COUNT(*) > 0
                FROM twitch.custom_commands
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                cmd_name,
            )
            return result


@asyncpg_error_handler
async def list_custom_commands(pool: Pool, channel_id: str) -> list[CustomCommand]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT channel_id, name, message, level, enabled
                FROM twitch.custom_commands
                WHERE channel_id = $1;
                """,
                channel_id,
            )
            return [CustomCommand(**result) for result in results]


@asyncpg_error_handler
async def show_custom_command(pool: Pool, channel_id: str, cmd_name: str) -> CustomCommand | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT channel_id, name, message, level, enabled
                FROM twitch.custom_commands
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                cmd_name,
            )
            if result is None:
                return None
            return CustomCommand(**result)


@asyncpg_error_handler
async def add_custom_command(pool: Pool, channel_id: str, cmd_name: str, message: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.custom_commands (channel_id, name, message)
                VALUES ($1, $2, $3);
                """,
                channel_id,
                cmd_name,
                message,
            )


@asyncpg_error_handler
async def delete_custom_command(pool: Pool, channel_id: str, cmd_name: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                DELETE FROM twitch.custom_commands
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                cmd_name,
            )


@asyncpg_error_handler
async def edit_custom_command(pool: Pool, channel_id: str, cmd_name: str, new_message: str) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.custom_commands
                SET message = $1
                WHERE channel_id = $2 AND name = $3;
                """,
                new_message,
                channel_id,
                cmd_name,
            )


@asyncpg_error_handler
async def enable_custom_command(pool: Pool, channel_id: str, cmd_name: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.custom_commands
                SET enabled = TRUE
                WHERE channel_id = $1 AND name = $1;
                """,
                channel_id,
                cmd_name,
            )
            return int(result.split()[-1]) > 0


@asyncpg_error_handler
async def set_permissions(
    pool: Pool,
    channel_id: str,
    cmd_name: str,
    permission: Literal["BROADCASTER", "MOD", "VIP", "SUBSCRIBER", "FOLLOWER", "EVERYONE"],
) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                UPDATE twitch.custom_commands
                SET level = $3
                WHERE channel_id = $1 AND name = $2;
                """,
                channel_id,
                cmd_name,
                permission,
            )


@asyncpg_error_handler
async def disable_custom_command(pool: Pool, channel_id: str, cmd_name: str) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                UPDATE twitch.custom_commands
                SET enabled = FALSE
                WHERE channel_id = $1 AND name = $1;
                """,
                channel_id,
                cmd_name,
            )
            return int(result.split()[-1]) > 0
