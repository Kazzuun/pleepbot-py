from collections import Counter
import os

from asyncpg import Pool, Record

from .models import BlockedTerm, Message
from shared.database.exceptions import asyncpg_error_handler


@asyncpg_error_handler
async def random_message(
    pool: Pool,
    channel_id: str,
    sender: str | None,
    *,
    included_words: list[str],
    excluded_words: list[str],
    min_word_count: int | None,
    max_word_count: int | None,
    exclude_commands: bool = True,
    prefixes: tuple[str, ...] | None = None,
) -> Message | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            params: list[str | int] = [channel_id]
            query = """
                SELECT channel_id, sender, message, sent_at 
                FROM twitch.messages
                WHERE channel_id = $1
            """

            if sender is None:
                ...
            else:
                query += " AND sender = $2"
                params.append(sender)

            if len(included_words) + len(excluded_words) > 0:
                query += f" AND to_tsvector('english', message) @@ to_tsquery('english', ${len(params)+1})"
                search_query = " & ".join(
                    [word.lstrip("!") for word in included_words] + [f"!{word}" for word in excluded_words]
                )
                params.append(search_query)

            if min_word_count is not None:
                query += f" AND ARRAY_LENGTH(STRING_TO_ARRAY(message, ' '), 1) > ${len(params)+1}"
                params.append(min_word_count)

            if max_word_count is not None:
                query += f" AND ARRAY_LENGTH(STRING_TO_ARRAY(message, ' '), 1) < ${len(params)+1}"
                params.append(max_word_count)

            if exclude_commands and prefixes is not None and len(prefixes) > 0:
                for prefix in prefixes:
                    query += f" AND NOT message LIKE ${len(params)+1}"
                    params.append(prefix.replace("%", r"\%") + "%")

            query += " ORDER BY RANDOM() LIMIT 1;"

            result: Record | None = await con.fetchrow(query, *params)
            if result is None:
                return None
            return Message(**result)


@asyncpg_error_handler
async def number_of_messages(
    pool: Pool,
    channel_id: str,
    sender: str | None,
    *,
    included_words: list[str],
    excluded_words: list[str],
    min_word_count: int | None,
    max_word_count: int | None,
    exclude_commands: bool = False,
    prefixes: tuple[str, ...] | None = None,
) -> int:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            params: list[str | int] = [channel_id]
            query = "SELECT COUNT(*) FROM twitch.messages WHERE channel_id = $1"

            if sender is not None:
                query += " AND sender = $2"
                params.append(sender)

            if len(included_words) + len(excluded_words) > 0:
                query += f" AND to_tsvector('english', message) @@ to_tsquery('english', ${len(params)+1})"
                search_query = " & ".join(
                    [word.lstrip("!") for word in included_words] + [f"!{word}" for word in excluded_words]
                )
                params.append(search_query)

            if min_word_count is not None:
                query += f" AND ARRAY_LENGTH(STRING_TO_ARRAY(message, ' '), 1) > ${len(params)+1}"
                params.append(min_word_count)

            if max_word_count is not None:
                query += f" AND ARRAY_LENGTH(STRING_TO_ARRAY(message, ' '), 1) < ${len(params)+1}"
                params.append(max_word_count)

            if exclude_commands and prefixes is not None and len(prefixes) > 0:
                for prefix in prefixes:
                    query += f" AND NOT message LIKE ${len(params)+1}"
                    params.append(prefix.replace("%", r"\%") + "%")

            result: int = await con.fetchval(query, *params)
            return result


@asyncpg_error_handler
async def top_chatters(pool: Pool, channel_id: str) -> Counter[str]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results: list[Record] = await con.fetch(
                """
                SELECT sender, COUNT(*) AS count
                FROM twitch.messages
                WHERE channel_id = $1
                GROUP BY sender;
                """,
                channel_id,
            )
            return Counter({result["sender"]: result["count"] for result in results})


