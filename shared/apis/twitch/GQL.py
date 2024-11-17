from datetime import datetime, timedelta, UTC
import os
from typing import Literal

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

from .models import Emote, Founders, Message, ModVip, Schedule, SocialMedia, Subage, User
from ..cache import async_cache
from ..exceptions import gql_error_handler


__all__ = (
    "message_by_id",
    "emote_by_id",
    "emote_set_by_id",
    "founders",
    "mods",
    "vips",
    "username_available",
    "subage",
    "schedule",
    "social_medias",
    "user_info",
)


# https://github.com/daylamtayari/Twitch-GQL/blob/master/schema.graphql
ENDPOINT = "https://gql.twitch.tv/gql"
HEADERS = {
    "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",  # this is public
    "Content-Type": "application/json",
    "Authorization": f"OAuth {os.environ['TWITCH_OAUTH']}",  # TODO: figure out what to do with this
}
TIMEOUT = 7


@gql_error_handler()
async def message_by_id(message_id: str) -> Message | None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($id: ID!) { 
                message(id: $id) {
                    content {
                        fragments {
                            content {
                                ... on Emote {
                                    id
                                    setID
                                    token
                                }
                            }
                            text
                        }
                        text
                    }
                    deletedAt
                    id
                    sender {
                        id
                        login
                        displayName
                    }
                    sentAt
                }
            }
        """
        )
        variables = {"id": message_id}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["message"] is None:
            return None
        emotes = []
        for fragment in query_results["message"]["content"]["fragments"]:
            if fragment["content"] is not None:
                emotes.append(fragment["content"])
        query_results["message"]["content"]["emotes"] = emotes
        return Message(**query_results["message"])


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def emote_by_id(emote_id: str) -> Emote | None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($id: ID!) { 
                emote(id: $id) {
                    assetType
                    artist {
                        id
                        login
                        displayName
                    }
                    id
                    owner {
                        id
                        login
                        displayName
                    }
                    setID
                    subscriptionTier
                    suffix
                    token
                    type
                }
            }
        """
        )
        variables = {"id": emote_id}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["emote"] is None:
            return None
        return Emote(**query_results["emote"])


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def emote_set_by_id(emote_id: str) -> list[Emote]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($id: ID!) { 
                emoteSet(id: $id) {
                    emotes {
                        assetType
                        artist {
                            id
                            login
                            displayName
                        }
                        id
                        owner {
                            id
                            login
                            displayName
                        }
                        setID
                        subscriptionTier
                        suffix
                        token
                        type
                    }
                }
            }
        """
        )
        variables = {"id": emote_id}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["emoteSet"] is None:
            return []
        return [Emote(**emote) for emote in query_results["emoteSet"]["emotes"]]


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def founders(channel_id: str) -> Founders | None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($channelID: ID!) { 
                channel(id: $channelID) {
                    founders {
                        entitlementStart
                        isSubscribed
                        user {
                            id
                            login
                            displayName
                        }
                    }
                    founderBadgeAvailability
                }
            }
        """
        )
        variables = {"channelID": channel_id}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["channel"] is None:
            return None
        return Founders(**query_results["channel"])


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def mods(channel: str, first: int = 100) -> list[ModVip]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($login: String!, $first: Int!) { 
                user(login: $login) {
                    mods(first: $first) {
                        edges {
                            user: node {
                                displayName
                                id
                                login
                            }
                            grantedAt
                        }
                    }
                }
            }
        """
        )
        variables = {"login": channel, "first": first}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["user"] is None:
            return []
        return [ModVip(**user) for user in query_results["user"]["mods"]["edges"]]


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def vips(channel: str, first: int = 100) -> list[ModVip]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($login: String!, $first: Int!) { 
                user(login: $login) {
                    vips(first: $first) {
                        edges {
                            user: node {
                                id
                                login
                                displayName
                            }
                            grantedAt
                        }
                    }
                }
            }
        """
        )
        variables = {"login": channel, "first": first}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["user"] is None:
            return []
        return [ModVip(**user) for user in query_results["user"]["vips"]["edges"]]


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def username_available(username: str) -> bool:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($username: String!) { 
                isUsernameAvailable(username: $username)
            }
        """
        )
        variables = {"username": username}
        query_results = await session.execute(query, variable_values=variables)
        return query_results["isUsernameAvailable"]


@gql_error_handler()
@async_cache(timedelta(minutes=1))
async def subage(user_id: str, target_user_id: str) -> Subage | None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query($userID: ID!, $targetUserID: ID!) { 
                user(id: $userID) {
                    relationship(targetUserID: $targetUserID) {
                        followedAt
                        subscriptionBenefit {
                            endsAt
                            gift {
                                giftDate
                                gifter {
                                    id
                                    login
                                    displayName
                                }
                                isGift
                            }
                            platform
                            purchasedWithPrime
                            renewsAt
                            tier
                        }
                        cumulative: subscriptionTenure(tenureMethod: CUMULATIVE) {
                            daysRemaining
                            elapsedDays
                            end
                            months
                            start
                        }
                        streak: subscriptionTenure(tenureMethod: STREAK) {
                            months
                        }
                    }
                }
            }
        """
        )
        variables = {"userID": user_id, "targetUserID": target_user_id}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["user"] is None:
            return None
        return Subage(**query_results["user"]["relationship"])


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def schedule(channel_id: str) -> Schedule | None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query ($userID: ID!, $startingWeekday: String) {
                user(id: $userID) {
                    channel {
                        schedule {
                            nextSegment {
                                categories {
                                    displayName
                                }
                                endAt
                                isCancelled
                                startAt
                                title
                            }
                            segments(startingWeekday: $startingWeekday) {
                                categories {
                                    displayName
                                }
                                endAt
                                isCancelled
                                startAt
                                title
                            }
                        }
                    }
                }
            }
        """
        )
        variables = {"userID": channel_id, "startingWeekday": datetime.now(UTC).strftime("%A")}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["user"] is None or query_results["user"]["channel"]["schedule"] is None:
            return None
        return Schedule(**query_results["user"]["channel"]["schedule"])


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def social_medias(channel_id: str) -> list[SocialMedia]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query ($userID: ID!) {
                user(id: $userID) {
                    channel {
                        socialMedias {
                            name
                            title
                            url
                        }
                    }
                }
            }
        """
        )
        variables = {"userID": channel_id}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["user"] is None:
            return []
        return [SocialMedia(**media) for media in query_results["user"]["channel"]["socialMedias"]]


