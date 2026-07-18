\
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from audd_client import AudDError, recognize_file, recognize_url
from tracklist import extract_detections, render_tracklist


load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
AUDD_API_TOKEN = os.getenv("AUDD_API_TOKEN", "").strip()
MIN_SCORE = float(os.getenv("MIN_SCORE", "55"))
AUDD_SKIP = int(os.getenv("AUDD_SKIP", "1"))
AUDD_EVERY = int(os.getenv("AUDD_EVERY", "1"))
TEMP_DIR = Path(os.getenv("TEMP_DIR", "./tmp"))

API_BASE = os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org").rstrip("/")
FILE_BASE = os.getenv("TELEGRAM_FILE_BASE_URL", "https://api.telegram.org/file").rstrip("/")

POLL_TIMEOUT = 50
HTTP_TIMEOUT = 70

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("dj-tracklist-bot")


def api_url(method: str) -> str:
    return f"{API_BASE}/bot{BOT_TOKEN}/{method}"


def file_url(file_path: str) -> str:
    return f"{FILE_BASE}/bot{BOT_TOKEN}/{file_path.lstrip('/')}"


async def telegram_call(client: httpx.AsyncClient, method: str, **params: Any) -> Any:
    response = await client.post(api_url(method), json=params)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description") or f"Telegram {method} failed")
    return payload.get("result")


async def send_message(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    # Telegram message text limit is 4096 chars. Split on lines.
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > 3900 and current:
            chunks.append(current.rstrip())
            current = ""
        current += line
    if current:
        chunks.append(current.rstrip())

    for chunk in chunks or [text]:
        await telegram_call(client, "sendMessage", chat_id=chat_id, text=chunk)


async def send_text_file(
    client: httpx.AsyncClient,
    chat_id: int,
    content: str,
    filename: str = "tracklist.txt",
) -> None:
    files = {"document": (filename, content.encode("utf-8"), "text/plain; charset=utf-8")}
    data = {"chat_id": str(chat_id)}
    response = await client.post(api_url("sendDocument"), data=data, files=files)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description") or "sendDocument failed")


def is_http_url(text: str) -> bool:
    try:
        parsed = urlparse(text.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


async def process_payload(
    client: httpx.AsyncClient,
    chat_id: int,
    payload: dict[str, Any],
) -> None:
    detections = extract_detections(payload, min_score=MIN_SCORE)
    tracklist = render_tracklist(detections)
    await send_message(
        client,
        chat_id,
        f"Готово. Распознано треков: {len(detections)}\n\n{tracklist}",
    )
    await send_text_file(client, chat_id, tracklist)


async def handle_url(client: httpx.AsyncClient, chat_id: int, url: str) -> None:
    await send_message(
        client,
        chat_id,
        "Анализирую ссылку. Для длинного DJ-микса обработка может занять некоторое время.",
    )
    try:
        payload = await recognize_url(
            url,
            AUDD_API_TOKEN,
            skip=AUDD_SKIP,
            every=AUDD_EVERY,
        )
        await process_payload(client, chat_id, payload)
    except (AudDError, ValueError, RuntimeError) as exc:
        logger.exception("URL analysis failed")
        await send_message(client, chat_id, f"Ошибка анализа: {exc}")


def pick_telegram_file(message: dict[str, Any]) -> tuple[str, str] | None:
    audio = message.get("audio")
    if audio:
        return audio["file_id"], audio.get("file_name") or "mix.mp3"

    document = message.get("document")
    if document:
        mime = (document.get("mime_type") or "").lower()
        name = document.get("file_name") or "mix.bin"
        allowed_ext = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".mp4"}
        if mime.startswith(("audio/", "video/")) or Path(name).suffix.lower() in allowed_ext:
            return document["file_id"], name
    return None


async def download_telegram_file(
    client: httpx.AsyncClient,
    file_id: str,
    original_name: str,
) -> Path:
    info = await telegram_call(client, "getFile", file_id=file_id)
    remote_path = str(info["file_path"])

    # A local Bot API server may return an absolute local path.
    local_candidate = Path(remote_path)
    if local_candidate.is_absolute() and local_candidate.exists():
        return local_candidate

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_name).suffix or Path(remote_path).suffix or ".bin"
    fd, tmp_name = tempfile.mkstemp(prefix="djmix_", suffix=suffix, dir=TEMP_DIR)
    os.close(fd)
    destination = Path(tmp_name)

    try:
        async with client.stream("GET", file_url(remote_path)) as response:
            response.raise_for_status()
            with destination.open("wb") as out:
                async for chunk in response.aiter_bytes():
                    out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return destination


