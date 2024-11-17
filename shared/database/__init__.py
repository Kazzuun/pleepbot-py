import asyncio
import os

import asyncpg


async def init_pool(loop: asyncio.AbstractEventLoop, *, localhost: bool = False) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        database=os.environ["PGDATABASE"],
        host="localhost" if localhost else os.environ["PGHOST"],
        port=os.environ["PGPORT"],
        min_size=2,
        max_size=10,
        loop=loop,
    )
    assert pool is not None
    return pool
