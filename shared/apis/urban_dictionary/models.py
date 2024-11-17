from datetime import datetime

from pydantic import BaseModel, field_validator


__all__ = ("Definition",)


class Definition(BaseModel):
    definition: str
    permalink: str
    thumbs_up: int
    author: str
    word: str
    defid: int
    written_on: datetime
    example: str
    thumbs_down: int

    @field_validator("definition", "example", mode="before")
    @classmethod
    def clean_brakets(cls, field: str) -> str:
        field = field.replace("[", "").replace("]", "")
        return field
