import asyncio
from functools import wraps

import aiohttp
from gql.transport.exceptions import TransportQueryError, TransportServerError


# TODO: add a function to use the api with fallback or just return None if it times out

class APIRequestError(Exception):
    def __init__(self, message: str, source: Exception | None = None):
        self.message = message
        self.source = source


class SendableAPIRequestError(APIRequestError):
    def __init__(self, message: str, source: Exception | None = None):
        super().__init__(message, source)


def aiohttp_error_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except aiohttp.ClientConnectionError as e:
            raise APIRequestError("Connection error", e)
        except aiohttp.ClientResponseError as e:
            raise SendableAPIRequestError(f"An api request failed: {e.message} (status: {e.status})", e)
        except aiohttp.ClientPayloadError as e:
            raise APIRequestError("Payload error", e)
        except asyncio.TimeoutError as e:
            raise SendableAPIRequestError("Request timed out. Try again later", e)
        # Propagate already handled exception
        except APIRequestError as e:
            raise e
        except Exception as e:
            raise APIRequestError("An unexpected error occurred", e)

    return wrapper


def gql_error_handler(fetch: bool = True):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            action = f"{'fetch' if fetch else ''} {func.__name__.replace('_', ' ')}"
            try:
                return await func(*args, **kwargs)
            except TransportQueryError as e:
                if e.errors is None or len(e.errors) == 0:
                    message = "no reason given"
                else:
                    message = e.errors[0]["message"].lower()
                    # Remove possible unnecessary id of the error
                    if message.split()[0].isdigit():
                        message = " ".join(message.split()[1:])
                raise SendableAPIRequestError(f"Failed to {action} ({message})", e)
            except TransportServerError as e:
                raise SendableAPIRequestError(f"Failed to {action} (server error: {e.code})", e)
            except asyncio.TimeoutError as e:
                raise SendableAPIRequestError(f"Failed to {action} (request timed out)", e)
            # Propagate already handled exception
            except APIRequestError as e:
                raise e
            except Exception as e:
                raise APIRequestError("An unexpected error occurred", e)

        return wrapper

    return decorator
