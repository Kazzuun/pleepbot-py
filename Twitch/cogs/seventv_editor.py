import base64
import binascii
from difflib import SequenceMatcher
import json
import os
import time
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from shared.apis import seventv
from shared.database.twitch import channels
from Twitch.exceptions import ValidationError
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


# TODO: allow commands to add and remove multiple editors and emotes at once
# TODO: figure out how to add multiple emotes at once
# Added suggestion to yoink if no matching emote is found
class SevenTVEditor(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.bot.loop.run_until_complete(self.__ainit__())

    async def __ainit__(self) -> None:
        try:
            # Extract the 7tv user from the jwt token
            token_payload = json.loads(base64.b64decode(os.environ["SEVENTV_TOKEN"].split(".")[1] + "=="))
        except binascii.Error:
            logger.warning("Invalid 7tv token, make sure it is correct, 7tv editor commands are disabled")
            self.bot.remove_cog(self.name)
            return
        expiration_time = token_payload["exp"]
        if expiration_time < time.time():
            logger.warning("7tv token is expired, 7tv editor commands are disabled")
            self.bot.remove_cog(self.name)
            return
        seventv_user_id = token_payload["sub"]
        self.seventv_user_id = seventv_user_id
        user = await seventv.user_from_id(seventv_user_id)
        twitch_connection = user.connection_by_platform("TWITCH")
        if twitch_connection is not None:
            self.seventv_username = twitch_connection.username
        else:
            self.seventv_username = user.username

    async def cog_check(self, ctx: commands.Context) -> bool:
        assert isinstance(ctx.author, twitchio.Chatter)
        assert ctx.command is not None

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        user_info = await seventv.account_info(channel_id)
        if user_info is None:
            return False

        editors = await seventv.editors(user_info.user.id)

        # Find if any editor has a twitch connection matching the bot's id
        editors_matching_bot = [
            editor
            for editor in editors
            if len([con for con in editor.user.connections if con.id == str(self.bot.user_id)]) == 1
        ]
        bot_is_editor = len(editors_matching_bot) == 1 or self.seventv_username == ctx.channel.name
        if not bot_is_editor:
            if ctx.author.is_broadcaster:
                bot_user = await seventv.user_from_id(self.seventv_user_id)
                raise ValidationError(
                    f"Bot's account ({bot_user.username}) is not a 7tv editor of this channel, you can add it in https://7tv.app/users/{user_info.user.id}"
                )
            else:
                raise ValidationError("I am not a 7tv editor of this channel")

        # Find if any editor has a twitch connection matching the user's id
        editors_matching_user = [
            editor
            for editor in editors
            if len([con for con in editor.user.connections if con.id == ctx.author.id]) == 1
        ]
        sender_is_editor = len(editors_matching_user) == 1 or ctx.author.is_broadcaster
        if not sender_is_editor:
            raise ValidationError("You are not a 7tv editor of this channel")

        need_manage_editor = {"addeditor", "removeeditor"}
        need_manage_sets = {"copyset"}
        need_modify_emotes = {"add", "remove", "rename", "yoink", "copyset"}

        if self.seventv_username != ctx.channel.name:
            bot_permissions = editors_matching_bot[0].permissions
            if ctx.command.name in need_manage_editor and not bot_permissions.manage_editors:
                raise ValidationError("Bot doesn't have permission to manage editors")
            if ctx.command.name in need_manage_sets and not bot_permissions.manage_emote_sets:
                raise ValidationError("Bot doesn't have permission to manage sets")
            if ctx.command.name in need_modify_emotes and not bot_permissions.modify_emotes:
                raise ValidationError("Bot doesn't have permission to manage emotes")

        if not ctx.author.is_broadcaster:
            user_permissions = editors_matching_user[0].permissions
            if ctx.command.name in need_manage_editor and not user_permissions.manage_editors:
                raise ValidationError("You don't have permission to manage editors")
            if ctx.command.name in need_manage_sets and not user_permissions.manage_emote_sets:
                raise ValidationError("You don't have permission to manage sets")
            if ctx.command.name in need_modify_emotes and not user_permissions.modify_emotes:
                raise ValidationError("You don't have permission to manage emotes")

        return True

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command(aliases=("ae",))
    async def addeditor(self, ctx: commands.Context, target: twitchio.PartialUser):
        """(7tv editor only) Adds a 7tv editor with default permissions; {prefix}addeditor <target>"""
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        channel_account = await seventv.account_info(channel_id)
        if channel_account is None:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have a 7tv account")
            return

        user_info = await seventv.account_info(str(target.id))
        if user_info is None:
            await self.bot.msg_q.send(ctx, "Target user doesn't have a 7tv account")
            return

        await seventv.add_editor(channel_account.user.id, user_info.user.id)
        await self.bot.msg_q.send(
            ctx,
            f"Added {user_info.username} as editor",
            [user_info.username],
            seventv.remove_editor,
            channel_account.user.id,
            user_info.user.id,
        )

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command(aliases=("rmeditor", "rme"))
    async def removeeditor(self, ctx: commands.Context, target: twitchio.PartialUser):
        """(7tv editor only) Removes a 7tv editor; {prefix}removeeditor <target>"""
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        channel_account = await seventv.account_info(channel_id)
        if channel_account is None:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have a 7tv account")
            return

        user_info = await seventv.account_info(str(target.id))
        if user_info is None:
            await self.bot.msg_q.send(ctx, "Target user doesn't have a 7tv account")
            return

        await seventv.remove_editor(channel_account.user.id, user_info.user.id)
        await self.bot.msg_q.send(
            ctx,
            f"Removed {user_info.username} as editor",
            [user_info.username],
            seventv.add_editor,
            channel_account.user.id,
            user_info.user.id,
        )

    @commands.cooldown(rate=2, per=60, bucket=commands.Bucket.channel)
    @commands.command()
    async def copyset(self, ctx: commands.Context, target_set: str, *args):
        """
        (7tv editor only) Copies the entire emote set; {prefix}copyset <emote set id> to make a new emote set for the emotes;
        {prefix}copyset <emote set id> <target emote set id> to copy to an existing emote set in the current channel;
        emote set id can also be a user whose currently active emote set will be copied; -a to activate the new emote set
        """
        if seventv.is_valid_id(target_set):
            from_emote_set = await seventv.emote_set_from_id(target_set, force_cache=True)
        elif target_user := await self.bot.fetch_users(names=[target_set]):
            user_account = await seventv.account_info(str(target_user[0].id), force_cache=True)
            if user_account is None:
                await self.bot.msg_q.send(ctx, "Target user doesn't have a 7tv account")
                return
            from_emote_set = await seventv.emote_set_from_id(user_account.emote_set.id, force_cache=True)
        else:
            await self.bot.msg_q.send(ctx, "Please input a valid emote set id or target user")
            return

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        channel_account = await seventv.account_info(channel_id)
        if channel_account is None:
            await self.bot.msg_q.send(ctx, "The current channel doesn't have a 7tv account")
            return

        if len(args) > 0 and seventv.is_valid_id(args[0]):
            to_emote_set = await seventv.emote_set_from_id(args[0], force_cache=True)
            if to_emote_set.owner.id != channel_account.user.id:
                await self.bot.msg_q.send(ctx, "You are only allowed to copy to sets in the current channel")
                return
        else:
            set_name = f"{from_emote_set.owner.display_name}'s emotes"
            target_emote_set_id = await seventv.create_emote_set(set_name, channel_account.user.id)
            capacity = channel_account.emote_set.capacity
            try:
                await seventv.update_emote_set(set_name, capacity, target_emote_set_id)
            except:
                await seventv.update_emote_set(set_name, 600, target_emote_set_id)
            if "-a" in args:
                await seventv.activate_emote_set(channel_id, target_emote_set_id, channel_account.user.id)
            to_emote_set = await seventv.emote_set_from_id(target_emote_set_id, force_cache=True)

        def is_valid_emote(emote: seventv.EmoteSetEmote) -> bool:
            return (
                emote.id not in [emote.id for emote in to_emote_set.emotes]
                and emote.name not in [emote.name for emote in to_emote_set.emotes]
                and not emote.data.flags.private
            )

        valid_emotes = list(filter(is_valid_emote, from_emote_set.emotes))
        if len(valid_emotes) == 0:
            await self.bot.msg_q.send(ctx, "There are no emotes that can be copied")
            return
        await self.bot.msg_q.send(
            ctx, f"Copying {len(valid_emotes)} emotes from {from_emote_set.id} to {to_emote_set.id}"
        )

        for i, emote in enumerate(valid_emotes, 1):
            await seventv.add_emote(to_emote_set.id, emote.id, emote.name)
            if i % 100 == 0:
                await self.bot.msg_q.send(ctx, f"Copying progress: {i}/{len(valid_emotes)}")

        await self.bot.msg_q.send(ctx, "Emote set successfully copied")

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def add(self, ctx: commands.Context, emote: str, *args):
        """
        (7tv editor only) Adds the given 7tv emote to the channel; emote can be specified with its name,
        id or link; if a name is given, a search is done to find it (see "{prefix}help search" for more info);
        an alias can be given to the emote; {prefix}add <emote> <optional alias> <search filters>;
        -f to remove the conflicting emote before adding
        """
        alias = None
        if len(args) > 0 and not args[0].startswith("-"):
            alias = args[0]

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        user_info = await seventv.account_info(channel_id)
        if user_info is None:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have a 7tv account")
            return

        channel_emote_set = await seventv.emote_set_from_id(user_info.emote_set.id, force_cache=True)

        if "7tv.app/emotes/" in emote and seventv.is_valid_id(emote.split("7tv.app/emotes/")[-1]):
            emote_id = emote.split("/")[-1]
            emote_from_id = await seventv.emote_from_id(emote_id)
            emote_name = emote_from_id.name
        elif seventv.is_valid_id(emote):
            emote_id = emote
            emote_from_id = await seventv.emote_from_id(emote_id)
            emote_name = emote_from_id.name
        else:
            result = await seventv.search_emote_by_name(
                emote_query=emote,
                animated="-a" in args,
                case_sensitive="-c" in args,
                exact_match="-e" in args,
                ignore_tags="-i" in args,
                zero_width="-z" in args,
            )
            if result.count == 0:
                await self.bot.msg_q.send(ctx, "Emote not found")
                return
            if exact_match := [e for e in result.emotes if e.name == emote]:
                emote_result = exact_match[0]
            elif names_match := [e for e in result.emotes if e.name.lower() == emote.lower()]:
                emote_result = names_match[0]
            elif phrase_in := [e for e in result.emotes if emote.lower() in e.name.lower()]:
                emote_result = phrase_in[0]
            else:
                emote_result = result.emotes[0]
            emote_id = emote_result.id
            emote_name = emote_result.name

        alias = emote_name if alias is None else alias

        added = 1
        callback = seventv.remove_emote

        if "-f" in args:
            same_emote_name = channel_emote_set.emote_by_name(alias)
            if same_emote_name is not None:
                await seventv.remove_emote(channel_emote_set.id, same_emote_name.id)
                added -= 1

                async def undo(emote_set_id: str, emote_id: str):
                    await seventv.remove_emote(emote_set_id, emote_id)
                    await seventv.add_emote(emote_set_id, same_emote_name.id, same_emote_name.name)

                callback = undo

        await seventv.add_emote(channel_emote_set.id, emote_id, alias)
        await self.bot.msg_q.send(
            ctx,
            f"Added {alias} ({min(channel_emote_set.emote_count + added, channel_emote_set.capacity)}/{channel_emote_set.capacity})",
            [],
            callback,
            channel_emote_set.id,
            emote_id,
        )

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def remove(self, ctx: commands.Context, *emotes: str):
        """(7tv editor only) Removes the given emote from the channel; {prefix}remove <emote>"""
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        user_info = await seventv.account_info(channel_id)
        if user_info is None:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have a 7tv account")
            return

        channel_emotes = await seventv.emote_set_from_id(user_info.emote_set.id, force_cache=True)

        emote_count = channel_emotes.emote_count
        emote_capacity = channel_emotes.capacity

        to_be_removed = set(emotes)
        removed_emotes = []

        for emote in to_be_removed:
            removed_emote = channel_emotes.emote_by_name(emote)
            if removed_emote is not None:
                removed_emotes.append(removed_emote)

        if len(removed_emotes) == 0:
            await self.bot.msg_q.send(ctx, "No emotes with given names found")
            return

        for emote in removed_emotes:
            await seventv.remove_emote(channel_emotes.id, emote.id)

        async def undo_callback():
            for emote in removed_emotes:
                await seventv.add_emote(channel_emotes.id, emote.id, emote.name)

        await self.bot.msg_q.send(
            ctx,
            f"Removed {len(removed_emotes)} emotes: {', '.join([e.name for e in removed_emotes])} ({emote_count - len(removed_emotes)}/{emote_capacity})",
            [],
            undo_callback,
        )

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command(aliases=("alias",))
    async def rename(self, ctx: commands.Context, emote_name: str, *args):
        """
        (7tv editor only) Renames the given emote to a new name; {prefix}rename <emote> <new name>;
        -o to use the original name and -f to remove the conflicting emote before renaming
        """
        if len([arg for arg in args if arg != "-f"]) == 0:
            await self.bot.msg_q.send(ctx, "Please specify a new name")
            return

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        user_info = await seventv.account_info(channel_id)
        if user_info is None:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have a 7tv account")
            return

        target_emote = user_info.emote_set.emote_by_name(emote_name)
        if target_emote is None:
            channel_emotes = await seventv.emote_set_from_id(user_info.emote_set.id, force_cache=True)
            target_emote = channel_emotes.emote_by_name(emote_name)
            if target_emote is None:
                await self.bot.msg_q.send(ctx, "No emote with given name found")
                return

        if "-o" in args:
            new_name = target_emote.data.name
        else:
            new_name = args[0]

        if emote_name == new_name:
            await self.bot.msg_q.send(ctx, "New name cannot be the same as the current one")
            return

        callback = seventv.rename_emote

        if "-f" in args:
            same_emote_name = user_info.emote_set.emote_by_name(new_name)
            if same_emote_name is not None:
                await seventv.remove_emote(user_info.emote_set.id, same_emote_name.id)

                async def undo(emote_set_id: str, emote_id: str, old_name: str):
                    await seventv.rename_emote(emote_set_id, emote_id, old_name)
                    await seventv.add_emote(emote_set_id, same_emote_name.id)

                callback = undo

        await seventv.rename_emote(user_info.emote_set.id, target_emote.id, new_name)
        await self.bot.msg_q.send(
            ctx,
            f"Renamed {emote_name} to {new_name}",
            [],
            callback,
            user_info.emote_set.id,
            target_emote.id,
            emote_name,
        )

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command()
    async def yoink(
        self,
        ctx: commands.Context,
        target_channel: twitchio.PartialUser,
        emote_name: str,
        *args,
    ):
        """
        (7tv editor only) Yoinks an emote from the specified channel; an alias can be specified;
        {prefix}yoink <channel> <emote> <optional alias>; -o to use the original name and
        -f to remove the conflicting emote before adding
        """
        alias = None
        if len(args) > 0 and not args[0].startswith("-"):
            alias = args[0]

        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        channel_user_info = await seventv.account_info(channel_id)
        if channel_user_info is None:
            await self.bot.msg_q.send(ctx, "Current channel doesn't have a 7tv account")
            return

        target_user_info = await seventv.account_info(str(target_channel.id), force_cache=True)
        if target_user_info is None:
            await self.bot.msg_q.send(ctx, "Target channel doesn't have a 7tv account")
            return

        matched_emotes = [
            emote for emote in target_user_info.emote_set.emotes if emote.name.lower() == emote_name.lower()
        ]
        if len(matched_emotes) == 0:
            similar_emotes = sorted(
                [
                    (SequenceMatcher(None, emote_name.lower(), emote.name.lower()).ratio(), emote.name)
                    for emote in target_user_info.emote_set.emotes
                ],
                reverse=True,
            )
            if similar_emotes[0][0] > 0:
                await self.bot.msg_q.send(
                    ctx, f"No emote with given name found. Did you mean {similar_emotes[0][1]} ?"
                )
            else:
                await self.bot.msg_q.send(ctx, "No emote with given name found")
            return
        elif len(matched_emotes) > 1:
            emotes_matching_query = [emote for emote in matched_emotes if emote.name == emote_name]
            # If an emote doesn't have exactly the same name
            if len(emotes_matching_query) != 1:
                await self.bot.msg_q.send(
                    ctx,
                    f"Multiple emotes with the same name found: {' '.join([emote.name for emote in matched_emotes])}",
                )
                return
            else:
                matched_emotes = emotes_matching_query

        emote = matched_emotes[0]
        use_original_name = "-o" in args
        if use_original_name:
            alias = emote.data.name
        elif alias is None:
            # Use the name of the emote it has in the channel
            alias = emote.name

        channel_emote_set = await seventv.emote_set_from_id(channel_user_info.emote_set.id, force_cache=True)

        added = 1
        callback = seventv.remove_emote

        if "-f" in args:
            same_emote_name = channel_emote_set.emote_by_name(alias)
            if same_emote_name is not None:
                await seventv.remove_emote(channel_emote_set.id, same_emote_name.id)
                added -= 1

                async def undo(emote_set_id: str, emote_id: str):
                    await seventv.remove_emote(emote_set_id, emote_id)
                    await seventv.add_emote(emote_set_id, same_emote_name.id, same_emote_name.name)

                callback = undo

        await seventv.add_emote(channel_emote_set.id, emote.id, alias)
        await self.bot.msg_q.send(
            ctx,
            f"Added {alias} ({min(channel_emote_set.emote_count + added, channel_emote_set.capacity)}/{channel_emote_set.capacity})",
            [],
            callback,
            channel_emote_set.id,
            emote.id,
        )


def prepare(bot: "Bot"):
    if "SEVENTV_TOKEN" not in os.environ or os.environ["SEVENTV_TOKEN"] == "":
        logger.warning("7tv token is not set, 7tv editor commands are disabled")
        return
    bot.add_cog(SevenTVEditor(bot))
