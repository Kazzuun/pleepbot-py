from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator


__all__ = (
    "EmoteSet",
    "TwitchUser",
    "Emote",
    "EmoteSearchResult",
    "User",
    "UserEditorWithConnections",
    "EditorPermissions",
    "EmoteSetEmote",
    "Subage",
    "Role",
    "CosmeticPaint",
    "UserCosmetic",
)


class Style(BaseModel):
    color: int | None = None
    paint_id: str | None = None
    badge_id: str | None = None


class UserConnection(BaseModel):
    id: str  # connection id
    platform: Literal["TWITCH", "YOUTUBE", "DISCORD", "KICK"]
    username: str
    display_name: str
    linked_at: datetime
    emote_capacity: int
    emote_set_id: str | None


class Owner(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    style: Style
    role_ids: list[str] = Field(default_factory=list)
    connections: list[UserConnection] = Field(default_factory=list)

    def connection_by_platformn(
        self, platform: Literal["TWITCH", "YOUTUBE", "DISCORD", "KICK"]
    ) -> UserConnection | None:
        for con in self.connections:
            if con.platform == platform:
                return con
        return None

    def is_subscribed(self):
        return "01F37R3RFR0000K96678WEQT01" in self.role_ids

    @field_validator("avatar_url", mode="before")
    @classmethod
    def add_protocol(cls, avatar_url: str | None):
        if avatar_url is not None:
            return "https:" + avatar_url


class EmoteFlags(BaseModel):
    value: int
    private: bool
    authentic: bool
    zero_width: bool
    sexual_content: bool
    epilepsy: bool
    edgy: bool
    twitch_disallowed: bool

    @classmethod
    def from_flags(cls, value: int) -> Self:
        return cls(
            value=value,
            private=(value >> 0) & 1 == 1,
            authentic=(value >> 1) & 1 == 1,
            zero_width=(value >> 8) & 1 == 1,
            sexual_content=(value >> 16) & 1 == 1,
            epilepsy=(value >> 17) & 1 == 1,
            edgy=(value >> 18) & 1 == 1,
            twitch_disallowed=(value >> 24) & 1 == 1,
        )


class Image(BaseModel):
    name: str
    static_name: str | None = None
    width: int
    height: int
    frame_count: int
    size: int
    format: Literal["AVIF", "WEBP", "PNG", "GIF"]


class ImageHost(BaseModel):
    url: str
    files: list[Image]

    @field_validator("url")
    @classmethod
    def add_protocol(cls, url: str):
        return "https:" + url


class EmoteData(BaseModel):
    id: str
    name: str
    flags: EmoteFlags  # see: https://github.com/SevenTV/Website/blob/01d690c62a9978ecc64c972632fa500f837513c9/src/structures/Emote.ts#L59
    tags: list[str] = Field(default_factory=list)
    lifecycle: int
    state: list[Literal["LISTED", "PERSONAL", "NO_PERSONAL"]]
    listed: bool
    animated: bool
    owner: Owner | None = None
    host: ImageHost

    @field_validator("flags", mode="before")
    @classmethod
    def validate_flags(cls, value: int) -> EmoteFlags:
        return EmoteFlags.from_flags(value)


class EmoteSetEmote(BaseModel):
    id: str
    name: str
    flags: int
    timestamp: datetime
    actor_id: str | None
    data: EmoteData
    origin_id: str | None


class UserEmoteSet(BaseModel):
    id: str
    name: str
    flags: int
    tags: list[str]
    immutable: bool
    privileged: bool
    emotes: list[EmoteSetEmote] = Field(default_factory=list)
    emote_count: int = 0
    capacity: int

    def emote_by_name(self, emote_name: str) -> EmoteSetEmote | None:
        for emote in self.emotes:
            if emote.name == emote_name:
                return emote
        return None


class EmoteSet(UserEmoteSet):
    owner: Owner


class EmoteSetPartial(BaseModel):
    id: str
    name: str
    flags: int
    tags: list[str]
    capacity: int


class EditorPermissions(BaseModel):
    value: int
    modify_emotes: bool
    use_private_emotes: bool
    manage_profile: bool
    manage_owned_emotes: bool
    manage_emote_sets: bool
    manage_billing: bool
    manage_editors: bool
    view_messages: bool

    @classmethod
    def to_permissions(cls, permissions: int) -> Self:
        return cls(
            value=permissions,
            modify_emotes=(permissions >> 0) & 1 == 1,
            use_private_emotes=(permissions >> 1) & 1 == 1,
            manage_profile=(permissions >> 2) & 1 == 1,
            manage_owned_emotes=(permissions >> 3) & 1 == 1,
            manage_emote_sets=(permissions >> 4) & 1 == 1,
            manage_billing=(permissions >> 5) & 1 == 1,
            manage_editors=(permissions >> 6) & 1 == 1,
            view_messages=(permissions >> 7) & 1 == 1,
        )

    @classmethod
    def from_permissions(
        cls,
        *,
        modify_emote_set: bool = False,  # default permission
        use_private_emotes: bool = False,
        manage_profile: bool = False,
        manage_owned_emotes: bool = False,
        manage_emote_sets: bool = False,  # default permission
        manage_billing: bool = False,
        manage_editors: bool = False,
        view_messages: bool = False
    ) -> Self:
        editor_permissions = 0
        editor_permissions |= modify_emote_set << 0
        editor_permissions |= use_private_emotes << 1
        editor_permissions |= manage_profile << 2
        editor_permissions |= manage_owned_emotes << 3
        editor_permissions |= manage_emote_sets << 4
        editor_permissions |= manage_billing << 5
        editor_permissions |= manage_editors << 6
        editor_permissions |= view_messages << 7
        return cls.to_permissions(editor_permissions)


class UserEditor(BaseModel):
    id: str  # 7tv id
    permissions: EditorPermissions  # see: https://github.com/SevenTV/Common/blob/048a247f3aa41a7bbf9a1fe105025314bcbdef95/structures/v3/type.user.go#L220
    visible: bool
    added_at: datetime

    @field_validator("permissions", mode="before")
    @classmethod
    def validate_permissions(cls, value: int) -> EditorPermissions:
        return EditorPermissions.to_permissions(value)


class UserBase(BaseModel):
    id: str
    username: str
    display_name: str
    biography: str | None = None
    created_at: datetime
    avatar_url: str
    style: Style
    emote_sets: list[EmoteSetPartial] = Field(default_factory=list)
    editors: list[UserEditor] = Field(default_factory=list)
    roles: list[str]

    @field_validator("avatar_url", mode="before")
    @classmethod
    def add_protocol(cls, avatar_url: str | None) -> str | None:
        if avatar_url is not None:
            return "https:" + avatar_url

    def is_subscibed(self) -> bool:
        return "01F37R3RFR0000K96678WEQT01" in self.roles


class UserInfo(UserBase):
    connections: list[UserConnection]

    def connection_by_platform(
        self, platform: Literal["TWITCH", "YOUTUBE", "DISCORD", "KICK"]
    ) -> UserConnection | None:
        for con in self.connections:
            if con.platform == platform:
                return con


class TwitchUser(BaseModel):
    id: str  # twitch id
    platform: Literal["TWITCH"]
    username: str
    display_name: str
    linked_at: datetime
    emote_capacity: int
    emote_set_id: str
    emote_set: UserEmoteSet
    user: UserInfo


class EmoteVersion(BaseModel):
    id: str
    name: str
    description: str
    lifecycle: int
    state: list[Literal["LISTED", "PERSONAL", "NO_PERSONAL"]]
    listed: bool
    animated: bool
    host: ImageHost
    created_at: datetime = Field(alias="createdAt")


class Emote(EmoteData):
    versions: list[EmoteVersion]


class UserConnectionFull(UserConnection):
    emote_set: UserEmoteSet


class User(UserBase):
    connections: list[UserConnectionFull]

    def connection_by_platform(
        self, platform: Literal["TWITCH", "YOUTUBE", "DISCORD", "KICK"]
    ) -> UserConnection | None:
        for con in self.connections:
            if con.platform == platform:
                return con


class SubscriptionCycle(BaseModel):
    timestamp: datetime
    unit: Literal["MONTH", "YEAR"]
    value: int
    status: Literal["ONGOING", "CANCELED"]
    internal: bool
    pending: bool
    trial_end: datetime | None


class Subscription(BaseModel):
    id: str
    provider: str | None
    product_id: str
    plan: str
    seats: int
    subscriber_id: str
    customer_id: str
    started_at: str
    ended_at: datetime | None
    cycle: SubscriptionCycle
    renew: bool


class Subage(BaseModel):
    active: bool
    age: int
    months: int
    renew: bool
    end_at: datetime | None
    subscription: Subscription | None


class UserPartialWithConnections(BaseModel):
    id: str
    username: str
    connections: list[UserConnection]


class UserEditorWithConnections(UserEditor):
    user: UserPartialWithConnections


class EmoteSearchEmote(BaseModel):
    id: str
    name: str
    state: list[Literal["LISTED", "PERSONAL", "NO_PERSONAL"]]
    trending: int | None


class EmoteSearchResult(BaseModel):
    count: int
    emotes: list[EmoteSearchEmote] = Field(alias="items")


class Role(BaseModel):
    id: str
    name: str
    allowed: int
    denied: int
    color: int
    invisible: bool


class CosmeticPaint(BaseModel):
    id: str
    name: str


class UserCosmetic(BaseModel):
    id: str
    kind: Literal["PAINT", "BADGE"]
    selected: bool
