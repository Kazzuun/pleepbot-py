from datetime import datetime, timedelta, UTC
import hashlib
import random
import re
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import dadjokes, mathjs, seventv, themealdb, twitch, urban_dictionary #TODO: use twitch
from shared.database.twitch import channels, messages, misc
from shared.util.formatting import format_timedelta

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Basic(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @commands.command(aliases=("ping",))
    async def pleep(self, ctx: commands.Context):
        """It's just pleep"""
        await self.bot.msg_q.send(ctx, "pleep")

    @commands.command(aliases=("%",))
    async def chance(self, ctx: commands.Context):
        """Gives a percentage between 0 and 100"""
        await self.bot.msg_q.reply(ctx, f"{random.randint(0, 100)}%")

    @commands.command(aliases=("chatters",))
    async def lurkers(self, ctx: commands.Context):
        """Shows the number of chatters connected to the current chat"""
        chatters = ctx.channel.chatters
        if chatters is None:
            # user_infos = await ivr.user_info(ctx.channel.name)
            # if len(user_infos) == 0:
            await self.bot.msg_q.send(ctx, "Failed to get the lurker count")
            return
            # lurkers = user_infos[0].chatter_count
        else:
            lurkers = len(chatters)
        emote = await seventv.best_fitting_emote(
            await channels.channel_id(self.bot.con_pool, ctx.channel.name),
            lambda emote: emote.lower() in ("erm", "urm", "scared"),
        )
        await self.bot.msg_q.send(ctx, f"{lurkers} lurkers {emote}")

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("cookie", "🍪", "🥠"))
    async def fortune(self, ctx: commands.Context):
        """Shows a random fortune"""
        fort = await misc.random_fortune(self.bot.con_pool)
        if fort is None:
            await self.bot.msg_q.send(ctx, "Ask the owner of the bot to add fortunes")
            return
        await self.bot.msg_q.reply(ctx, fort)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("joke",))
    async def dadjoke(self, ctx: commands.Context):
        """Tells a random dadjoke"""
        dadjoke = await dadjokes.random_dadjoke()
        await self.bot.msg_q.send(ctx, dadjoke.joke)

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("dict", "definition", "def", "urban"))
    async def dictionary(self, ctx: commands.Context, *args: str):
        """Fetches the definition to the given term from urban dictionary; {prefix}dictionary <term> <optional index>"""
        if len(args) == 0:
            await self.bot.msg_q.reply(ctx, "Please provide a term to search")
            return

        if len(args) == 1:
            index = 1
            term = args[0]
        else:
            # Last argument is the index of the definition if it's a valid integer
            if args[-1].isnumeric():
                index = int(args[-1])
                term = " ".join(args[:-1])
            else:
                index = 1
                term = " ".join(args)

        definitions = await urban_dictionary.fetch_definitions(term)
        if len(definitions) == 0:
            await self.bot.msg_q.reply(ctx, "No definitions found")
            return
        index = max(min(index, len(definitions)), 1)
        definition = definitions[index - 1]
        nerd_emote = await seventv.best_fitting_emote(
            await channels.channel_id(self.bot.con_pool, ctx.channel.name),
            lambda emote: "nerd" in emote.lower(),
        )
        await self.bot.msg_q.reply(ctx, f"{definition.word} — {definition.definition} {nerd_emote}")

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("randomdef", "randef", "randic"))
    async def randomdict(self, ctx: commands.Context):
        """Fetches a random definition from urban dictionary"""
        definition = await urban_dictionary.random_definitions()
        nerd_emote = await seventv.best_fitting_emote(
            await channels.channel_id(self.bot.con_pool, ctx.channel.name),
            lambda emote: "nerd" in emote.lower(),
        )
        await self.bot.msg_q.send(ctx, f"{definition.word} — {definition.definition} {nerd_emote}")

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("food",))
    async def meal(self, ctx: commands.Context):
        """Gives a random meal"""
        eating_emote = await seventv.best_fitting_emote(
            await channels.channel_id(self.bot.con_pool, ctx.channel.name),
            lambda emote: emote.lower() in ("bussin", "crunch", "eating") or emote.lower().startswith("very"),
        )
        meal = await themealdb.random_meal()
        await self.bot.msg_q.reply(ctx, f"{meal.area} dish: {meal.meal} {eating_emote} {meal.youtube}")

    @commands.command(aliases=("coin", "coinflip", "cf"))
    async def flip(self, ctx: commands.Context):
        """Flips a coin heads/tails or yes/no"""
        yes_emote = await seventv.best_fitting_emote(
            await channels.channel_id(self.bot.con_pool, ctx.channel.name),
            lambda emote: emote.lower() in ("yes", "yesyes", "nodders", "yesidothinkso"),
            default="yes",
        )
        no_emote = await seventv.best_fitting_emote(
            await channels.channel_id(self.bot.con_pool, ctx.channel.name),
            lambda emote: emote.lower() in ("no", "nono", "nopers", "noidontthinkso"),
            default="no",
        )
        await self.bot.msg_q.reply(ctx, random.choice([f"Heads / {yes_emote}", f"Tails / {no_emote}"]))

    @commands.command()
    async def choose(self, ctx: commands.Context, *args: str):
        """Choose a random argument given; {prefix}choose <arg1> <arg2>..."""
        if len(args) < 2:
            await self.bot.msg_q.reply(ctx, "Please provide at least two things to choose between")
            return
        await self.bot.msg_q.reply(ctx, random.choice(args))

    @commands.command()
    async def shuffle(self, ctx: commands.Context, *args: str):
        """
        Shuffles the given word around {prefix}shuffle <word> or shuffles given arguments
        {prefix}shuffle <arg1> <arg2>...
        """
        if len(args) == 0:
            await self.bot.msg_q.reply(ctx, "Please provide word(s) to shuffle")
        elif len(args) == 1:
            letters = list(args[0])
            random.shuffle(letters)
            await self.bot.msg_q.reply(ctx, "".join(letters))
        else:
            words = list(args)
            random.shuffle(words)
            await self.bot.msg_q.reply(ctx, " ".join(words))

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def math(self, ctx: commands.Context, *, expression: str):
        """Does math; {prefix}math <expression>"""
        expr = expression.lower()
        expr = re.sub(r"\bf\b", "fahrenheit", expr)
        expr = re.sub(r"\bc\b", "celsius", expr)
        result = await mathjs.evaluate(expr)
        await self.bot.msg_q.reply(ctx, result)

    @commands.command()
    async def showiq(self, ctx: commands.Context, target: twitchio.User | None):
        """
        Shows the IQ of of a person that has used {prefix}iq before; {prefix}showiq <target>
        or {prefix}showiq for self
        """
        if target is None:
            assert isinstance(ctx.author, twitchio.Chatter)
            assert ctx.author.id is not None
            target_user = ctx.author
        else:
            target_user = target

        iq = await misc.last_iq(self.bot.con_pool, str(target_user.id))
        if iq is None:
            await self.bot.msg_q.send(ctx, f"{target_user.name}'s IQ is currently unknown", [target_user.name])
            return

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        if iq.last_iq < 85:
            emote = await seventv.best_fitting_emote(
                channel_id,
                lambda emote: emote.lower().startswith("dank") or "idiot" in emote or "dumb" in emote,
                default="FeelsDankMan",
                include_global=True,
            )
        elif iq.last_iq < 115:
            emote = await seventv.best_fitting_emote(
                channel_id,
                lambda emote: "glad" in emote.lower() or "okay" in emote.lower(),
                default="FeelsOkayMan",
                include_global=True,
            )
        else:
            emote = await seventv.best_fitting_emote(
                channel_id,
                lambda emote: emote.lower() == "5head" or "wow" in emote.lower(),
                default="EZ",
            )
        await self.bot.msg_q.send(ctx, f"{target_user.name}'s IQ is {iq.last_iq} {emote}", [target_user.name])

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def iq(self, ctx: commands.Context):
        """Rolls a new IQ to yourself; can be used once every day"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        increase_max = int(hashlib.sha256(ctx.author.name.encode()).hexdigest(), 16) % 10 + 2
        decrease_max = int(ctx.author.id) % 10 + 2
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)

        iq = await misc.last_iq(self.bot.con_pool, ctx.author.id)
        if iq is None:
            new_iq = round(random.gauss(100, 15)) + random.randint(-decrease_max, increase_max)
            await misc.update_last_iq(self.bot.con_pool, ctx.author.id, new_iq)
            emote = await seventv.happy_emote(channel_id, default="FeelsOkayMan")
            await self.bot.msg_q.reply(ctx, f"Your starting IQ is {new_iq} {emote}")
            return

        current_time = datetime.now(UTC)
        last_midnight = datetime(current_time.year, current_time.month, current_time.day, tzinfo=UTC)
        if iq.last_updated > last_midnight:
            time_until = format_timedelta(current_time, last_midnight + timedelta(days=1))
            await self.bot.msg_q.reply(
                ctx, f"Your current IQ is {iq.last_iq} and you can check it again in {time_until}"
            )
            return

        tries = 0
        while True:
            tries += 1
            new_iq = round(random.gauss(100, 15))
            if iq.last_iq + increase_max >= new_iq >= iq.last_iq - decrease_max and new_iq != iq.last_iq:
                break
            elif tries > 10000:
                if iq.last_iq < 100:
                    new_iq = iq.last_iq + random.randint(1, increase_max)
                else:
                    new_iq = iq.last_iq - random.randint(1, decrease_max)
                break

        await misc.update_last_iq(self.bot.con_pool, ctx.author.id, new_iq)
        difference = new_iq - iq.last_iq
        sign = "" if difference < 0 else "+"

        if new_iq < 85:
            emote = await seventv.best_fitting_emote(
                channel_id,
                lambda emote: any(e in emote for e in ("dank", "Dank", "idiot", "dumb")),
                default="FeelsDankMan",
                include_global=True,
            )
        elif new_iq < 115:
            emote = await seventv.best_fitting_emote(
                channel_id,
                lambda emote: any(e in emote.lower() for e in ("okay", "glad")),
                default="FeelsOkayMan",
                include_global=True,
            )
        else:
            emote = await seventv.best_fitting_emote(
                channel_id,
                lambda emote: emote.lower() == "5head" or "wow" in emote.lower(),
                default="EZ",
            )
        await self.bot.msg_q.reply(ctx, f"Your new IQ is {new_iq} ({sign}{difference}) {emote}")

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("topiqs", "highiq", "highiqs"))
    async def topiq(self, ctx: commands.Context):
        """Shows the iqs of the top 10 people"""
        top_iqs = await misc.list_iqs(self.bot.con_pool)
        if len(top_iqs) == 0:
            await self.bot.msg_q.send(ctx, "No one's iq is known yet")
            return

        top_iqs = top_iqs[:10]
        users = await self.bot.fetch_users(ids=[int(iq.user_id) for iq in top_iqs])
        user_info = []
        usernames = [user.name for user in users]
        for i, last_iq in enumerate(top_iqs, 1):
            username = [user.name for user in users if str(user.id) == last_iq.user_id]
            if len(username) == 1:
                username = username[0]
            else:
                username = "<unknown user>"
            user_info.append(f"{i}. {username} - {last_iq.last_iq}")
        await self.bot.msg_q.send(ctx, " | ".join(user_info), usernames)

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("lowiq", "lowiqs", "bottomiqs"))
    async def bottomiq(self, ctx: commands.Context):
        """Shows the iqs of the lowest 10 people"""
        low_iqs = await misc.list_iqs(self.bot.con_pool, top=False)
        if len(low_iqs) == 0:
            await self.bot.msg_q.send(ctx, "No one's iq is known yet")
            return

        total_iqs = len(low_iqs)
        low_iqs = low_iqs[:10]
        users = await self.bot.fetch_users(ids=[int(iq.user_id) for iq in low_iqs])
        usernames = [user.name for user in users]
        user_info = []
        for i, last_iq in enumerate(low_iqs):
            username = [user.name for user in users if str(user.id) == last_iq.user_id]
            if len(username) == 1:
                username = username[0]
            else:
                username = "<unknown user>"
            user_info.append(f"{total_iqs-i}. {username} - {last_iq.last_iq}")
        await self.bot.msg_q.send(ctx, " | ".join(user_info), usernames)

    @commands.command(aliases=("tuckk",))
    async def tuck(self, ctx: commands.Context, target: str | None, emote: str | None):
        """Tucks the target to bed; {prefix}tuck <target> <optional emote>"""
        assert isinstance(ctx.author.name, str)

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        emotes = await seventv.emote_names(channel_id, include_global=True)

        targets = [ctx.author.name]
        if target is None or target.lower() == ctx.author.name:
            target_name = "themselves"
        else:
            target_name = target
            if target_name not in emotes:
                targets.append(target_name)

        if emote is None or emote not in emotes:
            emote = "FeelsOkayMan"

        await self.bot.msg_q.send(
            ctx,
            f"{ctx.author.name} tucked {target_name} to bed {emote} 👉 🛏",
            targets,
        )

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def fight(self, ctx: commands.Context, target: twitchio.User):
        """Fights the target; {prefix}fight <target>"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if ctx.author.name == target.name:
            await self.bot.msg_q.send(ctx, "What do you think you're doing? Stare")
            return

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        last_seen = await messages.last_seen(self.bot.con_pool, channel_id, target.name)
        if last_seen is None or datetime.now(UTC) - last_seen.sent_at > timedelta(hours=3):
            await self.bot.msg_q.reply(ctx, "You can only fight people that have been seen in chat recently")
            return

        winner = random.choice([ctx.author, target])
        results = await misc.fight(self.bot.con_pool, ctx.author.id, str(target.id), str(winner.id))
        wins, losses = results.user_stats(ctx.author.id)

        winning_messages = [
            f"You smashed {target.name} into the ground, leaving them in pieces",
            f"You ripped through {target.name} like a hurricane, leaving destruction behind",
            f"You obliterated {target.name}, and now their soul is shattered",
            f"You crushed {target.name} so hard they'll never recover",
            f"You broke {target.name} with a single, devastating blow",
            f"You tore {target.name} apart, limb from limb, with savage force",
            f"You annihilated {target.name}, leaving nothing but ruins",
            f"You demolished {target.name}, reducing them to rubble",
            f"You sent {target.name} flying into orbit, leaving them as a distant speck in the sky",
            f"You summoned a tidal wave that swallowed {target.name} whole, washing them into oblivion",
            f"You unleashed a black hole that sucked {target.name} into another dimension",
            f"You turned {target.name} into a pile of ash with a single touch of your fiery wrath",
            f"You transformed into a giant and stomped {target.name} into the ground like an insect",
            f"You snapped your fingers and {target.name} disintegrated into a cloud of dust",
            f"You called down lightning that vaporized {target.name}, leaving only a smoking crater",
            f"You unleashed a swarm of locusts that devoured {target.name}, leaving nothing but bones",
            f"You teleported behind {target.name}, sending them into the void with a single blow",
            f"You summoned a meteor that obliterated {target.name}, destroying half the earth with it",
            f"You summoned a supernova that engulfed {target.name}, leaving only cosmic dust in its wake",
            f"You split the earth in two, sending {target.name} tumbling into the fiery core of the planet",
            f"You turned into a whirlwind of blades and sliced {target.name} into a million pieces",
            f"You harnessed the power of the sun and incinerated {target.name} in a blinding flash of light",
            f"You summoned an army of clones that overwhelmed {target.name} in an instant",
            f"You teleported {target.name} to the moon, leaving them stranded in the void of space",
            f"You summoned a colossal beast that swallowed {target.name} whole in one massive gulp",
            f"You snapped reality in half, sending {target.name} into a chaotic dimension of pure madness",
            f"You rewrote the laws of physics and erased {target.name} from the timeline entirely",
            f"You summoned an intergalactic fleet that vaporized {target.name} with their laser cannons",
        ]
        losing_messages = [
            f"{target.name} shattered you into dust with a single strike",
            f"{target.name} ripped through you, leaving a trail of blood and pain",
            f"{target.name} crushed you into the ground, utterly destroying you",
            f"{target.name} obliterated you, and now your hopes are in pieces",
            f"{target.name} left you broken, bruised, and beaten into submission",
            f"{target.name} tore through you, leaving nothing but carnage behind",
            f"{target.name} flattened you, leaving your body limp and lifeless",
            f"{target.name} crushed you like a bug, splattering your dreams",
            f"{target.name} turned you into stone, leaving your frozen form as a monument to defeat",
            f"{target.name} opened a portal beneath you, sending you spiraling into another dimension",
            f"{target.name} unleashed a dragon that roasted you alive in a breath of fire",
            f"{target.name} snapped their fingers and time reversed, erasing you from existence",
            f"{target.name} shrunk you down to the size of an ant and squashed you underfoot",
            f"{target.name} summoned a storm that swept you away, leaving no trace behind",
            f"{target.name} called down an asteroid that flattened you, leaving only a smoking hole",
            f"{target.name} unleashed a vortex that tore you apart molecule by molecule",
            f"{target.name} trapped you in a bubble and sent you floating into the endless void",
            f"{target.name} turned you into a shadow, and you dissolved into the darkness forever",
            f"{target.name} unleashed a black hole that swallowed you whole, tearing you apart atom by atom",
            f"{target.name} summoned a massive tsunami that washed you away into the endless ocean",
            f"{target.name} reversed time, causing you to vanish before you even started the fight",
            f"{target.name} summoned an interdimensional portal that sent you spinning into the unknown",
            f"{target.name} turned you into pure energy and scattered you across the universe",
            f"{target.name} summoned a sentient storm that tore you apart with lightning and wind",
            f"{target.name} shattered the ground beneath you, sending you plunging into an endless abyss",
            f"{target.name} opened a wormhole that sucked you into the fabric of space and time itself",
            f"{target.name} summoned an asteroid that crashed down on you, flattening everything in sight",
        ]
        if winner == ctx.author:
            message = random.choice(winning_messages)
        else:
            message = random.choice(losing_messages).capitalize()

        message += f" (W:{wins}, L:{losses} | WR - {wins/(wins+losses)*100:.0f}%)"
        await self.bot.msg_q.reply(ctx, message, [target.name, target.name.capitalize()])

    @commands.command(aliases=("🎲", "die", "dice"))
    async def roll(self, ctx: commands.Context, *args: str):
        """
        Rolls a die/dice; {prefix}roll <rolls>d<sides>...; -d to make the rolls distinct
        (only works if the number of rolls is less than number of sides), -s to sort the rolls in
        ascending order
        """
        assert isinstance(ctx.author.name, str)

        roll_pattern = re.compile(r"\d{0,4}d\d{1,7}")
        rolls = list(filter(roll_pattern.match, args))

        if len(rolls) == 0:
            number = random.randint(1, 20)
            await self.bot.msg_q.send(ctx, f"{ctx.author.name} rolled {number} (1-20)", [ctx.author.name])
            return

        rolled = []
        for roll in rolls:
            count, sides = roll.split("d")
            if not count:
                count = 1
            else:
                count = int(count)
            sides = int(sides)

            if ("-d" in args or "-u" in args) and count <= sides:
                rolled.extend(random.sample(range(1, sides + 1), count))
            else:
                rolled.extend(random.choices(range(1, sides + 1), k=count))

        if len(rolled) == 1:
            message = f"{ctx.author.name} rolled {rolled[0]} (1-{rolls[0].split('d')[1]})"
        elif len(rolled) > 20:
            message = f"{ctx.author.name} rolled total: {sum(rolled)}"
        else:
            if "-s" in args:
                rolled.sort()
            message = f"{ctx.author.name} rolled {', '.join(map(str, rolled))} | total: {sum(rolled)}"
        await self.bot.msg_q.send(ctx, message, [ctx.author.name])

    @commands.cooldown(rate=3, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def rps(self, ctx: commands.Context, move: str):
        """Play rock-paper-scissors against the bot; {prefix}rps <move>"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        move = move.lower()
        if move.startswith("r"):
            move = "rock"
        elif move.startswith("p"):
            move = "paper"
        elif move.startswith("s"):
            move = "scissors"
        else:
            await self.bot.msg_q.reply(ctx, "Please provide a valid rock-paper-scissors move")
            return

        bot_move = random.choice(("rock", "paper", "scissors"))

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        if move == bot_move:
            stats = await misc.rps(self.bot.con_pool, ctx.author.id, "draw")
            outcome = "tie"
            emote = await seventv.best_fitting_emote(
                channel_id,
                lambda emote: emote.lower().startswith("dank"),
                default="FeelsDankMan",
                include_global=True,
            )
        elif (
            (move == "rock" and bot_move == "scissors")
            or (move == "paper" and bot_move == "rock")
            or (move == "scissors" and bot_move == "paper")
        ):
            stats = await misc.rps(self.bot.con_pool, ctx.author.id, "win")
            outcome = "you won"
            emote = await seventv.sad_emote(channel_id)
        else:
            stats = await misc.rps(self.bot.con_pool, ctx.author.id, "loss")
            outcome = "I won"
            emote = await seventv.happy_emote(channel_id)

        await self.bot.msg_q.reply(
            ctx,
            f"{bot_move} - {outcome} {emote} (W:{stats.wins}, T:{stats.draws}, L:{stats.losses})",
        )

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def fill(self, ctx: commands.Context, *words):
        """Fills the message with given words; {prefix}fill <arg1> <arg2>..."""
        if len(words) == 0:
            await self.bot.msg_q.send(ctx, "Please provide words to be used in the command")
            return
        max_length = 350
        message = ""
        word = random.choice(words)
        while len(message) + len(word) < max_length:
            message += f"{word} "
            word = random.choice(words)
        if not message:
            await self.bot.msg_q.send(ctx, "A word given was longer than the set max length")
            return
        await self.bot.msg_q.send(ctx, message)


def prepare(bot: "Bot"):
    bot.add_cog(Basic(bot))
