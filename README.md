# DJ Tracklist Telegram Bot

MVP Telegram bot that analyzes DJ mixes with the AudD Enterprise API and returns
a cleaned tracklist with approximate start timecodes.

## What it does

- accepts an audio/document sent to the bot;
- also accepts a direct public URL to an MP3/M4A/WAV file;
- sends the mix to AudD Enterprise;
- groups repeated recognitions of the same track;
- prefers ISRC for deduplication, falling back to normalized Artist + Title;
- estimates the track start from the scan offset and the recognized song timecode;
- filters low-confidence matches;
- returns a numbered tracklist and a `.txt` file.

## Important Telegram file-size note

The public Telegram Bot API currently lets bots download files only up to 20 MB
through `getFile`. A one-hour 320 kbps MP3 is much larger than that.

For real DJ mixes you have two practical choices:

1. Send the bot a direct public download URL to the mix.
2. Run Telegram's Local Bot API Server and point:
   - `TELEGRAM_API_BASE_URL`
   - `TELEGRAM_FILE_BASE_URL`
   to that server.

Telegram documents that a local Bot API server can download files without a
size limit and upload files up to 2000 MB.

## AudD cost / scan density

AudD Enterprise counts one request per 12 seconds of audio processed.
The bot exposes `AUDD_SKIP` and `AUDD_EVERY`.

Recommended first test:

```env
AUDD_EVERY=1
AUDD_SKIP=1
```

This scans 12 seconds and skips the next 12 seconds. For maximum recognition
coverage use `AUDD_SKIP=0`, but it costs more API requests.

## Setup

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add:

- `TELEGRAM_BOT_TOKEN`
- `AUDD_API_TOKEN`

Run:

```bash
python bot.py
```

## Bot usage

- `/start` — instructions.
- Send a direct `https://...` audio URL.
- Or send an MP3/M4A/WAV/FLAC as Audio or Document.

## Track start estimation

AudD returns scan-block offsets and the recognized song's own timecode.
The bot estimates:

`mix track start ≈ scan offset - song timecode`

Multiple detections are merged, and the earliest plausible start is retained.

This is intentionally approximate. DJ transitions, edits, loops, mashups,
unreleased tracks and pitch/tempo changes can reduce recognition accuracy.

## Local Telegram Bot API

For large Telegram uploads, deploy Telegram's official local Bot API server.
The bot code is endpoint-configurable, but deployment of that server requires
your Telegram `api_id` and `api_hash`, so those secrets are not included here.

Example `.env` when your local API is available at port 8081:

```env
TELEGRAM_API_BASE_URL=http://127.0.0.1:8081
TELEGRAM_FILE_BASE_URL=http://127.0.0.1:8081/file
```

If your bot process runs in a different Docker container, use the service name
instead of `127.0.0.1`.

## Next production improvements

- job queue and progress status;
- database with users/jobs/results;
- manual correction UI with inline buttons;
- Beatport/MusicBrainz metadata verification;
- export presets for SoundCloud, YouTube and 7KILOWATTE posts;
- per-user limits and payments.
