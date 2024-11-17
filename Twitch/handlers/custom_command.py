import random
import re

from asyncpg import Pool
import twitchio
from twitchio.ext import commands

from shared.apis import twitch # TODO: use twitch
from shared.database.twitch import channels, counters, custom_commands, custom_patterns

# TODO: use some kind of recursion to replace nested arguments (depth 3)
# TODO: add $(args) to access arguments as a list
# TODO: make it possible to search for matching 7tv emotes
async def parse_message_content(
    message: twitchio.Message, con_pool: Pool, channel_id: str, cmd_message: str, args: list[str]
) -> str | None:
    assert isinstance(message.author.name, str)

    # positional arguments $(1), $(2)...
    for pos_arg in set(re.findall(r"(\$\(([1-9])\))", cmd_message)):
        pattern, index = pos_arg[0], int(pos_arg[1])
        if len(args) < index:
            return None
        cmd_message = cmd_message.replace(pattern, args[index - 1])

    # TODO: $(user) with stuff like $(user.id) and other things

    # positional arguments or sender $(1|sender), $(2|sender)...
    # TODO: make it just 1 or some other thing which can be anything $(1|$(sender)) and move this to be last
    # for pos_arg_sender in set(re.findall(r"(\$\(([1-9]\s?\|\s?sender)\))", cmd_message)):
    #     pattern, index = pos_arg_sender[0], int(pos_arg_sender[1])
    #     try:
    #         cmd_message = cmd_message.replace(pattern, args[index - 1])
    #     except IndexError:
    #         cmd_message = cmd_message.replace(pattern, message.author.name)

    cmd_message = cmd_message.replace("$(sender)", message.author.name)

    # random integer interval $(random m-n)
    for random_interval in re.findall(
        r"(\$\(random (-?(?:0|[1-9]\d{0,6}))\s?-\s?(-?(?:0|[1-9]\d{0,6}))\))", cmd_message
    ):
        pattern, start, end = random_interval[0], int(random_interval[1]), int(random_interval[2])
        if start > end:
            continue
        random_num = random.randint(start, end)
        cmd_message = cmd_message.replace(pattern, str(random_num), 1)

    # randomly picked phrases $(random '<phrase>' '<phrase>' ...)
    for pattern in re.findall(r"\$\(random (?:'[^']*'\s?)+\)", cmd_message):
        random_phrase = random.choice(re.findall(r"'([^']*)'", cmd_message))
        cmd_message = cmd_message.replace(pattern, random_phrase, 1)

    # change count $(count <name> +-n)
    for change_counter in set(
        re.findall(r"(\$\((?:count|counter) (\S+) ((?:\+|-)(?:0|[1-9]\d{0,6}))\))", cmd_message)
    ):
        pattern, counter_name, change = change_counter[0], change_counter[1].lower(), int(change_counter[2])
        changed_counter = await counters.change_counter(con_pool, channel_id, counter_name, change)
        cmd_message = cmd_message.replace(pattern, str(changed_counter.value))

    # get count $(count <name>)
    for show_counter in set(re.findall(r"(\$\((?:count|counter) (\S+)\))", cmd_message)):
        pattern, counter_name = show_counter
        counter = await counters.show_counter(con_pool, channel_id, counter_name.lower())
        cmd_message = cmd_message.replace(pattern, str(counter.value))

    return cmd_message


async def handle_custom_command(ctx: commands.Context) -> None:
    assert isinstance(ctx.message.content, str)
    assert isinstance(ctx.author, twitchio.Chatter)

    message = ctx.message.content
    channel_prefixes = await ctx.bot.prefixes(ctx.channel.name)  # type: ignore
    for prefix in channel_prefixes:
        if message.startswith(prefix):
            message = message.replace(prefix, "", 1).strip()
            break
    if not message:
        return
    cmd_name, *args = message.split()

    channel_id = await channels.channel_id(ctx.bot.con_pool, ctx.channel.name)  # type: ignore
    command = await custom_commands.show_custom_command(ctx.bot.con_pool, channel_id, cmd_name.lower())  # type: ignore
    if command is None:
        return

    match command.level:
        # case "FOLLOWER":
        #     subage = await ivr.subage(ctx.author.name, ctx.channel.name)
        #     if not (
        #         ctx.author.is_mod
        #         or ctx.author.is_vip
        #         or (subage is not None and subage.streak is None)
        #         or (subage is not None and subage.followed_at is None)
        #     ):
        #         return

        # case "SUBSCRIBER":
        #     subage = await ivr.subage(ctx.author.name, ctx.channel.name)
        #     if not (ctx.author.is_mod or ctx.author.is_vip or (subage is not None and subage.streak is None)):
        #         return

        case "VIP":
            if not (ctx.author.is_mod or ctx.author.is_vip):
                return

        case "MOD":
            if not ctx.author.is_mod:
                return

        case "BROADCASTER":
            if not ctx.author.is_broadcaster:
                return

    cmd_message = await parse_message_content(ctx.message, ctx.bot.con_pool, channel_id, command.message, args)  # type: ignore
    if cmd_message is None:
        return
    await ctx.bot.msg_q.send_message(ctx.channel.name, cmd_message)  # type: ignore


async def custom_pattern_message(message: twitchio.Message, con_pool: Pool) -> str | None:
    assert isinstance(message.content, str)

    channel_id = await channels.channel_id(con_pool, message.channel.name)
    patterns = await custom_patterns.list_custom_patterns(con_pool, channel_id)
    for pattern in patterns:
        if (
            pattern.regex and re.compile(pattern.pattern).match(message.content)
        ) or pattern.pattern in message.content:
            if pattern.probability > random.random():
                pattern_message = await parse_message_content(
                    message, con_pool, channel_id, pattern.message, message.content.split()
                )
                return pattern_message
