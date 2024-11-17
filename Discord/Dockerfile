FROM python:3.12.4-slim

WORKDIR /discord_bot

RUN pip install poetry
COPY pyproject.toml poetry.lock /discord_bot/
RUN poetry config virtualenvs.create false && poetry install --no-root

COPY ./shared ./shared
COPY ./Discord ./Discord

CMD ["python3", "Discord/discordbot.py"]
