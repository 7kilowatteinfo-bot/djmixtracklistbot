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

    parts = str(value).split(":")

    try:
        nums = [int(float(x)) for x in parts]
    except Exception:
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


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def track_key(song: dict[str, Any]) -> str:

    isrc = str(song.get("isrc") or "").strip().upper()

    if isrc:
        return f"isrc:{isrc}"

    return (
        "meta:"
        + normalize(str(song.get("artist") or ""))
        + ":"
        + normalize(str(song.get("title") or ""))
    )


def calculate_start(song: dict[str, Any], block: dict[str, Any]) -> int:

    offset = parse_timecode(
        str(block.get("offset") or "0")
    )

    timecode = parse_timecode(
        str(song.get("timecode") or "0")
    )

    start = offset - timecode

    if start < 0:
        return 0

    return start


def extract_detections(
    payload: dict[str, Any],
    min_score: float = 55
) -> list[Detection]:


    if payload.get("status") != "success":
        return []


    merged: dict[str, Detection] = {}


    for block in payload.get("result", []):

        for song in block.get("songs", []):


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



            key = track_key(song)


            item = Detection(
                key=key,
                artist=artist,
                title=title,
                score=score,
                estimated_start=calculate_start(song, block),
                isrc=song.get("isrc"),
                label=song.get("label"),
                song_link=song.get("song_link"),
            )


            old = merged.get(key)


            if old is None:

                merged[key] = item


            else:

                # оставляем самое раннее появление трека
                old.estimated_start = min(
                    old.estimated_start,
                    item.estimated_start
                )

                # оставляем лучший score
                if item.score > old.score:
                    item.estimated_start = old.estimated_start
                    merged[key] = item



    result = list(merged.values())


    # сортировка по времени появления
    result.sort(
        key=lambda x: x.estimated_start
    )


    # дополнительная очистка дублей подряд
    cleaned = []


    for item in result:

        duplicate = False

        for old in cleaned:

            same_artist = normalize(item.artist) == normalize(old.artist)

            same_title = normalize(item.title) == normalize(old.title)


            if same_artist and same_title:

                old.estimated_start = min(
                    old.estimated_start,
                    item.estimated_start
                )

                duplicate = True
                break


        if not duplicate:
            cleaned.append(item)


    return cleaned



def render_tracklist(
    detections: list[Detection]
) -> str:


    if not detections:
        return "Треки не распознаны."


    lines = [
        "TRACKLIST",
        ""
    ]


    for i, item in enumerate(detections, start=1):

        lines.append(
            f"{i:02d}. "
            f"{format_timecode(item.estimated_start)} — "
            f"{item.artist} — "
            f"{item.title}"
        )


    return "\n".join(lines)
