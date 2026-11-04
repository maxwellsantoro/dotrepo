"""Bounded R2 REST writes using the deployment's existing environment credentials."""

from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

TRANSIENT = {408, 429, 500, 502, 503, 504}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RequestBudget:
    """Reserve attempts in a rolling window, including retries and the final log."""

    def __init__(self, limit=1000, window=300):
        self.limit, self.window = limit, window
        self.starts = deque()
        self.lock = threading.Lock()
        self.attempts = 0
        self.attempted_body_bytes = 0

    def reserve(self, body_bytes=0):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.starts and self.starts[0] <= now - self.window:
                    self.starts.popleft()
                if len(self.starts) < self.limit:
                    self.starts.append(now)
                    self.attempts += 1
                    self.attempted_body_bytes += body_bytes
                    return
                delay = self.starts[0] + self.window - now
            time.sleep(min(delay, 60))


class Uploader:
    def __init__(self, bucket, concurrency):
        self.account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        self.token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        if not re.fullmatch(r"[0-9a-f]{32}", self.account) or not self.token:
            raise ValueError(
                "R2 API upload requires the deployment account and API token environment"
            )
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
            raise ValueError("invalid R2 bucket name")
        self.bucket, self.concurrency = bucket, concurrency
        self.budget = RequestBudget()

    def put(self, key, body, content_type, cache_control):
        if (
            not key.startswith("v0/snapshots/")
            or "\\" in key
            or any(part in {"", ".", ".."} for part in key.split("/"))
        ):
            raise ValueError("R2 archive key must stay under v0/snapshots/")
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account}"
            f"/r2/buckets/{self.bucket}/objects/{quote(key, safe='/')}"
        )
        for attempt in range(3):
            self.budget.reserve(len(body))
            request = Request(
                url,
                data=body,
                method="PUT",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": content_type,
                    "Cache-Control": cache_control,
                    "User-Agent": "dotrepo-archive/1.0",
                },
            )
            delay = 2**attempt
            try:
                # A new opener per worker avoids sharing mutable handler state;
                # redirects cannot forward the deployment credential elsewhere.
                with build_opener(NoRedirect()).open(request, timeout=30) as response:
                    response.read(65536)
                return
            except HTTPError as error:
                with error:
                    status = error.code
                    retry_after = error.headers.get("Retry-After", "")
                if status not in TRANSIENT or attempt == 2:
                    raise RuntimeError(f"R2 PUT {key}: HTTP {status}; upload stopped") from None
                if retry_after.isdigit():
                    if int(retry_after) > 300:
                        raise RuntimeError(
                            "R2 Retry-After exceeds the bounded retry budget"
                        ) from None
                    delay = max(delay, int(retry_after))
                print(
                    f"R2 PUT {key}: HTTP {status}; retrying this object ({attempt + 1}/3)",
                    flush=True,
                )
            except (URLError, TimeoutError, ConnectionError):
                if attempt == 2:
                    raise RuntimeError(f"R2 PUT {key}: transport failed after 3 attempts") from None
            while delay > 0:
                pause = min(delay, 60)
                time.sleep(pause)
                delay -= pause
        raise AssertionError("upload attempts exhausted")

    def payloads(self, paths, public_root, content_type):
        pending = iter(paths)
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            active = set()

            def submit():
                path = next(pending, None)
                if path is not None:
                    active.add(
                        pool.submit(
                            self.put,
                            path.relative_to(public_root).as_posix(),
                            path.read_bytes(),
                            content_type(path),
                            "public, max-age=31536000, immutable",
                        )
                    )

            for _ in range(self.concurrency):
                submit()
            try:
                while active:
                    done, active = wait(active, return_when=FIRST_COMPLETED)
                    # Inspect every completed write before scheduling more.
                    for future in done:
                        future.result()
                    for _ in done:
                        submit()
            except BaseException:
                for future in active:
                    future.cancel()
                raise
