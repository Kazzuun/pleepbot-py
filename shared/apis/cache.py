import copy
from datetime import datetime, timedelta, UTC
from functools import wraps
import random
from typing import Any


cache: dict[tuple, tuple[Any, datetime]] = {}

last_cleaned = datetime.now(UTC)
cleanup_interval = timedelta(minutes=5)


def cleanup_cache() -> None:
    for key, (_, expiration_time) in cache.copy().items():
        if expiration_time < datetime.now(UTC):
            del cache[key]


def async_cache(ttl: timedelta):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, force_cache: bool = False, **kwargs):
            global last_cleaned

            if last_cleaned + cleanup_interval < datetime.now(UTC):
                cleanup_cache()
                last_cleaned = datetime.now(UTC)

            cache_key = (func.__name__, *args)

            if not force_cache and cache_key in cache:
                result, expiration_time = cache[cache_key]
                if datetime.now(UTC) < expiration_time:
                    # Return deep copies of the cached value to avoid sharing the same mutable objects
                    return copy.deepcopy(result)

            result = await func(*args, **kwargs)

            expiration_time = datetime.now(UTC) + ttl
            jitter = random.randint(-int(ttl.total_seconds() / 3), int(ttl.total_seconds() / 3))
            expiration_time += timedelta(seconds=jitter)
            cache[cache_key] = (result, expiration_time)

            return result
        return wrapper
    return decorator
