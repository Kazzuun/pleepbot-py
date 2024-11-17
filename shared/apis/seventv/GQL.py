from datetime import timedelta
import os
from typing import Literal

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError

from .models import (
    EmoteSearchResult,
    EmoteData,
    UserEditorWithConnections,
    CosmeticPaint,
    UserCosmetic,
    Role,
    EditorPermissions,
)
from .REST import emote_from_id
from ..cache import async_cache
from ..exceptions import gql_error_handler, SendableAPIRequestError


__all__ = (
    "editors",
    "editor_of",
    "owned_emotes",
    "paint",
    "user_cosmetics",
    "roles",
    "create_emote_set",
    "update_emote_set",
    "activate_emote_set",
    "search_emote_by_name",
    "add_emote",
    "remove_emote",
    "rename_emote",
    "add_editor",
    "remove_editor",
)


ENDPOINT = "https://7tv.io/v3/gql"
HEADERS = {
    "Authorization": f"Bearer {os.environ['SEVENTV_TOKEN']}",
    "Content-Type": "application/json",
}
TIMEOUT = 7


@gql_error_handler()
@async_cache(timedelta(hours=6))
async def editors(seventv_id: str) -> list[UserEditorWithConnections]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query GetCurrentUser ($id: ObjectID!) {
                user (id: $id) {
                    editors {
                        id
                        user {
                            id
                            username
                            connections {
                                id
                                platform
                                username
                                display_name
                                linked_at
                                emote_capacity
                                emote_set_id
                            }
                        }
                        permissions
                        visible
                        added_at
                    }
                }
            }
        """
        )
        variables = {"id": seventv_id}

        query_results = await session.execute(query, variable_values=variables)
        editors = [UserEditorWithConnections(**editor) for editor in query_results["user"]["editors"]]
        return editors


@gql_error_handler()
@async_cache(timedelta(hours=6))
async def editor_of(seventv_id: str) -> list[UserEditorWithConnections]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query GetCurrentUser ($id: ObjectID!) {
                user (id: $id) {
                    editor_of {
                        id
                        user {
                            id
                            username
                            connections {
                                id
                                platform
                                username
                                display_name
                                linked_at
                                emote_capacity
                                emote_set_id
                            }
                        }
                        permissions
                        visible
                        added_at
                    }
                }
            }
        """
        )
        variables = {"id": seventv_id}

        query_results = await session.execute(query, variable_values=variables)
        editors_of = [UserEditorWithConnections(**editor) for editor in query_results["user"]["editor_of"]]
        return editors_of


@gql_error_handler()
@async_cache(timedelta(hours=6))
async def owned_emotes(seventv_id: str) -> list[EmoteData]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query GetCurrentUser ($id: ObjectID!) {
                user (id: $id) {
                    owned_emotes {
                        id
                        name
                        flags
                        lifecycle
                        state
                        listed
                        animated
                        owner {
                            id
                            username
                            display_name
                            avatar_url
                            roles
                            style {
                                color
                                paint_id
                                badge_id
                            }
                        }
                        host {
                            url
                            files {
                                name
                                width
                                height
                                frame_count
                                size
                                format
                            }
                        }
                    }
                }
            }
        """
        )
        variables = {"id": seventv_id}

        query_results = await session.execute(query, variable_values=variables)
        owned_emotes = [EmoteData(**emote) for emote in query_results["user"]["owned_emotes"]]
        return owned_emotes


@gql_error_handler()
@async_cache(timedelta(hours=6))
async def paint(paint_id: str) -> CosmeticPaint:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query GetCosmestics($list: [ObjectID!]) {
                cosmetics(list: $list) {
                    paints {
                        id
                        name
                        image_url
                    }
                }
            }
        """
        )
        variables = {"list": [paint_id]}

        query_results = await session.execute(query, variable_values=variables)
        return CosmeticPaint(**query_results["cosmetics"]["paints"][0])


@gql_error_handler()
@async_cache(timedelta(hours=6))
async def user_cosmetics(user_id: str) -> list[UserCosmetic]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query GetUserCosmetics($id: ObjectID!) {
                user(id: $id) {
                    cosmetics {
                        id
                        kind
                        selected
                    }
                }
            }
        """
        )
        variables = {"id": user_id}

        query_results = await session.execute(query, variable_values=variables)
        return [UserCosmetic(**cosmetic) for cosmetic in query_results["user"]["cosmetics"]]


@gql_error_handler()
async def roles(role_ids: list[str]) -> list[Role]:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query AppState {
                roles: roles {
                    id
                    name
                    allowed
                    denied
                    position
                    color
                    invisible
                }
            }
        """
        )
        query_results = await session.execute(query)
        roles = [Role(**role) for role in query_results["roles"]]
        return [role for role in roles if role.id in role_ids]


