from datetime import datetime, timedelta, UTC
import random
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import seventv
from shared.database.twitch import channels, fishing, reminders
from shared.util.formatting import format_timedelta

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Fish(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.MAX_LEVEL = 100
        self.equipment_catalogue = fishing.FishingEquipmentCatalogue()

    def level_from_exp(self, experience: int) -> int:
        level = min(int(0.41 * experience**0.4) + 1, self.MAX_LEVEL)
        return level

    def level_to_exp(self, level: int) -> int:
        """Inverse function of level_from_exp"""
        exp = int(((min(level, self.MAX_LEVEL) - 1) / 0.41) ** (1 / 0.4))
        return exp

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.user)
    @commands.command(aliases=("fishing", "fishinge", "fishingtime", "fishh", "fihs", "🐟", "🎣"))
    async def fish(self, ctx: commands.Context, *args):
        """
        You go fishing; number of fish you catch is based on luck, fishing level, and time since last fished (afk fishing),
        which is capped at 10 days; a haul of fish can be caught really rarely and gives 20-30 extra fish;
        set a reminder to remind you to fish when the cooldown is up with -r
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        fisher = await fishing.fisher(self.bot.con_pool, ctx.author.id)
        owned_equipment = self.equipment_catalogue.equipment_owned(fisher.equipment)

        fish_flat: int = sum(
            [e.effect for e in owned_equipment if e.equipment_type == "FISHFLAT"]  # type:ignore
        )
        cooldown_flat: int = sum(
            [e.effect for e in owned_equipment if e.equipment_type == "COOLDOWNFLAT"]  # type:ignore
        )
        fish_multi: float = 1 + sum(
            [e.effect for e in owned_equipment if e.equipment_type == "FISHMULTI"]  # type:ignore
        )
        exp_multi: float = 1 + sum(
            [e.effect for e in owned_equipment if e.equipment_type == "EXPMULTI"]  # type:ignore
        )
        afk_multi: float = 1 + sum(
            [e.effect for e in owned_equipment if e.equipment_type == "AFKMULTI"]  # type:ignore
        )
        haul_chance: float = 0.01 + sum(
            [e.effect for e in owned_equipment if e.equipment_type == "HAULCHANCE"]  # type:ignore
        )
        haul_multi: float = 1 + sum(
            [e.effect for e in owned_equipment if e.equipment_type == "HAULSIZEMULTI"]  # type:ignore
        )
        lessrng: bool = len([e for e in owned_equipment if e.equipment_type == "LESSRNG"]) > 0  # type:ignore
        norng: bool = len([e for e in owned_equipment if e.equipment_type == "NORNG"]) > 0  # type:ignore

        cooldown_period = 3 * 3600 - cooldown_flat
        current_time = datetime.now(UTC)
        if fisher.last_fished is None:
            seconds_ellapsed = cooldown_period
        else:
            seconds_ellapsed = (current_time - fisher.last_fished).total_seconds()

        # Manage cooldown
        if seconds_ellapsed < cooldown_period:
            cooldown_left = timedelta(seconds=cooldown_period - seconds_ellapsed)

            if "-r" in args:
                prefixes = await self.bot.prefixes(ctx.channel.name)
                rem_id = await reminders.set_reminder(
                    self.bot.con_pool,
                    channel_id,
                    ctx.author.id,
                    ctx.author.id,
                    f"{prefixes[0]}fish",
                    current_time + cooldown_left,
                    True,
                )
                reminder_msg = f"| Reminding you to fish when the time is up (ID {rem_id})"
            else:
                reminder_msg = ""

            time_remaning = format_timedelta(current_time, current_time + cooldown_left)
            await self.bot.msg_q.reply(ctx, f"You can go fishing again in {time_remaning} {reminder_msg}")
            return

        hours = seconds_ellapsed / 3600
        cooldown_hours = cooldown_period / 3600
        level_before = self.level_from_exp(fisher.exp)

        haul_fish = 0
        haul_success = False
        if random.random() < haul_chance:
            haul_success = True
            if norng:
                haul_fish = 30
            elif lessrng:
                haul_fish = max(random.randint(20, 30), random.randint(20, 30))
            else:
                haul_fish = random.randint(20, 30)
            haul_fish *= haul_multi

        if norng:
            total_fish_count = int(
                (
                    2
                    + (level_before - 1) ** 0.6
                    + (min(hours, 10 * 24 + cooldown_hours) ** 0.4 - cooldown_hours**0.4)
                    * (1 + level_before / 100)
                    * afk_multi
                    + fish_flat
                )
                * fish_multi
                + haul_fish
            )
        else:
            attempts = []
            for _ in range(2):
                # Base count of 1 or 2 fish + random number based on current level + count based on hours since last fished
                attempts.append(
                    int(
                        (
                            random.randint(1, 2)
                            + (random.random() + 1) / 2 * ((level_before - 1) ** 0.6)
                            + (random.random() + 3)
                            / 4
                            * (min(hours, 10 * 24 + cooldown_hours) ** 0.4 - cooldown_hours**0.4)
                            * (1 + level_before / 100)
                            * afk_multi
                            + fish_flat
                        )
                        * fish_multi
                        + haul_fish
                    )
                )
            if lessrng:
                total_fish_count = max(attempts)
            else:
                total_fish_count = attempts[0]

        # Check this just in case
        if total_fish_count < 1:
            await self.bot.msg_q.reply(ctx, "You suck at fishing...")
            return

        account_info = await seventv.account_info(channel_id)
        global_emote_set = await seventv.global_emote_set()

        emotes = []
        emotes.extend([emote.name for emote in global_emote_set.emotes])
        if account_info is not None:
            emotes.extend([emote.name for emote in account_info.emote_set.emotes])

        n = 10
        top_emotes = random.choices(emotes, k=n)

        fish_caught = random.choices(
            # The most common has the smallest index
            [(i, emote) for i, emote in enumerate(top_emotes)],
            # The most common has the highest weight
            weights=[1 / j for j in range(1, n + 1)],
            k=total_fish_count,
        )
        # Sort caught fish by its rarity (index), most common first
        fish_caught.sort()

        # Linearly assign the exp value to fish based on how common the emote is
        total_exp_amount = int(sum([3 * index + 6 for index, _ in fish_caught]) * exp_multi)

        exp_after = fisher.exp + total_exp_amount
        level_after = self.level_from_exp(exp_after)
        level_up_notif = "" if level_before == level_after else f", LEVEL UP {level_before}->{level_after}!"

        await fishing.fish(
            self.bot.con_pool,
            ctx.author.id,
            total_fish_count,
            total_exp_amount,
        )

        if "-r" in args:
            cooldown = timedelta(seconds=cooldown_period)
            prefixes = await self.bot.prefixes(ctx.channel.name)
            rem_id = await reminders.set_reminder(
                self.bot.con_pool,
                channel_id,
                ctx.author.id,
                ctx.author.id,
                f"{prefixes[0]}fish",
                current_time + cooldown,
                True,
            )
            hours = cooldown_period / 3600
            reminder_msg = f"| Reminding you to fish in {hours:.1f} hours (ID {rem_id})"
        else:
            reminder_msg = ""

        fish_caught_count = {}
        for _, name in fish_caught:
            fish_caught_count[name] = fish_caught_count.get(name, 0) + 1

        caught = " | ".join([f"{count}x {name}" for name, count in fish_caught_count.items()])
        if haul_success:
            await self.bot.msg_q.reply(
                ctx,
                f"You got {total_exp_amount} exp from your massive haul of {total_fish_count} fish: {caught} {level_up_notif} {reminder_msg}",
            )
        else:
            await self.bot.msg_q.reply(
                ctx,
                f"You got {total_exp_amount} exp from {total_fish_count} fish: {caught} {level_up_notif} {reminder_msg}",
            )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("fs", "exp", "level", "fishcount"))
    async def fishstats(self, ctx: commands.Context, target: twitchio.User | None):
        """
        Shows the number of fish you have caught; can be used with a target:
        {prefix}fishcount <target>
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        target_user = target if target is not None else ctx.author
        fisher = await fishing.fisher(self.bot.con_pool, str(target_user.id))
        level = self.level_from_exp(fisher.exp)
        exp_to_next_level = max(self.level_to_exp(level + 1) - fisher.exp, 0)
        await self.bot.msg_q.send(
            ctx,
            f"{target_user.name} (level {level}) has caught {fisher.fish_count:,} fish and has {fisher.exp:,} exp ({exp_to_next_level:,} exp to level up)",
            [str(target_user.name)],
        )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("topfish", "toplevel"))
    async def topexp(self, ctx: commands.Context, *args):
        """Shows the fishing stats of the top 5 people ordered by exp"""
        top_fishers = await fishing.top_exp(self.bot.con_pool)
        if len(top_fishers) == 0:
            await self.bot.msg_q.send(ctx, "No one has fished yet")
            return

        top_fishers = top_fishers[:5]
        users = await self.bot.fetch_users(ids=[int(fisher.user_id) for fisher in top_fishers])
        usernames = [user.name for user in users]
        user_info = []
        for i, fisher in enumerate(top_fishers, 1):
            username = [user.name for user in users if str(user.id) == fisher.user_id]
            if len(username) == 1:
                username = username[0]
            else:
                username = "<unknown user>"
            level = self.level_from_exp(fisher.exp)
            user_info.append(f"{i}. {username} - level {level}, {fisher.exp} exp, {fisher.fish_count} caught")
        await self.bot.msg_q.send(ctx, " | ".join(user_info), usernames)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("fishstore", "shop", "fishshop"))
    async def store(self, ctx: commands.Context, page: int = 1):
        """
        Shows every available item to be purchased; all bought items give permanent buffs to fishing
        abilities; items have a level requirement, and they cost exp, meaning you lose levels
        when buying an item; to view possible additional pages: {prefix}store <page>
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        fisher = await fishing.fisher(self.bot.con_pool, ctx.author.id)
        not_owned = self.equipment_catalogue.equipment_not_owned(fisher.equipment)
        if len(not_owned) == 0:
            await self.bot.msg_q.send(ctx, "The store is empty")
            return

        def format_cost(cost: int):
            if cost >= 1000:
                return f"{cost/1000:0.1f}k"
            else:
                return str(cost)

        formatted_items = [
            f"({e.id}) {e.name}: {e.effect_disc} (req: lvl {e.level_req}) (cost: {format_cost(e.cost)} exp)"
            for e in not_owned
        ]
        pages = {}
        store_page = []
        for item in formatted_items:
            if sum([len(item) for item in store_page]) + len(item) > 350:
                pages[len(pages) + 1] = store_page
                store_page = []
            store_page.append(item)
        pages[len(pages) + 1] = store_page

        if page in pages:
            await self.bot.msg_q.reply(ctx, " | ".join(pages[page]))
        else:
            await self.bot.msg_q.reply(ctx, "Page not found")

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def buy(self, ctx: commands.Context, item_id: int):
        """
        Buys an item from the store; item is specified by its id shown in parentheses in the store;
        see {prefix}store for the store; {prefix}buy <item id>
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        fisher = await fishing.fisher(self.bot.con_pool, ctx.author.id)
        not_owned = self.equipment_catalogue.equipment_not_owned(fisher.equipment)

        target_item = [item for item in not_owned if item.id == item_id]
        if len(target_item) == 0:
            if self.equipment_catalogue.item_by_id(item_id) is None:
                await self.bot.msg_q.reply(ctx, "Invalid item")
            else:
                await self.bot.msg_q.reply(ctx, "You already own that item")
            return

        target_item = target_item[0]
        level = self.level_from_exp(fisher.exp)

        def format_cost(cost: int):
            if cost >= 1000:
                return f"{cost/1000:0.1f}k"
            else:
                return str(cost)

        if target_item.level_req > level:
            await self.bot.msg_q.reply(ctx, f"Your level is too low: {level}<{target_item.level_req}")
        # Check this just in case
        elif target_item.cost > fisher.exp:
            await self.bot.msg_q.reply(ctx, "You don't have enough exp")
        else:
            await fishing.buy_fishing_equipment(self.bot.con_pool, ctx.author.id, target_item.id, target_item.cost)
            exp_after = fisher.exp - target_item.cost
            level_after = self.level_from_exp(exp_after)
            await self.bot.msg_q.reply(
                ctx,
                f"You bought {target_item.name} ({target_item.effect_disc}) for {format_cost(target_item.cost)} exp, level {level}->{level_after}",
            )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("items",))
    async def equipment(self, ctx: commands.Context, page: int = 1):
        """Shows all your bought fishing equipment"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        fisher = await fishing.fisher(self.bot.con_pool, ctx.author.id)
        owned = self.equipment_catalogue.equipment_owned(fisher.equipment)
        if len(owned) == 0:
            await self.bot.msg_q.reply(ctx, "You don't own any equipment")
            return

        formatted_items = [f"({e.id}) {e.name}: {e.effect_disc}" for e in owned]
        pages = {}
        store_page = []
        for item in formatted_items:
            if sum([len(item) for item in store_page]) + len(item) > 350:
                pages[len(pages) + 1] = store_page
                store_page = []
            store_page.append(item)
        pages[len(pages) + 1] = store_page

        if page in pages:
            await self.bot.msg_q.reply(ctx, " | ".join(pages[page]))
        else:
            await self.bot.msg_q.reply(ctx, "Page not found")


def prepare(bot: "Bot"):
    bot.add_cog(Fish(bot))
