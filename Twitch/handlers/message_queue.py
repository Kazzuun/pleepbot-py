from abc import ABC, abstractmethod
from asyncio import Queue, sleep, Task
from datetime import datetime, timedelta, UTC
from functools import partial
import re
from typing import Any, Callable, Coroutine, TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import twitch # TODO: use twitch
from shared.database.twitch import channels, messages, users
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Action:
    def __init__(
        self,
        ctx: commands.Context,
        channel: str,
        actor: str,
        actor_id: str,
        command: str,
        message: str,
        undo_callback: Callable[..., Coroutine[Any, Any, Any]] | None = None,
        reply: bool = False,
    ) -> None:
        self.ctx = ctx
        self.channel = channel
        self.actor = actor
        self.actor_id = actor_id
        self.command = command
        self.message = message
        self.undo_callback = undo_callback
        self.reply = reply
        self.executed_at = datetime.now(UTC)

    async def undo(self):
        if self.undo_callback is not None:
            await self.undo_callback()


class ActionStorage:
    def __init__(self) -> None:
        self._action_expiration = timedelta(minutes=30)
        self._actions: dict[tuple[str, str], Action] = {}

    def add_action(self, action: Action) -> None:
        self._actions[(action.channel, action.actor)] = action

    def remove_action(self, channel: str, actor: str) -> None:
        if (channel, actor) in self._actions:
            del self._actions[(channel, actor)]

    def get_last_action(self, channel: str, actor: str) -> Action | None:
        return self._actions.get((channel, actor))

    def action_undoable(self, channel: str, actor: str) -> bool:
        action = self.get_last_action(channel, actor)
        if action is None:
            return False
        if action.undo_callback is None:
            return False
        if action.executed_at < datetime.now(UTC) - self._action_expiration:
            return False
        return True

    async def undo_action(self, channel: str, actor: str) -> None:
        if self.action_undoable(channel, actor):
            action = self.get_last_action(channel, actor)
            assert action is not None
            await action.undo()
            self.remove_action(channel, actor)

    def create_and_add_action(
        self,
        ctx: commands.Context,
        message: str,
        reply: bool = False,
        undo_callback: Callable[..., Coroutine[Any, Any, Any]] | None = None,
        *undo_args,
        **undo_kwargs,
    ) -> Action:
        assert isinstance(ctx.author.name, str)
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.command is not None
        assert ctx.author.id is not None

        if undo_callback is not None:
            callback = partial(undo_callback, *undo_args, **undo_kwargs)
        else:
            callback = None
        action = Action(
            ctx,
            ctx.channel.name,
            ctx.author.name,
            ctx.author.id,
            ctx.command.name,
            message,
            callback,
            reply,
        )
        self.add_action(action)
        return action


class SendableMessage(ABC):
    def __init__(self, *args, **kwargs) -> None:
        self.message: str
        self.channel: str
        self.bot_is_mod_or_vip: bool

    @abstractmethod
    async def send(self) -> None:
        pass


class CommandMessage(SendableMessage):
    def __init__(self, action: Action, bot_is_mod_or_vip: bool) -> None:
        self.action = action
        self.message = action.message
        self.channel = action.channel
        self.bot_is_mod_or_vip = bot_is_mod_or_vip

    async def send(self) -> None:
        if self.action.reply:
            await self.action.ctx.reply(self.message)
        else:
            await self.action.ctx.send(self.message)


class Message(SendableMessage):
    def __init__(self, bot: "Bot", channel: str, message: str, bot_is_mod_or_vip: bool) -> None:
        self.bot = bot
        self.channel = channel
        self.message = message
        self.bot_is_mod_or_vip = bot_is_mod_or_vip

    async def send(self) -> None:
        self.current_channel = self.bot.get_channel(self.channel)
        assert self.current_channel is not None
        await self.current_channel.send(self.message)


