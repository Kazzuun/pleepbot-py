import re
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import seventv
from shared.database.twitch import channels, users

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Util(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    # @commands.cooldown(rate=1, per=COG_COOLDOWN, bucket=commands.Bucket.member)
    # @commands.command()
    # async def ping(self, ctx: commands.Context):
    #     """"""
    #     # TODO: Make this show other stats too like python version
    #     ...

    @commands.cooldown(rate=4, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("replies",))
    async def reply(self, ctx: commands.Context, action: str):
        """Makes the bot disable or re-enable replies; {prefix}reply off to disable or {prefix}reply on to enable"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        match action:
            case "on":
                success = await users.replies_on(self.bot.con_pool, ctx.author.id)
                if success:
                    await self.bot.msg_q.reply(
                        ctx,
                        "I will reply to you again",
                        [],
                        users.replies_off,
                        self.bot.con_pool,
                        ctx.author.id,
                    )
                else:
                    await self.bot.msg_q.reply(ctx, "Replies are already on")

            case "off":
                success = await users.replies_off(self.bot.con_pool, ctx.author.id)
                if success:
                    await self.bot.msg_q.reply(
                        ctx,
                        "I will no longer ping you with replies",
                        [],
                        users.replies_on,
                        self.bot.con_pool,
                        ctx.author.id,
                    )
                else:
                    await self.bot.msg_q.reply(ctx, "Replies are already off")

            case _:
                raise commands.MissingRequiredArgument

    @commands.cooldown(rate=4, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def optin(self, ctx: commands.Context, *commands):
        """Opts in to given commands; {prefix}optin <command1> <command2>... or {prefix}optin all to optin to every command"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if len(commands) == 0:
            await self.bot.msg_q.reply(ctx, "Please provide commands to opt in for again")
            return

        if commands[0] == "all":
            commands = tuple(self.bot.commands.keys())

        optoutable = []
        for command in commands:
            cmd = self.bot.get_command(command)
            if (
                cmd is not None
                and not cmd.no_global_checks
                and any(["target" in param.name for param in cmd.params.values()])
            ):
                optoutable.append(cmd.name)

        if len(optoutable) == 0:
            await self.bot.msg_q.reply(ctx, "None of the given commands are optoutable")
            return

        await users.optin(self.bot.con_pool, ctx.author.id, optoutable)
        await self.bot.msg_q.reply(
            ctx,
            f"Opted in to {', '.join(optoutable)}",
            [],
            users.optout,
            self.bot.con_pool,
            ctx.author.id,
            optoutable,
        )

    @commands.cooldown(rate=4, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def optout(self, ctx: commands.Context, *commands):
        """Opts out of given commands; {prefix}optout <command1> <command2>... or {prefix}optout all to optout of every command"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if len(commands) == 0:
            await self.bot.msg_q.reply(ctx, "Please provide commands to opt out of")
            return

        if commands[0] == "all":
            commands = tuple(self.bot.commands.keys())

        optoutable = []
        for command in commands:
            cmd = self.bot.get_command(command)
            if (
                cmd is not None
                and not cmd.no_global_checks
                and any(["target" in param.name for param in cmd.params.values()])
            ):
                optoutable.append(cmd.name)

        if len(optoutable) == 0:
            await self.bot.msg_q.reply(ctx, "None of the given commands are optoutable")
            return

        await users.optout(self.bot.con_pool, ctx.author.id, optoutable)
        await self.bot.msg_q.reply(
            ctx,
            f"Opted out of {', '.join(optoutable)}",
            [],
            users.optin,
            self.bot.con_pool,
            ctx.author.id,
            optoutable,
        )

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def undo(self, ctx: commands.Context):
        """Undoes the last action if it is undoable"""
        assert isinstance(ctx.author.name, str)

        action = self.bot.msg_q.actions.get_last_action(ctx.channel.name, ctx.author.name)
        if action is None:
            await self.bot.msg_q.reply(ctx, "No last action found")
            return
        if not self.bot.msg_q.actions.action_undoable(ctx.channel.name, ctx.author.name):
            await self.bot.msg_q.reply(ctx, f"Unable to undo last command <{action.command}>")
            return
        await self.bot.msg_q.actions.undo_action(ctx.channel.name, ctx.author.name)
        await self.bot.msg_q.reply(ctx, f"Undid command <{action.command}>")

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("commands",))
    async def cmds(self, ctx: commands.Context):
        """Shows all the commands currently enabled in the chat and that you are allowed to use"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        not_included_cogs = ["Admin"]

        if not ctx.author.is_mod:
            not_included_cogs.append("Moderator")

        if ctx.channel.name != self.bot.nick:
            not_included_cogs.append("Join")

        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        if not channel_config.logging:
            not_included_cogs.append("Message")

        seventv_account = await seventv.account_info(channel_config.channel_id)
        if seventv_account is not None:
            editors = await seventv.editors(seventv_account.user.id)
            editors_matching_user = [
                editor
                for editor in editors
                if len([con for con in editor.user.connections if con.id == ctx.author.id]) == 1
            ]
            sender_is_editor = len(editors_matching_user) == 1 or ctx.author.is_broadcaster
            if not sender_is_editor:
                not_included_cogs.append("SevenTVEditor")

        filtered_cogs = [cog for cog in self.bot.cogs.values() if cog.name not in not_included_cogs]

        messages = [
            " | ".join(
                [
                    ", ".join([cmd for cmd in cog.commands if cmd not in channel_config.disabled_commands])
                    for cog in filtered_cogs
                ]
            )
        ]

        if len(messages[0]) > 500:
            half_of_cogs = len(filtered_cogs) // 2
            messages = [
                " | ".join(
                    [
                        ", ".join([cmd for cmd in cog.commands if cmd not in channel_config.disabled_commands])
                        for cog in filtered_cogs[:half_of_cogs]
                    ]
                ),
                " | ".join(
                    [
                        ", ".join([cmd for cmd in cog.commands if cmd not in channel_config.disabled_commands])
                        for cog in filtered_cogs[half_of_cogs:]
                    ]
                ),
            ]

        for message in messages:
            await self.bot.msg_q.send(ctx, message)

    @commands.command()
    async def help(self, ctx: commands.Context, command: str | None):
        """Shows the command description of the given command; {prefix}help <command>"""
        if command is None:
            command = "help"
        cmd = self.bot.get_command(command.lower())
        if cmd is None:
            await self.bot.msg_q.send(ctx, "Given command doesn't exist")
            return

        description = self.bot.commands[cmd.name]._callback.__doc__
        if not description:
            await self.bot.msg_q.send(ctx, "No command description")
        else:
            cleaned = re.sub(r"\s+", " ", description.strip())
            prefixes = await self.bot.prefixes(ctx.channel.name)
            add_prefix = cleaned.replace("{prefix}", prefixes[0])
            await self.bot.msg_q.send(ctx, add_prefix)


def prepare(bot: "Bot"):
    bot.add_cog(Util(bot))
