import os
from typing import Literal

import aiohttp

from .models import SearchListReponse, ChannelListResponse, PlaylistItemListReponse, VideoListResponse
from ..exceptions import aiohttp_error_handler


__all__ = ("search_by_keywords", "get_channel_info", "get_playlist_items", "get_video_by_id")


ENDPOINT = "https://www.googleapis.com/youtube/v3"
TIMEOUT = aiohttp.ClientTimeout(total=30)


@aiohttp_error_handler
async def search_by_keywords(
    q: str,
    *,
    limit: int = 5,
    channel_id: str | None = None,
    search_type: list[Literal["channel", "playlist", "video"]] | Literal["channel", "playlist", "video"] = [
        "channel",
        "playlist",
        "video",
    ],
    order: Literal["date", "rating", "relevance", "title", "videoCount", "viewCount"] = "relevance",
    video_duration: Literal["any", "long", "medium", "short"] = "any",
    event_type: Literal["completed", "live", "upcoming"] | None = None,
    page_token: str | None = None,
) -> SearchListReponse:
    limit = max(min(limit, 50), 0)
    args = {"key": os.environ["GOOGLE_API_KEY"], "q": q, "maxResults": limit, "order": order, "part": "snippet"}
    if channel_id is not None:
        args["channelId"] = channel_id

    if isinstance(search_type, list):
        args["type"] = ",".join(search_type)
    else:
        args["type"] = search_type

    if len(search_type) == 1 and "video" in search_type:
        args["videoDuration"] = video_duration
        if event_type is not None:
            args["eventType"] = event_type

    if page_token is not None:
        args["pageToken"] = page_token

    url = f"{ENDPOINT}/search"
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(url, params=args, raise_for_status=True) as resp:
            response = await resp.json()
            return SearchListReponse(**response)


@aiohttp_error_handler
async def get_channel_info(
    channel_id: str | None = None,
    *,
    for_username: str | None = None,
    for_handle: str | None = None,
    hl: str = "en_US",
) -> ChannelListResponse:
    assert channel_id or for_username or for_handle

    url = f"{ENDPOINT}/channels"
    args = {"key": os.environ["GOOGLE_API_KEY"], "part": "contentDetails,snippet,statistics", "hl": hl}
    if channel_id is not None:
        args["id"] = channel_id
    elif for_username is not None:
        args["forUsername"] = for_username
    elif for_handle is not None:
        args["forHandle"] = for_handle

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(url, params=args, raise_for_status=True) as resp:
            response = await resp.json()
            return ChannelListResponse(**response)


@aiohttp_error_handler
async def get_playlist_items(
    playlist_id: str,
    *,
    limit: int = 5,
) -> PlaylistItemListReponse:
    limit = min(limit, 50)
    url = f"{ENDPOINT}/playlistItems"
    args = {
        "key": os.environ["GOOGLE_API_KEY"],
        "part": "contentDetails,snippet,id",
        "playlistId": playlist_id,
        "maxResults": limit,
    }
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(url, params=args, raise_for_status=True) as resp:
            response = await resp.json()
            return PlaylistItemListReponse(**response)


@aiohttp_error_handler
async def get_video_by_id(video_id: str, *, hl: str = "en_US") -> VideoListResponse:
    url = f"{ENDPOINT}/videos"
    args = {
        "key": os.environ["GOOGLE_API_KEY"],
        "part": "contentDetails,snippet,statistics,id",
        "id": video_id,
        "hl": hl,
    }
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.get(url, params=args, raise_for_status=True) as resp:
            response = await resp.json()
            return VideoListResponse(**response)
