from pydantic import BaseModel


__all__ = ("Dadjoke",)


class Dadjoke(BaseModel):
    id: str
    joke: str
