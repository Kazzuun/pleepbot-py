from datetime import datetime, UTC, timedelta
import os
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands, routines

from shared.apis import seventv, youtube
from shared.database.twitch import channels, notifications
from Twitch.exceptions import ValidationError
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Youtube(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.poll_youtube_videos.start(stop_on_error=False)

    @routines.routine(minutes=10, wait_first=True)
    async def poll_youtube_videos(self):
        youtube_upload_notifs = await notifications.youtube_notifications(self.bot.con_pool)
        playlist_ids = set(notif.playlist_id for notif in youtube_upload_notifs)
        for playlist_id in playlist_ids:
            uploads = await youtube.get_playlist_items(playlist_id)
            for video in uploads.items:
                if video.content_details.video_published_at < datetime.now(UTC) - timedelta(minutes=10):
                    continue

                channel_name = video.snippet.channel_title
                video_title = video.snippet.title
                video_id = video.content_details.video_id

                video_info = await youtube.get_video_by_id(video_id)
                duration = video_info.items[0].content_details.duration

                for sub in [notif for notif in youtube_upload_notifs if notif.playlist_id == playlist_id]:
                    channel_config = await channels.channel_config_from_id(self.bot.con_pool, sub.channel_id)
                    if not channel_config.notifications_online and channel_config.currently_online:
                        continue

                    emote = await seventv.happy_emote(sub.channel_id)
                    pings = []
                    if len(sub.pings) > 0:
                        users = await self.bot.fetch_users(ids=[int(user) for user in sub.pings])
                        pings = [f"@{ping.name}" for ping in users]

                    await self.bot.msg_q.send_message(
                        channel_config.username,
                        f"{channel_name} uploaded a new {'short' if duration <= 62 else 'video'}: {video_title} youtu.be/{video_id} {emote} {' '.join(pings)}",
                    )

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("yt", "ytsearch"))
    async def youtube(self, ctx: commands.Context, *, query: str = ""):
        """Searches youtube videos and returns a few top video results; {prefix}youtube <query>"""
        search_count = 3
        result = await youtube.search_by_keywords(q=query, search_type="video", limit=search_count)

        def format_title(title: str) -> str:
            max_title_length = min(int(350 / search_count - 25), 100)
            if len(title) > max_title_length:
                return title[:max_title_length] + "..."
            return title

        if result.page_info.total_results == 0:
            await self.bot.msg_q.send(ctx, "Search returned no results")
            return

        search_results = [f"{format_title(r.snippet.title)} youtu.be/{r.id.video_id}" for r in result.items]
        await self.bot.msg_q.send(ctx, " — ".join(search_results))

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def ytnotify(self, ctx: commands.Context, channel_handle: str):
        """(Mod only) Subscribes to upload notifications to target youtube channel; {prefix}ytnotify <target>"""
        assert isinstance(ctx.author, twitchio.Chatter)
        if not ctx.author.is_mod:
            raise ValidationError("You must be a mod to use this command")

        channel_response = await youtube.get_channel_info(for_handle=channel_handle)
        if channel_response.page_info.total_results == 0:
            await self.bot.msg_q.reply(ctx, "Channel not found")
            return

        channel_name = channel_response.items[0].snippet.title
        uploads_playlist_id = channel_response.items[0].content_details.related_playlists.uploads
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)

        success = await notifications.sub_to_youtube_notifications(self.bot.con_pool, channel_id, uploads_playlist_id)
        if success:
            message = f"Notifying when {channel_name} uploads"
        else:
            message = f"This channel is already recieving notifications when {channel_name} uploads"
        await self.bot.msg_q.reply(ctx, message)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def ytunnotify(self, ctx: commands.Context, channel_handle: str):
        """(Mod only) Unsubscribes from upload notifications to target youtube channel; {prefix}ytunnotify <target>"""
        assert isinstance(ctx.author, twitchio.Chatter)
        if not ctx.author.is_mod:
            raise ValidationError("You must be a mod to use this command")

        # TODO: unnotify all
        channel_response = await youtube.get_channel_info(for_handle=channel_handle)
        if channel_response.page_info.total_results == 0:
            await self.bot.msg_q.reply(ctx, "Channel not found")
            return

        channel_name = channel_response.items[0].snippet.title
        uploads_playlist_id = channel_response.items[0].content_details.related_playlists.uploads
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)

        success = await notifications.unsub_to_youtube_notifications(
            self.bot.con_pool, channel_id, uploads_playlist_id
        )
        if success:
            message = f"No longer notifying when {channel_name} uploads"
        else:
            message = f"This channel isn't recieving any youtube notifications from {channel_name}"
        await self.bot.msg_q.reply(ctx, message)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def ytpingme(self, ctx: commands.Context, channel_handle: str):
        """
        Makes the bot ping you whenever the target channel uploads; {prefix}ytpingme <channel>
        (the current channel needs to be subscribed to upload notifications for the target channel)
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_response = await youtube.get_channel_info(for_handle=channel_handle)
        if channel_response.page_info.total_results == 0:
            await self.bot.msg_q.reply(ctx, "Channel not found")
            return

        playlist_id = channel_response.items[0].content_details.related_playlists.uploads
        channel_name = channel_response.items[0].snippet.title

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        notifs = await notifications.youtube_notifications(self.bot.con_pool)
        if channel_id not in [notif.channel_id for notif in notifs if notif.playlist_id == playlist_id]:
            await self.bot.msg_q.send(
                ctx,
                f"Current channel is not subscribed to upload notifications for {channel_name}",
            )
            return

        success = await notifications.ytping(self.bot.con_pool, ctx.author.id, channel_id, playlist_id)
        if success:
            await self.bot.msg_q.send(
                ctx,
                f"I will ping you when {channel_name} uploads",
                [],
                notifications.ytunping,
                self.bot.con_pool,
                ctx.author.id,
                channel_id,
                playlist_id,
            )
        else:
            await self.bot.msg_q.send(ctx, f"You have already made me ping you when {channel_name} goes live")

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def ytunpingme(self, ctx: commands.Context, channel_handle: str):
        """
        Makes the bot no longer ping you whenever the target channel uploads; {prefix}ytunpingme <channel>
        (the current channel needs to be subscribed to upload notifications for the target channel)
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_response = await youtube.get_channel_info(for_handle=channel_handle)
        if channel_response.page_info.total_results == 0:
            await self.bot.msg_q.reply(ctx, "Channel not found")
            return

        playlist_id = channel_response.items[0].content_details.related_playlists.uploads
        channel_name = channel_response.items[0].snippet.title

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        notifs = await notifications.youtube_notifications(self.bot.con_pool)
        if channel_id not in [notif.channel_id for notif in notifs if notif.playlist_id == playlist_id]:
            await self.bot.msg_q.send(
                ctx,
                f"Current channel is not subscribed to upload notifications for {channel_name}",
            )
            return

        success = await notifications.ytunping(self.bot.con_pool, ctx.author.id, channel_id, playlist_id)
        if success:
            await self.bot.msg_q.send(
                ctx,
                f"I will no longer ping you when {channel_name} uploads",
                [],
                notifications.ytping,
                self.bot.con_pool,
                ctx.author.id,
                channel_id,
                playlist_id,
            )
        else:
            await self.bot.msg_q.send(ctx, "You haven't made me ping you before")


def prepare(bot: "Bot"):
    if "GOOGLE_API_KEY" not in os.environ:
        logger.warning("Google api key is not set, youtube commands are disabled")
        return
    bot.add_cog(Youtube(bot))
