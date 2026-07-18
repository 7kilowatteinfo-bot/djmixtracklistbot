from __future__ import annotations

import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from audd_client import recognize_url
from tracklist import build_tracklist, render


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

AUDD_TOKEN = os.getenv(
    "AUDD_API_TOKEN"
)



async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "DJ Tracklist Bot\n\n"
        "Пришли публичную HTTPS ссылку на MP3 микс.\n\n"
        "Я распознаю треки и верну tracklist с таймкодами."
    )



async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text


    if not text:

        return


    if not text.startswith(
        "http"
    ):

        await update.message.reply_text(
            "Нужна прямая HTTPS ссылка на MP3."
        )

        return



    await update.message.reply_text(
        "Анализирую микс...\n"
        "Это может занять время."
    )


    try:


        response = await recognize_url(
            text,
            AUDD_TOKEN
        )


        tracks = build_tracklist(
            response
        )


        result = render(
            tracks
        )


        await update.message.reply_text(
            result
        )


        logging.info(
            "Recognized tracks: %s",
            len(tracks)
        )


    except Exception as e:


        logging.exception(e)


        await update.message.reply_text(
            f"Ошибка:\n{e}"
        )




def main():


    if not TOKEN:

        raise RuntimeError(
            "Нет TELEGRAM_BOT_TOKEN"
        )


    if not AUDD_TOKEN:

        raise RuntimeError(
            "Нет AUDD_API_TOKEN"
        )



    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )


    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    app.add_handler(
        MessageHandler(
            filters.TEXT,
            handle_message
        )
    )


    logging.info(
        "Bot started"
    )


    app.run_polling()



if __name__ == "__main__":

    main()
