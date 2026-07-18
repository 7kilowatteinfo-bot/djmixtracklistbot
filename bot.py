from __future__ import annotations

import os
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from recognizer import process_mix


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("dj-tracklist-bot")


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "DJ Tracklist Bot\n\n"
        "Отправь DJ-микс MP3.\n\n"
        "Я распознаю треки через AudD, "
        "уберу повторы и создам треклист с таймкодами."
    )



async def handle_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message


    if not message:
        return


    file_obj = None


    if message.audio:

        file_obj = await message.audio.get_file()
        filename = message.audio.file_name or "mix.mp3"


    elif message.document:

        file_obj = await message.document.get_file()
        filename = message.document.file_name or "mix.mp3"


    else:

        await message.reply_text(
            "Пришли MP3 файлом."
        )

        return



    path = DOWNLOAD_DIR / filename


    await message.reply_text(
        "Файл получен.\n"
        "Начинаю анализ..."
    )


    await file_obj.download_to_drive(
        custom_path=str(path)
    )


    try:

        result = await process_mix(path)


        output = DOWNLOAD_DIR / "tracklist.txt"

        output.write_text(
            result,
            encoding="utf-8"
        )


        await message.reply_text(
            f"Готово.\n\n{result}"
        )


        await message.reply_document(
            document=output.open(
                "rb"
            ),
            filename="tracklist.txt"
        )


    except Exception as e:

        logger.exception(e)

        await message.reply_text(
            f"Ошибка анализа:\n{e}"
        )


    finally:

        try:
            path.unlink()
        except Exception:
            pass




def main():

    if not TOKEN:

        raise RuntimeError(
            "Не найден TELEGRAM_BOT_TOKEN"
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
            filters.AUDIO |
            filters.Document.ALL,
            handle_audio
        )
    )


    logger.info(
        "Bot started"
    )


    app.run_polling()



if __name__ == "__main__":
    main()
