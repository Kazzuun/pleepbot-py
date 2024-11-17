import discord
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool: # type: ignore
        return await self.bot.is_owner(ctx.author)

    @commands.command()
    async def sync(self, ctx: commands.Context) -> None:
        fmt = await self.bot.tree.sync()
        await ctx.send(f"Synced {len(fmt)} commands")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
