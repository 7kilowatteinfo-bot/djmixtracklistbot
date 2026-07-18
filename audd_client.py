\
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


AUDD_ENTERPRISE_URL = "https://enterprise.audd.io/"


class AudDError(RuntimeError):
    pass


async def recognize_file(
    path: Path,
    api_token: str,
    *,
    skip: int = 1,
    every: int = 1,
    timeout_seconds: float = 3600,
) -> dict[str, Any]:
    data = {
        "api_token": api_token,
        "accurate_offsets": "true",
        "skip": str(max(0, skip)),
        "every": str(max(1, every)),
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            with path.open("rb") as handle:
                files = {"file": (path.name, handle, "application/octet-stream")}
                response = await client.post(AUDD_ENTERPRISE_URL, data=data, files=files)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise AudDError(f"AudD HTTP error: {exc}") from exc
    except ValueError as exc:
        raise AudDError("AudD returned invalid JSON") from exc

    if payload.get("status") != "success":
        error = payload.get("error") or {}
        message = (
            error.get("error_message")
            or error.get("message")
            or payload.get("status")
            or "unknown AudD error"
        )
        raise AudDError(str(message))

    return payload


async def recognize_url(
    url: str,
    api_token: str,
    *,
    skip: int = 1,
    every: int = 1,
    timeout_seconds: float = 3600,
) -> dict[str, Any]:
    data = {
        "api_token": api_token,
        "url": url,
        "accurate_offsets": "true",
        "skip": str(max(0, skip)),
        "every": str(max(1, every)),
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = await client.post(AUDD_ENTERPRISE_URL, data=data)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise AudDError(f"AudD HTTP error: {exc}") from exc
    except ValueError as exc:
        raise AudDError("AudD returned invalid JSON") from exc

    if payload.get("status") != "success":
        error = payload.get("error") or {}
        message = (
            error.get("error_message")
            or error.get("message")
            or payload.get("status")
            or "unknown AudD error"
        )
        raise AudDError(str(message))

    return payload