@gql_error_handler()
@async_cache(timedelta(minutes=1))
async def user_info(
    username: str | None = None, user_id: str | None = None, *, pfp_width: Literal[28, 50, 70, 96, 150, 300, 600] = 96
) -> User | None:
    if (user_id is None and username is None) or (user_id is not None and username is not None):
        raise ValueError("Specify only either user id or username")
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query ($userID: ID, $login: String, $width: Int!) {
                user(id: $userID, login: $login, lookupType: ALL) {
                    bannerImageURL
                    broadcastSettings {
                        game {
                            displayName
                        }
                        isMature
                        title
                    }
                    channel {
                        chatters {
                            count
                        }
                        founderBadgeAvailability
                        url
                    }
                    chatColor
                    createdAt
                    deletedAt
                    description
                    displayName
                    emoticonPrefix {
                        name
                    }
                    followers {
                        totalCount
                    }
                    id
                    lastBroadcast {
                        game {
                            displayName
                        }
                        startedAt
                        title
                    }
                    login
                    offlineImageURL
                    profileImageURL(width: $width)
                    profileURL
                    roles {
                        isAffiliate
                        isPartner
                        isStaff
                    }
                    stream {
                        averageFPS
                        bitrate
                        clipCount
                        createdAt
                        game {
                            displayName
                        }
                        id
                        title
                        type
                        viewersCount
                    }
                    updatedAt
                }
            }
        """
        )
        variables = {"userID": user_id, "login": username, "width": pfp_width}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["user"] is None:
            return None
        return User(**query_results["user"])


@gql_error_handler()
@async_cache(timedelta(hours=1))
async def chat_settings_for_bot(channel_id: str):
    """Returns authenticated user's relation to target channel"""
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query ($userID: ID!) {
                user(id: $userID) {
                    chatSettings {
                        blockLinks
                        chatDelayMs
                        followersOnlyDurationMinutes
                        isEmoteOnlyModeEnabled
                        isFastSubsModeEnabled
                        isSubscribersOnlyModeEnabled
                        isUniqueChatModeEnabled
                        requireVerifiedAccount
                        rules
                        slowModeDurationSeconds
                    }
                    self {
                        banStatus {
                            bannedUser {
                                displayName
                                id
                                login
                            }
                            createdAt
                            expiresAt
                            isPermanent
                            moderator {
                                displayName
                                id
                                login
                            }
                            reason
                        }
                        isModerator
                        isVIP
                    }
                }
            }
        """
        )
        variables = {"userID": channel_id}
        query_results = await session.execute(query, variable_values=variables)
        if query_results["user"] is None:
            return None
        return query_results
