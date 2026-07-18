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

    try:
        parts = [int(float(x)) for x in str(value).split(":")]
    except ValueError:
        return 0

    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]

    if len(parts) == 2:
        return parts[0] * 60 + parts[1]

    return parts[0] if parts else 0


def format_timecode(seconds: int) -> str:
    seconds = max(0, int(seconds))

    minutes, secs = divmod(seconds, 60)

    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def _normalize(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.casefold()
    )


def _track_key(song: dict[str, Any]) -> str:

    isrc = str(
        song.get("isrc") or ""
    ).strip().upper()

    if isrc:
        return f"isrc:{isrc}"

    artist = _normalize(
        str(song.get("artist") or "")
    )

    title = _normalize(
        str(song.get("title") or "")
    )

    return f"meta:{artist}:{title}"


def _estimate_start(
    song: dict[str, Any],
    block: dict[str, Any]
) -> int:

    if song.get("start_offset"):

        try:
            return int(
                float(song["start_offset"])
            )
        except Exception:
            pass


    offset = parse_timecode(
        block.get("offset")
    )

    position = parse_timecode(
        song.get("timecode")
    )

    start = offset - position

    return max(0, start)



def extract_detections(
    payload: dict[str, Any],
    min_score: float = 55
) -> list[Detection]:

    if payload.get("status") != "success":
        raise ValueError(
            "AudD request failed"
        )


    merged: dict[str, Detection] = {}


    for block in payload.get("result", []):

        for song in block.get("songs", []):

            artist = str(
                song.get("artist") or ""
            ).strip()

            title = str(
                song.get("title") or ""
            ).strip()


            if not artist or not title:
                continue


            try:
                score = float(
                    song.get("score") or 0
                )
            except Exception:
                score = 0


            if score < min_score:
                continue


            item = Detection(
                key=_track_key(song),
                artist=artist,
                title=title,
                score=score,
                estimated_start=_estimate_start(
                    song,
                    block
                ),
                isrc=song.get("isrc"),
                label=song.get("label"),
                song_link=song.get("song_link")
            )


            old = merged.get(
                item.key
            )


            if old is None:

                merged[item.key] = item

            else:

                old.estimated_start = min(
                    old.estimated_start,
                    item.estimated_start
                )

                if item.score > old.score:
                    item.estimated_start = old.estimated_start
                    merged[item.key] = item



    tracks = sorted(
        merged.values(),
        key=lambda x: x.estimated_start
    )


    # удаляем ложные совпадения рядом друг с другом
    cleaned: list[Detection] = []


    for track in tracks:

        if cleaned:

            previous = cleaned[-1]


            same_time = (
                abs(
                    track.estimated_start -
                    previous.estimated_start
                )
                < 20
            )


            if same_time:

                if track.score > previous.score:
                    cleaned[-1] = track

                continue


        cleaned.append(track)



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
