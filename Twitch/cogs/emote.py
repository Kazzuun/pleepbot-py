import re
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import twitchtools
from Twitch.exceptions import ValidationError

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Emote(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot


    @commands.command()
    async def emotes(self, ctx: commands.Context, target: twitchio.User):
        """Sends a link to a page that shows all emotes of the channel"""
        message = f"https://emotes.raccatta.cc/twitch/{target.name.lower()}"
        await self.bot.msg_q.send(ctx, message)


    @commands.cooldown(rate=3, per=30, bucket=commands.Bucket.member)
    @commands.command()
    async def eprefix(self, ctx: commands.Context, prefix: str):
        """"""
        if not re.match(r"[a-z0-9]{1,9}", prefix):
            raise ValidationError("Prefix needs to consist of only lower case letters and nubers")

        page = 1
        while True:
            prefix_search = await twitchtools.emotes_by_prefix(prefix, page)
            # search for prefix
            for result in prefix_search.results:

                if re.match(rf"{prefix}[a-z].*", result.token):
                    continue

                if re.match(rf"{prefix}[0-9]{1,3}[A-Z].*", result.token):
                    continue

                # if found give the user info of the owner and return

            if not prefix_search.has_next_page:
                # say prefix not found
                return

            page += 1


def prepare(bot: "Bot"):
    return
    bot.add_cog(Emote(bot))
