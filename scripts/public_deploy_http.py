"""Bounded, consistently identified HTTP reads for public deployment continuity."""

from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

USER_AGENT = "dotrepo-public-deploy/1.0"
MAX_ERROR_BYTES = 1024
TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}


class DeploymentFetchError(ValueError):
    """Fetching trusted deployment state failed; publication must stop."""


def fetch_public_bytes(url: str, timeout: float, *, max_bytes: int, attempts: int = 3) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
        raise DeploymentFetchError("deployment URL must be an absolute HTTPS URL")
    if attempts < 1 or timeout <= 0 or max_bytes < 1:
        raise DeploymentFetchError("attempts, timeout, and byte limit must be positive")
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": USER_AGENT,
        },
    )
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise DeploymentFetchError(f"deployed asset exceeds {max_bytes} bytes: {url}")
            return body
        except HTTPError as exc:
            with exc:
                detail = " ".join(exc.read(MAX_ERROR_BYTES).decode("utf-8", "replace").split())
                ray = exc.headers.get("cf-ray", "unknown") if exc.headers else "unknown"
            error = DeploymentFetchError(f"GET {url}: HTTP {exc.code}; cf-ray={ray}; body={detail}")
            if exc.code not in TRANSIENT_STATUSES or attempt + 1 == attempts:
                raise error from exc
        except (URLError, TimeoutError, ConnectionError) as exc:
            if attempt + 1 == attempts:
                raise DeploymentFetchError(
                    f"GET {url} failed after {attempts} attempts: {exc}"
                ) from exc
        time.sleep(min(2**attempt, 4))
    raise AssertionError("unreachable")
