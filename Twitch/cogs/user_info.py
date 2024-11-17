from datetime import datetime, timedelta, UTC
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands, routines

from shared.apis import twitch
from shared.database.twitch import channels, users
from shared.util.formatting import format_timedelta
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class UserInfo(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.add_watch_time.start(stop_on_error=False)

    @routines.routine(seconds=10, wait_first=True)
    async def add_watch_time(self):
        for channel in self.bot.connected_channels:
            if channel.chatters is None:
                logger.warning("Unable to get channel chatters for #%s", channel.name)
                continue

            channel_config = await channels.channel_config(self.bot.con_pool, channel.name)
            if self.watchtime.name in channel_config.disabled_commands:
                continue

            chatters = [user.name for user in channel.chatters if type(user.name) == str]
            if channel_config.currently_online:
                await users.add_online_time(self.bot.con_pool, channel_config.channel_id, chatters, 10)
            else:
                await users.add_offline_time(self.bot.con_pool, channel_config.channel_id, chatters, 10)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("u",))
    async def user(self, ctx: commands.Context, target: str | None):
        """
        Shows some information about the target user; {prefix}user <target>; can be searched with an id
        {prefix}user #<target id>; leave empty for self
        """
        if target is None:
            user_info = await twitch.user_info(ctx.author.name)
        elif target.startswith("#") and target[1:].isnumeric():
            user_info = await twitch.user_info(user_id=target[1:])
        else:
            user_info = await twitch.user_info(target)

        if user_info is None:
            if target is not None and not (target.startswith("#") and target[1:].isnumeric()):
                availability = f"username '{target}' is {'' if await twitch.username_available(target) else 'not'} available"
                await self.bot.msg_q.send(ctx, f"Given user doesn't exist, {availability}")
            else:
                await self.bot.msg_q.send(ctx, "Given user doesn't exist")
            return

        infos = []

        infos.append(f"@{user_info.username}")
        infos.append(f"ID: {user_info.id}")

        if user_info.description is not None:
            if len(user_info.description) > 35:
                infos.append(f"Bio: {user_info.description[:35]}...")
            else:
                infos.append(f"Bio: {user_info.description}")

        infos.append(f"Followers: {user_info.followers}")
        infos.append(f"Chatters: {user_info.channel.chatters}")

        if user_info.roles.is_affiliate:
            infos.append("Role: Affiliate")
        elif user_info.roles.is_partner:
            infos.append("Role: Partner")

        if user_info.channel.founder_badge_availability > 0:
            infos.append(f"Founders available: {user_info.channel.founder_badge_availability}")

        if user_info.roles.is_affiliate or user_info.roles.is_partner:
            user = await self.bot.fetch_users(ids=[int(user_info.id)])
            emotes = await user[0].fetch_channel_emotes()
            infos.append(f"Emotes: {len(emotes)}")

        if user_info.emote_prefix is not None:
            infos.append(f"Prefix: {user_info.emote_prefix}")

        infos.append(f"Color: {'<no color>' if user_info.chat_color is None else user_info.chat_color}")

        if user_info.stream is not None:
            online_time = format_timedelta(user_info.stream.started_at, datetime.now(UTC))
            infos.append(f"Live: {online_time}")
        elif user_info.last_broadcast.started_at is not None:
            time_offline = format_timedelta(user_info.last_broadcast.started_at, datetime.now(UTC))
            infos.append(f"Last live: {time_offline} ago")

        if user_info.updated_at is not None:
            updated_since = format_timedelta(user_info.updated_at, datetime.now(UTC))
            infos.append(f"Updated: {user_info.updated_at.strftime('%Y-%m-%d')} ({updated_since} ago)")

        account_age = format_timedelta(user_info.created_at, datetime.now(UTC))
        infos.append(f"Created: {user_info.created_at.strftime('%Y-%m-%d')} ({account_age} ago)")

        infos.append(f"Channel link: {user_info.profile_URL}")

        await self.bot.msg_q.send(ctx, " — ".join(infos))

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("title", "game", "downtime"))
    async def stream(self, ctx: commands.Context, target: twitchio.User | None):
        """Shows some stream related information; {prefix}stream <channel>; leave empty for current channel"""
        channel = ctx.channel.name if target is None else target.name
        user_info = await twitch.user_info(channel)
        if user_info is None:
            await self.bot.msg_q.send(ctx, "Target channel doesn't exist")
            return

        current_stream = user_info.stream
        if current_stream is not None:
            title = current_stream.title if current_stream.title else "<no title>"
            viewer_count = current_stream.viewers_count
            game = current_stream.game.display_name if current_stream.game else "<no category>"
            online_time = format_timedelta(current_stream.started_at, datetime.now(UTC))
            await self.bot.msg_q.send(
                ctx,
                f"(Live) Title: {title} — Game: {game} — Clips: {current_stream.clip_count} — Bitrate: {current_stream.bitrate} — Viewer count: {viewer_count} — Live: {online_time}",
            )
            return

        title = user_info.broadcast_settings.title if user_info.broadcast_settings.title else "<no title>"
        game = user_info.broadcast_settings.game.display_name if user_info.broadcast_settings.game else "<no category>"
        last_stream = user_info.last_broadcast

        if last_stream.started_at is None:
            await self.bot.msg_q.send(ctx, f"(Offline) Title: {title} — Game: {game} — Last live: never")
            return

        streamed_at = last_stream.started_at
        time_offline = format_timedelta(streamed_at, datetime.now(UTC))
        await self.bot.msg_q.send(
            ctx,
            f"(Offline) Title: {title} — Game: {game} — Last live: {streamed_at.strftime('%Y-%m-%d')} ({time_offline} ago)",
        )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("fa",))
    async def followage(
        self,
        ctx: commands.Context,
        user_1: twitchio.User | None,
        user_2: twitchio.User | None,
    ):
        """
        Shows the followage; {prefix}followage for own followage of the current channel;
        {prefix}followage <channel> for own followage of the target channel,
        {prefix}followage <target> <channel> for the followage of the target for the target channel
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if user_1 is None:
            user = ctx.author.name
            user_id = ctx.author.id
            channel = ctx.channel.name
            channel_id = await channels.channel_id(self.bot.con_pool, channel)
        elif user_2 is None:
            user = ctx.author.name
            user_id = ctx.author.id
            channel = user_1.name
            channel_id = str(user_1.id)
        else:
            user = user_1.name
            user_id = str(user_1.id)
            channel = user_2.name
            channel_id = str(user_2.id)

        if user_id == channel_id:
            await self.bot.msg_q.reply(ctx, "You cannot follow yourself")
            return

        subage = await twitch.subage(user_id, channel_id)
        if subage is None:
            await self.bot.msg_q.send(ctx, "One or more users don't exist")
            return

        followed_at = subage.followed_at
        if followed_at is None:
            await self.bot.msg_q.send(ctx, f"{user} doesn't follow {channel}", [user, channel])
            return
        follow_time = format_timedelta(followed_at, datetime.now(UTC))
        await self.bot.msg_q.send(
            ctx,
            f"{user} has been following {channel} for {follow_time} since {followed_at.strftime('%Y-%m-%d')}",
            [user, channel],
        )

    # TODO: rewrite this terrible piece of code
    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("sa",))
    async def subage(
        self,
        ctx: commands.Context,
        arg1: twitchio.User | None,
        arg2: twitchio.User | None,
    ):
        """
        Shows the subage; {prefix}subage for own subage of the current channel;
        {prefix}subage <channel> for own subage of the target channel,
        {prefix}subage <target> <channel> for the subage of the target for the target channel
        """
        assert isinstance(ctx.author.name, str)
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if arg1 is None:
            user = ctx.author.name
            user_id = ctx.author.id
            channel = ctx.channel.name
        elif arg2 is None:
            user = ctx.author.name
            user_id = ctx.author.id
            channel = arg1.name
        else:
            user = arg1.name
            user_id = str(arg1.id)
            channel = arg2.name

        user_info = await twitch.user_info(channel)
        if user_info is None:
            await self.bot.msg_q.send(ctx, "Target channel doesn't exist")
            return

        if not user_info.roles.is_affiliate and not user_info.roles.is_partner:
            await self.bot.msg_q.send(
                ctx, "Target channel is not an affiliate or partnered and doesn't have subscription benefits available"
            )
            return

        subage = await twitch.subage(user_id, user_info.id)
        if subage is None:
            await self.bot.msg_q.send(ctx, "Target user not found")
            return

        if subage.subscription_benefit is None and subage.cumulative is None and subage.streak is None:
            await self.bot.msg_q.send(ctx, f"{user} has never been subbed to {channel}", [user, channel])
            return

        elif subage.subscription_benefit is None and subage.cumulative is not None:
            time_since = format_timedelta(subage.cumulative.end, datetime.now(UTC))
            await self.bot.msg_q.send(
                ctx,
                f"{user} was previously subbed to {channel} for {subage.cumulative.months} months. The sub ended {time_since} ago",
                [user, channel],
            )
            return

        elif subage.subscription_benefit is None:
            return

        if subage.cumulative is not None and subage.cumulative.end != subage.subscription_benefit.ends_at:
            anniversary_in = format_timedelta(datetime.now(UTC), subage.cumulative.end)
            anniversary = f". The next sub anniversary is in {anniversary_in}"
        else:
            anniversary = ""

        sub_ends_in = (
            format_timedelta(datetime.now(UTC), subage.subscription_benefit.ends_at)
            if subage.subscription_benefit.ends_at is not None
            else "never"
        )
        renews = subage.subscription_benefit.renews_at is not None
        subbed_months = 1 if subage.cumulative is None else subage.cumulative.months
        streak_months = 1 if subage.streak is None else subage.streak.months

        targets = [user, channel]
        gift = subage.subscription_benefit.gift
        if gift.is_gift:
            if gift.gifter is None:
                gifter = "anonymous gifter"
            else:
                gifter = gift.gifter.username
                targets.append(gifter)
            message = f"{user} was gifted a tier {subage.subscription_benefit.tier} sub to {channel} by {gifter}. They have been a sub for {subbed_months} months with a streak of {streak_months} months. The gift sub ends in {sub_ends_in}{anniversary}"
        else:
            if subage.subscription_benefit.purchased_with_prime:
                sub_type = "prime"
            else:
                sub_type = f"tier {subage.subscription_benefit.tier}"
            message = f"{user} is subbed to {channel} with a {sub_type} sub. They have been a sub for {subbed_months} months with a streak of {streak_months} months. The sub {'renews' if renews else 'ends'} in {sub_ends_in}{anniversary}"
        await self.bot.msg_q.send(ctx, message, targets)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def socials(self, ctx: commands.Context, target_channel: twitchio.User | None):
        """Shows the socials set on twitch for the current channel; a target channel can be specified: {prefix}socials <target>"""
        if target_channel is None:
            channel = ctx.channel.name
            channel_id = await channels.channel_id(self.bot.con_pool, channel)
        else:
            channel = target_channel.name
            channel_id = str(target_channel.id)

        social_medias = await twitch.social_medias(channel_id)
        if len(social_medias) == 0:
            await self.bot.msg_q.send(ctx, f"{channel} doesn't have any socials set on twitch", [channel])
            return

        all_socials = [f"{social.title}: {social.url}" for social in social_medias]
        await self.bot.msg_q.send(ctx, f"{channel}'s socials: {' — '.join(all_socials)}", [channel])

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def schedule(self, ctx: commands.Context, target_channel: twitchio.User | None):
        """Shows the twitch schedule for the next 7 days for the current channel; a target channel can be specified: {prefix}schedule <target>"""
        if target_channel is None:
            channel = ctx.channel.name
            channel_id = await channels.channel_id(self.bot.con_pool, channel)
        else:
            channel = target_channel.name
            channel_id = str(target_channel.id)

        schedule = await twitch.schedule(channel_id)
        if schedule is None:
            await self.bot.msg_q.send(ctx, f"{channel} has never set their schedule on twitch", [channel])
            return

        if schedule.segments is None:
            await self.bot.msg_q.send(ctx, f"{channel} does not have any streams set in the next week", [channel])
            return

        segments = []
        for segment in schedule.segments:
            games = (
                "<no category>"
                if len(segment.categories) == 0
                else ", ".join(cat.display_name for cat in segment.categories)
            )
            starts_at = segment.start_at.strftime("%A %b %d %H:%M:%S")
            if datetime.now(UTC) < segment.start_at:
                starts_in = f"in {format_timedelta(datetime.now(UTC), segment.start_at)}"
            else:
                starts_in = f"{format_timedelta(segment.start_at, datetime.now(UTC))} ago"
            segments.append(f"{games} stream {starts_at} ({starts_in})")

        await self.bot.msg_q.send(ctx, f"{channel}'s schedule: {' — '.join(segments)}", [channel])

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("nextstream", "today"))
    async def next(self, ctx: commands.Context, target_channel: twitchio.User | None):
        """Shows the info of the next scheduled stream of the current channel; a target channel can be specified: {prefix}next <target>"""
        if target_channel is None:
            channel = ctx.channel.name
            channel_id = await channels.channel_id(self.bot.con_pool, channel)
        else:
            channel = target_channel.name
            channel_id = str(target_channel.id)

        schedule = await twitch.schedule(channel_id)
        if schedule is None:
            await self.bot.msg_q.send(ctx, f"{channel} has never set their schedule on twitch", [channel])
            return

        if schedule.next_segment is None:
            await self.bot.msg_q.send(ctx, f"{channel} does not have next stream set in the schedule", [channel])
            return

        title = schedule.next_segment.title
        games = (
            "<no category>"
            if len(schedule.next_segment.categories) == 0
            else ", ".join(cat.display_name for cat in schedule.next_segment.categories)
        )
        starts_at = schedule.next_segment.start_at.strftime("%A %Y-%m-%d %H:%M:%S %Z")
        starts_in = format_timedelta(datetime.now(UTC), schedule.next_segment.start_at)
        duration = format_timedelta(schedule.next_segment.start_at, schedule.next_segment.end_at, exclude_zeros=True)
        await self.bot.msg_q.send(
            ctx,
            f"{channel}'s next stream is on {starts_at} (in {starts_in}) streaming {games} for about {duration} — {title}",
            [channel],
        )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def founders(self, ctx: commands.Context, target_channel: twitchio.User | None):
        """Shows the founders of the target channel; {prefix}mods <target>; leave empty for the current channel"""
        if target_channel is None:
            channel = ctx.channel.name
            channel_id = await channels.channel_id(self.bot.con_pool, channel)
        else:
            channel = target_channel.name
            channel_id = str(target_channel.id)
        founders = await twitch.founders(channel_id)
        if founders is None or len(founders.founders) == 0:
            await self.bot.msg_q.send(ctx, f"{channel} doesn't have any founders", [channel])
            return
        founder_names = [
            "<unknown user>" if founder.user is None else founder.user.username for founder in founders.founders
        ]
        founder_availability = (
            "" if founders.founder_badge_availability == 0 else f" ({founders.founder_badge_availability} available)"
        )
        await self.bot.msg_q.send(
            ctx,
            f"{channel} has {len(founder_names)} founder{'' if len(founder_names) == 1 else 's'}{founder_availability}: {', '.join(founder_names)}",
            [channel] + founder_names,
        )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("moderators",))
    async def mods(self, ctx: commands.Context, target_channel: twitchio.User | None):
        """Shows the mods of the target channel; {prefix}mods <target>; leave empty for the current channel"""
        channel = ctx.channel.name if target_channel is None else target_channel.name
        mods = await twitch.mods(channel)
        if len(mods) == 0:
            await self.bot.msg_q.send(ctx, f"{channel} doesn't have any moderators", [channel])
            return
        mod_names = ["<unknown user>" if mod.user is None else mod.user.username for mod in mods]
        await self.bot.msg_q.send(
            ctx,
            f"{channel} has {len(mod_names)} mod{'' if len(mod_names) == 1 else 's'}: {', '.join(mod_names)}",
            [channel] + mod_names,
        )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def vips(self, ctx: commands.Context, target_channel: twitchio.User | None):
        """Shows the vips of the target channel; {prefix}mods <target>; leave empty for the current channel"""
        channel = ctx.channel.name if target_channel is None else target_channel.name
        vips = await twitch.vips(channel)
        if len(vips) == 0:
            await self.bot.msg_q.send(ctx, f"{channel} doesn't have any vips", [channel])
            return
        vip_names = ["<unknown user>" if vip.user is None else vip.user.username for vip in vips]
        await self.bot.msg_q.send(
            ctx,
            f"{channel} has {len(vip_names)} vip{'' if len(vip_names) == 1 else 's'}: {', '.join(vip_names)}",
            [channel] + vip_names,
        )

    @commands.cooldown(rate=4, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def watchtime(self, ctx: commands.Context, target: twitchio.User | None):
        """
        Shows the offline and online time of the target user; the tracking of watchtime is disabled if this command is disabled;
        {prefix}watchtime <target>; leave empty for self
        """
        channel = ctx.channel.name
        if target is None:
            assert isinstance(ctx.author.name, str)
            user = ctx.author.name
        else:
            user = target.name

        channel_id = await channels.channel_id(self.bot.con_pool, channel)
        watchtime = await users.watchtime(self.bot.con_pool, channel_id, user)
        online_time = format_timedelta(datetime.now(UTC), datetime.now(UTC) + timedelta(seconds=watchtime.online_time))
        total_time = format_timedelta(datetime.now(UTC), datetime.now(UTC) + timedelta(seconds=watchtime.total_time))
        await self.bot.msg_q.send(
            ctx,
            f"{user} has watched {channel} for {online_time} and in total has spent {total_time} in chat",
            [user, channel],
        )


def prepare(bot: "Bot"):
    bot.add_cog(UserInfo(bot))