@gql_error_handler(fetch=False)
async def search_emote_by_name(
    emote_query: str,
    *,
    limit: int = 20,
    page: int = 1,
    animated: bool = False,
    case_sensitive: bool = False,
    exact_match: bool = False,
    ignore_tags: bool = False,
    trending: bool = False,
    zero_width: bool = False,
) -> EmoteSearchResult:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            query SearchEmotes($query: String!, $page: Int, $limit: Int, $filter: EmoteSearchFilter) {
                emotes(query: $query, page: $page, limit: $limit, filter: $filter) {
                    count
                    items {
                        id
                        name
                        state
                        trending
                    }
                }
            }
        """
        )
        variables = {
            "query": emote_query,
            "limit": limit,
            "page": page,
            "filter": {
                "animated": animated,
                "case_sensitive": case_sensitive,
                "category": "TRENDING_DAY" if trending else "TOP",
                "exact_match": exact_match,
                "ignore_tags": ignore_tags,
                "zero_width": zero_width,
            },
        }
        query_results = await session.execute(query, variable_values=variables)
        search_result = EmoteSearchResult(**query_results["emotes"])
        return search_result


@gql_error_handler(fetch=False)
async def create_emote_set(name: str, user_id: str) -> str:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            mutation CreateEmoteSet($user_id: ObjectID!, $data: CreateEmoteSetInput!) {
                createEmoteSet(user_id: $user_id, data: $data) {
                    id
                    name
                    capacity
                    owner {
                        id
                        display_name
                        style {
                            color
                        }
                        avatar_url
                    }
                    emotes {
                        id
                        name
                    }
                }
            }
        """
        )
        variables = {"data": {"name": name}, "user_id": user_id}
        query_results = await session.execute(query, variable_values=variables)
        return query_results["createEmoteSet"]["id"]


@gql_error_handler(fetch=False)
async def update_emote_set(name: str, capacity: int, emote_set_id: str) -> None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            mutation UpdateEmoteSet($id: ObjectID!, $data: UpdateEmoteSetInput!) {
                emoteSet(id: $id) {
                    update(data: $data) {
                        id,
                        name
                    }
                }
            }
        """
        )
        variables = {
            "data": {"name": name, "capacity": capacity, "origins": None},
            "id": emote_set_id,
        }
        await session.execute(query, variable_values=variables)


@gql_error_handler(fetch=False)
async def activate_emote_set(conn_id: str, emote_set_id: str, user_id: str) -> None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            mutation UpdateUserConnection($id: ObjectID!, $conn_id: String!, $d: UserConnectionUpdate!) {
                user(id: $id) {
                    connections(id: $conn_id, data: $d) {
                        id
                        platform
                        display_name
                        emote_set_id
                    }
                }
            }
        """
        )
        variables = {
            "conn_id": conn_id,
            "d": {"emote_set_id": emote_set_id},
            "id": user_id,
        }
        await session.execute(query, variable_values=variables)


async def _modify_emoteset(
    emote_set_id: str,
    action: Literal["ADD", "REMOVE", "UPDATE"],
    emote_id: str,
    alias: str | None = None,
) -> None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            mutation ChangeEmoteInSet($id: ObjectID! $action: ListItemAction! $emote_id: ObjectID!, $name: String) {
                emoteSet(id: $id) {
                    emotes(id: $emote_id action: $action, name: $name) {
                        id
                        name
                    }
                }
            }
        """
        )
        variables = {
            "id": emote_set_id,
            "action": action,
            "emote_id": emote_id,
            "name": alias,
        }
        try:
            await session.execute(query, variable_values=variables)
        except TransportQueryError as tqe:
            if tqe.errors is None:
                message = "no message"
            else:
                message = tqe.errors[0]["message"].lower()

            if message.split()[0].isdigit():
                message = " ".join(message.split()[1:])
            if action == "ADD" and alias:
                emote_name = alias
            else:
                emote_info = await emote_from_id(emote_id)
                emote_name = emote_info.name

            raise SendableAPIRequestError(f"Failed to {action.lower()} emote {emote_name} ({message})")


@gql_error_handler(fetch=False)
async def add_emote(emote_set_id: str, emote_id: str, alias: str | None = None) -> None:
    await _modify_emoteset(emote_set_id, "ADD", emote_id, alias)


@gql_error_handler(fetch=False)
async def remove_emote(emote_set_id: str, emote_id: str) -> None:
    await _modify_emoteset(emote_set_id, "REMOVE", emote_id)


@gql_error_handler(fetch=False)
async def rename_emote(emote_set_id: str, emote_id: str, new_name: str) -> None:
    await _modify_emoteset(emote_set_id, "UPDATE", emote_id, new_name)


async def _modify_editors(id: str, editor_id: str, permissions: int) -> None:
    transport = AIOHTTPTransport(url=ENDPOINT, headers=HEADERS, timeout=TIMEOUT)
    async with Client(transport=transport) as session:
        query = gql(
            """
            mutation UpdateUserEditors($id: ObjectID!, $editor_id: ObjectID!, $d: UserEditorUpdate!) {
                user(id: $id) {
                    editors(editor_id: $editor_id, data: $d) {
                        id
                    }
                }
            }
        """
        )
        variables = {
            "d": {"permissions": permissions},
            "id": id,
            "editor_id": editor_id,
        }
        await session.execute(query, variable_values=variables)


@gql_error_handler(fetch=False)
async def add_editor(id: str, editor_id: str, permissions: EditorPermissions | None = None) -> None:
    if permissions is None:
        permissions = EditorPermissions.from_permissions(modify_emote_set=True, manage_emote_sets=True)
    await _modify_editors(id, editor_id, permissions.value)


@gql_error_handler(fetch=False)
async def remove_editor(id: str, editor_id: str) -> None:
    await _modify_editors(id, editor_id, 0)
