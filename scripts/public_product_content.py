"""Render user-facing facts from exported profiles, never inferred marketing counts."""

import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def profiles(public_root: Path, inventory: dict):
    for entry in inventory.get("repositories", []):
        identity = entry["identity"]
        path = (
            public_root
            / "v0/repos"
            / identity["host"]
            / identity["owner"]
            / identity["repo"]
            / "profile.json"
        )
        if path.is_file():
            yield json.loads(path.read_text())


def record_status(record: dict, now: str) -> tuple[str, int | None]:
    try:
        checked = datetime.fromisoformat(record["generatedAt"].replace("Z", "+00:00"))
        exported = datetime.fromisoformat(now.replace("Z", "+00:00"))
        if checked.tzinfo is None or exported.tzinfo is None or checked > exported:
            return "unknown", None
        age = exported - checked
        return ("stale" if age.total_seconds() > 30 * 86400 else "fresh"), age.days
    except (KeyError, TypeError, ValueError, AttributeError):
        return "unknown", None


def freshness_summary(public_root: Path, inventory: dict, now: str) -> dict:
    counts = Counter()
    ages = []
    for profile in profiles(public_root, inventory):
        status, age = record_status(profile.get("record", {}), now)
        counts[status] += 1
        if age is not None:
            ages.append(age)
    missing = max(0, inventory.get("repositoryCount", 0) - sum(counts.values()))
    counts["unknown"] += missing
    return {
        "fresh": counts["fresh"],
        "stale": counts["stale"],
        "unknown": counts["unknown"],
        "oldestDays": max(ages) if ages else None,
        "evaluatedAt": now,
        "staleAfterDays": 30,
    }


def render_record_freshness(public_root: Path, inventory: dict, now: str) -> str:
    summary = freshness_summary(public_root, inventory, now)
    return f"""<div class="stat"><strong>{summary["fresh"]} records within 30 days</strong>
      <span>{summary["stale"]} stale · {summary["unknown"]} unknown record ages at export time.
      A new export does not refresh the underlying facts.</span></div>"""


def render_profile_example(public_root: Path, inventory: dict, base_path: str) -> str:
    candidates = list(profiles(public_root, inventory))
    if not candidates:
        return '<section class="panel section"><h2>Profile example</h2><p>No exported profile is available.</p></section>'
    profile = next(
        (
            p
            for p in candidates
            if p["identity"]["owner"] == "BurntSushi" and p["identity"]["repo"] == "ripgrep"
        ),
        candidates[0],
    )
    identity = profile["identity"]
    label = "/".join(identity[key] for key in ("host", "owner", "repo"))
    record = profile.get("record", {})
    status, age = record_status(record, profile.get("freshness", {}).get("generatedAt", ""))
    age_text = f"{age} days old" if age is not None else "age unknown"
    rows = []
    for label_text, value in [
        ("Purpose", profile.get("purpose")),
        ("Build", profile.get("execution", {}).get("build")),
        ("Test", profile.get("execution", {}).get("test")),
        ("Documentation", profile.get("docs", {}).get("root")),
        ("Security reporting", profile.get("ownership", {}).get("securityContact")),
    ]:
        rows.append(
            f'<div class="endpoint"><strong>{html.escape(label_text)}</strong><span>{html.escape(value or "Unknown — inspect upstream sources")}</span></div>'
        )
    evidence = record.get("evidencePath")
    evidence_link = (
        f'<a href="https://github.com/maxwellsantoro/dotrepo/blob/main/index/{html.escape(evidence, quote=True)}">Inspect supporting evidence</a>'
        if evidence
        else "Supporting evidence unavailable"
    )
    return f'''<section class="panel section"><h2>A profile from this export</h2>
      <p><strong>{html.escape(label)}</strong> · {html.escape(status)} · {age_text}</p>
      <div class="endpoint-list">{"".join(rows)}</div>
      <p>Record generated: {html.escape(record.get("generatedAt") or "unknown")}.
      Status: {html.escape(profile.get("trust", {}).get("selectedStatus", "unknown"))}.
      Verification records pipeline checks, not human review or a guarantee of correctness.</p>
      <p>{evidence_link} · <a href="{html.escape(base_path + "/v0/repos/" + label + "/profile.json", quote=True)}">Full profile JSON</a></p>
      </section>'''
