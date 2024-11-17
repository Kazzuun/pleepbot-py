from datetime import datetime, UTC
import os
import re
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
import twitchio
from twitchio.ext import commands

from handlers.custom_command import handle_custom_command, custom_pattern_message
from handlers.emote_streak import EmoteStreaks
from handlers.message_queue import MessageQueues
from logger import logger
from shared import database
from shared.apis.exceptions import SendableAPIRequestError
from shared.database.twitch import channels, messages, reminders, users
from Twitch.exceptions import ValidationError


# TODO: join and leave methods
class Bot(commands.Bot):
    def __init__(self) -> None:
        async def prefix_callback(bot: commands.Bot, message: twitchio.Message) -> tuple[str, ...]:
            return await self.prefixes(message.channel.name)

        super().__init__(
            token=os.environ["TMI_TOKEN"],
            client_id=os.environ["CLIENT_ID"],
            nick=os.environ["BOT_NICK"],
            prefix=prefix_callback,
        )
        self.loop.run_until_complete(self.__ainit__())
        self.msg_q = MessageQueues(self, self.initial_channels)
        self.emote_streaks = EmoteStreaks(self.con_pool)
        self.check(self.global_check)  # type: ignore

        for filename in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/cogs"):
            if filename.endswith(".py"):
                self.load_module(f"cogs.{filename[:-3]}")

    async def __ainit__(self):
        self.con_pool = await database.init_pool(self.loop)
        self.initial_channels = await channels.initial_channels(self.con_pool)
        if len(self.initial_channels) == 0:
            self.initial_channels.append(self.nick)  # type: ignore
            await channels.join_channel(self.con_pool, str(self.user_id), self.nick)  # type: ignore

    async def prefixes(self, channel: str) -> tuple[str, ...]:
        config = await channels.channel_config(self.con_pool, channel)
        if len(config.prefixes) == 0:
            return (os.environ["GLOBAL_PREFIX"],)
        return config.prefixes

    async def event_ready(self) -> None:
        await self.join_channels(self.initial_channels)
        logger.debug("Logged in as %s", str(self.nick))

    async def event_message(self, message: twitchio.Message) -> None:
        assert isinstance(message.content, str)
        message.content = re.sub(r"\s+", " ", message.content.strip()).replace("ACTION ", "")

        channel_config = await channels.channel_config(self.con_pool, message.channel.name)

        if message.echo:
            assert isinstance(self.nick, str)
            await messages.log_message(
                self.con_pool, channel_config.channel_id, self.nick, message.content, channel_config.currently_online
            )
            return

        assert isinstance(message.author.name, str)
        if channel_config.logging:
            await messages.log_message(
                self.con_pool,
                channel_config.channel_id,
                message.author.name,
                message.content,
                channel_config.currently_online,
            )

        # Log the messge with the null character to make the detecting the same message easier
        # and keeping the removed pings when a message is used in some commands,
        # but remove it here just in case it might cause problems, mostly for commands
        message.content = message.content.replace("\U000E0000", "")

        if message.content == "":
            return

        if not (isinstance(message.author, twitchio.Chatter) and message.author.id is not None):
            return

        if message.author.id in channel_config.banned_users:
            return

        user_config = await users.user_config(self.con_pool, message.author.id)
        if user_config.is_banned():
            return

        afk_status = await reminders.afk_status(self.con_pool, channel_config.channel_id, message.author.id)

        await self.handle_commands(message)

        if afk_status is not None:
            msg, targets = await afk_status.formatted_message(message.author.name)
            await self.msg_q.send_message(message.channel.name, msg, targets)
            await reminders.set_afk_as_sent(self.con_pool, afk_status.id)

        pattern_message = await custom_pattern_message(message, self.con_pool)
        if pattern_message is not None:
            await self.msg_q.send_message(message.channel.name, pattern_message)

        if channel_config.emote_streaks:
            streak_result = await self.emote_streaks.streak_message(
                message.channel.name, message.author.name, message.content
            )
            if streak_result is not None:
                streak_message, targets = streak_result
                await self.msg_q.send_message(message.channel.name, streak_message, targets)

        rems = await reminders.sendable_not_timed_reminders(self.con_pool, message.author.id)
        for rem in rems:
            if not channel_config.outside_reminds and rem.channel_id != channel_config.channel_id:
                continue
            rem_users = await self.fetch_users(ids=[int(rem.sender_id), int(rem.target_id)])
            sender = [user for user in rem_users if user.id == int(rem.sender_id)]
            if len(sender) == 1:
                sender_name = sender[0].name
            else:
                sender_name = "<unknown user>"
            target = [user for user in rem_users if user.id == int(rem.target_id)][0]
            msg, targets = await rem.formatted_message(sender_name, target.name)
            await self.msg_q.send_message(message.channel.name, msg, targets)
            await reminders.set_reminder_as_sent(self.con_pool, rem.id)

    async def handle_commands(self, message: twitchio.Message) -> None:
        assert isinstance(message.content, str) and message.content != ""
        # Allow a whitespace between prefix and the command name
        if message.content.startswith(tuple(prefix + " " for prefix in await self.prefixes(message.channel.name))):
            message.content = message.content.replace(" ", "", 1)
        cmd_and_args = message.content.split(maxsplit=1)
        # Make commands case insensitive
        message.content = f"{cmd_and_args[0].lower()} {' '.join(cmd_and_args[1:])}"
        # Allow using _ before targets
        message.content = " ".join([word.lstrip("_") for word in message.content.split()])
        await super().handle_commands(message)

    async def event_command_error(self, context: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            await handle_custom_command(context)

        elif isinstance(error, commands.CommandOnCooldown):
            await self.msg_q.reply(context, "Slow down a bit and try again later")

        elif isinstance(error, SendableAPIRequestError) or isinstance(error, ValidationError):
            await self.msg_q.reply(context, error.message)

        elif (
            isinstance(error, commands.ArgumentParsingFailed)
            or isinstance(error, commands.BadArgument)
            or isinstance(error, commands.MissingRequiredArgument)
        ):
            prefixes = await self.prefixes(context.channel.name)
            assert context.command is not None
            command_name = context.command.name
            await self.msg_q.reply(
                context,
                f'Some arguments to the command are missing or wrong; see "{prefixes[0]}help {command_name}" for instructions',
            )

        elif isinstance(error, commands.CheckFailure):
            pass

        else:
            await self.msg_q.reply(context, "An unexpected error occured")
            await super().event_command_error(context, error)

    async def event_notice(self, message: str, msg_id: str | None, channel: twitchio.Channel | None):
        logger.debug(f"{message=}, {msg_id=}, {channel=}")

    async def global_check(self, ctx: commands.Context) -> bool:
        """Global check if a target has opted out of the command or is banned"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        user_config = await users.user_config(self.con_pool, ctx.author.id)
        if ctx.command is not None and ctx.command.name in user_config.optouts:
            raise ValidationError("You cannot use a command you have opted out of")

        channel_config = await channels.channel_config(self.con_pool, ctx.channel.name)
        if ctx.command is not None and ctx.command.name in channel_config.disabled_commands:
            return False

        if ctx.args is None:
            return True

        target_users = [
            arg
            for arg in ctx.args
            if (isinstance(arg, twitchio.User) or isinstance(arg, twitchio.PartialUser))
            and ctx.author.name != arg.name
        ]

        for target in target_users:
            user_config = await users.user_config(self.con_pool, str(target.id))
            if user_config.is_banned() or str(target.id) in channel_config.banned_users:
                return False
            if ctx.command is not None and ctx.command.name in user_config.optouts:
                raise ValidationError("Target has opted out of the command")

        return True

    async def global_before_invoke(self, ctx: commands.Context):
        ctx.exec_time = datetime.now(UTC)  # type: ignore
        if isinstance(ctx.author, twitchio.Chatter) and ctx.author.id is not None:
            await users.create_user_config(self.con_pool, ctx.author.id)

    async def global_after_invoke(self, ctx: commands.Context) -> None:
        assert isinstance(ctx.author.name, str)
        last_action = self.msg_q.actions.get_last_action(ctx.channel.name, ctx.author.name)
        if last_action is not None:
            exec_time_ellapsed = round((datetime.now(UTC) - ctx.exec_time).total_seconds() * 1000, 3)  # type: ignore
            channel_id = await channels.channel_id(self.con_pool, last_action.channel)
            await messages.log_command_usage(
                self.con_pool,
                channel_id,
                last_action.actor_id,
                last_action.command,
                last_action.message,
                exec_time_ellapsed,
            )


if __name__ == "__main__":
    load_dotenv()
    bot = Bot()
    bot.run()