@asyncpg_error_handler
async def emote_count(pool: Pool, channel_id: str, emote: str) -> int:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: int = await con.fetchval(
                """
                SELECT SUM((LENGTH(message) - LENGTH(REGEXP_REPLACE(message, '\\y' || $2 || '\\y', '', 'g'))) / LENGTH($2))
                FROM twitch.messages
                WHERE channel_id = $1 AND sender != $2;
                """,
                channel_id,
                emote,
                os.environ["BOT_NICK"],
            )
            return result


@asyncpg_error_handler
async def emote_counts(pool: Pool, channel_id: str, emotes: list[str]) -> Counter[str]:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            results = await con.fetch(
                """
                SELECT message
                FROM twitch.messages
                WHERE channel_id = $1 AND sender != $2;
                """,
                channel_id,
                os.environ["BOT_NICK"],
            )
            words = [word for sublist in [result["message"].split() for result in results] for word in sublist]
            word_frequency = Counter(words)
            emote_frequency = {emote: word_frequency[emote] if emote in word_frequency else 0 for emote in emotes}
            return Counter(emote_frequency)


@asyncpg_error_handler
async def last_seen(pool: Pool, channel_id: str, user: str) -> Message | None:
    async with pool.acquire() as con:
        async with con.transaction(readonly=True):
            result: Record | None = await con.fetchrow(
                """
                SELECT channel_id, sender, message, sent_at
                FROM twitch.messages
                WHERE channel_id = $1 AND sender = $2
                ORDER BY sent_at DESC
                LIMIT 1;
                """,
                channel_id,
                user,
            )
            if result is None:
                return None
            return Message(**result)


@asyncpg_error_handler
async def log_message(pool: Pool, channel_id: str, sender: str, message: str, channel_online: bool) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.messages (channel_id, sender, message, online)
                VALUES ($1, $2, $3, $4);
                """,
                channel_id,
                sender,
                message,
                channel_online,
            )


@asyncpg_error_handler
async def log_command_usage(
    pool: Pool, channel_id: str, user_id: str, command: str, message: str, use_time_ms: float
) -> None:
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                """
                INSERT INTO twitch.command_usage_log (channel_id, user_id, command, message, use_time_ms)
                VALUES ($1, $2, $3, $4, $5);
                """,
                channel_id,
                user_id,
                command,
                message,
                use_time_ms,
            )


@asyncpg_error_handler
async def blocked_terms(pool: Pool) -> list[BlockedTerm]:
    async with pool.acquire() as con:
        async with con.transaction():
            results: list[Record] = await con.fetch(
                """
                SELECT id, pattern, regex
                FROM twitch.blocked_terms;
                """
            )
            return [BlockedTerm(**result) for result in results]


@asyncpg_error_handler
async def blocked_term(pool: Pool, id: int) -> BlockedTerm | None:
    async with pool.acquire() as con:
        async with con.transaction():
            result: Record | None = await con.fetchrow(
                """
                SELECT id, pattern, regex
                FROM twitch.blocked_terms
                WHERE id = $1;
                """,
                id,
            )
            if result is None:
                return None
            return BlockedTerm(**result)


@asyncpg_error_handler
async def add_blocked_term(pool: Pool, pattern: str, regex: bool) -> int:
    async with pool.acquire() as con:
        async with con.transaction():
            result: int = await con.fetchval(
                """
                INSERT INTO twitch.blocked_terms (pattern, regex)
                VALUES ($1, $2)
                RETURNING id;
                """,
                pattern,
                regex,
            )
            return result


@asyncpg_error_handler
async def delete_blocked_term(pool: Pool, id: int) -> bool:
    async with pool.acquire() as con:
        async with con.transaction():
            result: str = await con.execute(
                """
                DELETE FROM twitch.blocked_terms
                WHERE id = $1;
                """,
                id,
            )
            return int(result.split()[-1]) > 0
