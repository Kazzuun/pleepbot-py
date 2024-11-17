from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from shared.apis import dadjokes, themealdb, urban_dictionary
from shared.database.twitch import misc

if TYPE_CHECKING:
    from Discord.discordbot import Bot

# TODO: catpic/dogpic, catfact/dogfact

class Basic(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @commands.command()
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send("pong")

    @commands.command(aliases=("cookie", "🍪", "🥠"))
    async def fortune(self, ctx: commands.Context):
        """Shows a random fortune"""
        fort = await misc.random_fortune(self.bot.con_pool)
        if fort is None:
            await ctx.send("Ask the owner of the bot to add fortunes")
            return
        await ctx.send(fort)

    @commands.command(aliases=("joke",))
    async def dadjoke(self, ctx: commands.Context):
        """Tells a random dadjoke"""
        dadjoke = await dadjokes.random_dadjoke()
        await ctx.send(dadjoke.joke)

    @commands.command(aliases=("dict", "definition", "def", "urban"))
    async def dictionary(self, ctx: commands.Context, *args: str):
        """Fetches the definition to the given term from urban dictionary; {prefix}dictionary <term> <optional index>"""
        if len(args) == 0:
            await ctx.send("Please provide a term to search")
            return

        if len(args) == 1:
            index = 1
            term = args[0]
        else:
            # Last argument is the index of the definition if it's a valid integer
            if args[-1].isnumeric():
                index = int(args[-1])
                term = " ".join(args[:-1])
            else:
                index = 1
                term = " ".join(args)

        definitions = await urban_dictionary.fetch_definitions(term)
        if len(definitions) == 0:
            await ctx.send("No definitions found")
            return
        index = max(min(index, len(definitions)), 1)
        definition = definitions[index - 1]
        embed = discord.Embed(color=discord.Color.random(), title=definition.word, description=definition.definition)
        embed.set_footer(text=f"Written on: {definition.written_on.strftime('%Y-%m-%d')}")
        await ctx.send(embed=embed)

    @commands.command(aliases=("randomdef", "randef", "randict", "randdef", "randdict"))
    async def randomdict(self, ctx: commands.Context):
        """Fetches a random definition from urban dictionary"""
        definition = await urban_dictionary.random_definitions()
        embed = discord.Embed(color=discord.Color.random(), title=definition.word, description=definition.definition)
        embed.set_footer(text=f"Written on: {definition.written_on.strftime('%Y-%m-%d')}")
        await ctx.send(embed=embed)

    @commands.command(aliases=("food",))
    async def meal(self, ctx: commands.Context):
        """Gives a random meal"""
        meal = await themealdb.random_meal()
        embed = discord.Embed(color=discord.Color.random(), title=f"{meal.area} dish: {meal.meal}")
        ingredients = zip(meal.ingredients, meal.measures)
        embed.add_field(
            name="Ingredients", value="\n".join(f"{ing} ({mes})" for ing, mes in ingredients), inline=False
        )
        instructions = []
        instruction = ""
        for ins in meal.instructions.split("\n"):
            if len(instruction + ins) < 1024:
                instruction += "\n" + ins
            else:
                instructions.append(instruction)
                instruction = ins
        instructions.append(instruction)
        for i, instruction in enumerate(instructions):
            name = "Instructions" if i == 0 else ""
            embed.add_field(name=name, value=instruction, inline=False)
        embed.add_field(name="Youtube", value=meal.youtube)
        embed.set_image(url=meal.picture)
        await ctx.send(embed=embed)


async def setup(bot: "Bot") -> None:
    await bot.add_cog(Basic(bot))
