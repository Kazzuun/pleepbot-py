from datetime import datetime, UTC, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from shared.apis import seventv
from shared.util.formatting import format_timedelta


class ChannelConfig(BaseModel):
    channel_id: str
    username: str
    currently_online: bool
    joined_at: datetime
    logging: bool
    emote_streaks: bool
    commands_online: bool
    reminds_online: bool
    notifications_online: bool
    outside_reminds: bool
    disabled_commands: set[str]
    banned_users: set[str]
    prefixes: tuple[str, ...]


class UserConfig(BaseModel):
    user_id: str
    role: Literal["ADMIN", "DEFAULT", "RESTRICTED", "BANNED"] = "DEFAULT"
    no_replies: bool = False
    optouts: set[str] = Field(default_factory=set)

    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    def is_banned(self) -> bool:
        return self.role == "BANNED"


class Watchtime(BaseModel):
    channel_id: str
    username: str
    total_time: int = 0
    online_time: int = 0


class BlockedTerm(BaseModel):
    id: int
    pattern: str
    regex: bool


class Reminder(BaseModel):
    id: int
    channel_id: str
    sender_id: str
    target_id: str
    message: str | None
    created_at: datetime
    scheduled_at: datetime | None

    async def formatted_message(self, sender: str, target: str) -> tuple[str, list[str]]:
        time_ellapsed = format_timedelta(self.created_at, datetime.now(UTC), precision=6, exclude_zeros=True)

        message = self.message
        if message is None:
            message = "(no message)"

        if self.sender_id == self.target_id:
            sender = "yourself"
            targets = []
        else:
            targets = [sender]

        if self.scheduled_at is None:
            remind_type = "reminder"
        else:
            remind_type = "message"

        return (f"@{target}, {remind_type} from {sender} ({time_ellapsed} ago): {message}", targets)


class AfkStatus(BaseModel):
    id: int
    channel_id: str
    target_id: str
    kind: Literal["AFK", "GN", "WORK"]
    created_at: datetime

    async def formatted_message(self, target: str) -> tuple[str, list[str]]:
        time_ellapsed = format_timedelta(self.created_at, datetime.now(UTC))
        targets = [target]

        match self.kind:
            case "AFK":
                emote = await seventv.happy_emote(self.channel_id)
                message = f"Welcome back {target} {emote} ({time_ellapsed})"

            case "GN":
                emote = await seventv.best_fitting_emote(
                    self.channel_id,
                    lambda emote: emote.lower().startswith("hug")
                    or emote.lower().endswith("hug")
                    or "kiss" in emote.lower(),
                    default="peepoHappy",
                )
                message = f"Good morning {target} {emote} ({time_ellapsed})"

            case "WORK":
                emote = await seventv.best_fitting_emote(
                    self.channel_id, lambda emote: "corpa" in emote.lower() or "money" in emote.lower()
                )
                message = f"{target} finished all of their work {emote} ({time_ellapsed})"

        return (message, targets)


class Message(BaseModel):
    channel_id: str
    sender: str
    message: str
    sent_at: datetime


class CustomCommand(BaseModel):
    channel_id: str
    name: str
    message: str
    level: Literal["BROADCASTER", "MOD", "VIP", "SUBSCRIBER", "FOLLOWER", "EVERYONE"]
    enabled: bool


class CustomPattern(BaseModel):
    channel_id: str
    name: str
    message: str
    pattern: str
    regex: bool
    probability: float
    enabled: bool


class Counter(BaseModel):
    channel_id: str
    name: str
    value: int = 0


class Timer(BaseModel):
    channel_id: str
    channel_name: str
    name: str
    message: str
    next_time: datetime
    time_between: timedelta
    enabled: bool
    # TODO: enabled online, offline or both


class LiveNotification(BaseModel):
    channel_id: str
    target_id: str
    pings: set[str]


class YoutubeUploadNotification(BaseModel):
    channel_id: str
    playlist_id: str
    pings: set[str]


class Fisher(BaseModel):
    user_id: str
    fish_count: int = 0
    exp: int = 0
    last_fished: datetime | None = None
    equipment: int = 0


class FishingEquipment(BaseModel):
    id: int
    name: str
    cost: int
    level_req: int
    effect: float | None
    effect_disc: str
    equipment_type: Literal[
        "FISHFLAT",
        "FISHMULTI",
        "EXPMULTI",
        "AFKMULTI",
        "COOLDOWNFLAT",
        "NORNG",
        "LESSRNG",
        "HAULCHANCE",
        "HAULSIZEMULTI",
    ]


class LastIq(BaseModel):
    user_id: str
    last_iq: int
    last_updated: datetime


class RpsStats(BaseModel):
    user_id: str
    wins: int
    draws: int
    losses: int


class FightStats(BaseModel):
    user_id_1: str
    user_id_2: str
    user_1_wins: int
    user_2_wins: int

    def user_stats(self, user_id: str) -> tuple[int, int]:
        """Returns the wins and losses of the given user as a tuple"""
        if self.user_id_1 == user_id:
            return (self.user_1_wins, self.user_2_wins)
        elif self.user_id_2 == user_id:
            return (self.user_2_wins, self.user_1_wins)
        else:
            raise ValueError("User with given id not part of the fight")


class Location(BaseModel):
    user_id: str
    latitude: float
    longitude: float
    address: str
    private: bool
