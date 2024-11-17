import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from shared import database
from shared.apis.exceptions import SendableAPIRequestError


# get help from this: https://github.com/kkrypt0nn/Python-Discord-Bot-Template/tree/main


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(os.environ["GLOBAL_PREFIX"]),
            case_insensitive=True,
            strip_after_prefix=True,
            intents=intents,
            # TODO: experiment help command
            # help_command=None
        )

    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    async def on_message(self, message: discord.Message):
        if message.author == self.user or message.author.bot:
            return
        await self.process_commands(message)

    async def setup_hook(self) -> None:
        self.con_pool = await database.init_pool(self.loop)
        for filename in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
        await self.tree.sync()

    async def on_command_error(self, context: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await context.send("Slow down a bit and try again later")
        elif isinstance(error, commands.MissingPermissions):
            await context.send("You don't have permissions to do that")
        elif isinstance(error, commands.BotMissingPermissions):
            await context.send("The bot doesn't have permissions to do that")
        elif isinstance(error, commands.MissingRequiredArgument):
            await context.send("Some arguments to the command are missing")
        elif isinstance(error, SendableAPIRequestError):
            await context.send(error.message)
        elif (
            isinstance(error, commands.CheckFailure)
            or isinstance(error, app_commands.CheckFailure)
            or isinstance(error, commands.CommandNotFound)
        ):
            pass
        else:
            await context.send("An unexpected error occured")
            await super().on_command_error(context, error)


if __name__ == "__main__":
    load_dotenv()
    bot = Bot()
    bot.run(token=os.environ["DISCORD_TOKEN"])
