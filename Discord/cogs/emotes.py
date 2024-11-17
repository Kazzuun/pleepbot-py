import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from shared.apis import seventv


# TODO: now that gif and png are included in the files, check the size that way
class Emotes(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def permissions(interaction: discord.Interaction):  # type: ignore
        if interaction.guild is None:
            await interaction.response.send_message("This command doesn't work in dms")
            return False

        if not interaction.app_permissions.manage_emojis:
            await interaction.response.send_message("The bot doesn't have permission to manage emotes")
            return False

        if not interaction.permissions.manage_emojis:
            await interaction.response.send_message("You don't have permissions to manage emotes")
            return False

        return True

    @app_commands.check(permissions)
    @app_commands.command(description="add an existing discord emote from another server to this server")
    @app_commands.describe(emote="a valid discord emote")
    @app_commands.describe(alias="alias to name the emote to, otherwise using the original name")
    async def yoink(self, interaction: discord.Interaction, emote: str, alias: str | None) -> None:
        assert interaction.guild is not None

        if emote.startswith("<:") or emote.startswith("<a:"):
            emote_name = emote.split(":")[1] if alias is None else alias
            emote_id = int(emote.split(":")[-1][:-1])
            extension = "gif" if emote.startswith("<a:") else "png"
        else:
            await interaction.response.send_message("Invalid emote format")
            return

        if emote_id in [emoji.id for emoji in interaction.guild.emojis]:
            await interaction.response.send_message("This emote is already in this server")
            return

        maximum_size = 262144
        async with aiohttp.ClientSession() as session:
            for res in [96, 48]:
                host_url = f"https://cdn.discordapp.com/emojis/{emote_id}.{extension}?size={res}&quality=lossless"
                async with session.get(host_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to fetch image: {response.status}")
                    image_bytes = await response.read()
                    if len(image_bytes) < maximum_size:
                        break
            else:
                await interaction.response.send_message("The image of the emote is too big and cannot be added")
                return

        try:
            await interaction.guild.create_custom_emoji(name=emote_name, image=image_bytes)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to add the emote: {e}")
            return

        added_emoji = [emoji for emoji in interaction.guild.emojis if emoji.name == emote_name]
        await interaction.response.send_message(f"Added emote {added_emoji[0]} successfully")

    @app_commands.check(permissions)
    @app_commands.command(description="add 7tv emote to server")
    @app_commands.describe(emote="link to the emote or its id")
    @app_commands.describe(alias="alias to name the emote to, otherwise using the original name")
    async def add(self, interaction: discord.Interaction, emote: str, alias: str | None) -> None:
        assert interaction.guild is not None

        if "7tv.app/emotes/" in emote and seventv.is_valid_id(emote.split("7tv.app/emotes/")[-1]):
            emote_id = emote.split("/")[-1]
        elif seventv.is_valid_id(emote):
            emote_id = emote
        else:
            await interaction.response.send_message("You need to provide the link or the id of the emote")
            return

        emote_from_id = await seventv.emote_from_id(emote_id)
        emote_name = emote_from_id.name if alias is None else alias
        animated = emote_from_id.animated
        host = emote_from_id.host.url
        extension = "gif" if animated else "png"

        maximum_size = 262144
        async with aiohttp.ClientSession() as session:
            for i in range(4, 0, -1):
                host_url = f"{host}/{i}x.{extension}"
                async with session.get(host_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to fetch image: {response.status}")
                    image_bytes = await response.read()
                    if len(image_bytes) < maximum_size:
                        break
            else:
                await interaction.response.send_message("The image of the emote is too big and cannot be added")
                return

        try:
            await interaction.guild.create_custom_emoji(name=emote_name, image=image_bytes)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to add the emote: {e}")
            return

        added_emoji = [emoji for emoji in interaction.guild.emojis if emoji.name == emote_name]
        await interaction.response.send_message(f"Added emote {added_emoji[0]} successfully")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Emotes(bot))
