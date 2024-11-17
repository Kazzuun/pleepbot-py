import os
import re
from typing import TYPE_CHECKING

from twitchio.ext import commands

from shared.apis import google
from Twitch.logger import logger

if TYPE_CHECKING:
    from Twitch.twitchbot import Bot


class Translate(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.language_codes = {
            "af": "Afrikaans",
            "sq": "Albanian",
            "am": "Amharic",
            "ar": "Arabic",
            "hy": "Armenian",
            "as": "Assamese",
            "ay": "Aymara",
            "az": "Azerbaijani",
            "bm": "Bambara",
            "eu": "Basque",
            "be": "Belarusian",
            "bn": "Bengali",
            "bho": "Bhojpuri",
            "bs": "Bosnian",
            "bg": "Bulgarian",
            "ca": "Catalan",
            "ceb": "Cebuano",
            "zh-CN": "Chinese (Simplified)",
            "zh-TW": "Chinese (Traditional)",
            "co": "Corsican",
            "hr": "Croatian",
            "cs": "Czech",
            "da": "Danish",
            "dv": "Dhivehi",
            "doi": "Dogri",
            "nl": "Dutch",
            "en": "English",
            "eo": "Esperanto",
            "et": "Estonian",
            "ee": "Ewe",
            "fil": "Filipino",
            "fi": "Finnish",
            "fr": "French",
            "fy": "Frisian",
            "gl": "Galician",
            "ka": "Georgian",
            "de": "German",
            "el": "Greek",
            "gn": "Guarani",
            "gu": "Gujarati",
            "ht": "Haitian Creole",
            "ha": "Hausa",
            "haw": "Hawaiian",
            "he": "Hebrew",
            "hi": "Hindi",
            "hmn": "Hmong",
            "hu": "Hungarian",
            "is": "Icelandic",
            "ig": "Igbo",
            "ilo": "Ilocano",
            "id": "Indonesian",
            "ga": "Irish",
            "it": "Italian",
            "ja": "Japanese",
            "jv": "Javanese",
            "kn": "Kannada",
            "kk": "Kazakh",
            "km": "Khmer",
            "rw": "Kinyarwanda",
            "gom": "Konkani",
            "ko": "Korean",
            "kri": "Krio",
            "ku": "Kurdish",
            "ckb": "Kurdish",
            "ky": "Kyrgyz",
            "lo": "Lao",
            "la": "Latin",
            "lv": "Latvian",
            "ln": "Lingala",
            "lt": "Lithuanian",
            "lg": "Luganda",
            "lb": "Luxembourgish",
            "mk": "Macedonian",
            "mai": "Maithili",
            "mg": "Malagasy",
            "ms": "Malay",
            "ml": "Malayalam",
            "mt": "Maltese",
            "mi": "Maori",
            "mr": "Marathi",
            "mni-Mtei": "Meiteilon",
            "lus": "Mizo",
            "mn": "Mongolian",
            "my": "Myanmar",
            "ne": "Nepali",
            "no": "Norwegian",
            "ny": "Nyanja",
            "or": "Odia",
            "om": "Oromo",
            "ps": "Pashto",
            "fa": "Persian",
            "pl": "Polish",
            "pt": "Portuguese",
            "pa": "Punjabi",
            "qu": "Quechua",
            "ro": "Romanian",
            "ru": "Russian",
            "sm": "Samoan",
            "sa": "Sanskrit",
            "gd": "Scots Gaelic",
            "nso": "Sepedi",
            "sr": "Serbian",
            "st": "Sesotho",
            "sn": "Shona",
            "sd": "Sindhi",
            "si": "Sinhala",
            "sk": "Slovak",
            "sl": "Slovenian",
            "so": "Somali",
            "es": "Spanish",
            "su": "Sundanese",
            "sw": "Swahili",
            "sv": "Swedish",
            "tl": "Tagalog",
            "tg": "Tajik",
            "ta": "Tamil",
            "tt": "Tatar",
            "te": "Telugu",
            "th": "Thai",
            "ti": "Tigrinya",
            "ts": "Tsonga",
            "tr": "Turkish",
            "tk": "Turkmen",
            "ak": "Twi",
            "uk": "Ukrainian",
            "ur": "Urdu",
            "ug": "Uyghur",
            "uz": "Uzbek",
            "vi": "Vietnamese",
            "cy": "Welsh",
            "xh": "Xhosa",
            "yi": "Yiddish",
            "yo": "Yoruba",
            "zu": "Zulu",
        }

    @commands.cooldown(rate=3, per=15, bucket=commands.Bucket.member)
    @commands.command(aliases=("tr", "tl", "trans"))
    async def translate(self, ctx: commands.Context, language: str | None, *args: str):
        """
        Translates the given message; by default detects the source language and translates it to english; source and target
        languages can be specified {prefix}translate source>target <message>; source language can be left off and it will
        get detected instead; if replied to a message with this command, the replied to message gets translated;
        see possible source and target language codes here: https://cloud.google.com/translate/docs/languages
        """
        language_pattern = rf"^({'|'.join(self.language_codes)})?(?:>|->|:)({'|'.join(self.language_codes)})$"
        if "reply-parent-msg-body" in ctx.message.tags:
            if language is not None and not bool(re.compile(language_pattern).match(language)):
                language = None
            query = ctx.message.tags["reply-parent-msg-body"].replace(r"\s", " ")
        elif language is None or (bool(re.compile(language_pattern).match(language)) and len(args) == 0):
            raise commands.MissingRequiredArgument
        elif not bool(re.compile(language_pattern).match(language)):
            query = " ".join((language,) + args)
            language = None
        else:
            query = " ".join(args)

        if language is None:
            target = "en"
            translation = await google.translate(query, target)
            source = translation.detected_source_language
            assert source is not None
        else:
            source, target = re.findall(language_pattern, language)[0]
            if not source:
                source = None
            else:
                source = source.lower()
            target = target.lower()

            translation = await google.translate(query, target, source)
            if source is None:
                source = translation.detected_source_language
                assert source is not None

        await self.bot.msg_q.reply(
            ctx, f"({self.language_codes.get(source, source)} -> {self.language_codes.get(target, target)}) {translation.translated_text}"
        )


def prepare(bot: "Bot"):
    if "GOOGLE_API_KEY" not in os.environ or os.environ["GOOGLE_API_KEY"] == "":
        logger.warning("Google api key is not set, location commands are disabled")
        return
    bot.add_cog(Translate(bot))
