#!/usr/bin/env -S uv run python

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "dotrepo-public-lookup-workload/v0"


BASE_FIELDS = ["repo.description", "repo.homepage"]
PROFILE_TO_MANIFEST_FIELDS = [
    ("hasLicense", "repo.license"),
    ("hasBuild", "repo.build"),
    ("hasTest", "repo.test"),
    ("hasDocs", "docs.root"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a representative public lookup workload from exported profiles."
    )
    parser.add_argument(
        "--public-root",
        default="public",
        help="Public export root containing v0/repos/index.json (default: public)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum repositories to include; 0 means all repositories",
    )
    parser.add_argument(
        "--min-fields",
        type=int,
        default=2,
        help="Minimum fields required for a task to be included",
    )
    parser.add_argument("--output", required=True, help="Output workload JSON path")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"failed to parse JSON in {path}: {exc}") from exc


def repository_from_identity(identity: dict[str, Any]) -> str:
    try:
        return "/".join([identity["host"], identity["owner"], identity["repo"]])
    except KeyError as exc:
        raise SystemExit(f"inventory entry missing identity key: {exc}") from exc


def profile_path(public_root: Path, repository: str) -> Path:
    host, owner, repo = repository.split("/", 2)
    return public_root / "v0" / "repos" / host / owner / repo / "profile.json"


def workload_fields(profile: dict[str, Any]) -> list[str]:
    completeness = profile.get("completeness") or {}
    ownership = profile.get("ownership") or {}
    fields = list(BASE_FIELDS)
    for signal, field in PROFILE_TO_MANIFEST_FIELDS:
        if completeness.get(signal):
            fields.append(field)
    if completeness.get("hasSecurityContact") and ownership.get("securityContact"):
        fields.append("owners.security_contact")
    if isinstance(ownership.get("maintainers"), list) and ownership["maintainers"]:
        fields.append("owners.maintainers")
    elif ownership.get("team"):
        fields.append("owners.team")
    if profile.get("languages"):
        fields.append("repo.languages")
    if profile.get("topics"):
        fields.append("repo.topics")
    return fields


def build_workload(public_root: Path, limit: int = 0, min_fields: int = 2) -> dict[str, Any]:
    inventory_path = public_root / "v0" / "repos" / "index.json"
    inventory = load_json(inventory_path)
    repositories = inventory.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise SystemExit(f"inventory must contain a non-empty repositories array: {inventory_path}")

    tasks = []
    for entry in sorted(repositories, key=lambda item: repository_from_identity(item.get("identity") or {})):
        repository = repository_from_identity(entry.get("identity") or {})
        profile = load_json(profile_path(public_root, repository))
        fields = workload_fields(profile)
        if len(fields) < min_fields:
            continue
        tasks.append(
            {
                "id": repository.replace("/", "-"),
                "repository": repository,
                "fields": fields,
            }
        )
        if limit > 0 and len(tasks) >= limit:
            break

    if not tasks:
        raise SystemExit("no workload tasks matched the requested constraints")

    return {
        "schema": SCHEMA,
        "description": "Generated from a dotrepo public export inventory and profile completeness signals.",
        "source": {
            "publicRoot": public_root.as_posix(),
            "inventory": "v0/repos/index.json",
            "limit": limit,
            "minFields": min_fields,
            "repositoryCount": len(repositories),
        },
        "tasks": tasks,
    }


def main() -> None:
    args = parse_args()
    if args.limit < 0:
        raise SystemExit("--limit must be >= 0")
    if args.min_fields < 1:
        raise SystemExit("--min-fields must be >= 1")
    workload = build_workload(Path(args.public_root), limit=args.limit, min_fields=args.min_fields)
    Path(args.output).write_text(json.dumps(workload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
