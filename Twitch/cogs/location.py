from datetime import datetime, timedelta, UTC
from math import asin, cos, pi, sqrt
import os
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import google, openweather
from shared.database.twitch import locations
from shared.util.formatting import format_timedelta
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Location(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @commands.command(aliases=("loc",))
    async def location(self, ctx: commands.Context, action: str, *args: str):
        """
        Manage location for commands that use it; location is set to private by default; possible usages of the command:
        {prefix}location set <location>; {prefix}location delete; {prefix}location private; {prefix}location public
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        action = action.lower()
        match action:
            case "set":
                if len(args) == 0:
                    await self.bot.msg_q.reply(ctx, "Please provide a location to set your location to")
                    return
                location = await google.geocode(" ".join(args))
                if location is None:
                    await self.bot.msg_q.reply(ctx, "Location provided was not found")
                    return
                await locations.set_location(
                    self.bot.con_pool,
                    ctx.author.id,
                    location.geometry.location.latitude,
                    location.geometry.location.longitude,
                    location.formatted_address,
                )
                await self.bot.msg_q.reply(
                    ctx,
                    f"Location set to {location.formatted_address}",
                    [],
                    locations.delete,
                    self.bot.con_pool,
                    ctx.author.id,
                )

            case "delete":
                location = await locations.user_location(self.bot.con_pool, ctx.author.id)
                if location is None:
                    await self.bot.msg_q.reply(ctx, "You have not set your location yet")
                    return
                await locations.delete(self.bot.con_pool, ctx.author.id)
                await self.bot.msg_q.reply(
                    ctx,
                    "Location deleted",
                    [],
                    locations.set_location,
                    self.bot.con_pool,
                    ctx.author.id,
                    location.latitude,
                    location.longitude,
                    location.address,
                )

            case "private":
                location = await locations.user_location(self.bot.con_pool, ctx.author.id)
                if location is None:
                    await self.bot.msg_q.reply(ctx, "You have not set your location yet")
                    return
                success = await locations.set_location_private(self.bot.con_pool, ctx.author.id)
                if success:
                    await self.bot.msg_q.reply(
                        ctx,
                        "Location set to private",
                        [],
                        locations.set_location_public,
                        self.bot.con_pool,
                        ctx.author.id,
                    )
                else:
                    await self.bot.msg_q.reply(ctx, "Your location is already set to private")

            case "public":
                location = await locations.user_location(self.bot.con_pool, ctx.author.id)
                if location is None:
                    await self.bot.msg_q.reply(ctx, "You have not set your location yet")
                    return
                success = await locations.set_location_public(self.bot.con_pool, ctx.author.id)
                if success:
                    await self.bot.msg_q.reply(
                        ctx,
                        "Location set to public",
                        [],
                        locations.set_location_private,
                        self.bot.con_pool,
                        ctx.author.id,
                    )
                else:
                    await self.bot.msg_q.reply(ctx, "Your location is already set to public")

            case _:
                raise commands.MissingRequiredArgument

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def weather(self, ctx: commands.Context, *args: str):
        """
        Shows weather details of the given location; {prefix}weather <location>; leave location empty to use your set location;
        location can be set with {prefix}location set <location>
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if len(args) == 0:
            location = await locations.user_location(self.bot.con_pool, ctx.author.id)
            if location is None:
                await self.bot.msg_q.reply(ctx, "You have not set your location")
                return
            imperial = "USA" in location.address or "United States" in location.address
            address = "(location hidden)" if location.private else location.address
            cw = await openweather.current_weather(
                location.latitude, location.longitude, "imperial" if imperial else "metric"
            )
        else:
            location = await google.geocode(" ".join(args))
            if location is None:
                await self.bot.msg_q.reply(ctx, "Location provided was not found")
                return
            imperial = location.is_united_states()
            address = location.formatted_address
            cw = await openweather.current_weather(
                location.geometry.location.latitude,
                location.geometry.location.longitude,
                "imperial" if imperial else "metric",
            )

        features = []
        features.append(
            f"{cw.weather[0].description} {cw.get_weather_icon()} {cw.main.temp:.1f}°{'F' if imperial else 'C'}"
        )
        features.append(f"feels like {cw.main.feels_like:.1f}°{'F' if imperial else 'C'}")
        if cw.rain is not None:
            features.append(f"raining: {cw.rain:.1f} mm")
        if cw.snow is not None:
            features.append(f"snowing: {cw.snow:.1f} mm")
        features.append(f"cloud cover: {cw.clouds}%")
        features.append(f"humidity: {cw.main.humidity}%")
        features.append(f"wind speed: {cw.wind.speed:.1f} {'mi/h' if imperial else 'm/s'}")
        features.append(f"air pressure: {cw.main.pressure} hPa")
        air_quality = await google.air_quality(cw.coord.lat, cw.coord.lon)
        if air_quality is not None:
            features.append(f"{air_quality[1]} {air_quality[0].lower()}")
        else:
            features.append("❌ air quality not available")
        message = f"{address}: {', '.join(features)}"
        await self.bot.msg_q.send(ctx, message)

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def time(self, ctx: commands.Context, *args: str):
        """Shows the time in the given location; {prefix}time <location>; leave location empty to use your set location"""
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        if len(args) == 0:
            location = await locations.user_location(self.bot.con_pool, ctx.author.id)
            if location is None:
                await self.bot.msg_q.reply(ctx, "You have not set your location")
                return
            imperial = "USA" in location.address or "United States" in location.address
            address = "(location hidden)" if location.private else location.address
            cw = await openweather.current_weather(location.latitude, location.longitude)
        else:
            location = await google.geocode(" ".join(args))
            if location is None:
                await self.bot.msg_q.reply(ctx, "Location provided was not found")
                return
            imperial = location.is_united_states()
            address = location.formatted_address
            cw = await openweather.current_weather(
                location.geometry.location.latitude, location.geometry.location.longitude
            )

        current_time = datetime.now(UTC)
        user_time = current_time + timedelta(seconds=cw.timezone)
        timezone_offset = cw.timezone / 3600
        sign = "-" if timezone_offset < 0 else "+"
        if int(timezone_offset) == timezone_offset:
            offset = f"{sign}{abs(int(timezone_offset))}"
        else:
            offset = f"{sign}{abs(int(timezone_offset))}:30"
        if imperial:
            formatted_time = f"{user_time.strftime('%A, %Y-%m-%d, %I:%M:%S %p')} (UTC{offset})"
        else:
            formatted_time = f"{user_time.strftime('%A, %Y-%m-%d, %H:%M:%S')} (UTC{offset})"

        if current_time < cw.sys.sunrise:
            sun = f"sun rises in: {format_timedelta(current_time, cw.sys.sunrise)}"
        elif current_time < cw.sys.sunset:
            sun = f"sun sets in: {format_timedelta(current_time, cw.sys.sunset)}"
        else:
            sun = f"sun set {format_timedelta(cw.sys.sunset, current_time)} ago"

        await self.bot.msg_q.send(ctx, f"{address}: {formatted_time}, {sun}")

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command(aliases=("d", "dist"))
    async def distance(self, ctx: commands.Context, *, message: str):
        """
        Gives the geodesic distance between two locations; {prefix}distance <location1> | <location2>; {prefix}distance <location>
        to get the distance from your set location to the target location
        """
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.author.id is not None

        target_locations = message.split("|")
        if len(target_locations) > 2:
            await self.bot.msg_q.reply(ctx, "You can only give two locations at most")
            return
        elif len(target_locations) == 2:
            loc1 = await google.geocode(target_locations[0].strip())
            if loc1 is None:
                await self.bot.msg_q.reply(ctx, "The first location doesn't exist")
                return
            loc2 = await google.geocode(target_locations[1].strip())
            if loc2 is None:
                await self.bot.msg_q.reply(ctx, "The second location doesn't exist")
                return
            address1 = loc1.formatted_address
            address2 = loc2.formatted_address
            lat1 = loc1.geometry.location.latitude
            lon1 = loc1.geometry.location.longitude
            lat2 = loc2.geometry.location.latitude
            lon2 = loc2.geometry.location.longitude
        else:
            loc1 = await locations.user_location(self.bot.con_pool, ctx.author.id)
            if loc1 is None:
                await self.bot.msg_q.reply(
                    ctx, "You have not set your location. Set your location or provide two locations"
                )
                return
            loc2 = await google.geocode(target_locations[0].strip())
            if loc2 is None:
                await self.bot.msg_q.reply(ctx, "The given location doesn't exist")
                return

            address1 = "(location hidden)" if loc1.private else loc1.address
            address2 = loc2.formatted_address
            lat1 = loc1.latitude
            lon1 = loc1.longitude
            lat2 = loc2.geometry.location.latitude
            lon2 = loc2.geometry.location.longitude

        def distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            radius = 6371
            radians = pi / 180
            haversine = (
                0.5
                - cos((lat2 - lat1) * radians) / 2
                + cos(lat1 * radians) * cos(lat2 * radians) * (1 - cos((lon2 - lon1) * radians)) / 2
            )
            return 2 * radius * asin(sqrt(haversine))

        d = distance(lat1, lon1, lat2, lon2)
        d_in_miles = d / 1.609
        await self.bot.msg_q.send(
            ctx, f"The distance between {address1} and {address2} is {d:.0f} km ({d_in_miles:.0f} mi)"
        )


def prepare(bot: "Bot"):
    if "OPEN_WEATHER_MAP_KEY" not in os.environ or os.environ["OPEN_WEATHER_MAP_KEY"] == "":
        logger.warning("Open weather api key is not set, location commands are disabled")
        return
    if "GOOGLE_API_KEY" not in os.environ or os.environ["GOOGLE_API_KEY"] == "":
        logger.warning("Google api key is not set, location commands are disabled")
        return
    bot.add_cog(Location(bot))
