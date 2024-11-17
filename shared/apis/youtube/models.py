from datetime import datetime
import html
from typing import Literal, Self

import isodate
from pydantic import BaseModel, Field, model_validator, field_validator


__all__ = ("SearchListReponse", "ChannelListResponse", "PlaylistItemListReponse", "VideoListResponse")


class Thumbnail(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None


class Thumbnails(BaseModel):
    default: Thumbnail
    medium: Thumbnail
    high: Thumbnail
    standard: Thumbnail | None = None
    maxres: Thumbnail | None = None


class Localized(BaseModel):
    title: str
    description: str | None = None

    @field_validator("description", mode="before")
    @classmethod
    def nullify_empty(cls, description: str) -> str | None:
        if not description:
            return None
        return description


class PageInfo(BaseModel):
    total_results: int = Field(alias="totalResults")
    results_per_page: int = Field(alias="resultsPerPage")


class SearchResultId(BaseModel):
    kind: Literal["youtube#video", "youtube#channel", "youtube#playlist"]
    video_id: str | None = Field(None, alias="videoId")
    channel_id: str | None = Field(None, alias="channelId")
    playlist_id: str | None = Field(None, alias="playlistId")

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.kind == "youtube#video":
            assert type(self.video_id) == str
            assert self.channel_id is None
            assert self.playlist_id is None
        elif self.kind == "youtube#channel":
            assert self.video_id is None
            assert type(self.channel_id) == str
            assert self.playlist_id is None
        elif self.kind == "youtube#playlist":
            assert self.video_id is None
            assert self.channel_id is None
            assert type(self.playlist_id) == str
        return self


class SearchResultSnippet(BaseModel):
    published_at: datetime = Field(alias="publishedAt")
    channel_id: str = Field(alias="channelId")
    title: str
    description: str | None
    thumbnails: Thumbnails
    channel_title: str = Field(alias="channelTitle")
    live_broadcast_content: Literal["upcoming", "live", "none"] = Field(alias="liveBroadcastContent")

    @field_validator("title", mode="before")
    @classmethod
    def unescape_title(cls, title: str) -> str:
        return html.unescape(title)

    @field_validator("description", mode="before")
    @classmethod
    def nullify_empty(cls, description: str) -> str | None:
        if not description:
            return None
        return description


class SearchResult(BaseModel):
    kind: Literal["youtube#searchResult"]
    etag: str
    id: SearchResultId
    snippet: SearchResultSnippet


class SearchListReponse(BaseModel):
    kind: Literal["youtube#searchListResponse"]
    etag: str
    next_page_token: str | None = Field(None, alias="nextPageToken")
    prev_page_token: str | None = Field(None, alias="prevPageToken")
    region_code: str = Field(alias="regionCode")
    page_info: PageInfo = Field(alias="pageInfo")
    items: list[SearchResult] = Field(default_factory=list)


class ChannelSnippet(BaseModel):
    title: str
    description: str | None
    custom_url: str = Field(alias="customUrl")
    created_at: datetime = Field(alias="publishedAt")
    thumbnails: Thumbnails
    default_language: str | None = Field(None, alias="defaultLanguage")
    localized: Localized
    country: str | None = None

    @field_validator("description", mode="before")
    @classmethod
    def nullify_empty(cls, description: str) -> str | None:
        if not description:
            return None
        return description


class RelatedPlaylists(BaseModel):
    likes: str | None
    uploads: str

    @field_validator("likes", mode="before")
    @classmethod
    def nullify_empty(cls, likes: str) -> str | None:
        if not likes:
            return None
        return likes


class ChannelContentDetails(BaseModel):
    related_playlists: RelatedPlaylists = Field(alias="relatedPlaylists")


class ChannelStatistics(BaseModel):
    view_count: int = Field(alias="viewCount")
    subscriber_count: int = Field(alias="subscriberCount")
    hidden_subscriber_count: bool = Field(alias="hiddenSubscriberCount")
    video_count: int = Field(alias="videoCount")


class Channel(BaseModel):
    kind: Literal["youtube#channel"]
    etag: str
    id: str
    snippet: ChannelSnippet
    content_details: ChannelContentDetails = Field(alias="contentDetails")
    statistics: ChannelStatistics


class ChannelListResponse(BaseModel):
    kind: Literal["youtube#channelListResponse"]
    etag: str
    page_info: PageInfo = Field(alias="pageInfo")
    items: list[Channel] = Field(default_factory=list)


class PlaylistItemResourceId(BaseModel):
    kind: str
    video_id: str = Field(alias="videoId")


class PlaylistItemSnippet(BaseModel):
    published_at: datetime = Field(alias="publishedAt")
    channel_id: str = Field(alias="channelId")
    title: str
    description: str | None
    thumbnails: Thumbnails
    channel_title: str = Field(alias="channelTitle")
    video_owner_channel_title: str = Field(alias="videoOwnerChannelTitle")
    video_owner_channel_id: str = Field(alias="videoOwnerChannelId")
    playlist_id: str = Field(alias="playlistId")
    position: int
    resource_id: PlaylistItemResourceId = Field(alias="resourceId")

    @field_validator("description", mode="before")
    @classmethod
    def nullify_empty(cls, description: str) -> str | None:
        if not description:
            return None
        return description


class PlaylistItemContentDetails(BaseModel):
    video_id: str = Field(alias="videoId")
    note: str | None = None
    video_published_at: datetime = Field(alias="videoPublishedAt")


class PlaylistItem(BaseModel):
    kind: Literal["youtube#playlistItem"]
    etag: str
    id: str
    snippet: PlaylistItemSnippet
    content_details: PlaylistItemContentDetails = Field(alias="contentDetails")


class PlaylistItemListReponse(BaseModel):
    kind: Literal["youtube#playlistItemListResponse"]
    etag: str
    page_info: PageInfo = Field(alias="pageInfo")
    items: list[PlaylistItem] = Field(default_factory=list)


class VideoSnippet(BaseModel):
    published_at: datetime = Field(alias="publishedAt")
    channel_id: str = Field(alias="channelId")
    title: str
    description: str | None
    thumbnails: Thumbnails
    channel_title: str = Field(alias="channelTitle")
    tags: list[str] = Field(default_factory=list)
    category_id: str = Field(alias="categoryId")
    live_broadcast_content: Literal["upcoming", "live", "none"] = Field(alias="liveBroadcastContent")
    default_language: str | None = Field(None, alias="defaultLanguage")
    localized: Localized
    default_audio_language: str | None = Field(None, alias="defaultAudioLanguage")

    @field_validator("description", mode="before")
    @classmethod
    def nullify_empty(cls, description: str) -> str | None:
        if not description:
            return None
        return description


class VideoContentDetails(BaseModel):
    duration: int
    dimension: Literal["2d", "3d"]
    definition: Literal["hd", "sd"]
    caption: bool
    licensed_content: bool = Field(alias="licensedContent")

    @field_validator("duration", mode="before")
    @classmethod
    def parse_duration(cls, duration: str) -> int:
        return int(isodate.parse_duration(duration).total_seconds())

    @field_validator("caption", mode="before")
    @classmethod
    def caption_to_boolean(cls, caption: Literal["false", "true"]) -> bool:
        if caption == "true":
            return True
        else:
            return False


class VideoStatistics(BaseModel):
    view_count: int = Field(alias="viewCount")
    like_count: int = Field(alias="likeCount")
    comment_count: int = Field(alias="commentCount")


class Video(BaseModel):
    kind: Literal["youtube#video"]
    etag: str
    id: str
    snippet: VideoSnippet
    content_details: VideoContentDetails = Field(alias="contentDetails")
    statistics: VideoStatistics


class VideoListResponse(BaseModel):
    kind: Literal["youtube#videoListResponse"]
    etag: str
    page_info: PageInfo = Field(alias="pageInfo")
    items: list[Video] = Field(default_factory=list)