class MessageQueues:
    def __init__(self, bot: "Bot", initial_channels: list[str]) -> None:
        self.bot = bot
        self.actions = ActionStorage()
        self._queues: dict[str, Queue[SendableMessage]] = {}
        self._tasks: dict[str, Task] = {}
        for channel in initial_channels:
            self.add_channel(channel)

    async def _clear_queue(self, channel: str) -> None:
        while True:
            message = await self._queues[channel].get()
            await message.send()
            if not message.bot_is_mod_or_vip:
                await sleep(1.2)
            else:
                await sleep(0.1)

    def add_channel(self, channel: str) -> None:
        if channel not in self._queues:
            self._queues[channel] = Queue()
        if channel not in self._tasks:
            self._tasks[channel] = self.bot.loop.create_task(self._clear_queue(channel))

    def remove_channel(self, channel: str) -> None:
        if channel in self._tasks:
            task = self._tasks[channel]
            task.cancel()
            del self._tasks[channel]
        if channel in self._queues:
            del self._queues[channel]

    async def _add_to_queue(self, msg: SendableMessage, targets: list[str] | tuple[str, ...]) -> None:
        """Processing of the message before it is added to the queue."""
        msg.message = re.sub(r"\s+", " ", msg.message.strip())

        blocked_words = await messages.blocked_terms(self.bot.con_pool)
        replacement_word = "<pleep>"
        for word in blocked_words:
            if word.regex:
                try:
                    msg.message = re.sub(word.pattern, replacement_word, msg.message)
                except re.error as e:
                    logger.warning(
                        f"Invalid regex in blocked words: %s (id: %d) %s",
                        word.pattern,
                        word.id,
                        str(e),
                    )
            else:
                msg.message = msg.message.replace(word.pattern, replacement_word)

        def insert_null_character(string: str) -> str:
            if len(string) == 0:
                return string
            return string[:2] + "\U000E0000" + string[2:]

        if isinstance(msg, CommandMessage) and msg.action.reply:
            user_config = await users.user_config(self.bot.con_pool, msg.action.actor_id)
            if user_config.no_replies:
                msg.action.reply = False
                msg.message = f"{insert_null_character(msg.action.actor)}, {msg.message}"

        for user in targets:
            msg.message = re.sub(rf"\b@?{user}[,.:-]?\b", insert_null_character(user), msg.message)

        if not msg.bot_is_mod_or_vip:
            channel_id = await channels.channel_id(self.bot.con_pool, msg.channel)
            bot_last_message = await messages.last_seen(self.bot.con_pool, channel_id, self.bot.nick)  # type: ignore
            if (
                bot_last_message is not None
                and bot_last_message.message == msg.message
                and (datetime.now(UTC) - bot_last_message.sent_at).seconds <= 30
            ):
                msg.message = insert_null_character(msg.message)

        if len(msg.message) > 500:
            msg.message = msg.message[:496] + " ..."

        await self._queues[msg.channel].put(msg)

    async def send_message(self, channel: str, message: str, targets: list[str] | tuple[str, ...] = tuple()):
        # mods_and_vips = await ivr.modvip(ctx.channel.name)
        # bot_is_mod_or_vip = self.bot.nick in [user.username for user in mods_and_vips.vips + mods_and_vips.mods]
        current_channel = self.bot.get_channel(channel)
        bot_is_mod_or_vip = bool(current_channel._bot_is_mod()) if current_channel is not None else False
        await self._add_to_queue(Message(self.bot, channel, message, bot_is_mod_or_vip), targets)

    async def send(
        self,
        ctx: commands.Context,
        message: str,
        targets: list[str] | tuple[str, ...] = tuple(),
        undo_callback: Callable[..., Coroutine[Any, Any, Any]] | None = None,
        *undo_args,
        **undo_kwargs,
    ) -> None:
        action = self.actions.create_and_add_action(ctx, message, False, undo_callback, *undo_args, **undo_kwargs)
        # mods_and_vips = await ivr.modvip(ctx.channel.name)
        # bot_is_mod_or_vip = self.bot.nick in [user.username for user in mods_and_vips.vips + mods_and_vips.mods]
        bot_is_mod_or_vip = bool(ctx.channel._bot_is_mod())
        await self._add_to_queue(CommandMessage(action, bot_is_mod_or_vip), targets)

    async def reply(
        self,
        ctx: commands.Context,
        message: str,
        targets: list[str] | tuple[str, ...] = tuple(),
        undo_callback: Callable[..., Coroutine[Any, Any, Any]] | None = None,
        *undo_args,
        **undo_kwargs,
    ) -> None:
        action = self.actions.create_and_add_action(ctx, message, True, undo_callback, *undo_args, **undo_kwargs)
        # mods_and_vips = await ivr.modvip(ctx.channel.name)
        # bot_is_mod_or_vip = self.bot.nick in [user.username for user in mods_and_vips.vips + mods_and_vips.mods]
        bot_is_mod_or_vip = bool(ctx.channel._bot_is_mod())
        await self._add_to_queue(CommandMessage(action, bot_is_mod_or_vip), targets)
