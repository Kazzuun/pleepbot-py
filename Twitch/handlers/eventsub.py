import asyncio
from datetime import datetime, timedelta, UTC
import os
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands, eventsub

from shared.apis import seventv, twitch
from shared.database.twitch import channels, notifications
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


esbot = commands.Bot.from_client_credentials(
    client_id=os.environ["CLIENT_ID"], client_secret=os.environ["CLIENT_SECRET"]
)

esclient = eventsub.EventSubClient(
    esbot, webhook_secret=os.environ["WEBHOOK_SECRET"], callback_route=os.environ["CALLBACK_ROUTE_TWITCH"]
)


async def subscribe_stream_start(target_id: str | int) -> bool:
    try:
        await esclient.subscribe_channel_stream_start(broadcaster=target_id)
        return True
    except twitchio.HTTPException as e:
        logger.error("Error subscribing to eventsub live notifications for %s: %s", str(target_id), str(e))
        return False


async def subscribe_stream_end(target_id: str | int) -> bool:
    try:
        await esclient.subscribe_channel_stream_end(broadcaster=target_id)
        return True
    except twitchio.HTTPException as e:
        logger.error("Error subscribing to eventsub offline notifications for %s: %s", str(target_id), str(e))
        return False


async def subscribe_user_updated(user_id: str | int) -> bool:
    try:
        await esclient.subscribe_user_updated(user=user_id)
        return True
    except twitchio.HTTPException as e:
        logger.error("Error subscribing to eventsub user updates for %s: %s", str(user_id), str(e))
        return False


def register_eventsub_handlers(bot: "Bot") -> None:
    @esbot.event()
    async def event_eventsub_notification_stream_start(payload: eventsub.NotificationEvent) -> None:
        data: eventsub.StreamOnlineData = payload.data  # type: ignore
        logger.debug("Received a stream start event for %s", data.broadcaster.name)
        # This does nothing if the bot isn't currently in the channel
        await channels.set_online(bot.con_pool, str(data.broadcaster.id))

        channel = await twitch.user_info(user_id=str(data.broadcaster.id))
        if channel is None:
            return

        if channel.last_broadcast.started_at is not None and datetime.now(UTC) - channel.last_broadcast.started_at <= timedelta(minutes=5):
            logger.debug("%s was recently live so no notification is sent", data.broadcaster.name)
            return

        title = channel.broadcast_settings.title if channel.broadcast_settings.title is not None else "<no title>"
        category = channel.broadcast_settings.game.display_name if channel.broadcast_settings.game is not None else "<no category>"

        subs = await notifications.twitch_notifications_to_target(bot.con_pool, str(data.broadcaster.id))
        for sub in subs:
            channel_config = await channels.channel_config_from_id(bot.con_pool, sub.channel_id)
            if not channel_config.notifications_online and channel_config.currently_online:
                continue

            emote = await seventv.happy_emote(sub.channel_id)

            pings = []
            if len(sub.pings) > 0:
                users = await bot.fetch_users(ids=[int(user) for user in sub.pings])
                pings = [f"@{ping.name}" for ping in users]

            await bot.msg_q.send_message(
                channel_config.username,
                f"@{channel.username} went live streaming {category}: {title} {channel.profile_URL} {emote} {' '.join(pings)}",
            )

        

    @esbot.event()
    async def event_eventsub_notification_stream_end(payload: eventsub.NotificationEvent) -> None:
        data: eventsub.StreamOfflineData = payload.data  # type: ignore
        logger.debug("Received a stream end event for %s", data.broadcaster.name)

        target_channel = data.broadcaster.name
        if target_channel is None:
            user = await bot.fetch_users(ids=[data.broadcaster.id])
            target_channel = user[0].name

        # This does nothing if the bot isn't currently in the channel
        await channels.set_offline(bot.con_pool, str(data.broadcaster.id))

    @esbot.event()
    async def event_eventsub_notification_user_update(payload: eventsub.NotificationEvent) -> None:
        data: eventsub.UserUpdateData = payload.data  # type: ignore
        if data.user.name is None:
            logger.debug("Received a user update event for <missing name> (id: %d)", data.user.name, data.user.id)
            return
        logger.debug("Received a user update event for %s (id: %d)", data.user.name, data.user.id)

        updated_name = data.user.name.lower()
        channel_config = await channels.channel_config_from_id(bot.con_pool, str(data.user.id))
        if data.user.name is not None and channel_config.username != updated_name:
            logger.debug("User %s changed their name to %s", channel_config.username, updated_name)

            await bot.part_channels([channel_config.username])
            bot.msg_q.remove_channel(channel_config.username)

            await channels.join_channel(bot.con_pool, str(data.user.id), updated_name)

            await asyncio.sleep(5)
            await bot.join_channels([updated_name])
            bot.msg_q.add_channel(updated_name)

            await bot.msg_q.send_message(updated_name, "Stare")
