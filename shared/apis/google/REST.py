from datetime import timedelta
import os

import aiohttp

from .models import Geolocation, Translation
from ..cache import async_cache
from ..exceptions import aiohttp_error_handler, APIRequestError, SendableAPIRequestError


TIMEOUT = aiohttp.ClientTimeout(total=10)
HEADERS = {"content-type": "application/json"}


@async_cache(timedelta(hours=3))
@aiohttp_error_handler
async def geocode(address: str) -> Geolocation | None:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={os.environ['GOOGLE_API_KEY']}"
        async with session.get(url) as resp:
            response = await resp.json()
            if response["status"] == "ZERO_RESULTS":
                return None
            elif response["status"] == "OK":
                return Geolocation(**response["results"][0])
            else:
                raise APIRequestError(response["status"])


@async_cache(timedelta(hours=1))
@aiohttp_error_handler
async def air_quality(lat: float, lon: float) -> tuple[str, str] | None:
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
        url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={os.environ['GOOGLE_API_KEY']}"
        data = {"location": {"latitude": lat, "longitude": lon}}
        async with session.post(url, json=data) as resp:
            response = await resp.json()
            if "error" in response:
                return None
            aqi = response["indexes"][0]["aqi"]
            if aqi >= 80:
                color = "🔵"
            elif aqi >= 60:
                color = "🟢"
            elif aqi >= 40:
                color = "🟡"
            elif aqi >= 20:
                color = "🟠"
            elif aqi >= 5:
                color = "🔴"
            else:
                color = "💀"
            return (response["indexes"][0]["category"], color)


@aiohttp_error_handler
async def translate(query: str, target: str = "en", source: str | None = None) -> Translation:
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
        url = "https://translation.googleapis.com/language/translate/v2"
        data = {
            "q": query,
            "target": target,
            "format": "text",
            "key": os.environ['GOOGLE_API_KEY'],
        }
        if source is not None:
            data["source"] = source
        async with session.get(url, params=data) as resp:
            if resp.status == 400:
                raise SendableAPIRequestError("Error: Invalid language code")
            response = await resp.json()
            if "error" in response:
                raise APIRequestError(response["error"])
            translations = response["data"]["translations"]
            return Translation(**translations[0])
