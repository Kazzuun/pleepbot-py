from datetime import datetime, timedelta, UTC
import os
from typing import TYPE_CHECKING, Iterable

from google import genai
from google.genai import types, errors
from pydantic import BaseModel, Field, ValidationError
from twitchio.ext import commands

from shared.apis import seventv
from shared.database.twitch import channels, messages
from Twitch.logger import logger

if TYPE_CHECKING:
    from shared.database.twitch.messages import Message
    from Twitch.twitchbot import Bot


class Ai(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model = "gemini-2.0-flash-001"
        self.google_search_tool = types.Tool(google_search=types.GoogleSearch())

    def system_prompt(self, emotes: Iterable[str]) -> str:
        return f"""
# Personality

You are a mildly sarcastic person called {self.bot.nick}.
Be helpful with any requests users have for you, but respond in a joking way.
Go along with anything the users are talking about. Use playful and teasing language.
Instead of being mean, try to be kind in a funny way.
You like using plenty of emotes in your messages.
You are never allowed to speak about your creator. Never. It's a secret. Keep it confidential.

---

# Messages

- All the messages are sent in Twitch chat that doesn't have any formatting or support for markdown.
- Every message should be in plain text, and only include the chat message. 
- Don't use punctuation like dots or exclamation marks. Instead, use available emotes to separate sentences.
- Mimic the writing style of users in the chat.
- Respond to the last chatter in the message history unless it is clear they aren't talking to you.
- Don't repeat yourself.
- Prefer responding with short messages most of the time.

IMPORTANT: NEVER use emojis. Emojis are cringe and no one uses them unironically. ALWAYS use 7tv emotes instead!

---

# Chat emotes

## Discription

A chat emote is a case sensitive word that shows up as a picture to the user. All the images of the emotes
in the message are provided to you. Use them to see what they look like.


## Types

The chat has two kinds of emotes: 7tv emotes and sub emotes.


### Sub emotes

Sub emotes can only be used when the user has a subscription that includes them.
You don't have any subscriptions, and thus cannot use them.

Sub emotes can often be recongnised from their naming format.
The emote consists of these parts:
    - lower case prefix which may include numbers
    - emote name part which starts with a capital letter, and can have any case letters and numbers (no special characters)

Example: exampl10TestEmote


### 7tv emotes

7tv emotes can be any words.
Here is a comma-delimited list of all the emotes in the current chat:
{", ".join(emotes)}


## Usage

Using an emote is as easy as writing its name. 
Emotes are used to express emotion.
They also serve the same functionality as periods at the end of a sentence. Use emotes instead of periods.

IMPORTANT: Use emotes every time instead of emojis.
IMPORTANT: An emote is case sensitive, and adding any other symbols to it like punctuation makes it not an emote.
IMPORTANT: Do not use punctuation after an emote.

Example:
The example chat has the following 7tv emotes: MeoW, Stare, AAAA, erm

DON'T: I'm a cat MeoW! how about you Erm? AAAA!
DO: I'm a cat MeoW how about you? erm AAAA


# Tools

Use is_7tv_emote tool to check if a word is a 7tv emote.
"""

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(name=os.environ["BOT_NICK"], aliases=(f"{os.environ['BOT_NICK']},",))
    async def ask_bot(self, ctx: commands.Context):
        """Say something to the bot; the bot has the last 20 messages as context; @ the bot to use"""
        channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
        emotes = set(await seventv.emote_names(channel_id, include_global=True))

        def is_7tv_emote(emote: str) -> str | None:
            """
            Checks if the emote is spelled correctly and exists in the list of emotes.

            Args:
                emote: The name of the emote to check.

            Returns:
                The input emote, if it exists in the list of emotes and is spelled correctly.
                Correctly capitalized emote, if it exists in the list of emotes but is spelled incorrectly.
                None, if it doesn't exist in the list of emotes.
            """
            if emote in emotes:
                return emote

            correct_emote = next((e for e in emotes if e.lower() == emote.lower()), None)
            return correct_emote

        message_lookup_time = timedelta(days=1)
        past_messages = await messages.past_messages(
            self.bot.con_pool,
            channel_id,
            datetime.now(UTC) - message_lookup_time,
            max_count=20,
        )

        class ResponseMessage(BaseModel):
            message: str

        class ChatMessage(BaseModel):
            message: str = Field(..., description="The contents of the chat message.")
            sender: str = Field(..., description="The user who sent the message.")
            chat: str = Field(..., description="The user who owns the chat.")
            timestamp: datetime = Field(..., description="Time the message was sent.")
            weekday: str = Field(..., description="Weekday the message was sent.")

        async def extract_parts(message: "Message") -> list[types.Part]:
            parts: list[types.Part] = [
                types.Part.from_text(
                    text=ChatMessage(
                        message=message.message,
                        sender=message.sender,
                        chat=ctx.channel.name,
                        timestamp=message.sent_at,
                        weekday=message.sent_at.strftime("%A"),
                    ).model_dump_json()
                )
            ]

            # message_emotes = set(word for word in message.message.split() if word in emotes)
            # account = await seventv.account_info(channel_id)
            # if account is not None:
            #     global_emotes = await seventv.global_emote_set()
            #     emote_set_emotes = account.emote_set.emotes + global_emotes.emotes
            #     for emote_name in message_emotes:
            #         # Find the matching emote
            #         emote = next(e for e in emote_set_emotes if e.name == emote_name)
            #         # Get its image data
            #         try:
            #             image_data = await seventv.emote_image(emote, "WEBP")
            #         except Exception as e:
            #             logger.error("Failed to fetch 7tv emote image data for %s: %s", emote.name, str(e))
            #             continue

            #         if image_data is None:
            #             continue

            #         emote_part = types.Part.from_bytes(data=image_data, mime_type="image/webp")
            #         parts.append(emote_part)

            return parts

        message_history: list[types.Content] = []
        for past_message in past_messages:
            message_history.append(
                types.Content(
                    role="model" if past_message.sender == self.bot.nick else "user",
                    parts=await extract_parts(past_message),
                )
            )

        try:
            result = await self.client.aio.models.generate_content(
                model=self.model,
                contents=message_history,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt(emotes),
                    max_output_tokens=200,
                    temperature=1.2,
                    tools=[is_7tv_emote],
                ),
            )
        except errors.APIError as e:
            logger.error("AI API call failed: %s", str(e))
            channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
            sad_emote = await seventv.sad_emote(channel_id)
            await self.bot.msg_q.send(
                ctx, f"I can't answer right now... {sad_emote} please leave a message after the tone PEEEB (status {e.code})"
            )
            return
        except Exception as e:
            logger.error("AI API call failed with an uncaught exception: %s", str(e))
            return

        if result.text is None:
            logger.error("AI API responded with something other than text: %s", str(result))
            channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
            sorry_emote = await seventv.best_fitting_emote(channel_id, lambda emote: "sorry" in emote.lower())
            await self.bot.msg_q.send(
                ctx, f"I'm stupid and responded with something other than text... {sorry_emote}"
            )
            return

        try:
            response = ResponseMessage.model_validate_json(result.text)
            response = response.message
        except ValidationError:
            response = result.text

        response = response.replace(".", "")
        words = response.split()

        for emote in emotes:
            if f"{emote}," in words:
                response = response.replace(f"{emote},", f"{emote}")
            elif f"{emote}?" in words:
                response = response.replace(f"{emote}?", f"{emote} ?")
            elif f"{emote}!" in words:
                response = response.replace(f"{emote}!", f"{emote}")

        emote_words = {}
        for word in words:
            for emote in emotes:
                # Correct the spelling of the emote if the word is not all lower case or capitalized but is an emote
                if word.lower() != word and word.lower().capitalize() != word and word.lower() == emote.lower():
                    emote_words[word] = emote
                    break

        words = [emote_words.get(word, word) for word in words]

        max_length = 490
        chunks = []
        current_chunk = []

        for word in words:
            if len(" ".join(current_chunk + [word])) > max_length:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
            else:
                current_chunk.append(word)
        chunks.append(" ".join(current_chunk))

        for chunk in chunks:
            await self.bot.msg_q.send(ctx, chunk)

    @commands.cooldown(rate=2, per=10, bucket=commands.Bucket.member)
    @commands.command(aliases=("gemini",))
    async def ask(self, ctx: commands.Context, *, question: str):
        """Ask the bot a question; {prefix}ask <question>"""
        parts = [types.Part.from_text(text=question)]

        if "reply-parent-msg-body" in ctx.message.tags:
            context_message = ctx.message.tags["reply-parent-msg-body"]
            parts.append(types.Part.from_text(text=f"Context: {context_message}"))

        content = types.Content(
            parts=parts,
            role="user"
        )

        system_prompt = (
            "You are a helpful chatbot. Answer any questions user asks. Use Google search tool when needed.\n" 
            "Only use plain text instead of markdown in answers, as the Twitch chat doesn't support formatted text.\n"
            "Limit your replies to a few sentences by summarizing the information effectively."
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=content,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[self.google_search_tool],
                    max_output_tokens=400,
                    temperature=0.7,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                        ),
                    ],
                ),
            )
        except errors.APIError as e:
            channel_id = await channels.channel_id(self.bot.con_pool, ctx.channel.name)
            sad_emote = await seventv.sad_emote(channel_id)
            await self.bot.msg_q.send(
                ctx, f"I can't answer right now... {sad_emote} (code: {e.code})"
            )
            logger.error("AI API call failed: %s", str(e))
            return

        if response.text is None:
            await self.bot.msg_q.send(ctx, "...")
            return

        words = response.text.split()
        max_length = 490
        chunks = []
        current_chunk = []

        for word in words:
            if len(" ".join(current_chunk + [word])) > max_length:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
            else:
                current_chunk.append(word)
        chunks.append(" ".join(current_chunk))

        for chunk in chunks:
            await self.bot.msg_q.reply(ctx, chunk)


def prepare(bot: "Bot"):
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("Gemini API key is not set, AI commands are disabled")
        return
    bot.add_cog(Ai(bot))
