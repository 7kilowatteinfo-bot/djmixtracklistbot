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

    return (
        "meta:"
        + _normalize(str(song.get("artist") or ""))
        + ":"
        + _normalize(str(song.get("title") or ""))
    )


def _get_start_time(song: dict[str, Any], block: dict[str, Any]) -> int:

    if song.get("start_offset") is not None:
        try:
            return int(float(song["start_offset"]))
        except Exception:
            pass

    block_offset = parse_timecode(
        str(block.get("offset") or "0")
    )

    timecode = parse_timecode(
        str(song.get("timecode") or "0")
    )

    return max(0, block_offset - timecode)


def extract_detections(
    payload: dict[str, Any],
    min_score: float = 55
) -> list[Detection]:

    if payload.get("status") != "success":
        raise ValueError("AudD request failed")

    merged: dict[str, Detection] = {}

    for block in payload.get("result") or []:

        for song in block.get("songs") or []:

            artist = str(song.get("artist") or "").strip()
            title = str(song.get("title") or "").strip()

            if not artist or not title:
                continue

            score = float(song.get("score") or 100)

            if score < min_score:
                continue

            key = _track_key(song)

            candidate = Detection(
                key=key,
                artist=artist,
                title=title,
                score=score,
                estimated_start=_get_start_time(song, block),
                label=song.get("label"),
                song_link=song.get("song_link"),
            )

            old = merged.get(key)

            if old is None:
                merged[key] = candidate
            else:
                old.estimated_start = min(
                    old.estimated_start,
                    candidate.estimated_start
                )

                if candidate.score > old.score:
                    merged[key] = candidate


    return sorted(
        merged.values(),
        key=lambda x: x.estimated_start
    )


def render_tracklist(
    detections: list[Detection]
) -> str:

    if not detections:
        return "Треки не распознаны."

    lines = [
        "TRACKLIST",
        ""
    ]

    for i, item in enumerate(detections, 1):

        lines.append(
            f"{i:02d}. "
            f"{format_timecode(item.estimated_start)} — "
            f"{item.artist} — "
            f"{item.title}"
        )

    return "\n".join(lines)
