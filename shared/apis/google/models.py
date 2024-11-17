from typing import Literal

from pydantic import BaseModel, Field


__all__ = ("Geolocation", "Translation")


class AddressComponent(BaseModel):
    long_name: str
    short_name: str
    types: list[str]


class Coords(BaseModel):
    latitude: float = Field(alias="lat")
    longitude: float = Field(alias="lng")


class Bounds(BaseModel):
    northeast: Coords
    southwest: Coords


class Geometry(BaseModel):
    bounds: Bounds | None = None
    location: Coords
    location_type: Literal["ROOFTOP", "RANGE_INTERPOLATED", "GEOMETRIC_CENTER", "APPROXIMATE"]
    viewport: Bounds


class Geolocation(BaseModel):
    address_components: list[AddressComponent]
    formatted_address: str
    geometry: Geometry
    place_id: str
    types: list[str]

    def is_united_states(self) -> bool:
        for component in self.address_components:
            if component.long_name == "United States":
                return True
        return False


class Translation(BaseModel):
    translated_text: str = Field(alias="translatedText")
    detected_source_language: str | None = Field(None, alias="detectedSourceLanguage")
