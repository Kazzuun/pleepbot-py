from pydantic import BaseModel


__all__ = ("EmotePrefixSearch",)


class Emote(BaseModel):
    id: str
    token: str
    is_animated: bool


class EmotePrefixSearch(BaseModel):
    query: str
    page: int
    results_count: int
    results: list[Emote]
    has_next_page: bool
    error: bool
