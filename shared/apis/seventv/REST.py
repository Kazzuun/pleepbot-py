import aiohttp
from datetime import timedelta
import random
import re
from typing import Callable

from .models import Emote, EmoteSet, Subage, TwitchUser, User
from ..cache import async_cache
from ..exceptions import aiohttp_error_handler


__all__ = (
    "global_emote_set",
    "emote_set_from_id",
    "account_info",
    "emote_names",
    "emote_from_id",
    "user_from_id",
    "subage",
    "best_fitting_emote",
    "happy_emote",
    "sad_emote",
    "is_valid_id",
)


ENDPOINT = "https://7tv.io/v3"
TIMEOUT = aiohttp.ClientTimeout(total=7)


async def global_emote_set() -> EmoteSet:
    return await emote_set_from_id("global")


@aiohttp_error_handler
@async_cache(timedelta(hours=3))
async def emote_set_from_id(emote_set_id: str, *, force_cache: bool = False) -> EmoteSet:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/emote-sets/{emote_set_id}"
        async with session.get(url, raise_for_status=True) as resp:
            response = await resp.json()
            return EmoteSet(**response)


@aiohttp_error_handler
@async_cache(timedelta(hours=3))
async def account_info(twitch_id: str, *, force_cache: bool = False) -> TwitchUser | None:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/users/twitch/{twitch_id}"
        async with session.get(url) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            response = await resp.json()
            return TwitchUser(**response)


async def emote_names(twitch_id: str, *, force_cache: bool = False, include_global: bool = False) -> list[str]:
    user_info = await account_info(twitch_id, force_cache=force_cache)
    emotes = []
    if user_info is not None:
        emotes.extend([emote.name for emote in user_info.emote_set.emotes])
    if include_global:
        global_emotes = await global_emote_set()
        emotes.extend([emote.name for emote in global_emotes.emotes])
    return emotes


@aiohttp_error_handler
@async_cache(timedelta(hours=3))
async def emote_from_id(emote_id: str, *, force_cache: bool = False) -> Emote:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/emotes/{emote_id}"
        async with session.get(url, raise_for_status=True) as resp:
            response = await resp.json()
            return Emote(**response)


@aiohttp_error_handler
@async_cache(timedelta(hours=3))
async def user_from_id(seventv_user_id: str, *, force_cache: bool = False) -> User:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/users/{seventv_user_id}"
        async with session.get(url, raise_for_status=True) as resp:
            response = await resp.json()
            return User(**response)


@aiohttp_error_handler
@async_cache(timedelta(hours=3))
async def subage(seventv_user_id: str, *, force_cache: bool = False) -> Subage:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"https://7tv.io/egvault/v1/subscriptions/{seventv_user_id}"
        async with session.get(url, raise_for_status=True) as resp:
            response = await resp.json()
            return Subage(**response)


async def best_fitting_emote(
    channel_id: str,
    filter_func: Callable[[str], bool],
    *,
    default: str = "",
    include_global: bool = False,
) -> str:
    emotes = []

    if include_global:
        global_emotes = await global_emote_set()
        emotes.extend(global_emotes.emotes)

    account = await account_info(channel_id)
    if account is not None:
        emotes.extend(account.emote_set.emotes)

    filtered_emotes = [emote.name for emote in emotes if filter_func(emote.name)]
    if len(filtered_emotes) == 0:
        return default
    return random.choice(filtered_emotes)


async def happy_emote(channel_id: str, *, default: str = "peepoHappy", include_global: bool = False) -> str:
    emote = await best_fitting_emote(
        channel_id,
        lambda emote: (
            any(e in emote.lower() for e in ("happ", "wow", ":3")) or ("YAA" in emote and emote.endswith("Y"))
        )
        and "happyb" not in emote.lower(),
        default=default,
        include_global=include_global,
    )
    return emote


async def sad_emote(channel_id: str, *, default: str = "peepoSad", include_global: bool = False) -> str:
    emote = await best_fitting_emote(
        channel_id,
        lambda emote: ("sad" in emote.lower() or "cry" in emote.lower()) and not "jam" in emote.lower(),
        default=default,
        include_global=include_global,
    )
    return emote


def is_valid_id(seventv_id: str) -> bool:
    return bool(re.match(r"^[0-9A-Z]{26}$", seventv_id)) or bool(re.match(r"^[0-9a-fA-F]{24}$", seventv_id))
