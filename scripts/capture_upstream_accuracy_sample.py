#!/usr/bin/env -S uv run python
"""Freeze independently sourced GitHub facts for a preselected identity list.

Reads no dotrepo values. This evaluates structured metadata, not command accuracy.
Never regenerate gold from the output of the system being evaluated.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

import requests

from measure_public_factual_accuracy import WORKLOAD_SCHEMA


def repository_selection(text: str) -> tuple[list[str], str]:
    repositories = [line.strip() for line in text.splitlines() if line.strip()]
    if not repositories or len(set(repositories)) != len(repositories):
        raise ValueError("repository list must be nonempty and contain no duplicates")
    for identity in repositories:
        if not re.fullmatch(r"github\.com/[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+", identity):
            raise ValueError(f"invalid GitHub identity: {identity!r}")
        if identity.rsplit("/", 1)[1] in (".", ".."):
            raise ValueError(f"invalid GitHub identity: {identity!r}")
    digest = hashlib.sha256(("\n".join(repositories) + "\n").encode()).hexdigest()
    return repositories, (
        f"Explicit list of {len(repositories)} identities frozen before upstream capture; "
        f"normalized identity-list SHA-256: {digest}. Selection method is caller-supplied."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repositories", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sources-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        repositories, selection = repository_selection(args.repositories.read_text())
    except ValueError as err:
        parser.error(str(err))
    args.sources_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    if os.environ.get("GITHUB_TOKEN"):
        session.headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    checked = datetime.now(timezone.utc).isoformat()
    assertions = []
    for identity in repositories:
        host, owner, repo = identity.split("/")
        if host != "github.com":
            raise SystemExit("only GitHub identities are supported")
        url = f"https://api.github.com/repos/{owner}/{repo}"
        response = session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        source_path = args.sources_dir / f"{owner}--{repo}.json"
        # Freeze only relevant upstream metadata, not unrelated API payloads.
        source = {
            key: data.get(key)
            for key in ("full_name", "html_url", "description", "license", "visibility", "archived")
        }
        source["checkedAt"] = checked
        source_path.write_text(json.dumps(source, indent=2) + "\n")
        fields = {
            "repo.description": ("description", data.get("description")),
            "repo.visibility": ("visibility", data.get("visibility")),
            "x.github.archived": ("archived", data.get("archived")),
        }
        license_id = (data.get("license") or {}).get("spdx_id")
        if license_id and license_id != "NOASSERTION":
            fields["repo.license"] = ("license.spdx_id", license_id)
        for field, (locator, expected) in fields.items():
            if field == "repo.description" and not expected:
                continue  # An empty GitHub summary does not prove absence in README.
            assertions.append(
                {
                    "id": identity + ":" + field,
                    "repository": identity,
                    "path": field,
                    "expected": expected,
                    "source": {"url": url, "locator": locator, "checkedAt": checked},
                }
            )
    workload = {
        "schema": WORKLOAD_SCHEMA,
        "description": "Preselected upstream structured metadata sample; command accuracy is measured separately.",
        "selection": selection,
        "assertions": assertions,
    }
    args.output.write_text(json.dumps(workload, indent=2) + "\n")
    print(
        f"Captured {len(assertions)} assertions across {len({a['repository'] for a in assertions})} repositories"
    )


if __name__ == "__main__":
    main()
