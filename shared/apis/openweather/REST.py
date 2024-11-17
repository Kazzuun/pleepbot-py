import aiohttp
from datetime import timedelta
import os
from typing import Literal

from .models import CurrentWeather
from ..cache import async_cache
from ..exceptions import aiohttp_error_handler


__all__ = ("current_weather",)


ENDPOINT = "https://api.openweathermap.org"
TIMEOUT = aiohttp.ClientTimeout(total=10)


@async_cache(timedelta(minutes=30))
@aiohttp_error_handler
async def current_weather(
    latitude: float, longitude: float, units: Literal["standard", "metric", "imperial"] = "metric"
) -> CurrentWeather:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{ENDPOINT}/data/2.5/weather?lat={latitude}&lon={longitude}&appid={os.environ['OPEN_WEATHER_MAP_KEY']}&units={units}"
        async with session.get(url) as resp:
            response = await resp.json()
            return CurrentWeather(**response)
