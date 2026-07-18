from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Track:
    artist: str
    title: str
    start: int
    score: float


def format_time(seconds: int) -> str:
    minutes, sec = divmod(int(seconds), 60)
    return f"{minutes:02d}:{sec:02d}"


def normalize(text: str) -> str:
    return (
        text.lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


def build_tracklist(
    payload: dict[str, Any]
) -> list[Track]:

    result = payload.get("result") or []

    found: dict[str, Track] = {}


    for item in result:

        songs = item.get("songs") or []

        start = int(
            item.get("offset") or
            item.get("start_offset") or
            0
        )


        for song in songs:

            artist = str(
                song.get("artist") or ""
            ).strip()

            title = str(
                song.get("title") or ""
            ).strip()


            if not artist or not title:
                continue


            score = float(
                song.get("score") or 0
            )


            key = (
                normalize(artist)
                +
                normalize(title)
            )


            track = Track(
                artist=artist,
                title=title,
                start=start,
                score=score,
            )


            old = found.get(key)


            if old is None:

                found[key] = track


            else:

                if track.start < old.start:
                    old.start = track.start

                if track.score > old.score:
                    found[key] = track



    tracks = list(
        found.values()
    )


    tracks.sort(
        key=lambda x: x.start
    )


    # убираем слишком близкие ложные совпадения

    cleaned = []


    for track in tracks:

        if cleaned:

            last = cleaned[-1]

            if (
                abs(track.start - last.start)
                < 15
            ):
                if track.score > last.score:
                    cleaned[-1] = track

                continue


        cleaned.append(track)


    return cleaned



def render(
    tracks: list[Track]
) -> str:


    if not tracks:
        return "Треки не найдены."


    lines = [
        "TRACKLIST",
        ""
    ]


    for i, track in enumerate(
        tracks,
        start=1
    ):

        lines.append(
            f"{i:02d}. "
            f"{format_time(track.start)} — "
            f"{track.artist} — "
            f"{track.title}"
        )


    return "\n".join(lines)
