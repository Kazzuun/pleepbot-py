from datetime import timedelta

import aiohttp

from .models import Definition
from ..cache import async_cache
from ..exceptions import aiohttp_error_handler


__all__ = ("fetch_definitions", "random_definitions")


ENDPOINT = "https://api.urbandictionary.com/v0"
TIMEOUT = aiohttp.ClientTimeout(total=7)


@aiohttp_error_handler
@async_cache(ttl=timedelta(hours=1))
async def fetch_definitions(term: str) -> list[Definition]:
    """Returns an empty list if no definitions found"""
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/define?term={term}"
        async with session.get(url, raise_for_status=True) as resp:
            response = await resp.json()
            return [Definition(**definition) for definition in response["list"]]


@aiohttp_error_handler
async def random_definitions() -> Definition:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/random"
        async with session.get(url, raise_for_status=True) as resp:
            response = await resp.json()
            return Definition(**response["list"][0])
