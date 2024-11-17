FROM python:3.12.4-slim

WORKDIR /twitch_bot

RUN pip install poetry
COPY pyproject.toml poetry.lock /twitch_bot/
RUN poetry config virtualenvs.create false && poetry install --no-root

COPY ./shared ./shared
COPY ./Twitch ./Twitch

EXPOSE 4000

CMD ["python3", "Twitch/twitchbot.py"]
