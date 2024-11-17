from datetime import datetime, timedelta, UTC
from dateutil.relativedelta import relativedelta
import random
import re
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands, routines

from shared.apis import seventv
from shared.database.twitch import channels, reminders, timers, users
from shared.util.formatting import format_timedelta
from Twitch.exceptions import ValidationError

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Remind(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.check_reminders.start()
        self.check_timers.start()

    @routines.routine(seconds=1, wait_first=True)
    async def check_reminders(self):
        rems = await reminders.sendable_timed_reminders(self.bot.con_pool)
        for rem in rems:
            channel_config = await channels.channel_config_from_id(self.bot.con_pool, rem.channel_id)
            if not channel_config.reminds_online and channel_config.currently_online:
                continue
            users = await self.bot.fetch_users(ids=[int(rem.sender_id), int(rem.target_id)])
            sender = [user for user in users if user.id == int(rem.sender_id)]
            if len(sender) == 1:
                sender_name = sender[0].name
            else:
                sender_name = "<unknown user>"
            target = [user for user in users if user.id == int(rem.target_id)]
            if len(target) == 1:
                target_name = target[0].name
            else:
                continue
            message, targets = await rem.formatted_message(sender_name, target_name)
            await self.bot.msg_q.send_message(channel_config.username, message, targets)
            await reminders.set_reminder_as_sent(self.bot.con_pool, rem.id)

    @routines.routine(seconds=1, wait_first=True)
    async def check_timers(self):
        times = await timers.sendable_timers(self.bot.con_pool)
        for timer in times:
            channel_config = await channels.channel_config(self.bot.con_pool, timer.channel_name)
            if not channel_config.reminds_online and channel_config.currently_online:
                continue
            await self.bot.msg_q.send_message(timer.channel_name, timer.message)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def remind(self, ctx: commands.Context, target: twitchio.User | None, *args: str):
        """
        Sets a reminder for target user or "me" for self;
        {prefix}remind <target> <message>;
        {prefix}remind <target> <message> in <time>;
        {prefix}remind <target> <message> at <yyyy-mm-dd hh:mm:ss+tz>;
        {prefix}remind <target> <message> between <time>-<time>
        """
        # time format yyyy-mm-dd hh:mm:ss+tz
        assert isinstance(ctx.author, twitchio.Chatter)
        assert isinstance(ctx.author.name, str)
        assert ctx.author.id is not None

        if target is not None:
            target_name = target.name
            target_id = str(target.id)
        elif len(args) > 0 and args[-1] == "me":
            target_name = ctx.author.name
            target_id = ctx.author.id
            args = args[:-1]
        else:
            raise ValidationError("Please provide a valid target")

        # TODO: possibly move this somewhere else with all the regex
        def time_args_to_timedelta(time_args: list | tuple) -> relativedelta:
            assert len(time_args) % 2 == 0
            delta = relativedelta()
            for i in range(0, len(time_args), 2):
                multiplier = float(time_args[i])
                unit = time_args[i + 1].lower()
                if unit in ("s", "sec", "secs", "second", "seconds"):
                    delta += timedelta(seconds=multiplier)
                elif unit in ("m", "min", "mins", "minute", "minutes"):
                    delta += timedelta(minutes=multiplier)
                elif unit in ("h", "hr", "hrs", "hour", "hours"):
                    delta += timedelta(hours=multiplier)
                elif unit in ("d", "day", "days"):
                    delta += timedelta(days=multiplier)
                elif unit in ("w", "week", "weeks"):
                    delta += timedelta(weeks=multiplier)
                elif unit in ("mon", "month", "months"):
                    delta += relativedelta(months=int(multiplier)) + timedelta(
                        days=(multiplier - int(multiplier)) * 30
                    )
                elif unit in ("y", "year", "years"):
                    delta += relativedelta(years=int(multiplier)) + timedelta(days=(multiplier - int(multiplier)) * 365)
                else:
                    raise ValidationError(f"An invalid time unit was given: {unit}")
            return delta

        message = " ".join(args)
        current_time = datetime.now(UTC)

        common_part_1 = r"at\s(?:[1-9][0-9][0-9][0-9]-(?:0[1-9]|1[0-2])-(?:0[1-9]|[1-2][0-9]|3[0-1])(?:T|\s)(?:[0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:(?:\+|-)[0-1][0-9](?::[03][0])?)?)"
        datetime_pattern = rf"^{common_part_1}|\b{common_part_1}$"

        common_part_2 = r"in\s(?:-?\d+(?:\.\d+)?\s?[a-zA-Z]+\s?)+"
        time_pattern = rf"^{common_part_2}|\b{common_part_2}$"

        common_pattern_3 = r"between\s\d+(?:\.\d+)?\s?[a-zA-Z]+\s?-\s?\d+(?:\.\d+)?\s?[a-zA-Z]+"
        interval_pattern = rf"^{common_pattern_3}|\b{common_pattern_3}$"

        time_arg_pattern = r"-?\d*\.\d+|-?\d+|[a-zA-Z]+"

        iso_format = re.findall(datetime_pattern, message)
        time_intervals = re.findall(time_pattern, message)
        random_interval = re.findall(interval_pattern, message)

        if len(iso_format) > 0:
            message = re.sub(datetime_pattern, "", message).strip()
            time_arg = iso_format[0][3:].strip()
            # 19 is the length of the timestamp without timezone
            if len(time_arg) == 19:
                time_arg += "+00"
            scheduled_at = datetime.fromisoformat(time_arg)

        elif len(time_intervals) > 0:
            message = re.sub(time_pattern, "", message).strip()
            time_args = time_intervals[0][3:].strip()
            parsed_time_args = re.findall(time_arg_pattern, "".join(time_args.split()))
            scheduled_at = current_time + time_args_to_timedelta(parsed_time_args)

        elif len(random_interval) > 0:
            message = re.sub(interval_pattern, "", message).strip()
            time_args = random_interval[0][8:].strip().replace("-", "")
            parsed_time_args = re.findall(time_arg_pattern, "".join(time_args.split()))
            start_time = current_time + time_args_to_timedelta(parsed_time_args[:2])
            end_time = current_time + time_args_to_timedelta(parsed_time_args[2:])

            if start_time >= end_time:
                raise ValidationError("Lower bound of the random interval should be smaller than the upper bound")
            random_seconds = random.randint(0, int((end_time - start_time).total_seconds()))
            scheduled_at = current_time + timedelta(seconds=random_seconds)

        else:
            scheduled_at = None

        min_time = current_time + timedelta(seconds=10)
        max_time = current_time + relativedelta(years=100)
        if scheduled_at is not None and (min_time > scheduled_at or max_time < scheduled_at):
            raise ValidationError("Time is out of allowed bounds")

        if message == "":
            message = None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        id = await reminders.set_reminder(
            self.bot.con_pool,
            channel_id,
            ctx.author.id,
            target_id,
            message,
            scheduled_at,
        )
        if id is None:
            await self.bot.msg_q.reply(ctx, "Failed to set a reminder")
            return

        if scheduled_at is None:
            message = f"Sending a message to {target_name} when they type next (ID {id})"
        else:
            if target_name == ctx.author.name:
                target_name = "you"
            time_until = format_timedelta(current_time, scheduled_at, precision=6, exclude_zeros=True)
            message = (
                f"Reminding {target_name} in {time_until} at {scheduled_at.strftime('%Y-%m-%d %H:%M:%S %Z')} (ID {id})"
            )
        await self.bot.msg_q.reply(
            ctx,
            message,
            [target_name],
            reminders.cancel_reminder,
            self.bot.con_pool,
            id,
        )

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("goodnight",))
    async def gn(self, ctx: commands.Context):
        """The bot says goodnight to you"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        goodnight_emote = await seventv.best_fitting_emote(
            channel_id,
            lambda emote: emote.lower() in ("goodnight", "gn"),
            default="Goodnight",
        )
        bed_emote = await seventv.best_fitting_emote(
            channel_id,
            lambda emote: any(e in emote.lower() for e in ("bedge", "sleep", "tuck"))
            and not emote.endswith("0")
            and "untuck" not in emote.lower(),
        )
        await reminders.set_afk(self.bot.con_pool, channel_id, ctx.author.id, "GN")
        await self.bot.msg_q.send(
            ctx,
            f"{goodnight_emote} {ctx.author.name} sleep well {bed_emote}",
            [ctx.author.name],
        )

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def afk(self, ctx: commands.Context):
        """You go afk"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        await reminders.set_afk(self.bot.con_pool, channel_id, ctx.author.id, "AFK")
        await self.bot.msg_q.send(ctx, f"{ctx.author.name} is now afk", [ctx.author.name])

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("corpa",))
    async def work(self, ctx: commands.Context):
        """You go afk for work"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        emote = await seventv.best_fitting_emote(
            channel_id,
            lambda emote: emote.lower() in ("money", "corpa"),
        )
        await reminders.set_afk(self.bot.con_pool, channel_id, ctx.author.id, "WORK")
        await self.bot.msg_q.send(ctx, f"{ctx.author.name} is now working {emote}", [ctx.author.name])

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("canrem",))
    async def delrem(self, ctx: commands.Context, reminder_id: int):
        """Deletes the target reminder; {prefix}delrem <reminder id>"""
        assert isinstance(ctx.author.name, str)
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        user_config = await users.user_config(self.bot.con_pool, ctx.author.id)
        if user_config.is_admin():
            success = await reminders.cancel_reminder(self.bot.con_pool, reminder_id)
        else:
            success = await reminders.cancel_reminder_check_sender(self.bot.con_pool, reminder_id, ctx.author.id)
        if success:
            emote = await seventv.best_fitting_emote(
                await channels.channel_id(self.bot.con_pool, ctx.channel.name),
                lambda emote: emote.lower() in ("ok", "thumbsup", "okayge", "okayeg"),
                default="FeelsOkayMan",
                include_global=True,
            )
            await self.bot.msg_q.reply(
                ctx,
                f"Reminder cancelled {emote}",
                [],
                reminders.uncancel_reminder,
                reminder_id,
            )
        else:
            await self.bot.msg_q.reply(ctx, "Failed to cancel reminder")

    @commands.cooldown(rate=2, per=30, bucket=commands.Bucket.member)
    @commands.command()
    async def rafk(self, ctx: commands.Context):
        """Continues your previous afk status"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        # TODO: make this get the last type of afk
        success = await reminders.continue_afk(self.bot.con_pool, channel_id, ctx.author.id)
        if success:
            emote = await seventv.best_fitting_emote(
                await channels.channel_id(self.bot.con_pool, ctx.channel.name),
                lambda emote: emote.lower() in ("ok", "thumbsup", "okayge", "okayeg"),
                default="FeelsOkayMan",
                include_global=True,
            )
            await self.bot.msg_q.reply(ctx, f"Your afk status has been resumed {emote}")
        else:
            await self.bot.msg_q.reply(ctx, "Failed to resume afk status")


def prepare(bot: "Bot"):
    bot.add_cog(Remind(bot))
