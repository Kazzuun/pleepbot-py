from functools import wraps

import asyncpg


class DatabaseError(Exception):
    def __init__(self, message, source: Exception | None = None):
        self.message = message
        self.source = source


def asyncpg_error_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except asyncpg.PostgresError as e:
            raise DatabaseError("Postgres error", e)
        # Propagate already handled exception
        except DatabaseError as e:
            raise e
        except Exception as e:
            raise DatabaseError("An unexpected error occurred", e)

    return wrapper
