import asyncio
from datetime import datetime, UTC
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from dotenv import load_dotenv

from output_folder import get_output_path
from shared.apis import seventv
from shared import database
from shared.database.twitch import channels, messages
from shared.util.formatting import format_timedelta


async def emote_usage(channel: str):
    con_pool = await database.init_pool(asyncio.get_event_loop(), localhost=True)
    try:
        channel_id = await channels.channel_id(con_pool, channel)
    except:
        print("Channel not found in the database")
        return
    account_info = await seventv.account_info(channel_id)
    if account_info is None:
        print("Channel doesn't have a 7tv account")
        return
    emote_names = await seventv.emote_names(channel_id)
    if len(emote_names) == 0:
        print("Channel doesn't have any 7tv emotes")
        return
    emote_frequency = await messages.emote_counts(con_pool, channel_id, emote_names)

    usage = []
    for i, emote in enumerate(emote_frequency.most_common(), 1):
        emote_info = account_info.emote_set.emote_by_name(emote[0])
        if emote_info is None:
            continue
        time_formatted = format_timedelta(emote_info.timestamp, datetime.now(UTC))
        usage.append(f"{i}. {emote[0]} — {emote[1]} — ({time_formatted})")

    output_path = get_output_path()
    file_path = os.path.abspath(os.path.join(output_path, f"{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}_{channel}_emote_usage.txt"))
    with open(file_path, "w") as file:
        file.write("\n".join(usage))


if __name__ == "__main__":
    load_dotenv()
    channel = input("Name the channel you want to get emote usage from: ")
    asyncio.run(emote_usage(channel.lower()))
