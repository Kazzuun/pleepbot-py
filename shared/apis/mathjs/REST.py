import aiohttp

from ..exceptions import aiohttp_error_handler


__all__ = ("evaluate",)


ENDPOINT = "http://api.mathjs.org/v4/"
TIMEOUT = aiohttp.ClientTimeout(total=7)
HEADERS = {"content-type": "application/json"}


@aiohttp_error_handler
async def evaluate(expression: str, precision: int = 5) -> str:
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as session:
        data = {"expr": expression, "precision": precision}
        async with session.post(ENDPOINT, json=data) as resp:
            response = await resp.json()
            if response["error"] is None:
                return response["result"]
            else:
                return response["error"]
