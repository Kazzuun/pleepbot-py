import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv

from shared.apis import google
from shared import database
from shared.database.twitch import locations


async def set_location(user_id: str, address: str):
    location = await google.geocode(address)
    if location is None:
        print("Location was not found")
        return
    print(f"Setting location to {location.formatted_address}")

    con_pool = await database.init_pool(asyncio.get_event_loop(), localhost=True)
    await locations.set_location(
        con_pool,
        user_id,
        location.geometry.location.latitude,
        location.geometry.location.longitude,
        location.formatted_address,
    )


if __name__ == "__main__":
    load_dotenv()
    user_id = input("User id: ")
    address = input("Address: ")
    asyncio.run(set_location(user_id, address))
