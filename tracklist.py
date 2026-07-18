\
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
    """Parse HH:MM:SS or MM:SS into integer seconds."""
    if not value:
        return 0
    parts = value.strip().split(":")
    try:
        nums = [int(float(p)) for p in parts]
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
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _track_key(song: dict[str, Any]) -> str:
    isrc = (song.get("isrc") or "").strip().upper()
    if isrc:
        return f"isrc:{isrc}"
    artist = _normalize(str(song.get("artist") or ""))
    title = _normalize(str(song.get("title") or ""))
    return f"meta:{artist}:{title}"


def extract_detections(payload: dict[str, Any], min_score: float = 55) -> list[Detection]:
    """
    Convert raw AudD Enterprise response into deduplicated detections.

    AudD Enterprise returns entries shaped roughly as:
      {"offset": "08:48", "songs": [{... "timecode": "01:06"}]}

    We estimate the mix start as:
      scan offset - recognized song timecode

    Repeated hits are merged by ISRC, otherwise normalized Artist + Title.
    """
    if payload.get("status") != "success":
        error = payload.get("error") or {}
        message = error.get("error_message") or error.get("message") or "AudD request failed"
        raise ValueError(str(message))

    result = payload.get("result") or []
    merged: dict[str, Detection] = {}

    for block in result:
        block_offset = parse_timecode(str(block.get("offset") or "0"))
        for song in block.get("songs") or []:
            artist = str(song.get("artist") or "").strip()
            title = str(song.get("title") or "").strip()
            if not artist or not title:
                continue

            try:
                score = float(song.get("score") or 0)
            except (TypeError, ValueError):
                score = 0.0
            if score < min_score:
                continue

            estimated_start = int(song.get("start_offset") or block_offset)
key = _track_key(song)

            candidate = Detection(
                key=key,
                artist=artist,
                title=title,
                score=score,
                estimated_start=estimated_start,
                isrc=(str(song.get("isrc")).strip() if song.get("isrc") else None),
                label=(str(song.get("label")).strip() if song.get("label") else None),
                song_link=(str(song.get("song_link")).strip() if song.get("song_link") else None),
            )

            existing = merged.get(key)
            if existing is None:
                merged[key] = candidate
                continue

            # Earliest plausible appearance is used as the track start.
            existing.estimated_start = min(existing.estimated_start, candidate.estimated_start)

            # Keep metadata from the highest-confidence hit.
            if candidate.score > existing.score:
                candidate.estimated_start = existing.estimated_start
                merged[key] = candidate

    detections = sorted(merged.values(), key=lambda d: (d.estimated_start, -d.score))

    # Collapse near-identical adjacent metadata keys that escaped ISRC matching.
    cleaned: list[Detection] = []
    for item in detections:
        if cleaned:
            prev = cleaned[-1]
            same_meta = (
                _normalize(prev.artist) == _normalize(item.artist)
                and _normalize(prev.title) == _normalize(item.title)
            )
            if same_meta:
                prev.estimated_start = min(prev.estimated_start, item.estimated_start)
                if item.score > prev.score:
                    item.estimated_start = prev.estimated_start
                    cleaned[-1] = item
                continue
        cleaned.append(item)

    return cleaned


def render_tracklist(detections: list[Detection]) -> str:
    if not detections:
        return "Треки не распознаны."

    lines = ["TRACKLIST", ""]
    for index, item in enumerate(detections, start=1):
        lines.append(
            f"{index:02d}. {format_timecode(item.estimated_start)} — "
            f"{item.artist} — {item.title}"
        )
    return "\n".join(lines)
