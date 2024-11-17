import re
import sys
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis.cache import cache
from shared.database.twitch import channels, messages, users
from Twitch.handlers import eventsub
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Admin(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None
        config = await users.user_config(self.bot.con_pool, ctx.author.id)
        return config.is_admin()

    @commands.command(no_global_checks=True)
    async def test(self, ctx: commands.Context):
        logger.debug(ctx.message.tags)
        logger.debug(ctx.message.tags.get("emotes"))
        logger.debug(ctx.message.tags.get("reply-parent-user-login"))
        logger.debug(ctx.message.tags.get("reply-parent-msg-body"))

    @commands.command(no_global_checks=True)
    async def restartreminds(self, ctx: commands.Context):
        self.bot.cogs["Remind"].check_reminders.restart()  # type: ignore
        self.bot.cogs["Remind"].check_timers.restart()  # type: ignore
        await self.bot.msg_q.send(ctx, "Reminds restarted")

    @commands.command(no_global_checks=True)
    async def areconnect(self, ctx: commands.Context, *target_channels):
        connected = [
            channel for channel in target_channels if channel in [ch.name for ch in self.bot.connected_channels]
        ]
        if len(connected) == 0:
            connected = [ctx.channel.name]
        await self.bot.part_channels(connected)
        for channel in connected:
            self.bot.msg_q.remove_channel(channel)
            self.bot.msg_q.add_channel(channel)
        await self.bot.join_channels(connected)
        await self.bot.msg_q.send(ctx, f"Reconnected to channels {', '.join(connected)}", connected)

    @commands.command(no_global_checks=True)
    async def ajoin(self, ctx: commands.Context, *target_channels):
        targets = await self.bot.fetch_users(list(target_channels))
        if len(targets) == 0:
            await self.bot.msg_q.send(ctx, "Please provide valid users")
            return
        for target in targets:
            await channels.join_channel(self.bot.con_pool, str(target.id), target.name)
            if target.name not in [channel.name for channel in self.bot.connected_channels]:
                await self.bot.join_channels([target.name])
            self.bot.msg_q.add_channel(target.name)

            subs_to_target = await eventsub.esclient.get_subscriptions(user_id=target.id)
            sub_types = [sub.type for sub in subs_to_target]

            if "stream.online" not in sub_types:
                await eventsub.subscribe_stream_start(target.id)

            if "stream.offline" not in sub_types:
                await eventsub.subscribe_stream_end(target.id)

        streams = await self.bot.fetch_streams(user_logins=[user.name for user in targets])
        for stream in streams:
            await channels.set_online(self.bot.con_pool, str(stream.user.id))

        joined = [target.name for target in targets]
        await self.bot.msg_q.send(ctx, f"Joined {', '.join(joined)}", joined)

    @commands.command(no_global_checks=True)
    async def apart(self, ctx: commands.Context, *target_channels):
        targets = await self.bot.fetch_users(list(target_channels))
        if len(targets) == 0:
            await self.bot.msg_q.send(ctx, "Please provide valid users")
            return
        left = []
        for target in targets:
            if target.name in [channel.name for channel in self.bot.connected_channels]:
                self.bot.msg_q.remove_channel(target.name)
                await self.bot.part_channels([target.name])
                await channels.part_channel(self.bot.con_pool, str(target.id))
                left.append(target.name)
        if len(left) == 0:
            await self.bot.msg_q.reply(ctx, "The bot is currently not connected to any given chats")
        else:
            await self.bot.msg_q.reply(ctx, f"Left {', '.join(left)}", left)

    @commands.command(aliases=("renameu",), no_global_checks=True)
    async def renameuser(self, ctx: commands.Context, old_name: str, new_name: str):
        old_name = old_name.lower()
        new_name = new_name.lower()
        await users.rename_user(self.bot.con_pool, old_name, new_name)
        await self.bot.msg_q.send(
            ctx,
            f"Renamed {old_name} to {new_name}",
            [old_name, new_name],
            users.rename_user,
            self.bot.con_pool,
            new_name,
            old_name,
        )

    @commands.command(aliases=("bonk",), no_global_checks=True)
    async def aban(self, ctx: commands.Context, target: twitchio.User):
        user_config = await users.user_config(self.bot.con_pool, str(target.id))
        if user_config.is_admin():
            await self.bot.msg_q.send(ctx, "You cannot ban another admin user")
            return

        success = await users.ban_globally(self.bot.con_pool, str(target.id), target.name)
        if success:
            await self.bot.msg_q.send(
                ctx,
                "User banned successfully",
                [],
                users.unban_globally,
                self.bot.con_pool,
                str(target.id),
                target.name,
            )
        else:
            await self.bot.msg_q.send(ctx, "User is already banned")

    @commands.command(no_global_checks=True)
    async def aunban(self, ctx: commands.Context, target: twitchio.User):
        success = await users.unban_globally(self.bot.con_pool, str(target.id), target.name)
        if success:
            await self.bot.msg_q.send(
                ctx,
                "User unbanned successfully",
                [],
                users.ban_globally,
                self.bot.con_pool,
                str(target.id),
                target.name,
            )
        else:
            await self.bot.msg_q.send(ctx, "User is not banned")

    @commands.command(no_global_checks=True)
    async def block(self, ctx: commands.Context, *words):
        id = await messages.add_blocked_term(self.bot.con_pool, " ".join(words), False)
        await self.bot.msg_q.send(
            ctx,
            f"Term blocked (id: {id})",
            [],
            messages.delete_blocked_term,
            self.bot.con_pool,
            id,
        )

    @commands.command(no_global_checks=True)
    async def blockregex(self, ctx: commands.Context, *words):
        pattern = " ".join(words)
        try:
            re.compile(pattern)
        except re.error:
            await self.bot.msg_q.send(ctx, "Invalid regex")
            return
        id = await messages.add_blocked_term(self.bot.con_pool, pattern, True)
        await self.bot.msg_q.send(
            ctx,
            f"Term blocked (id: {id})",
            [],
            messages.delete_blocked_term,
            self.bot.con_pool,
            id,
        )

    @commands.command(no_global_checks=True)
    async def unblock(self, ctx: commands.Context, id: int):
        blocked_term = await messages.blocked_term(self.bot.con_pool, id)
        if blocked_term is None:
            await self.bot.msg_q.send(ctx, "Term with the given id not found")
            return
        success = await messages.delete_blocked_term(self.bot.con_pool, id)
        if success:
            await self.bot.msg_q.send(
                ctx,
                "Term unblocked",
                [],
                messages.add_blocked_term,
                self.bot.con_pool,
                id,
                blocked_term.pattern,
                blocked_term.regex,
            )
        else:
            await self.bot.msg_q.send(ctx, "Failed to unblock term with given id")

    @commands.command(aliases=("kill", "sd"), no_global_checks=True)
    async def shutdown(self, ctx: commands.Context):
        for channel in self.bot.connected_channels:
            self.bot.msg_q.remove_channel(channel.name)
        await self.bot.close()
        sys.exit(0)

    @commands.command(aliases=("say",), no_global_checks=True)
    async def echo(self, ctx: commands.Context, *args):
        if len(args) == 0:
            return
        if args[0] in [channel.name for channel in self.bot.connected_channels] and len(args) > 1:
            channel = args[0]
            message = " ".join(args[1:])
        else:
            channel = ctx.channel.name
            message = " ".join(args)
        await self.bot.msg_q.send_message(channel, message)

    @commands.command(no_global_checks=True)
    async def cache(self, ctx: commands.Context):
        cache.clear()
        await self.bot.msg_q.send(ctx, "Cache cleared")

    @commands.command(aliases=("listchatters",), no_global_checks=True)
    async def listlurkers(self, ctx: commands.Context, *args):
        if ctx.channel.chatters is None or len(ctx.channel.chatters) == 0:
            await self.bot.msg_q.send(ctx, "Failed to get lurkers of this channel")
        else:
            lurkers = [chatter.name for chatter in ctx.channel.chatters if chatter.name is not None]
            targets = [] if "-p" in args else lurkers
            await self.bot.msg_q.send(ctx, ", ".join(lurkers), targets)


def prepare(bot: "Bot"):
    bot.add_cog(Admin(bot))
