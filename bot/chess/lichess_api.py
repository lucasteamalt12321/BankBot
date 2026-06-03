"""Small async Lichess API client used by chess commands."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

LICHESS_API_BASE_URL = "https://lichess.org/api"
DEFAULT_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class LichessUser:
    """Normalized Lichess user profile."""

    username: str
    title: str | None = None
    online: bool = False


class LichessApiError(RuntimeError):
    """Raised when Lichess API cannot be reached or returns an unexpected error."""


def parse_lichess_user(payload: dict[str, Any]) -> LichessUser | None:
    """Convert a Lichess API JSON payload into a normalized user object."""

    username = payload.get("username") or payload.get("id")
    if not isinstance(username, str) or not username.strip():
        return None

    title = payload.get("title")
    return LichessUser(
        username=username.strip(),
        title=title if isinstance(title, str) and title else None,
        online=bool(payload.get("online", False)),
    )


async def fetch_lichess_user(username: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> LichessUser | None:
    """Fetch a Lichess user by username.

    Returns:
        Normalized user, `None` for a real 404/not found response.

    Raises:
        LichessApiError: For network errors, timeouts and non-404 API errors.
    """

    normalized_username = username.strip()
    if not normalized_username:
        return None

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    url = f"{LICHESS_API_BASE_URL}/user/{normalized_username}"
    headers = {"Accept": "application/json", "User-Agent": "BankBot/ChessModule"}

    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 404:
                    return None
                if response.status != 200:
                    text = await response.text()
                    logger.warning(
                        "Lichess user lookup failed",
                        extra={"status": response.status, "body_preview": text[:200]},
                    )
                    raise LichessApiError(f"Lichess API returned HTTP {response.status}")

                payload = await response.json(content_type=None)
    except TimeoutError as exc:
        raise LichessApiError("Lichess API timeout") from exc
    except aiohttp.ClientError as exc:
        raise LichessApiError("Lichess API network error") from exc

    if not isinstance(payload, dict):
        raise LichessApiError("Lichess API returned invalid payload")

    return parse_lichess_user(payload)
