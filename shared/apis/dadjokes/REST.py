import aiohttp

from .models import Dadjoke
from shared.apis.exceptions import aiohttp_error_handler


__all__ = ("random_dadjoke",)


ENDPOINT = "https://icanhazdadjoke.com/"
TIMEOUT = aiohttp.ClientTimeout(total=7)
HEADERS = {"Accept": "application/json"}


@aiohttp_error_handler
async def random_dadjoke() -> Dadjoke:
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
        async with session.get(ENDPOINT, raise_for_status=True) as resp:
            response = await resp.json()
            joke = Dadjoke(**response)
            return joke
