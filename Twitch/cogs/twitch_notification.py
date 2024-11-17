import asyncio
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.database.twitch import channels, notifications
from Twitch.exceptions import ValidationError
from Twitch.handlers import eventsub
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class TwitchNotifications(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.bot.loop.run_until_complete(self.__ainit__())

    async def __ainit__(self):
        initial_channel_ids = await channels.initial_channel_ids(self.bot.con_pool)
        streams = await self.bot.fetch_streams(user_ids=[int(id) for id in initial_channel_ids])
        online_channel_ids = [str(stream.user.id) for stream in streams]
        offline_channel_ids = initial_channel_ids.difference(online_channel_ids)

        for online_channel_id in online_channel_ids:
            await channels.set_online(self.bot.con_pool, online_channel_id)

        for offline_channel_id in offline_channel_ids:
            await channels.set_offline(self.bot.con_pool, offline_channel_id)

        self.bot.loop.create_task(eventsub.esclient.listen(port=4000))
        eventsub.register_eventsub_handlers(self.bot)

        online_notification_target_ids = await notifications.twitch_notifications(self.bot.con_pool)
        online_notification_ids = initial_channel_ids.union(online_notification_target_ids)

        subs = await eventsub.esclient.get_subscriptions("enabled")

        online_subs = [sub.condition["broadcaster_user_id"] for sub in subs if sub.type == "stream.online"]
        for target_id in online_notification_ids:
            if target_id not in online_subs:
                await eventsub.subscribe_stream_start(target_id)

        offline_subs = [sub.condition["broadcaster_user_id"] for sub in subs if sub.type == "stream.offline"]
        for target_id in initial_channel_ids:
            if target_id not in offline_subs:
                await eventsub.subscribe_stream_end(target_id)

        user_update_subs = [sub.condition["user_id"] for sub in subs if sub.type == "user.update"]
        for target_id in initial_channel_ids:
            if target_id not in user_update_subs:
                await eventsub.subscribe_user_updated(target_id)

        logger.debug("Notifications ready")

    @commands.cooldown(rate=5, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def notify(self, ctx: commands.Context, target_channel: twitchio.User):
        """(Mod only) Subscribes to live notifications to target channel; {prefix}notify <target>"""
        assert isinstance(ctx.author, twitchio.Chatter)
        if not ctx.author.is_mod:
            raise ValidationError("You must be a mod to use this command")

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        success = await notifications.sub_to_twitch_notifications(
            self.bot.con_pool, channel_id, str(target_channel.id)
        )

        if not success:
            await self.bot.msg_q.reply(
                ctx,
                f"This channel is already receiving live notifications for {target_channel.name}",
                [target_channel.name],
            )
            return

        subs_to_target = await eventsub.esclient.get_subscriptions(user_id=target_channel.id)
        if len(subs_to_target) == 0:
            success = await eventsub.subscribe_stream_start(target_channel.id)
            if not success:
                await notifications.unsub_to_twitch_notifications(
                    self.bot.con_pool, channel_id, str(target_channel.id)
                )
                await self.bot.msg_q.reply(ctx, "Failed to subscribe to live notifications")
                return

        await self.bot.msg_q.reply(ctx, f"Notifying when {target_channel.name} goes live", [target_channel.name])

    @commands.cooldown(rate=5, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def unnotify(self, ctx: commands.Context, target_channel: twitchio.User):
        """(Mod only) Unsubscribes from live notifications to target channel; {prefix}unnotify <target>"""
        assert isinstance(ctx.author, twitchio.Chatter)
        if not ctx.author.is_mod:
            raise ValidationError("You must be a mod to use this command")

        # TODO: unnotify all
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        success = await notifications.unsub_to_twitch_notifications(
            self.bot.con_pool, channel_id, str(target_channel.id)
        )

        if not success:
            await self.bot.msg_q.reply(
                ctx,
                f"This channel is not subscribed to live notifications to {target_channel.name}",
                [target_channel.name],
            )
            return

        if target_channel.name not in [con.name for con in self.bot.connected_channels]:
            notifs_to_target = await notifications.twitch_notifications_to_target(
                self.bot.con_pool, str(target_channel.id)
            )
            if len(notifs_to_target) == 0:
                subs_to_target = await eventsub.esclient.get_subscriptions(user_id=target_channel.id)
                await eventsub.esclient.delete_subscription(subs_to_target[0].id)

        await self.bot.msg_q.reply(
            ctx, f"Unsubscribed from live notifications to {target_channel.name}", [target_channel.name]
        )

    @commands.command()
    async def pingme(self, ctx: commands.Context, target_channel: twitchio.User):
        """
        Makes the bot ping you whenever the target channel goes live; {prefix}pingme <channel>
        (the current channel needs to be subscribed to live notifications for the target channel)
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        notifs = await notifications.twitch_notifications_to_target(self.bot.con_pool, str(target_channel.id))
        if channel_id not in [notif.channel_id for notif in notifs]:
            await self.bot.msg_q.send(
                ctx,
                f"Current channel is not subscribed to live notifications for {target_channel.name}",
                [target_channel.name],
            )
            return

        success = await notifications.ping(self.bot.con_pool, ctx.author.id, channel_id, str(target_channel.id))
        if success:
            await self.bot.msg_q.send(
                ctx,
                f"I will ping you when {target_channel.name} goes live",
                [target_channel.name],
                notifications.unping,
                self.bot.con_pool,
                ctx.author.id,
                channel_id,
                str(target_channel.id),
            )
        else:
            await self.bot.msg_q.send(
                ctx, f"You have already made me ping you when {target_channel.name} goes live", [target_channel.name]
            )

    @commands.command()
    async def unpingme(self, ctx: commands.Context, target_channel: twitchio.User):
        """
        Makes the bot no longer ping you whenever the target channel goes live; {prefix}unpingme <channel>
        (the current channel needs to be subscribed to live notifications for the target channel)
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        notifs = await notifications.twitch_notifications_to_target(self.bot.con_pool, str(target_channel.id))
        if channel_id not in [notif.channel_id for notif in notifs]:
            await self.bot.msg_q.send(
                ctx,
                f"Current channel is not subscribed to live notifications for {target_channel.name}",
                [target_channel.name],
            )
            return

        success = await notifications.unping(self.bot.con_pool, ctx.author.id, channel_id, str(target_channel.id))
        if success:
            await self.bot.msg_q.send(
                ctx,
                f"I will no longer ping you when {target_channel.name} goes live",
                [target_channel.name],
                notifications.unping,
                self.bot.con_pool,
                ctx.author.id,
                channel_id,
                str(target_channel.id),
            )
        else:
            await self.bot.msg_q.send(ctx, "You haven't made me ping you before")


def prepare(bot: "Bot"):
    bot.add_cog(TwitchNotifications(bot))
