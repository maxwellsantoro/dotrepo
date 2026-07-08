"""Shared language-family classification for index and public quality scripts.

Classifies by the *dominant* language only (`repo.languages[0]`), not by whether
a language appears anywhere in the list. GitHub's languages endpoint reports
byte counts, and `dotrepo-crawler` orders `repo.languages` by byte count
descending (see `crates/dotrepo-crawler/src/github.rs`'s
`languages_by_byte_count_descending`) so index `[0]` is the dominant language.

An any-occurrence check previously misclassified repositories with a minor
vendored language (for example a few Rust files in an otherwise Go or TypeScript
project) into the wrong family — found via `scripts/audit_index_sample.py`
flagging docker/awesome-compose and firecrawl/firecrawl as "Rust" family.

Import from sibling scripts with ``from language_family import ...`` (sys.path[0]
is the script directory when running ``uv run python scripts/<name>.py``).
"""

from __future__ import annotations

from typing import Any

LANGUAGE_FAMILIES = ("Rust", "TypeScript / JavaScript", "Python", "Go", "Other")


def languages_from_record(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return []
    raw = record.get("repo", {}).get("languages") if isinstance(record.get("repo"), dict) else None
    if not isinstance(raw, list):
        return []
    return [str(language).lower() for language in raw]


def dominant_language(record: Any) -> str:
    languages = languages_from_record(record)
    return languages[0] if languages else ""


def inferred_language_family(record: Any) -> str:
    dominant = dominant_language(record)
    if dominant == "rust":
        return "Rust"
    if dominant == "go":
        return "Go"
    if dominant in {"python", "cython"}:
        return "Python"
    if dominant in {"typescript", "javascript", "tsx", "jsx", "vue", "svelte"}:
        return "TypeScript / JavaScript"
    return "Other"
