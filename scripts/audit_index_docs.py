"""Offline documentation evidence and URL association signals, not verdicts.

These checks cover every record independently of random audit sampling. URL
identity mismatches require source inspection: custom domains, shared docs and
renames are legitimate. Never use these signals as automatic rejection gates.
"""

import json
import re
from typing import Any
from urllib.parse import unquote, urlsplit


def url_parts(value: str) -> tuple[str, str] | None:
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        return parsed.hostname.lower(), unquote(parsed.path).rstrip("/")
    except ValueError:
        return None


def identity_supported(url: str, identity: str, homepage: str) -> bool:
    parts = url_parts(url)
    if parts is None:
        return False
    host, path = parts
    _, owner, repo = identity.split("/")

    # Match whole host labels/path segments, never arbitrary substrings or
    # query strings (e.g. "uv" inside "uvicorn" is not identity evidence).
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    identities = {normalize(owner), normalize(repo)} - {""}
    components = {normalize(value) for value in [*host.split("."), *path.split("/")]}
    if identities & components:
        return True
    home = url_parts(homepage)
    if home is None or home[0] != host:
        return False
    # Repository metadata can corroborate a custom documentation domain.
    # On shared hosts require the homepage's project path, not just its host.
    shared = host in {"github.com", "gitlab.com", "bitbucket.org", "docs.rs", "readthedocs.org"}
    return not shared or bool(home[1] and (path == home[1] or path.startswith(home[1] + "/")))


def audit_docs(document: dict[str, Any], identity: str, evidence_text: str) -> list[dict[str, Any]]:
    findings = []
    docs = document.get("docs") or {}
    evidence = document.get("x", {}).get("dotrepo", {}).get("field_evidence", {})
    homepage = document.get("repo", {}).get("homepage") or ""
    for name, value in sorted(docs.items()):
        if not isinstance(value, str) or not value:
            continue
        field = f"docs.{name}"
        signals = []
        metadata = evidence.get(field) or {}
        try:
            matches = json.loads(metadata.get("valueJson", "null")) == value
        except (ValueError, TypeError):
            matches = False
        if not (
            matches
            and metadata.get("source")
            and metadata.get("reason")
            and metadata.get("method") in {"extracted", "inferred"}
            and metadata.get("checkedAt")
            and metadata["checkedAt"] == document.get("record", {}).get("generated_at")
        ):
            signals.append("missing-or-mismatched-field-evidence")
        if not any(field in line and value in line for line in evidence_text.splitlines()):
            signals.append("missing-specific-evidence-note")
        if url_parts(value) is not None and not identity_supported(value, identity, homepage):
            signals.append("url-identity-unconfirmed")
        if signals:
            findings.append(
                {"identity": identity, "field": field, "value": value, "signals": signals}
            )
    root = url_parts(docs.get("root") or "")
    start = url_parts(docs.get("getting_started") or "")
    if root and start and root[0] != start[0]:
        findings.append(
            {
                "identity": identity,
                "field": "docs.root",
                "value": docs["root"],
                "signals": ["docs-origins-disagree"],
            }
        )
    return findings


def audit_cross_record_targets(records: list[dict[str, Any]]) -> None:
    homepages: dict[tuple[str, str], list[str]] = {}
    for record in records:
        key = url_parts(record["homepageUrl"])
        if key:
            homepages.setdefault(key, []).append(record["identity"])
    for record in records:
        for field, value in sorted(record["docsUrls"].items()):
            key = url_parts(value)
            other = sorted(
                identity for identity in homepages.get(key, []) if identity != record["identity"]
            )
            if other:
                record["docsAuditFindings"].append(
                    {
                        "identity": record["identity"],
                        "field": f"docs.{field}",
                        "value": value,
                        "signals": ["target-matches-another-repository-homepage"],
                        "relatedIdentities": other,
                    }
                )
