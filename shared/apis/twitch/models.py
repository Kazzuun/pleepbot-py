from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


__all__ = ("Message", "EmoteType", "Emote", "ModVip", "Founders", "Subage", "Schedule", "SocialMedia", "User")


class PartialEmote(BaseModel):
    id: str
    set_id: str = Field(alias="setID")
    name: str = Field(alias="token")


class PartialUser(BaseModel):
    id: str
    username: str = Field(alias="login")
    display_name: str = Field(alias="displayName")


class MessageContent(BaseModel):
    emotes: list[PartialEmote]
    text: str


class Message(BaseModel):
    content: MessageContent
    deleted_at: datetime | None = Field(alias="deletedAt")
    id: str
    sender: PartialUser
    sent_at: datetime = Field(alias="sentAt")


class EmoteType(StrEnum):
    CHANNEL_POINTS = "CHANNEL_POINTS"
    BITS_BADGE_TIERS = "BITS_BADGE_TIERS"
    SUBSCRIPTIONS = "SUBSCRIPTIONS"
    PRIME = "PRIME"
    TURBO = "TURBO"
    TWO_FACTOR = "TWO_FACTOR"
    SMILIES = "SMILIES"
    GLOBALS = "GLOBALS"
    LIMITED_TIME = "LIMITED_TIME"
    HYPE_TRAIN = "HYPE_TRAIN"
    MEGA_COMMERCE = "MEGA_COMMERCE"
    ARCHIVE = "ARCHIVE"
    FOLLOWER = "FOLLOWER"
    UNKNOWN = "UNKNOWN"


class Emote(PartialEmote):
    asset_type: Literal["ANIMATED", "STATIC", "UNKNOWN"] = Field(alias="assetType")
    artist: PartialUser | None
    owner: PartialUser | None
    subscription_tier: Literal[1, 2, 3] | None = Field(alias="subscriptionTier")
    suffix: str | None
    emote_type: EmoteType = Field(alias="type")

    @field_validator("subscription_tier", mode="before")
    @classmethod
    def sub_tier_to_number(cls, subscription_tier: Literal["TIER_1", "TIER_2", "TIER_3"] | None) -> int | None:
        if subscription_tier is None:
            return None
        return int(subscription_tier[-1])


class ModVip(BaseModel):
    granted_at: datetime = Field(alias="grantedAt")
    user: PartialUser | None


class Founder(BaseModel):
    is_subscribed: bool = Field(alias="isSubscribed")
    entitlement_start: datetime = Field(alias="entitlementStart")
    user: PartialUser | None


class Founders(BaseModel):
    founders: list[Founder]
    founder_badge_availability: int = Field(alias="founderBadgeAvailability")


class SubscriptionGift(BaseModel):
    gift_date: datetime | None = Field(alias="giftDate")
    gifter: PartialUser | None
    is_gift: bool = Field(alias="isGift")


class SubscriptionBenefit(BaseModel):
    ends_at: datetime | None = Field(alias="endsAt")
    gift: SubscriptionGift
    platform: Literal["NONE", "WEB", "IOS", "ANDROID", "MOBILE_ALL"]
    purchased_with_prime: bool = Field(alias="purchasedWithPrime")
    renews_at: datetime | None = Field(alias="renewsAt")
    tier: Literal[1, 2, 3]

    @field_validator("tier", mode="before")
    @classmethod
    def sub_tier_to_number(cls, subscription_tier: Literal["1000", "2000", "3000"]) -> int:
        return int(subscription_tier) // 1000


class CumulativeSubscription(BaseModel):
    days_remaining: int = Field(alias="daysRemaining")
    elapsed_days: int = Field(alias="elapsedDays")
    end: datetime
    months: int
    start: datetime


class Streak(BaseModel):
    months: int


class Subage(BaseModel):
    followed_at: datetime | None = Field(alias="followedAt")
    subscription_benefit: SubscriptionBenefit | None = Field(alias="subscriptionBenefit")
    cumulative: CumulativeSubscription | None
    streak: Streak | None


