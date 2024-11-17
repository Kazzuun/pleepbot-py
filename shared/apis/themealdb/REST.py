import aiohttp

from .models import Meal
from ..exceptions import aiohttp_error_handler


__all__ = ("random_meal",)


ENDPOINT = "https://www.themealdb.com/api/json/v1/1"
TIMEOUT = aiohttp.ClientTimeout(total=7)


@aiohttp_error_handler
async def random_meal() -> Meal:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/random.php"
        async with session.get(url, raise_for_status=True) as resp:
            response = await resp.json()
            return Meal(**response["meals"][0])
