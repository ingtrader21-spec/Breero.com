"""HTTP helpers shared by provider self-service routers.

Provider routes never accept a caller-selected vendor identifier; these helpers only
cover optimistic-concurrency headers and request correlation.
"""

import re

from fastapi import Request, Response

from app.core.errors import DomainError

ETAG_RE = re.compile(r"^[1-9][0-9]*$")


def optional_if_match(value: str | None) -> int | None:
    return None if value is None else require_if_match(value)


def require_if_match(value: str | None) -> int:
    if value is None:
        raise DomainError(
            "PRECONDITION_REQUIRED",
            "If-Match is required for provider changes.",
            428,
        )
    token = value.strip()
    if token.startswith("W/"):
        token = token[2:].strip()
    token = token.strip('"')
    if not ETAG_RE.fullmatch(token):
        raise DomainError(
            "INVALID_IF_MATCH",
            "If-Match must contain the current resource version.",
            400,
        )
    return int(token)


def set_etag(response: Response, version: int) -> None:
    response.headers["ETag"] = f'"{version}"'


def correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)