class Game(BaseModel):
    display_name: str = Field(alias="displayName")


class ScheduleSegment(BaseModel):
    categories: list[Game]
    end_at: datetime = Field(alias="endAt")
    is_cancelled: bool = Field(alias="isCancelled")
    start_at: datetime = Field(alias="startAt")
    title: str


class Schedule(BaseModel):
    next_segment: ScheduleSegment | None = Field(alias="nextSegment")
    segments: list[ScheduleSegment] | None


class SocialMedia(BaseModel):
    name: str
    title: str
    url: str


class BroadcastSettings(BaseModel):
    game: Game | None
    is_mature: bool = Field(alias="isMature")
    title: str | None


class Channel(BaseModel):
    chatters: int
    founder_badge_availability: int = Field(alias="founderBadgeAvailability")

    @field_validator("chatters", mode="before")
    @classmethod
    def chatters_to_count(cls, chatters: dict) -> int:
        return chatters["count"]


class LastBroadcast(BaseModel):
    game: Game | None
    started_at: datetime | None = Field(alias="startedAt")
    title: str | None  # Current title

    @field_validator("title", mode="before")
    @classmethod
    def null_title(cls, title: str) -> str | None:
        if title == "":
            return None
        return title


class Roles(BaseModel):
    is_affiliate: bool = Field(alias="isAffiliate")
    is_partner: bool = Field(alias="isPartner")


class Stream(BaseModel):
    average_FPS: int = Field(alias="averageFPS")
    bitrate: int
    clip_count: int = Field(alias="clipCount")
    started_at: datetime = Field(alias="createdAt")
    game: Game | None
    id: str
    title: str | None
    type: str
    viewers_count: int = Field(alias="viewersCount")


class User(PartialUser):
    banner_image_URL: str | None = Field(alias="bannerImageURL")
    broadcast_settings: BroadcastSettings = Field(alias="broadcastSettings")
    channel: Channel
    chat_color: str | None = Field(alias="chatColor")
    created_at: datetime = Field(alias="createdAt")
    deleted_at: datetime | None = Field(alias="deletedAt")
    description: str | None
    emote_prefix: str | None = Field(alias="emoticonPrefix")
    followers: int
    last_broadcast: LastBroadcast = Field(alias="lastBroadcast")
    offline_image_URL: str | None = Field(alias="offlineImageURL")
    profile_image_URL: str = Field(alias="profileImageURL")
    profile_URL: str = Field(alias="profileURL")
    roles: Roles
    stream: Stream | None
    updated_at: datetime | None = Field(alias="updatedAt")

    @field_validator("emote_prefix", mode="before")
    @classmethod
    def null_prefix(cls, emote_prefix: dict) -> str | None:
        if emote_prefix["name"] == "":
            return None
        return emote_prefix["name"]

    @field_validator("followers", mode="before")
    @classmethod
    def followers_to_count(cls, followers: dict) -> int:
        return followers["totalCount"]


# class ChatSettings(BaseModel):
#     chat_delay_ms: int = Field(alias="chatDelayMs")
#     followers_only_duration_minutes: int | None = Field(alias="followersOnlyDurationMinutes")
#     slow_mode_duration_seconds: int | None = Field(alias="slowModeDurationSeconds")
#     block_links: bool = Field(alias="blockLinks")
#     is_subscribers_only_mode_enabled: bool = Field(alias="isSubscribersOnlyModeEnabled")
#     is_emote_only_mode_enabled: bool = Field(alias="isEmoteOnlyModeEnabled")
#     is_fast_subs_mode_enabled: bool = Field(alias="isFastSubsModeEnabled")
#     is_unique_chat_mode_enabled: bool = Field(alias="isUniqueChatModeEnabled")
#     require_verified_account: bool = Field(alias="requireVerifiedAccount")
#     rules: list[str]
