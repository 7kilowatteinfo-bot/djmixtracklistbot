from __future__ import annotations

from typing import Any

import httpx


AUDD_URL = "https://enterprise.audd.io/"


class AudDError(Exception):
    pass


async def recognize_url(
    url: str,
    api_token: str,
    timeout: int = 3600,
) -> dict[str, Any]:

    data = {
        "api_token": api_token,
        "url": url,
        "accurate_offsets": "true",
    }

    try:

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.post(
                AUDD_URL,
                data=data
            )

        response.raise_for_status()

        result = response.json()


    except Exception as e:

        raise AudDError(
            f"AudD error: {e}"
        )


    if result.get("status") != "success":

        raise AudDError(
            str(result)
        )


    return result
