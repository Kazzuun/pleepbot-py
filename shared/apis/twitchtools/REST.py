import aiohttp
from datetime import timedelta

from .models import EmotePrefixSearch
from ..cache import async_cache
from ..exceptions import aiohttp_error_handler


__all__ = ("emotes_by_prefix",)


ENDPOINT = "https://twitch-tools.rootonline.de/api"
TIMEOUT = aiohttp.ClientTimeout(total=10)


@async_cache(timedelta(hours=2))
@aiohttp_error_handler
async def emotes_by_prefix(prefix: str, page: int = 1):
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/emotes/search/{prefix}?qc=1&qo=1&qt=0&page={page}"
        async with session.get(url) as resp:
            response = await resp.json()
            return EmotePrefixSearch(**response)
