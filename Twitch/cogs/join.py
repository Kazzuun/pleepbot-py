from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import seventv
from shared.database.twitch import channels
from Twitch.handlers import eventsub

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Join(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return ctx.channel.name == self.bot.nick

    @commands.cooldown(rate=2, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def join(self, ctx: commands.Context):
        """Makes the bot join your chat"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if ctx.author.name in [channel.name for channel in self.bot.connected_channels]:
            await self.bot.msg_q.reply(ctx, "The bot is currently connected to your chat")
            return

        await channels.join_channel(self.bot.con_pool, str(ctx.author.id), ctx.author.name)
        await self.bot.join_channels([ctx.author.name])
        self.bot.msg_q.add_channel(ctx.author.name)

        subs_to_target = await eventsub.esclient.get_subscriptions(user_id=int(ctx.author.id))
        sub_types = [sub.type for sub in subs_to_target]

        streams = await self.bot.fetch_streams(user_logins=[ctx.author.name])
        for stream in streams:
            await channels.set_online(self.bot.con_pool, str(stream.user.id))

        if "stream.online" not in sub_types:
            await eventsub.subscribe_stream_start(ctx.author.id)

        if "stream.offline" not in sub_types:
            await eventsub.subscribe_stream_end(ctx.author.id)

        await self.bot.msg_q.send(ctx, f"Joined {ctx.author.name}", [ctx.author.name])
        emote = await seventv.best_fitting_emote(
            str(ctx.author.id),
            lambda emote: (emote.lower().endswith("uh") and len(emote) == 3)
            or emote in ("plink", "plonk", "plenk", "pleep"),
            default="Stare",
        )
        await self.bot.msg_q.send_message(ctx.author.name, emote)

    @commands.cooldown(rate=2, per=15, bucket=commands.Bucket.member)
    @commands.command(aliases=("leave",))
    async def part(self, ctx: commands.Context):
        """Makes the bot leave your chat"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if ctx.author.name not in [channel.name for channel in self.bot.connected_channels]:
            await self.bot.msg_q.reply(ctx, "The bot is currently not connected to your chat")
            return

        self.bot.msg_q.remove_channel(ctx.author.name)
        await self.bot.part_channels([ctx.author.name])
        await channels.part_channel(self.bot.con_pool, ctx.author.id)
        await self.bot.msg_q.send(ctx, f"Left {ctx.author.name}", [ctx.author.name])


    @commands.cooldown(rate=2, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def reconnect(self, ctx: commands.Context):
        if ctx.channel.name in self.bot.connected_channels:
            await self.bot.part_channels(ctx.channel.name)
            self.bot.msg_q.remove_channel(ctx.channel.name)
            self.bot.msg_q.add_channel(ctx.channel.name)
            await self.bot.join_channels(ctx.channel.name)
            await self.bot.msg_q.send(ctx, f"Reconnected to {ctx.channel.name}", ctx.channel.name)
        else:
            await self.bot.msg_q.send(ctx, "The bot is currently not connected to your chat")


def prepare(bot: "Bot"):
    bot.add_cog(Join(bot))
