from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Detection:
    key: str
    artist: str
    title: str
    score: float
    estimated_start: int
    isrc: str | None = None
    label: str | None = None
    song_link: str | None = None


def parse_timecode(value: str | None) -> int:
    if not value:
        return 0

    parts = str(value).strip().split(":")

    try:
        nums = [int(float(x)) for x in parts]
    except ValueError:
        return 0

    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]

    if len(nums) == 2:
        return nums[0] * 60 + nums[1]

    if len(nums) == 1:
        return nums[0]

    return 0


def format_timecode(seconds: int) -> str:
    seconds = max(0, int(seconds))

    minutes, secs = divmod(seconds, 60)

    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _track_key(song: dict[str, Any]) -> str:
    isrc = str(song.get("isrc") or "").strip().upper()

    if isrc:
        return f"isrc:{isrc}"

    artist = _normalize(str(song.get("artist") or ""))
    title = _normalize(str(song.get("title") or ""))

    return f"meta:{artist}:{title}"


def _get_start_time(song: dict[str, Any], block: dict[str, Any]) -> int:
    """
    AudD Enterprise:
    start_offset = реальное начало найденного трека в файле.

    Fallback для старого ответа:
    offset - timecode
    """

    if song.get("start_offset") is not None:
        try:
            return max(0, int(float(song["start_offset"])))
        except Exception:
            pass

    block_offset = parse_timecode(
        str(block.get("offset") or "0")
    )

    song_position = parse_timecode(
        str(song.get("timecode") or "0")
    )

    return max(0, block_offset - song_position)


def extract_detections(
    payload: dict[str, Any],
    min_score: float = 55
) -> list[Detection]:

    if payload.get("status") != "success":
        error = payload.get("error") or {}
        raise ValueError(
            error.get("error_message")
            or error.get("message")
            or "AudD request failed"
        )

    result = payload.get("result") or []

    merged: dict[str, Detection] = {}

    for block in result:

        for song in block.get("songs") or []:

            artist = str(song.get("artist") or "").strip()
            title = str(song.get("title") or "").strip()

            if not artist or not title:
                continue


            try:
                score = float(song.get("score") or 0)
            except Exception:
                score = 0


            if score < min_score:
                continue


            estimated_start = _get_start_time(song, block)

            key = _track_key(song)


            candidate = Detection(
                key=key,
                artist=artist,
                title=title,
                score=score,
                estimated_start=estimated_start,
                isrc=(
                    str(song.get("isrc")).strip()
                    if song.get("isrc")
                    else None
                ),
                label=(
                    str(song.get("label")).strip()
                    if song.get("label")
                    else None
                ),
                song_link=(
                    str(song.get("song_link")).strip()
                    if song.get("song_link")
                    else None
                ),
            )


            existing = merged.get(key)


            if existing is None:

                merged[key] = candidate

            else:

                # берём самое раннее появление
                existing.estimated_start = min(
                    existing.estimated_start,
                    candidate.estimated_start
                )

                # сохраняем лучший результат AudD
                if candidate.score > existing.score:

                    candidate.estimated_start = (
                        existing.estimated_start
                    )

                    merged[key] = candidate


    detections = sorted(
        merged.values(),
        key=lambda x: x.estimated_start
    )


    return detections



def render_tracklist(
    detections: list[Detection]
) -> str:

    if not detections:
        return "Треки не распознаны."


    lines = [
        "TRACKLIST",
        ""
    ]


    for index, item in enumerate(
        detections,
        start=1
    ):

        lines.append(
            f"{index:02d}. "
            f"{format_timecode(item.estimated_start)} — "
            f"{item.artist} — "
            f"{item.title}"
        )


    return "\n".join(lines)
