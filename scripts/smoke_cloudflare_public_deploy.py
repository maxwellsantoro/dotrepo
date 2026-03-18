#!/usr/bin/env python3
"""Smoke-test the live Cloudflare Worker deployment from a reviewed export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test a deployed Cloudflare Worker public surface."
    )
    parser.add_argument(
        "--deploy-url",
        required=True,
        help="Base deployed Worker URL, for example https://name.subdomain.workers.dev",
    )
    parser.add_argument(
        "--base-path",
        default="/",
        help="Hosted base path emitted into the reviewed export, default: /",
    )
    parser.add_argument(
        "--public-root",
        required=True,
        help="Path to the reviewed exported public tree used for deployment",
    )
    return parser.parse_args()


def normalize_base_path(value: str) -> str:
    trimmed = value.strip()
    if trimmed in ("", "/"):
        return ""
    return trimmed if trimmed.startswith("/") else f"/{trimmed}"


def http_get_json(url: str) -> Any:
    try:
        with urlopen(url) as response:
            status = getattr(response, "status", response.getcode())
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"smoke failed ({exc.code}) for {url}: {body}") from exc
    except URLError as exc:
        raise SystemExit(f"smoke failed for {url}: {exc.reason}") from exc

    if status != 200:
        raise SystemExit(f"smoke failed ({status}) for {url}: {body}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"smoke returned invalid JSON for {url}: {exc}") from exc


def main() -> int:
    args = parse_args()
    public_root = Path(args.public_root).resolve()
    inventory_path = public_root / "v0" / "repos" / "index.json"
    if not inventory_path.is_file():
        raise SystemExit(f"missing reviewed export inventory: {inventory_path}")

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    repositories = inventory.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise SystemExit("reviewed export inventory contains no repositories")
    links = repositories[0].get("links", {})
    query_template = links.get("queryTemplate")
    if not isinstance(query_template, str):
        raise SystemExit("reviewed export inventory contains no queryTemplate")

    deploy_url = args.deploy_url.rstrip("/")
    base_path = normalize_base_path(args.base_path)

    meta_url = f"{deploy_url}{base_path}/v0/meta.json"
    meta = http_get_json(meta_url)
    if meta.get("apiVersion") != "v0":
        raise SystemExit(f"unexpected apiVersion from {meta_url}: {meta.get('apiVersion')}")

    query_url = (
        f"{deploy_url}{query_template.replace('{dot_path}', 'repo.description')}"
    )
    query_response = http_get_json(query_url)
    if query_response.get("path") != "repo.description":
        raise SystemExit("deployed queryTemplate smoke returned unexpected path")
    self_link = query_response.get("links", {}).get("self")
    expected_prefix = base_path or "/"
    if not isinstance(self_link, str) or not self_link.startswith(expected_prefix):
        raise SystemExit(
            f"deployed queryTemplate smoke returned unexpected self link: {self_link}"
        )

    print(f"smoke ok: {meta_url}")
    print(f"smoke ok: {query_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
