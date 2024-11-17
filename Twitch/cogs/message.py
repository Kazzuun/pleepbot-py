from datetime import datetime, UTC
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.database.twitch import channels, messages
from shared.util.formatting import format_timedelta
from Twitch.exceptions import ValidationError

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Message(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        if not channel_config.logging:
            raise ValidationError("This channel isn't being logged")
        return True

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("randommessage",))
    async def rm(self, ctx: commands.Context, target: twitchio.User | None, *args: str):
        """
        Sends a random message from the chat logs of the current channel; {prefix}rm <target> <arg1> <arg2>...;
        leave target empty for self, or use "all" for any target; possible arguments: +{prefix} to include commands (commands are excluded by default),
        +<arg> to include the word in the search and -<arg> to exclude, ><count> to search messages that have more words than
        the count and <<count> to have less words
        """
        if target is not None:
            sender = target.name
        elif len(args) > 0 and args[-1] == "all":
            sender = None
            args = args[:-1]
        else:
            assert isinstance(ctx.author.name, str)
            sender = ctx.author.name
            if len(args) > 0:
                args = (args[-1],) + args[:-1]

        included_words = []
        excluded_words = []
        min_word_count = None
        max_word_count = None
        exclude_commands = True
        prefixes = await self.bot.prefixes(ctx.channel.name)

        mode = None
        for arg in args:
            if arg.startswith(tuple(f"+{prefix}" for prefix in prefixes)):
                exclude_commands = False
                mode = None
            elif arg.startswith("+"):
                if len(arg[1:]) > 0:
                    included_words.append(arg[1:])
                mode = "+"
            elif arg.startswith("-"):
                if len(arg[1:]) > 0:
                    excluded_words.append(arg[1:])
                mode = "-"
            elif arg.startswith(">"):
                try:
                    if len(arg[1:]) > 0:
                        min_word_count = int(arg[1:])
                except ValueError:
                    pass
                mode = None
            elif arg.startswith("<"):
                try:
                    max_word_count = int(arg[1:])
                except ValueError:
                    pass
                mode = None
            elif mode == "+":
                if len(arg) > 0:
                    included_words.append(arg)
            elif mode == "-":
                if len(arg) > 0:
                    excluded_words.append(arg)

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        message = await messages.random_message(
            self.bot.con_pool,
            channel_id,
            sender,
            included_words=included_words,
            excluded_words=excluded_words,
            min_word_count=min_word_count,
            max_word_count=max_word_count,
            exclude_commands=exclude_commands,
            prefixes=prefixes if exclude_commands else None,
        )
        if message is None:
            await self.bot.msg_q.send(ctx, "No message found")
            return
        await self.bot.msg_q.send(
            ctx,
            f"({message.sent_at.strftime('%Y-%m-%d')}) {message.sender}: {message.message}",
            [message.sender],
        )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("messagecount", "numberofmessages"))
    async def nofm(self, ctx: commands.Context, target: twitchio.User | None, *args: str):
        """
        Sends the number of messages sent to the current channel; {prefix}nofm <target> <arg1> <arg2>...;
        leave target empty for self, or use "all" for any target; possible arguments: -{prefix} to include commands
        (commands are included by default), +<arg> to include the word in the search and -<arg> to exclude,
        ><count> to search messages that have more words than the count and <<count> to have less words
        """
        if target is not None:
            sender = target.name
        elif len(args) > 0 and args[-1] == "all":
            sender = None
            args = args[:-1]
        else:
            assert isinstance(ctx.author.name, str)
            sender = ctx.author.name
            if len(args) > 0:
                args = (args[-1],) + args[:-1]

        included_words = []
        excluded_words = []
        min_word_count = None
        max_word_count = None
        exclude_commands = False
        prefixes = await self.bot.prefixes(ctx.channel.name)

        mode = None
        for arg in args:
            if arg.startswith(tuple(f"-{prefix}" for prefix in prefixes)):
                exclude_commands = False
                mode = None
            elif arg.startswith("+"):
                if len(arg[1:]) > 0:
                    included_words.append(arg[1:])
                mode = "+"
            elif arg.startswith("-"):
                if len(arg[1:]) > 0:
                    excluded_words.append(arg[1:])
                mode = "-"
            elif arg.startswith(">"):
                try:
                    if len(arg[1:]) > 0:
                        min_word_count = int(arg[1:])
                except ValueError:
                    pass
                mode = None
            elif arg.startswith("<"):
                try:
                    if len(arg[1:]) > 0:
                        max_word_count = int(arg[1:])
                except ValueError:
                    pass
                mode = None
            elif mode == "+":
                if len(arg) > 0:
                    included_words.append(arg)
            elif mode == "-":
                if len(arg) > 0:
                    excluded_words.append(arg)

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        count = await messages.number_of_messages(
            self.bot.con_pool,
            channel_id,
            sender,
            included_words=included_words,
            excluded_words=excluded_words,
            min_word_count=min_word_count,
            max_word_count=max_word_count,
            exclude_commands=exclude_commands,
            prefixes=prefixes if exclude_commands else None,
        )
        if count == 0:
            await self.bot.msg_q.send(ctx, "No message found")
            return
        if sender is None:
            sender = "everyone"
        await self.bot.msg_q.send(ctx, f"Messages sent by {sender} matching given filters: {count}", [sender])

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def topchatters(self, ctx: commands.Context):
        """Sorts and shows the top 10 of the chatters of the current channel by the number of messages they have sent"""
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        chatters = await messages.top_chatters(self.bot.con_pool, channel_id)
        top_10 = chatters.most_common(10)
        users = [user[0] for user in top_10]
        message = " | ".join([f"{i}. {chatter[0]} - {chatter[1]}" for i, chatter in enumerate(top_10, 1)])
        await self.bot.msg_q.send(ctx, message, users)

    @commands.cooldown(rate=5, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("lastseen", "whereis"))
    async def ls(self, ctx: commands.Context, target: twitchio.User):
        """Shows the last message and time when the target was last seen in chat {prefix}ls <target>"""
        assert isinstance(ctx.author.name, str)

        if ctx.author.name == target.name:
            await self.bot.msg_q.reply(ctx, "You were here just now Stare")
            return
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        last_message = await messages.last_seen(self.bot.con_pool, channel_id, target.name)
        if last_message is None:
            message = f"{target.name} hasn't been seen in this chat"
        else:
            time_since = format_timedelta(last_message.sent_at, datetime.now(UTC))
            message = f"{target.name} was last seen {time_since} ago: {last_message.message}"
        await self.bot.msg_q.send(ctx, message, [target.name])


def prepare(bot: "Bot"):
    bot.add_cog(Message(bot))