async def handle_uploaded_file(
    client: httpx.AsyncClient,
    chat_id: int,
    file_id: str,
    filename: str,
) -> None:
    await send_message(client, chat_id, f"Получил файл «{filename}». Загружаю для анализа…")
    downloaded: Path | None = None
    should_delete = False

    try:
        downloaded = await download_telegram_file(client, file_id, filename)
        should_delete = str(downloaded.resolve()).startswith(str(TEMP_DIR.resolve()))

        await send_message(
            client,
            chat_id,
            "Файл загружен. Запускаю распознавание и очистку повторных совпадений.",
        )
        payload = await recognize_file(
            downloaded,
            AUDD_API_TOKEN,
            skip=AUDD_SKIP,
            every=AUDD_EVERY,
        )
        await process_payload(client, chat_id, payload)

    except httpx.HTTPStatusError as exc:
        logger.exception("Telegram file download failed")
        if exc.response.status_code in {400, 413}:
            text = (
                "Не удалось скачать этот файл через Telegram Bot API. "
                "Для больших DJ-миксов отправь прямую публичную ссылку на аудиофайл "
                "или подключи локальный Telegram Bot API server."
            )
        else:
            text = f"Ошибка загрузки файла: HTTP {exc.response.status_code}"
        await send_message(client, chat_id, text)

    except (AudDError, ValueError, RuntimeError) as exc:
        logger.exception("File analysis failed")
        await send_message(client, chat_id, f"Ошибка анализа: {exc}")

    finally:
        if downloaded and should_delete:
            downloaded.unlink(missing_ok=True)


async def handle_message(client: httpx.AsyncClient, message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    text = (message.get("text") or "").strip()

    if text.startswith("/start") or text.startswith("/help"):
        await send_message(
            client,
            chat_id,
            "DJ Tracklist Bot\n\n"
            "Отправь мне DJ-микс как аудиофайл/документ или пришли прямую "
            "публичную https-ссылку на файл.\n\n"
            "Я распознаю треки, объединю повторные совпадения и верну "
            "треклист с примерными таймкодами начала.",
        )
        return

    if text and is_http_url(text):
        await handle_url(client, chat_id, text)
        return

    selected = pick_telegram_file(message)
    if selected:
        file_id, filename = selected
        await handle_uploaded_file(client, chat_id, file_id, filename)
        return

    if text:
        await send_message(
            client,
            chat_id,
            "Пришли прямую https-ссылку на DJ-микс или отправь аудиофайл.",
        )


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing")
    if not AUDD_API_TOKEN:
        raise SystemExit("AUDD_API_TOKEN is missing")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    offset: int | None = None

    timeout = httpx.Timeout(HTTP_TIMEOUT, read=HTTP_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        me = await telegram_call(client, "getMe")
        logger.info("Started as @%s", me.get("username"))

        while True:
            params: dict[str, Any] = {
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message"],
            }
            if offset is not None:
                params["offset"] = offset

            try:
                updates = await telegram_call(client, "getUpdates", **params)
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    message = update.get("message")
                    if message:
                        # Process sequentially for MVP to avoid overlapping huge uploads.
                        await handle_message(client, message)

            except (httpx.HTTPError, RuntimeError) as exc:
                logger.exception("Polling error: %s", exc)
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
