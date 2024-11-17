from datetime import datetime, UTC
import os
import re
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import twitch  # TODO: use twitch
from shared.database.twitch import channels, counters, custom_commands, custom_patterns, timers, users
from shared.util.formatting import format_timedelta
from Twitch.exceptions import ValidationError

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Moderator(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if not ctx.author.is_mod:
            user_config = await users.user_config(self.bot.con_pool, ctx.author.id)
            if not user_config.is_admin():
                raise ValidationError("You must be a moderator to use this command")
        return True

    @commands.cooldown(rate=3, per=20, bucket=commands.Bucket.member)
    @commands.command()
    async def pyramid(self, ctx: commands.Context, size: int, *words):
        """
        (mod only) Creates a pyramid out of given message; minimum size is 2 and maximum is 15 when the bot is
        mod or vip and else 5; {prefix}pyramid <size> <message>
        """
        if len(words) == 0:
            return
        message = " ".join(words)
        # modvip = await ivr.modvip(ctx.channel.name)
        # bot_is_mod_or_vip = str(self.bot.user_id) in [user.id for user in modvip.mods + modvip.vips]
        bot_is_mod_or_vip = ctx.channel._bot_is_mod()
        max_size = 15 if bot_is_mod_or_vip else 5
        size = min(max(size, 2), min(350 // len(message), max_size))
        for i in range(1, size + 1):
            await self.bot.msg_q.send(ctx, f"{message} " * i)
        for j in range(size - 1, 0, -1):
            await self.bot.msg_q.send(ctx, f"{message} " * j)

    @commands.command(no_global_checks=True)
    async def ban(self, ctx: commands.Context, target: twitchio.PartialUser):
        """Bans the target from using the bot in the current channel; {prefix}ban <target>"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if ctx.author.id == str(target.id):
            await self.bot.msg_q.reply(ctx, "You cannot ban yourself")
            return

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)

        if str(target.id) == channel_id:
            await self.bot.msg_q.reply(ctx, "You cannot ban the channel owner")
            return

        # modvip = await ivr.modvip(ctx.channel.name)
        # if not ctx.author.is_broadcaster and str(target.id) in [mod.id for mod in modvip.mods]:
        #     await self.bot.msg_q.reply(ctx, "You cannot ban another moderator")
        #     return

        success = await channels.ban_in_channel(self.bot.con_pool, channel_id, str(target.id))
        if success:
            await self.bot.msg_q.reply(
                ctx,
                "User banned successfully",
                [],
                channels.unban_in_channel,
                self.bot.con_pool,
                channel_id,
                str(target.id),
            )
        else:
            await self.bot.msg_q.reply(ctx, "User is already banned")

    @commands.command(no_global_checks=True)
    async def unban(self, ctx: commands.Context, target: twitchio.PartialUser):
        """Unbans the target in the current channel; {prefix}unban <target>"""
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        success = await channels.unban_in_channel(self.bot.con_pool, channel_config.channel_id, str(target.id))
        if success:
            await self.bot.msg_q.reply(
                ctx,
                "User unbanned successfully",
                [],
                channels.ban_in_channel,
                self.bot.con_pool,
                channel_config.channel_id,
                str(target.id),
            )
        else:
            await self.bot.msg_q.reply(ctx, "User is not currently banned")

    @commands.command(no_global_checks=True)
    async def enable(self, ctx: commands.Context, *commands):
        """Enables commands in the channel that have been previously disabled; {prefix}enable <command1> <command2>..."""
        enableable = []
        for command in commands:
            cmd = self.bot.get_command(command)
            if cmd is not None and not cmd.no_global_checks:
                enableable.append(cmd.name)
        if len(enableable) == 0:
            await self.bot.msg_q.reply(ctx, "Please provide valid commands")
            return
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        await channels.enable_commands(self.bot.con_pool, channel_config.channel_id, enableable)
        await self.bot.msg_q.reply(
            ctx,
            f"Enabled commands {', '.join(enableable)}",
            [],
            channels.disable_commands,
            self.bot.con_pool,
            channel_config.channel_id,
            enableable,
        )

    @commands.command(no_global_checks=True)
    async def disable(self, ctx: commands.Context, *commands):
        """Disables commands in the channel; {prefix}disable <command1> <command2>..."""
        disableable = []
        for command in commands:
            cmd = self.bot.get_command(command)
            if cmd is not None and not cmd.no_global_checks:
                disableable.append(cmd.name)
        if len(disableable) == 0:
            await self.bot.msg_q.reply(ctx, "Please provide valid commands")
            return
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        await channels.disable_commands(self.bot.con_pool, channel_config.channel_id, disableable)
        await self.bot.msg_q.reply(
            ctx,
            f"Disabled commands {', '.join(disableable)}",
            [],
            channels.enable_commands,
            self.bot.con_pool,
            channel_config.channel_id,
            disableable,
        )

    @commands.command(aliases=("prefixes",))
    async def prefix(self, ctx: commands.Context, action: str | None, *args):
        """
        Allows giving the bot a custom prefix in the channel, max 3 can be given and if none are active, the global one is used,
        current prefixes in the channel can be shown with {prefix}prefix show; prefixes can be added with
        {prefix}prefix add <prefix1> <prefix2>... and removed with {prefix}prefix remove <prefix1> <prefix2>...
        """
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        match action:
            case "list" | "show" | None:
                if len(channel_config.prefixes) == 0:
                    await self.bot.msg_q.reply(
                        ctx,
                        f"This channel doesn't have any custom prefixes, the global prefix is '{os.environ['GLOBAL_PREFIX']}'",
                    )
                else:
                    await self.bot.msg_q.reply(
                        ctx, f"The prefixes in this channel are: {' '.join(channel_config.prefixes)}"
                    )

            case "add":
                if len(args) == 0:
                    await self.bot.msg_q.reply(ctx, "Please provide prefixes to add")
                    return
                max_prefixes = 3
                prefix_max_length = 5
                disallowed_prefixes = {"/"}
                new_prefixes = [
                    prefix
                    for prefix in args
                    if prefix not in disallowed_prefixes
                    and prefix not in channel_config.prefixes
                    and len(prefix) <= prefix_max_length
                ]
                if len(new_prefixes) == 0:
                    await self.bot.msg_q.reply(ctx, "Please provide valid prefixes that aren't already enabled")
                    return
                if len(new_prefixes) + len(channel_config.prefixes) > max_prefixes:
                    await self.bot.msg_q.reply(ctx, f"You can only have upto {max_prefixes} custom prefixes")
                    return
                await channels.add_prefixes(self.bot.con_pool, channel_config.channel_id, new_prefixes)
                await self.bot.msg_q.reply(
                    ctx,
                    f"The prefixes in this channel now are: {' '.join(list(channel_config.prefixes) + new_prefixes)}",
                    [],
                    channels.remove_prefixes,
                    self.bot.con_pool,
                    channel_config.channel_id,
                    new_prefixes,
                )

            case "remove":
                if len(args) == 0:
                    await self.bot.msg_q.reply(ctx, "Please provide prefixes to remove")
                    return
                removed_prefixes = [prefix for prefix in args if prefix in channel_config.prefixes]
                if len(removed_prefixes) == 0:
                    await self.bot.msg_q.reply(
                        ctx, "Please provide valid prefixes that are currently enabled to remove them"
                    )
                    return
                await channels.remove_prefixes(self.bot.con_pool, channel_config.channel_id, removed_prefixes)
                current_prefixes = await self.bot.prefixes(ctx.channel.name)
                await self.bot.msg_q.reply(
                    ctx,
                    f"The prefixes in this channel now are: {' '.join(current_prefixes)}",
                    [],
                    channels.add_prefixes,
                    self.bot.con_pool,
                    channel_config.channel_id,
                    removed_prefixes,
                )

            case _:
                raise commands.MissingRequiredArgument

    @commands.command(aliases=("option", "setting", "settings"))
    async def options(self, ctx: commands.Context, setting: str | None, on_or_off: str | None):
        """
        Allows changing of bot settings in the channel; settings can be shown with {prefix}options show;
        different settings can be disabled and enabled: {prefix}options <setting> <on/off>; possible settings to change:
        logging, streaks, commands, reminds, outsidereminds, notifications
        """
        enable_words = ("enable", "enabled", "on", "true")
        disable_words = ("disable", "disabled", "off", "false")

        if setting not in ("show", "list", None) and (
            on_or_off is None or (on_or_off not in enable_words and on_or_off not in disable_words)
        ):
            await self.bot.msg_q.reply(ctx, "Please specify whether to enable or disable the option")
            return

        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        match setting:
            case "list" | "show" | None:
                logging = "logging: " + ("enabled" if channel_config.logging else "disabled")
                emote_streaks = "emote streaks: " + ("enabled" if channel_config.emote_streaks else "disabled")
                commands_online = "commands online: " + ("enabled" if channel_config.commands_online else "disabled")
                reminds_online = "reminds online: " + ("enabled" if channel_config.reminds_online else "disabled")
                outside_reminds = "outside reminds: " + ("enabled" if channel_config.outside_reminds else "disabled")
                notifications_online = "notifications online: " + (
                    "enabled" if channel_config.notifications_online else "disabled"
                )
                await self.bot.msg_q.reply(
                    ctx,
                    ", ".join(
                        [
                            logging,
                            emote_streaks,
                            commands_online,
                            reminds_online,
                            outside_reminds,
                            notifications_online,
                        ]
                    ),
                )

            case "logging":
                if on_or_off in enable_words:
                    success = await channels.logging_on(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Logging is now enabled",
                            [],
                            channels.logging_off,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Logging is already enabled")
                else:
                    success = await channels.logging_off(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Logging is now disabled",
                            [],
                            channels.logging_on,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Logging is already disabled")

            case "streaks":
                if on_or_off in enable_words:
                    success = await channels.emote_streaks_on(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Emote streaks are now enabled",
                            [],
                            channels.emote_streaks_off,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Emote streaks are already enabled")
                else:
                    success = await channels.emote_streaks_off(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Emote streaks are now disabled",
                            [],
                            channels.emote_streaks_on,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Emote streaks are already disabled")

            case "commands":
                if on_or_off in enable_words:
                    success = await channels.commands_online_on(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Commands are now enabled when the channel is online",
                            [],
                            channels.commands_online_off,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Commands are already enabled")
                else:
                    success = await channels.commands_online_off(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Commands are now disabled when the channel is online",
                            [],
                            channels.commands_online_on,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Commands are already disabled")

            case "reminds":
                if on_or_off in enable_words:
                    success = await channels.reminds_online_on(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Reminders are now enabled when the channel is online",
                            [],
                            channels.reminds_online_off,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Reminders are already enabled")
                else:
                    success = await channels.reminds_online_off(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Reminders are now disabled when the channel is online",
                            [],
                            channels.reminds_online_on,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Reminders are already disabled")

            case "outsidereminds":
                if on_or_off in enable_words:
                    success = await channels.outside_reminds_on(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Reminders are now sent outside of the channel and outside reminders get sent in this channel",
                            [],
                            channels.outside_reminds_off,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Reminders to and from outside are already allowed")
                else:
                    success = await channels.outside_reminds_off(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Reminders are no longer sent to outside of the channel and outside reminders don't get sent in this channel",
                            [],
                            channels.outside_reminds_on,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Reminders to and from outside are already disallowed")

            case "notifications":
                if on_or_off in enable_words:
                    success = await channels.notifications_online_on(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Notifications are now enabled when the channel is online",
                            [],
                            channels.notifications_online_off,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Notifications are already enabled")
                else:
                    success = await channels.notifications_online_off(self.bot.con_pool, channel_config.channel_id)
                    if success:
                        await self.bot.msg_q.reply(
                            ctx,
                            "Notifications are now disabled when the channel is online",
                            [],
                            channels.notifications_online_on,
                            self.bot.con_pool,
                            channel_config.channel_id,
                        )
                    else:
                        await self.bot.msg_q.reply(ctx, "Notifications are already disabled")

            case _:
                raise commands.MissingRequiredArgument

    @commands.command(aliases=("counters",))
    async def counter(self, ctx: commands.Context, action: str, counter_name: str | None, value: int | None):
        """
        Allows editing  and showing of counters; to list the names of all counters: {prefix}counter list;
        to show the value of a specific counter: {prefix}counter show <name>; to set a specific counter to some value:
        {prefix}counter set <value>; to reset a counter: {prefix}counter reset <name>
        """
        if counter_name is not None:
            counter_name = counter_name.lower()
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        match action:
            case "reset":
                if counter_name is None:
                    await self.bot.msg_q.reply(ctx, "Please provide the name of the counter to reset")
                    return
                reset_counter = await counters.show_counter(self.bot.con_pool, channel_id, counter_name)
                await counters.reset_counter(self.bot.con_pool, channel_id, counter_name)
                await self.bot.msg_q.reply(
                    ctx,
                    f"Reset counter {counter_name} to 0",
                    [],
                    counters.set_counter,
                    self.bot.con_pool,
                    channel_id,
                    counter_name,
                    reset_counter.value,
                )

            case "set":
                if counter_name is None:
                    await self.bot.msg_q.reply(ctx, "Please provide the name and the value of the counter to be set")
                    return
                if value is None:
                    await self.bot.msg_q.reply(ctx, "Please provide a number to set the counter to")
                    return
                edit_counter = await counters.show_counter(self.bot.con_pool, channel_id, counter_name)
                await counters.set_counter(self.bot.con_pool, channel_id, counter_name, value)
                await self.bot.msg_q.reply(
                    ctx,
                    f"Set counter {counter_name} to {value}",
                    [],
                    counters.set_counter,
                    self.bot.con_pool,
                    channel_id,
                    counter_name,
                    edit_counter.value,
                )

            case "show":
                if counter_name is None:
                    await self.bot.msg_q.reply(ctx, "Please provide the name of the counter to be shown")
                    return
                counter = await counters.show_counter(self.bot.con_pool, channel_id, counter_name)
                await self.bot.msg_q.reply(ctx, f"The value of {counter.name} counter is {counter.value}")

            case "list":
                counter_list = await counters.list_counters(self.bot.con_pool, channel_id)
                if len(counter_list) == 0:
                    await self.bot.msg_q.reply(ctx, "No counters exist")
                    return
                await self.bot.msg_q.reply(
                    ctx, " | ".join([f"{counter.name}: {counter.value}" for counter in counter_list])
                )

            case _:
                raise commands.MissingRequiredArgument

    # TODO: add an option to choose when it's active (online/offline)
    # @commands.command()
    # async def timer(
    #     self,
    #     ctx: commands.Context,
    #     action: Literal["add", "remove", "edit", "copy", "enable", "disable", "show", "list"],
    #     timer_name: str | None,
    #     *args
    # ):
    #     """"""
    #     if timer_name is not None:
    #         timer_name = timer_name.lower()
    #     channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
    #     match action:
    #         case 'add':
    #             if timer_name is None:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify a name for the timer to be added')
    #                 return
    #             exists = await timers.timer_exists(self.bot.con_pool, channel_id, timer_name)
    #             if exists:
    #                 await self.bot.msg_q.reply(ctx, f'Timer <{timer_name}> already exists, edit instead?')
    #                 return
    #             # TODO
    #             # if len(args) == 0:
    #             #     await self.bot.msg_q.reply(ctx, 'Command must have a length greater than zero')
    #             #     return
    #             # message = ' '.join(args)
    #             await timers.add_timer(self.bot.con_pool, channel_id, timer_name)
    #             await self.bot.msg_q.reply(ctx, f'Added timer <{timer_name}>')

    #         case 'remove':
    #             if timer_name is None:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify the name of the timer to be removed')
    #                 return
    #             exists = await timers.timer_exists(self.bot.con_pool, channel_id, timer_name)
    #             if not exists:
    #                 await self.bot.msg_q.reply(ctx, f"Timer <{timer_name}> doesn't exist")
    #                 return
    #             await timers.delete_timer(self.bot.con_pool, channel_id, timer_name)
    #             await self.bot.msg_q.reply(ctx, f'Deleted timer <{timer_name}>')

    #         case 'edit':
    #             if timer_name is None:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify the name of the timer to be edited')
    #                 return
    #             exists = await timers.timer_exists(self.bot.con_pool, channel_id, timer_name)
    #             if not exists:
    #                 await self.bot.msg_q.reply(ctx, f"Timer <{timer_name}> doesn't exist, add instead?")
    #                 return
    #             # TODO
    #             # if len(args) == 0:
    #             #     await self.bot.msg_q.reply(ctx, 'Command must have a length greater than zero')
    #             #     return
    #             # new_content = ' '.join(args)
    #             await timers.edit_timer(self.bot.con_pool, channel_id, timer_name)
    #             await self.bot.msg_q.reply(ctx, f'Edited timer <{timer_name}>')

    #         case 'copy':
    #             if timer_name is None:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify the name of the timer to be copied')
    #                 return
    #             if len(args) == 0 or args[0].lower() not in [channel.name for channel in self.bot.connected_channels]:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify a channel the bot is in')
    #                 return
    #             channel_id = await channels.channel_id(self.bot.con_pool, args[0])
    #             target_timer = await timers.show_timer(self.bot.con_pool, channel_id, timer_name)
    #             if target_timer is None:
    #                 await self.bot.msg_q.reply(ctx, f"Timer <{timer_name}> doesn't exist")
    #                 return
    #             alias = timer_name if len(args[1:]) == 0 else args[1]
    #             exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, alias)
    #             if exists:
    #                 await self.bot.msg_q.reply(ctx, f"A timer <{alias}> already exists in this channel")
    #                 return
    #             await timers.add_timer(self.bot.con_pool, channel_id, alias, target_timer.message, target_timer.next_time, target_timer.time_between)
    #             await self.bot.msg_q.reply(ctx, f'Added timer <{timer_name}>')

    #         case 'enable':
    #             if timer_name is None:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify the name of the command to be enabled')
    #                 return
    #             exists = await timers.timer_exists(self.bot.con_pool, channel_id, timer_name)
    #             if not exists:
    #                 await self.bot.msg_q.reply(ctx, f"Timer <{timer_name}> doesn't exist")
    #                 return
    #             success = await timers.enable_timer(self.bot.con_pool, channel_id, timer_name)
    #             if success:
    #                 await self.bot.msg_q.reply(ctx, f'Enabled timer <{timer_name}>')
    #             else:
    #                 await self.bot.msg_q.reply(ctx, f'Timer <{timer_name}> is already enabled')

    #         case 'disable':
    #             if timer_name is None:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify the name of the timer to be disabled')
    #                 return
    #             exists = await timers.timer_exists(self.bot.con_pool, channel_id, timer_name)
    #             if not exists:
    #                 await self.bot.msg_q.reply(ctx, f"Timer <{timer_name}> doesn't exist")
    #                 return
    #             success = await timers.disable_timer(self.bot.con_pool, channel_id, timer_name)
    #             if success:
    #                 await self.bot.msg_q.reply(ctx, f'Disabled timer <{timer_name}>')
    #             else:
    #                 await self.bot.msg_q.reply(ctx, f'Timer <{timer_name}> is already disabled')

    #         case 'show':
    #             if timer_name is None:
    #                 await self.bot.msg_q.reply(ctx, 'Please specify the name of the timer to be shown')
    #                 return
    #             timer = await timers.show_timer(self.bot.con_pool, channel_id, timer_name)
    #             if timer is None:
    #                 await self.bot.msg_q.reply(ctx, f"Timer <{timer_name}> doesn't exist")
    #                 return
    #             await self.bot.msg_q.reply(ctx, f"Timer <{timer_name}> next time: {timer.next_time.strftime("%Y-%m-%d, %H:%M:%S")} (in {format_timedelta(datetime.now(UTC) - timer.next_time)}), time between: {format_timedelta(timer.time_between)}, enabled: {str(timer.enabled).lower()}, message: {timer.message} ")

    #         case 'list':
    #             times = await timers.list_timers(self.bot.con_pool, channel_id)
    #             if len(times) == 0:
    #                 await self.bot.msg_q.reply(ctx, "No timers exist")
    #                 return
    #             await self.bot.msg_q.reply(ctx, ", ".join([timer.name for timer in times]))

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def cmd(self, ctx: commands.Context, action: str | None, cmd_name: str | None, *args):
        """
        Allows managing of custom commands; to list all the custom commands in the current channel {prefix}cmd list;
        {prefix}cmd <action> <name> <possible args>; the actions are: add, remove, edit, level, copy, enable, disable, show;
        possible commands levels are: everyone, follower, subscriber, vip, mod, broadcaster
        """
        if cmd_name is not None:
            cmd_name = cmd_name.lower()
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        match action:
            case "list" | None:
                cmds = await custom_commands.list_custom_commands(self.bot.con_pool, channel_id)
                if len(cmds) == 0:
                    await self.bot.msg_q.reply(ctx, "No custom commands exist")
                    return
                await self.bot.msg_q.reply(ctx, ", ".join([cmd.name for cmd in cmds]))

            case "show":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify the name of the command to be shown")
                    return
                command = await custom_commands.show_custom_command(self.bot.con_pool, channel_id, cmd_name)
                if command is None:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> doesn't exist")
                    return
                await self.bot.msg_q.reply(
                    ctx,
                    f"Command <{cmd_name}> level: {command.level}, enabled: {str(command.enabled).lower()}, message: {command.message}",
                )

            case "add":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify a name for the command to be added")
                    return
                if cmd_name in self.bot.commands:
                    await self.bot.msg_q.reply(ctx, "Command name cannot share a name with global commands")
                    return
                if len(args) == 0:
                    await self.bot.msg_q.reply(ctx, "Command must have a length greater than zero")
                    return
                message = " ".join(args)
                exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, cmd_name)
                if exists:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> already exists, edit instead?")
                    return
                await custom_commands.add_custom_command(self.bot.con_pool, channel_id, cmd_name, message)
                await self.bot.msg_q.reply(ctx, f"Added command <{cmd_name}>")

            case "remove":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify the name of the command to be removed")
                    return
                exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, cmd_name)
                if not exists:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> doesn't exist")
                    return
                await custom_commands.delete_custom_command(self.bot.con_pool, channel_id, cmd_name)
                await self.bot.msg_q.reply(ctx, f"Deleted command <{cmd_name}>")

            case "edit":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify the name of the command to be edited")
                    return
                if cmd_name in self.bot.commands:
                    await self.bot.msg_q.reply(ctx, "Command name cannot share a name with global commands")
                    return
                if len(args) == 0:
                    await self.bot.msg_q.reply(ctx, "Command must have a length greater than zero")
                    return
                new_content = " ".join(args)
                exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, cmd_name)
                if not exists:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> doesn't exist, add instead?")
                    return
                await custom_commands.edit_custom_command(self.bot.con_pool, channel_id, cmd_name, new_content)
                await self.bot.msg_q.reply(ctx, f"Edited command <{cmd_name}>")

            case "level":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify the name of the command to be edited")
                    return
                if len(args) == 0 or args[0].upper() not in [
                    "BROADCASTER",
                    "MOD",
                    "VIP",
                    "SUBSCRIBER",
                    "FOLLOWER",
                    "EVERYONE",
                ]:
                    await self.bot.msg_q.reply(ctx, "Please provide a valid persmission level")
                    return
                exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, cmd_name)
                if not exists:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> doesn't exist, add it first instead?")
                    return
                await custom_commands.set_permissions(self.bot.con_pool, channel_id, cmd_name, args[0].upper())
                await self.bot.msg_q.reply(
                    ctx, f"Set the permisssion of command <{cmd_name}> to {args[0].capitalize()}"
                )

            case "copy":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify the name of the command to be copied")
                    return
                if len(args) == 0 or args[0].lower() not in [channel.name for channel in self.bot.connected_channels]:
                    await self.bot.msg_q.reply(ctx, "Please specify a channel the bot is in")
                    return
                channel_id = await channels.channel_id(self.bot.con_pool, args[0])
                target_command = await custom_commands.show_custom_command(self.bot.con_pool, channel_id, cmd_name)
                if target_command is None:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> doesn't exist")
                    return
                alias = cmd_name if len(args[1:]) == 0 else args[1]
                exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, alias)
                if exists:
                    await self.bot.msg_q.reply(ctx, f"A command <{alias}> already exists in this channel")
                    return
                await custom_commands.add_custom_command(self.bot.con_pool, channel_id, alias, target_command.message)
                await self.bot.msg_q.reply(ctx, f"Added command <{cmd_name}>")

            case "enable":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify the name of the command to be enabled")
                    return
                exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, cmd_name)
                if not exists:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> doesn't exist")
                    return
                success = await custom_commands.enable_custom_command(self.bot.con_pool, channel_id, cmd_name)
                if success:
                    await self.bot.msg_q.reply(ctx, f"Enabled command <{cmd_name}>")
                else:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> is already enabled")

            case "disable":
                if cmd_name is None:
                    await self.bot.msg_q.reply(ctx, "Please specify the name of the command to be disabled")
                    return
                exists = await custom_commands.command_exists(self.bot.con_pool, channel_id, cmd_name)
                if not exists:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> doesn't exist")
                    return
                success = await custom_commands.disable_custom_command(self.bot.con_pool, channel_id, cmd_name)
                if success:
                    await self.bot.msg_q.reply(ctx, f"Disabled command <{cmd_name}>")
                else:
                    await self.bot.msg_q.reply(ctx, f"Command <{cmd_name}> is already disabled")

            case _:
                raise commands.MissingRequiredArgument
            

    # @commands.cooldown(rate=1, per=COG_COOLDOWN, bucket=commands.Bucket.member)
    # @commands.command()
    # async def pattern(self, ctx: commands.Context, action: Literal["add", "addregex", "remove", "copy", "enable", "disable", "show", "list"], pattern_name: str, *args):
    #     """?pattern add <pattern name> <pattern> "<content>" <probability>"""
    #     # disallow editing?
    #     # how to determine what is the pattern and what is the message?
    #     #   - message in quotes?
    #     channel_id = '' # TODO
    #     match action:
    #         case 'addregex':
    #             if len(args) == 0:
    #                 print('pattern must have a length greater than zero')
    #                 return
    #             exists = await custom_patterns.pattern_exists(self.bot.con_pool, channel_id, pattern_name)
    #             if exists:
    #                 print(f'pattern called {pattern_name} already exists')
    #                 return

    #             # TODO: handle the possibility of pattern having quotes
    #             # check which quote type appears exactly twice?
    #             pattern = ''
    #             i = 0
    #             while not args[i].startswith(('\"', '\'')):
    #                 pattern += args[i]
    #             try:
    #                 re.compile(pattern)
    #             except re.error:
    #                 print('invalid regex')
    #                 return

    #             content = re.findall(r'"(.+)" | \'(.+)\'', ' '.join(args))
    #             if len(content) != 1:
    #                 print('put quotes around the content and content only')
    #                 return
    #             content = content[0]

    #             try:
    #                 probability = float(args[-1])
    #             except ValueError:
    #                 probability = 1.0

    #             await custom_patterns.add_custom_pattern(self.bot.con_pool, channel_id, pattern_name, pattern, content, probability, True)
    #             print('pattern added')


def prepare(bot: "Bot"):
    bot.add_cog(Moderator(bot))
