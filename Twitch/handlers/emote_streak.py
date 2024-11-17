from asyncpg import Pool

from shared.apis import seventv
from shared.database.twitch import channels


class EmoteStreaks:
    def __init__(self, con_pool: Pool) -> None:
        self.pyramids = Pyramids(con_pool)
        self.stairs = Stairs(con_pool)
        self.streaks = Streaks(con_pool)

    # Only one message from emote patterns is allowed: pyramid > stairs > streak
    # Those that overlap are reset by a former pattern to avoid multiple messages
    async def streak_message(self, channel: str, sender: str, message: str) -> tuple[str, list[str]] | None:
        pyramid_completion_message = await self.pyramids.increase(channel, sender, message)
        if pyramid_completion_message:
            self.streaks.reset(channel)
            self.stairs.reset(channel)

        stair_completion_message = await self.stairs.increase(channel, sender, message)
        if stair_completion_message:
            self.streaks.reset(channel)

        streak_break_message = await self.streaks.increase(channel, sender, message)

        for msg in [pyramid_completion_message, stair_completion_message, streak_break_message]:
            if msg is not None:
                return msg

    def reset_all(self, channel: str):
        self.pyramids.reset(channel)
        self.stairs.reset(channel)
        self.streaks.reset(channel)


class Streak:
    def __init__(self, emotes: set[str]) -> None:
        self.reset(emotes)

    def reset(self, emotes: set[str]):
        self.streak_count = 1
        self.streak_emotes = emotes

    def next(self, new_emotes: set[str]) -> tuple[str, int] | None:
        matching_emotes = self.streak_emotes.intersection(new_emotes)
        if len(matching_emotes) == 0:
            failed_streak = self.streak_emotes
            failed_streak_count = self.streak_count
            self.reset(new_emotes)
            if len(failed_streak) > 0:
                return (list(failed_streak)[0], failed_streak_count)
            return
        self.streak_count += 1
        self.streak_emotes = matching_emotes


class Streaks:
    def __init__(self, con_pool: Pool) -> None:
        self.con_pool = con_pool
        self._streaks: dict[str, Streak] = {}

    def reset(self, channel: str) -> None:
        if channel in self._streaks:
            del self._streaks[channel]

    async def increase(self, channel: str, sender: str, message: str) -> tuple[str, list[str]] | None:
        words = message.split()
        channel_id = await channels.channel_id(self.con_pool, channel)
        emote_names = await seventv.emote_names(channel_id, include_global=True)

        emotes_in_message = set(word for word in words if word in emote_names)
        current_streak = self._streaks.get(channel)
        if current_streak is None:
            self._streaks[channel] = Streak(emotes_in_message)
        else:
            streak_broken = current_streak.next(emotes_in_message)
            if streak_broken is not None and streak_broken[1] > 4:
                streak_emote, streak_reached = streak_broken
                if streak_reached > 15:
                    happy_emote = await seventv.best_fitting_emote(
                        channel_id,
                        lambda emote: any(e in emote for e in ["Pog", "pogs", "POG", "Pag"]),
                        default="peepoHappy",
                    )
                    return (f"{streak_reached}x {streak_emote} reached {happy_emote}", [])
                else:
                    sad_emote = await seventv.best_fitting_emote(
                        channel_id, lambda emote: "Sad" in emote or "Cry" in emote, default="peepoSad"
                    )
                    return (f"{sender} broke {streak_reached}x {streak_emote} streak {sad_emote}", [sender])


class Pyramid:
    def __init__(self, emote: str, sender: str) -> None:
        self.reset(emote, sender)

    def reset(self, emote: str, sender: str) -> None:
        self.current_height = 1
        self.peak_height = 1
        self.emote = emote
        self.increasing = True
        self.contributors = set([sender])

    def next(self, emote: str, count: int, sender: str) -> tuple[str, int, list[str]] | None:
        if self.emote != emote:
            self.reset(emote, sender)
        elif self.increasing and self.current_height + 1 == count:
            self.current_height += 1
            self.peak_height += 1
            self.contributors.add(sender)
        elif self.increasing and self.current_height - 1 == count and self.peak_height > 2:
            self.current_height -= 1
            self.increasing = False
            self.contributors.add(sender)
        elif not self.increasing and self.current_height - 1 == count:
            self.current_height -= 1
            self.contributors.add(sender)
            if self.current_height == 1:
                emote = self.emote
                peak = self.peak_height
                contributors = self.contributors
                self.reset(emote, sender)
                return (emote, peak, list(contributors))
        else:
            self.reset(emote, sender)


