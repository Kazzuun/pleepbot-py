from datetime import datetime, UTC

from pydantic import BaseModel, Field, field_validator


__all__ = ("CurrentWeather",)


class Coord(BaseModel):
    lat: float
    lon: float


class Weather(BaseModel):
    id: int
    main: str
    description: str
    icon: str


class Main(BaseModel):
    temp: float  # °C / °F / °K
    feels_like: float  # °C / °F / °K
    temp_min: float  # °C / °F / °K
    temp_max: float  # °C / °F / °K
    humidity: int  # %
    pressure: int  # hPa
    sea_level: int  # hPa
    ground_level: int = Field(alias="grnd_level")  # hPa


class Wind(BaseModel):
    speed: float  # m/s / mi/h
    deg: int  # degrees
    gust: float | None = None  # m/s / mi/h


class Sys(BaseModel):
    sunrise: datetime
    sunset: datetime


class CurrentWeather(BaseModel):
    coord: Coord
    weather: list[Weather]
    main: Main
    visibility: int | None = None  # m
    wind: Wind
    clouds: int  # %
    rain: float | None = None  # mm
    snow: float | None = None  # mm
    dt: datetime
    sys: Sys
    timezone: int  # offset in seconds

    @field_validator("rain", "snow", mode="before")
    @classmethod
    def check_rain(cls, rain: dict) -> float | None:
        if "1h" in rain:
            return rain["1h"]
        return None

    @field_validator("clouds", mode="before")
    @classmethod
    def check_clouds(cls, clouds: dict) -> int:
        return clouds["all"]

    def get_weather_icon(self) -> str:
        icons = {
            2: "⛈️",  # Thunderstorm
            3: "🌧️",  # Drizzle
            5: "🌧️",  # Rain
            6: "🌨️",  # Snow
            701: "🌫️",  # Mist
            711: "🔥💨",  # Smoke
            721: "🌫️",  # Haze
            731: "🏜️💨",  # Dust or sand whirls
            741: "🌫️",  # Fog
            751: "🏜️💨",  # Sand
            761: "🏜️💨",  # Dust
            762: "🌋💨",  # Volcanic ash
            771: "🌬️",  # Squalls
            781: "🌪️",  # Tornado
            800: "☀️" if self.sys.sunrise < datetime.now(UTC) < self.sys.sunset else "🌙",  # Clear sky
            801: "🌤️",  # Few clouds (11-25%)
            802: "🌥️",  # Scattered clouds (25-50%)
            803: "☁️",  # Broken clouds (51-84%)
            804: "☁️",  # Overcast clouds (85-100%)
        }
        if self.weather[0].id // 100 in icons:
            return icons[self.weather[0].id // 100]
        elif self.weather[0].id in icons:
            return icons[self.weather[0].id]
        else:
            return ""
