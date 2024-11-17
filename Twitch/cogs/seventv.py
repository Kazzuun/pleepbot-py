from datetime import datetime, UTC
import random
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import seventv
from shared.database.twitch import channels, messages
from shared.util.formatting import format_timedelta
from Twitch.exceptions import ValidationError

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class SevenTV(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @commands.cooldown(rate=2, per=15, bucket=commands.Bucket.member)
    @commands.command(name="7tvuser", aliases=("7tvu",))
    async def seventv_user(self, ctx: commands.Context, target: twitchio.PartialUser | None):
        """
        Shows some information about the 7tv account of the target user; {prefix}seventvuser <target>;
        leave empty for self
        """
        if target is None:
            assert isinstance(ctx.author, twitchio.Chatter)
            assert ctx.author.id is not None
            target_id = ctx.author.id
        else:
            target_id = str(target.id)

        user_info = await seventv.account_info(target_id, force_cache=True)
        if user_info is None:
            ValidationError("Target user doesn't have a 7tv account")
            return

        username = user_info.user.display_name
        emote_count = user_info.emote_set.emote_count
        set_capacity = user_info.emote_set.capacity
        editors = user_info.user.editors

        editor_of = await seventv.editor_of(user_info.user.id)
        owned_emotes = await seventv.owned_emotes(user_info.user.id)
        user_roles = await seventv.roles(user_info.user.roles)
        cosmetics = await seventv.user_cosmetics(user_info.user.id)

        infos = []
        infos.append(username)

        role_names = [role.name for role in user_roles if not role.invisible]
        if len(role_names) > 0:
            infos.append(f"Roles: {', '.join(role_names)}")

        if user_info.user.is_subscibed():
            selected_cosmetic = [cosmetic for cosmetic in cosmetics if cosmetic.kind == "PAINT" and cosmetic.selected]
            if len(selected_cosmetic) == 1:
                paint = await seventv.paint(selected_cosmetic[0].id)
                infos.append(f"Paint: {paint.name}")

        if len(cosmetics) > 0:
            paints = [cosmetic for cosmetic in cosmetics if cosmetic.kind == "PAINT"]
            badges = [cosmetic for cosmetic in cosmetics if cosmetic.kind == "BADGE"]
            infos.append(f"Unlocked: {len(paints)} paints, {len(badges)} badges")

        infos.append(f"Editors: {len(editors)}")
        infos.append(f"Editor of: {len(editor_of)}")
        infos.append(f"Owned emotes: {len(owned_emotes)}")
        infos.append(f"Set capacity: {emote_count}/{set_capacity}")
        created_since = format_timedelta(user_info.user.created_at, datetime.now(UTC))
        infos.append(f"Created on: {user_info.user.created_at.strftime('%Y-%m-%d')} ({created_since} ago)")
        infos.append(f"Profile: https://7tv.app/users/{user_info.user.id}")
        await self.bot.msg_q.send(ctx, " — ".join(infos), [username])

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(name="7tvsubage", aliases=("7tvsa",))
    async def seventv_subage(self, ctx: commands.Context, target: twitchio.User | None):
        """Shows 7tv subage info of the target user; {prefix}7tvsubage <target>; leave empty for self"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if target is None:
            target_name = ctx.author.name
            target_id = ctx.author.id
        else:
            target_name = target.name
            target_id = str(target.id)

        user_info = await seventv.account_info(target_id)
        if user_info is None:
            await self.bot.msg_q.send(ctx, f"{target_name} doesn't have a 7tv account", [target_name])
            return
        subage = await seventv.subage(user_info.user.id)

        if subage.months == 0:
            await self.bot.msg_q.send(ctx, f"{target_name} has not been subbed to 7tv", [target_name])
        elif subage.subscription is None or subage.end_at is None or not subage.active:
            await self.bot.msg_q.send(
                ctx,
                f"{target_name} was previously subbed to 7tv for {subage.months} months ({subage.age/365.25:.2f} years)",
                [target_name],
            )
        else:
            targets = [target_name]
            if subage.subscription.subscriber_id != subage.subscription.customer_id:
                gifter = await seventv.user_from_id(subage.subscription.customer_id)
                gift_message = f"The sub was gifted by {gifter.username}."
                targets.append(gifter.username)
            else:
                gift_message = ""
            ends_in = format_timedelta(datetime.now(UTC), subage.end_at)

            year = 365.25
            sub_badges = [1/12, 1/6, 1/4, 1/2, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75]
            remaining_badges = [badge for badge in sub_badges if badge * year > subage.age + year/12]
            if len(remaining_badges) == 0:
                badge_message = "They have all the current sub badges"
            else:
                next_badge = remaining_badges[0]
                previous_badge = sub_badges[sub_badges.index(next_badge) - 1]
                badge_progress = (subage.age - previous_badge * year + year / 12) / (next_badge * year - previous_badge * year) * 100
                badge_message = f"They have {int(badge_progress)}% progress towards the next badge ({int(next_badge * 12) if next_badge < 1 else next_badge} {'months' if next_badge < 1 else 'years'})"

            await self.bot.msg_q.send(
                ctx,
                f"{target_name} has been subscribed to 7tv for {subage.months} months ({subage.age/year:.2f} years). {gift_message} Sub {'renews' if subage.renew else 'ends'} in {ends_in}. {badge_message}",
                targets,
            )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def ecount(self, ctx: commands.Context, emote: str):
        """Shows the number of times the specified emote has been used in the channel; {prefix}ecount <emote>"""
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        if not channel_config.logging:
            raise ValidationError("This channel isn't being logged")

        emote_names = await seventv.emote_names(channel_config.channel_id, include_global=True)
        if emote not in emote_names:
            await self.bot.msg_q.send(ctx, "Emote not found in the current set")
            return
        count = await messages.emote_count(self.bot.con_pool, channel_config.channel_id, emote)
        await self.bot.msg_q.send(ctx, f"{emote} has been used {count} times")

    @commands.cooldown(rate=4, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("randomemote", "randemote"))
    async def re(self, ctx: commands.Context, count: int | None):
        """Sends random emotes(s) from the channel; {prefix}re <count>"""
        count = min(max(count if count is not None else 1, 1), 50)
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        user_info = await seventv.account_info(channel_config.channel_id)
        if user_info is None or user_info.emote_set.emote_count == 0:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have any 7tv emotes")
            return
        emote_names = [emote.name for emote in user_info.emote_set.emotes]
        message = " ".join(random.choices(emote_names, k=count))
        await self.bot.msg_q.send(ctx, message)

    @commands.cooldown(rate=2, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def search(self, ctx: commands.Context, page: int | None, *emote_query: str):
        """
        Searches for the given 7tv emote; filters can be specified: -a for animated, -c for case sensitive,
        -e for exact match, -i to ignore tags, -t for currently trending, -z for zero width
        (some filters in the 7tv api seem to be disabled and may not work); {prefix}search <optinal page> <emote> <filters>
        """
        if len(emote_query) == 0:
            await self.bot.msg_q.reply(ctx, "Please provide something to search")
            return
        search_terms = [word for word in emote_query if not word.startswith("-")]
        result = await seventv.search_emote_by_name(
            emote_query=" ".join(search_terms),
            limit=6,
            page=max(page, 1) if page is not None else 1,
            animated="-a" in emote_query,
            case_sensitive="-c" in emote_query,
            exact_match="-e" in emote_query,
            ignore_tags="-i" in emote_query,
            trending="-t" in emote_query,
            zero_width="-z" in emote_query,
        )
        if result.count == 0:
            await self.bot.msg_q.send(ctx, "Search didn't find any results")
            return
        search_results = [f"{emote.name} - 7tv.app/emotes/{emote.id}" for emote in result.emotes]
        await self.bot.msg_q.send(ctx, " | ".join(search_results))

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def added(self, ctx: commands.Context, emote: str):
        """Shows who and when added the specified emote; {prefix}added <emote>"""
        channel_config = await channels.channel_config(self.bot.con_pool, ctx.channel.name)
        user_info = await seventv.account_info(channel_config.channel_id)
        if user_info is None or user_info.emote_set.emote_count == 0:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have any 7tv emotes")
            return

        target_emote = [e for e in user_info.emote_set.emotes if e.name == emote]
        if len(target_emote) == 0:
            await self.bot.msg_q.send(ctx, "Emote not found")
            return
        target_emote = target_emote[0]

        targets = []
        if target_emote.actor_id is not None:
            actor_user = await seventv.user_from_id(target_emote.actor_id)
            actor = actor_user.username
            targets.append(actor)
        else:
            actor = "<unknown>"

        time_ellapsed = format_timedelta(target_emote.timestamp, datetime.now(UTC), precision=3)
        message = (
            f"{emote} was added by {actor} on {target_emote.timestamp.strftime('%Y-%m-%d')} ({time_ellapsed} ago)"
        )
        await self.bot.msg_q.send(ctx, message, targets)


def prepare(bot: "Bot"):
    bot.add_cog(SevenTV(bot))