class Pyramids:
    def __init__(self, con_pool: Pool) -> None:
        self.con_pool = con_pool
        self._pyramids: dict[str, Pyramid] = {}

    def reset(self, channel: str) -> None:
        if channel in self._pyramids:
            del self._pyramids[channel]

    async def increase(self, channel: str, sender: str, message: str) -> tuple[str, list[str]] | None:
        words = message.split()
        channel_id = await channels.channel_id(self.con_pool, channel)
        emote_names = await seventv.emote_names(channel_id, include_global=True)

        if not words[0] in emote_names:
            if channel in self._pyramids:
                del self._pyramids[channel]
            return
        else:
            emote = words[0]
            count = 0
            for word in words:
                if word == emote:
                    count += 1
                else:
                    break

        current_pyramid = self._pyramids.get(channel)
        if current_pyramid is None:
            self._pyramids[channel] = Pyramid(emote, sender)
        else:
            finished = current_pyramid.next(emote, count, sender)
            if finished is not None:
                emote, peak, contributors = finished
                clap_emote = await seventv.best_fitting_emote(
                    channel_id,
                    lambda emote: "clap" in emote.lower() or any(e in emote for e in ["Pog", "pogs", "POG", "Pag"]),
                    default="FeelsOkayMan Clap",
                )
                cont = ", ".join([name for name in contributors])[::-1].replace(",", "dna ", 1)[::-1]
                return (f"Nice {peak}-high {emote} pyramid {cont} {clap_emote}", contributors)


class Stair:
    def __init__(self, emote: str | None, count: int) -> None:
        self.reset(emote, count)

    def reset(self, emote: str | None, count: int) -> None:
        self.current_height = count
        self.peak_height = count
        self.emote = emote
        self.increasing = count == 1

    def next(self, emote: str | None, count: int) -> tuple[bool, str, int] | None:
        if self.emote is None or (self.emote != emote and not self.increasing):
            self.reset(emote, count)
        elif self.emote != emote:
            current_emote = self.emote
            peak = self.peak_height
            increasing = self.increasing
            self.reset(emote, count)
            return (increasing, current_emote, peak)
        elif self.increasing and self.current_height + 1 == count:
            self.current_height += 1
            self.peak_height += 1
        elif self.increasing and self.current_height - 1 == count:
            self.current_height -= 1
            self.increasing = False
        elif not self.increasing and self.current_height - 1 == count:
            self.current_height -= 1
            if self.current_height == 1:
                current_emote = self.emote
                peak = self.peak_height
                increasing = self.increasing
                self.reset(emote, count)
                return (increasing, current_emote, peak)
        else:
            current_emote = self.emote
            peak = self.peak_height
            increasing = self.increasing
            self.reset(emote, count)
            if increasing:
                return (increasing, current_emote, peak)


class Stairs:
    def __init__(self, con_pool: Pool) -> None:
        self.con_pool = con_pool
        self._stairs: dict[str, Stair] = {}

    def reset(self, channel: str) -> None:
        if channel in self._stairs:
            del self._stairs[channel]

    async def increase(self, channel: str, sender: str, message: str) -> tuple[str, list[str]] | None:
        words = message.split()
        channel_id = await channels.channel_id(self.con_pool, channel)
        emote_names = await seventv.emote_names(channel_id)

        if not words[0] in emote_names:
            emote = None
            count = 0
        else:
            emote = words[0]
            count = 0
            for word in words:
                if word == emote:
                    count += 1
                else:
                    break

        current_stairs = self._stairs.get(channel)
        if current_stairs is None:
            self._stairs[channel] = Stair(emote, count)
        else:
            stairs_broken_or_complete = current_stairs.next(emote, count)
            if stairs_broken_or_complete is not None and stairs_broken_or_complete[2] > 2:
                increasing, emote, peak = stairs_broken_or_complete
                if increasing:
                    dead_emote = await seventv.best_fitting_emote(
                        channel_id,
                        lambda emote: "dead" in emote.lower() or emote == "dejj" or emote == "RIPBOZO",
                        default="FeelsDankMan",
                    )
                    return (f"{sender} fell down {peak}-high {emote} stairs {dead_emote}", [sender])
                else:
                    clap_emote = await seventv.best_fitting_emote(
                        channel_id,
                        lambda emote: "clap" in emote.lower()
                        or any(e in emote for e in ["Pog", "pogs", "POG", "Pag"]),
                        default="FeelsOkayMan Clap",
                    )
                    return (f"Nice {peak}-high {emote} stairs {clap_emote}", [])
