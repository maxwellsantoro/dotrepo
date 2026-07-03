#!/usr/bin/env -S uv run python

import argparse
import html
import json
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from public_site_content import ARTICLES

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_BLOB_PREFIX = "https://github.com/maxwellsantoro/dotrepo/blob/main/"

DOCS_SECTIONS = [
    {
        "title": "Start here",
        "items": [
            {
                "label": "Project overview",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/README.md",
                "summary": "What dotrepo is, what ships, and the shortest paths for maintainers, contributors, and consumers.",
                "kind": "Repo doc",
            },
            {
                "label": "Install",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/docs/install.md",
                "summary": "Platform bundles, MCP and LSP binaries, and the VS Code extension package.",
                "kind": "Repo doc",
            },
            {
                "label": "Maintainer happy path",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/docs/maintainer-happy-path.md",
                "summary": "The canonical init, import, validate, trust, and generate-check loop for repository owners.",
                "kind": "Repo doc",
            },
        ],
    },
    {
        "title": "Trust and protocol",
        "items": [
            {
                "label": "Trust model",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/docs/trust-model.md",
                "summary": "Why provenance, precedence, and conflict visibility matter more than a new file extension.",
                "kind": "Repo doc",
            },
            {
                "label": "Roadmap",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/ROADMAP.md",
                "summary": "The mission, operating principles, product milestones, and path from protocol to shared research infrastructure.",
                "kind": "Repo doc",
            },
            {
                "label": "Public surface architecture",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/docs/public-surface.md",
                "summary": "How the hosted homepage, inventory, summary, trust, and query surfaces are built from one export family.",
                "kind": "Repo doc",
            },
        ],
    },
    {
        "title": "Live public surface",
        "items": [
            {
                "label": "Snapshot metadata",
                "href": "/v0/meta.json",
                "summary": "Freshness, snapshot digest, and expiry metadata for the currently hosted export.",
                "kind": "On-site",
            },
            {
                "label": "Repository inventory",
                "href": "/v0/repos/index.json",
                "summary": "The live indexed repository set with summary, trust, and query entrypoints.",
                "kind": "On-site",
            },
            {
                "label": "Public export examples",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/docs/public-export-examples.md",
                "summary": "Concrete response examples for inventory, repository summary, trust, and query routes.",
                "kind": "Repo doc",
            },
        ],
    },
    {
        "title": "Autonomous index",
        "items": [
            {
                "label": "Public index",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/index/README.md",
                "summary": "Index rules, evidence expectations, autonomous publication, and maintainer handoff.",
                "kind": "Repo doc",
            },
            {
                "label": "Crawler and escalation design",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/docs/factual-crawl-automation.md",
                "summary": "The deterministic-first pipeline, bounded model escalation, publication gates, and trust semantics.",
                "kind": "Repo doc",
            },
            {
                "label": "Maintainer-claim workflow",
                "href": "https://github.com/maxwellsantoro/dotrepo/blob/main/docs/maintainer-claim-review-workflow.md",
                "summary": "The reviewer path for accepted maintainer claims and canonical handoff decisions.",
                "kind": "Repo doc",
            },
        ],
    },
]


def validate_first_party_document_links() -> None:
    missing = []
    for section in DOCS_SECTIONS:
        for item in section["items"]:
            href = item["href"]
            if href.startswith(REPO_BLOB_PREFIX):
                path = REPO_ROOT / href.removeprefix(REPO_BLOB_PREFIX)
                if not path.is_file():
                    missing.append(path)
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise ValueError(f"missing first-party documentation links: {paths}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the dotrepo public site for an exported public tree."
    )
    parser.add_argument(
        "--input",
        dest="input_dir",
        default="public",
        help="Path to the exported public tree (default: public)",
    )
    parser.add_argument(
        "--index-root",
        default="index",
        help="Path to the checked-in index root used for progress counters (default: index)",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path}")
    return json.loads(path.read_text())


def load_optional_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def shorten_digest(value: str) -> str:
    if len(value) <= 20:
        return value
    return f"{value[:12]}...{value[-10:]}"


def format_timestamp_for_humans(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def compact_text(value: str, *, limit: int) -> str:
    cleaned = " ".join(value.strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}..."


def format_count(value: object) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "unknown"
    return f"{number:,}"


def format_bytes(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    units = ["B", "KB", "MB", "GB"]
    unit = units[0]
    for unit in units:
        if abs(number) < 1024 or unit == units[-1]:
            break
        number /= 1024
    if unit == "B":
        return f"{int(number):,} {unit}"
    return f"{number:.1f} {unit}"


def format_estimated_tokens(value: object) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if abs(number) >= 1_000_000:
        return f"~{number / 1_000_000:.1f}M"
    if abs(number) >= 1_000:
        return f"~{number / 1_000:.1f}K"
    return f"~{number:,}"


def is_low_signal_title(title: str) -> bool:
    normalized = title.strip().lower()
    return normalized in {"a project", "sponsors", "project", "repository"}


def is_low_signal_description(description: str) -> bool:
    normalized = description.strip().lower()
    return normalized.endswith("/readme.md") or normalized in {"readme", "readme.md"}


def repository_card_title(entry: dict, identity: dict) -> str:
    candidate = str(entry.get("name") or "").strip()
    if candidate and not is_low_signal_title(candidate):
        return candidate
    return str(identity.get("repo") or "unknown").strip() or "unknown"


def repository_card_description(entry: dict) -> str:
    fallback = "Repository metadata exported from the validated dotrepo index."
    candidate = str(entry.get("description") or "").strip()
    if not candidate or is_low_signal_description(candidate):
        return fallback
    return compact_text(candidate, limit=240)


def normalize_site_base_path(value: str) -> str:
    trimmed = value.strip()
    if trimmed in ("", "/"):
        return ""
    return trimmed if trimmed.startswith("/") else f"/{trimmed}"


def site_href(base_path: str, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    normalized = path if path.startswith("/") else f"/{path}"
    if base_path:
        return f"{base_path}{normalized}"
    return normalized


def query_input_href(base_path: str, entry: dict) -> str:
    host, owner, repo = repository_segments(entry)
    if not all((host, owner, repo)):
        return "#"
    return site_href(base_path, f"/query-input/{host}/{owner}/{repo}.json")


def detect_site_base_path(inventory: dict) -> str:
    marker = "/v0/"
    for entry in inventory.get("repositories", []):
        links = entry.get("links", {})
        for key in ("self", "trust", "queryTemplate"):
            value = links.get(key)
            if not isinstance(value, str):
                continue
            path = urlparse(value).path or value
            index = path.find(marker)
            if index >= 0:
                return normalize_site_base_path(path[:index])
    return ""


def repository_segments(entry: dict) -> tuple[str, str, str]:
    identity = entry.get("identity", {})
    return (
        str(identity.get("host", "")),
        str(identity.get("owner", "")),
        str(identity.get("repo", "")),
    )


def load_repository_surface(input_dir: Path, entry: dict, filename: str) -> dict:
    host, owner, repo = repository_segments(entry)
    return load_json(input_dir / "v0" / "repos" / host / owner / repo / filename)


def find_repository_entry(inventory: dict, host: str, owner: str, repo: str) -> dict | None:
    for entry in inventory.get("repositories", []):
        if repository_segments(entry) == (host, owner, repo):
            return entry
    return None


def normalize_language_family(languages: list[object]) -> str:
    for language in languages:
        normalized = str(language).strip().lower()
        if normalized == "rust":
            return "Rust"
        if normalized in {"typescript", "javascript"}:
            return "TypeScript/JS"
        if normalized == "python":
            return "Python"
        if normalized == "go":
            return "Go"
    return "Other"


def load_index_progress(index_root: Path) -> dict:
    repo_root = index_root / "repos"
    if not repo_root.is_dir():
        raise SystemExit(f"missing required index root: {repo_root}")

    language_counts: Counter[str] = Counter()
    reviewed_or_better_count = 0
    imported_or_inferred_count = 0
    for record_path in sorted(repo_root.glob("*/*/*/record.toml")):
        document = tomllib.loads(record_path.read_text())
        record = document.get("record", {})
        repo = document.get("repo", {})
        languages = repo.get("languages", [])
        if not isinstance(languages, list):
            languages = []
        language_counts[normalize_language_family(languages)] += 1
        status = record.get("status")
        if status in {"reviewed", "verified", "canonical"}:
            reviewed_or_better_count += 1
        if status in {"imported", "inferred"}:
            imported_or_inferred_count += 1

    accepted_claim_count = 0
    for claim_path in sorted(repo_root.glob("*/*/*/claims/*/claim.toml")):
        document = tomllib.loads(claim_path.read_text())
        claim = document.get("claim", {})
        if claim.get("state") == "accepted":
            accepted_claim_count += 1

    family_order = ["Rust", "TypeScript/JS", "Python", "Go", "Other"]
    language_mix = " · ".join(
        f"{family} {language_counts[family]}" for family in family_order if language_counts[family]
    )
    if not language_mix:
        language_mix = "No indexed records yet."

    return {
        "reviewedOrBetterCount": reviewed_or_better_count,
        "importedOrInferredCount": imported_or_inferred_count,
        "languageMix": language_mix,
        "acceptedClaimCount": accepted_claim_count,
    }


def build_query_example(input_dir: Path, inventory: dict) -> tuple[str, str, str]:
    repositories = inventory.get("repositories", [])
    if not repositories:
        return "#", "#", html.escape(json.dumps({"path": "repo.description"}, indent=2))

    summary = load_repository_surface(input_dir, repositories[0], "index.json")
    selection = summary.get("selection", {})
    selected_record = selection.get("record", {})
    record = selected_record.get("record", {})
    trust = record.get("trust", {})
    query_url = summary.get("links", {}).get("queryTemplate", "#").replace(
        "{dot_path}", "repo.description"
    )
    query_input_url = query_input_href(detect_site_base_path(inventory), repositories[0])
    example = {
        "path": "repo.description",
        "value": compact_text(str(summary.get("repository", {}).get("description") or ""), limit=220),
        "selection": {
            "reason": selection.get("reason"),
            "recordStatus": record.get("status"),
            "trust": {
                "confidence": trust.get("confidence"),
                "provenance": trust.get("provenance", [])[:3],
                "notes": compact_text(str(trust.get("notes") or ""), limit=220),
            },
            "evidencePath": selected_record.get("artifacts", {}).get("evidencePath"),
        },
        "conflicts": summary.get("conflicts", []),
    }
    return query_url, query_input_url, html.escape(json.dumps(example, indent=2))


def build_featured_trust_example(input_dir: Path, inventory: dict) -> dict:
    repositories = inventory.get("repositories", [])
    if not repositories:
        return {
            "name": "No featured repository yet",
            "label": "no featured repository",
            "summaryUrl": "#",
            "trustUrl": "#",
            "queryUrl": "#",
            "description": "The first accepted maintainer-claim example has not been exported yet.",
            "proofJson": html.escape(json.dumps({"selection": {"claim": None}}, indent=2)),
            "claimState": "none",
            "handoff": "none",
            "trustConfidence": "unknown",
            "provenance": "unknown",
            "notes": "No accepted maintainer-owned claim is available in the current export.",
            "reviewPath": None,
            "evidencePath": None,
        }

    entry = find_repository_entry(inventory, "github.com", "maxwellsantoro", "ries-rs")
    if entry is None:
        entry = repositories[0]

    summary = load_repository_surface(input_dir, entry, "index.json")
    trust = load_repository_surface(input_dir, entry, "trust.json")
    repository = summary.get("repository", {})
    selection = trust.get("selection", {})
    selected_record = selection.get("record", {})
    record = selected_record.get("record", {})
    trust_record = record.get("trust", {})
    claim = selected_record.get("claim", {})
    artifacts = selected_record.get("artifacts", {})
    identity = trust.get("identity", {})
    links = trust.get("links", {})
    query_url = query_input_href(detect_site_base_path(inventory), entry)
    proof = {
        "identity": {
            "host": identity.get("host"),
            "owner": identity.get("owner"),
            "repo": identity.get("repo"),
        },
        "selection": {
            "reason": selection.get("reason"),
            "recordStatus": record.get("status"),
            "claim": {
                "state": claim.get("state"),
                "handoff": claim.get("handoff"),
            },
            "trust": {
                "confidence": trust_record.get("confidence"),
                "provenance": trust_record.get("provenance", [])[:3],
                "notes": compact_text(str(trust_record.get("notes") or ""), limit=220),
            },
            "artifacts": {
                "reviewPath": claim.get("reviewPath"),
                "evidencePath": artifacts.get("evidencePath"),
            },
        },
        "conflicts": trust.get("conflicts", []),
    }
    host = str(identity.get("host", "")).strip()
    owner = str(identity.get("owner", "")).strip()
    repo = str(identity.get("repo", "")).strip()
    label = "/".join(segment for segment in (host, owner, repo) if segment) or "unknown"
    provenance = trust_record.get("provenance", [])
    if isinstance(provenance, list):
        provenance_label = ", ".join(str(item) for item in provenance) if provenance else "unknown"
    else:
        provenance_label = str(provenance)
    return {
        "name": repository_card_title(entry, identity),
        "label": label,
        "summaryUrl": links.get("repository", "#"),
        "trustUrl": links.get("self", "#"),
        "queryUrl": query_url,
        "description": compact_text(str(repository.get("description") or ""), limit=320),
        "proofJson": html.escape(json.dumps(proof, indent=2)),
        "claimState": str(claim.get("state") or "unknown"),
        "handoff": str(claim.get("handoff") or "unknown"),
        "trustConfidence": str(trust_record.get("confidence") or "unknown"),
        "provenance": provenance_label,
        "notes": compact_text(str(trust_record.get("notes") or ""), limit=220),
        "reviewPath": claim.get("reviewPath"),
        "evidencePath": artifacts.get("evidencePath"),
    }


def render_site_header(base_path: str, active: str | None = None) -> str:
    links = [
        ("home", site_href(base_path, "/"), "Home"),
        ("docs", site_href(base_path, "/docs/"), "Docs"),
        ("writing", site_href(base_path, "/writing/"), "Writing"),
        ("repositories", site_href(base_path, "/repositories/"), "Repositories"),
        ("efficiency", site_href(base_path, "/efficiency/"), "Efficiency"),
        ("github", "https://github.com/maxwellsantoro/dotrepo", "GitHub"),
        ("snapshot", site_href(base_path, "/v0/meta.json"), "Snapshot"),
    ]
    items = []
    for key, href, label in links:
        current = ' aria-current="page"' if active == key else ""
        items.append(f'<a href="{href}"{current}>{label}</a>')
    return """
    <header class="nav" aria-label="Top navigation">
      <div class="brand">
        <a class="brand__mark" href="{home_href}" aria-label="dotrepo — home"><span class="brand__dot" aria-hidden="true"></span><span>repo</span></a>
        <span class="brand__tag">open metadata protocol</span>
      </div>
      <nav class="nav__links">
        {items}
      </nav>
    </header>
    """.format(home_href=site_href(base_path, "/"), items="\n        ".join(items)).strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_homepage_snapshot_state(meta: dict, inventory: dict) -> str:
    payload = {
        "apiVersion": meta.get("apiVersion"),
        "generatedAt": meta.get("generatedAt"),
        "snapshotDigest": meta.get("snapshotDigest"),
        "staleAfter": meta.get("staleAfter"),
        "repositoryCount": inventory.get("repositoryCount"),
    }
    return json.dumps(payload, separators=(",", ":"))


def render_pagedigest_stats_dashboard(stats: dict, base_path: str) -> str:
    pagedigest = stats.get("pagedigest")
    if not isinstance(pagedigest, dict):
        return """
    <section class="panel section">
      <h2>PageDigest dogfood</h2>
      <p class="section__intro">
        The public stats endpoint is ready for PageDigest economics, but this
        checked-in public tree was rendered before the first stats-bearing
        export. Once <code>/v0/stats.json</code> is present, this section will
        publish records covered, skipped fetches, avoided bytes, and estimated
        tokens avoided directly from the export.
      </p>
      <p class="section__note">
        Contract endpoint: <code>/v0/stats.json</code>.
      </p>
    </section>
        """.strip()

    return """
    <section class="panel section">
      <h2>PageDigest dogfood</h2>
      <p class="section__intro">
        dotrepo publishes thousands of small JSON records. PageDigest lets a
        consumer check the whole covered set first, then fetch only records
        whose content actually changed. These numbers come from the current
        export's <a href="{stats_href}"><code>/v0/stats.json</code></a>.
      </p>
      <div class="stat-grid stat-grid--wide">
        <div class="stat">
          <strong>{records_covered} tracked records</strong>
          <span>Records covered by <code>/.well-known/pagedigest.json</code>.</span>
        </div>
        <div class="stat">
          <strong>{records_needing_fetch} needing fetch</strong>
          <span>New or changed records in this export cycle.</span>
        </div>
        <div class="stat">
          <strong>{fetches_avoided} fetches avoided</strong>
          <span>Covered records that a PageDigest-aware consumer can skip.</span>
        </div>
        <div class="stat">
          <strong>{bytes_avoided} avoided</strong>
          <span>Payload bytes skipped this cycle out of {bytes_covered} covered.</span>
        </div>
        <div class="stat">
          <strong>{tokens_avoided} tokens avoided</strong>
          <span>Coarse bytes ÷ 4 estimate for agent-context savings.</span>
        </div>
        <div class="stat">
          <strong>site_rev {site_rev}</strong>
          <span>Manifest size {manifest_bytes}; generated {generated}.</span>
        </div>
      </div>
    </section>
    """.format(
        stats_href=site_href(base_path, "/v0/stats.json"),
        records_covered=html.escape(format_count(pagedigest.get("recordsCovered"))),
        records_needing_fetch=html.escape(format_count(pagedigest.get("recordsNeedingFetch"))),
        fetches_avoided=html.escape(format_count(pagedigest.get("fetchesAvoided"))),
        bytes_avoided=html.escape(format_bytes(pagedigest.get("bytesAvoided"))),
        bytes_covered=html.escape(format_bytes(pagedigest.get("bytesCovered"))),
        tokens_avoided=html.escape(format_estimated_tokens(pagedigest.get("estimatedTokensAvoided"))),
        site_rev=html.escape(format_count(pagedigest.get("siteRev"))),
        manifest_bytes=html.escape(format_bytes(pagedigest.get("manifestBytes"))),
        generated=html.escape(format_timestamp_for_humans(str(pagedigest.get("generated", "unknown")))),
    ).strip()


def render_writing_cards(base_path: str) -> str:
    cards = []
    for article in ARTICLES:
        path = site_href(base_path, f"/writing/{article['slug']}/")
        companion_url = article.get("companion_url")
        companion_link = (
            f'<a href="{html.escape(str(companion_url))}">Companion essay</a>'
            if companion_url
            else ""
        )
        links = [
            f'<a href="{html.escape(path)}" aria-label="Read {html.escape(str(article["title"]), quote=True)}">Read article</a>'
        ]
        if companion_link:
            links.append(companion_link)
        cards.append(
            """
            <article class="repo-card">
              <div class="repo-card__head">
                <p class="repo-card__eyebrow">Writing</p>
                <h3>{title}</h3>
                <p class="repo-card__path">{published}</p>
              </div>
              <p class="repo-card__description">{summary}</p>
              <div class="repo-card__links">
                {links}
              </div>
            </article>
            """.format(
                title=html.escape(str(article["title"])),
                published=html.escape(str(article["published"])),
                summary=html.escape(str(article["summary"])),
                links="\n                ".join(links),
            ).strip()
        )
    return "\n".join(cards)


def render_docs_cards(base_path: str) -> str:
    cards = []
    for section in DOCS_SECTIONS:
        item_markup = []
        for item in section["items"]:
            href = site_href(base_path, str(item["href"]))
            item_markup.append(
                """
                <article class="doc-item">
                  <div class="doc-item__head">
                    <h3>{label}</h3>
                    <span>{kind}</span>
                  </div>
                  <p>{summary}</p>
                  <a href="{href}" aria-label="Open {aria_label}">Open</a>
                </article>
                """.format(
                    label=html.escape(str(item["label"])),
                    kind=html.escape(str(item["kind"])),
                    summary=html.escape(str(item["summary"])),
                    href=html.escape(href),
                    aria_label=html.escape(str(item["label"]), quote=True),
                ).strip()
            )
        cards.append(
            """
            <section class="panel section">
              <h2>{title}</h2>
              <div class="doc-grid">
                {items}
              </div>
            </section>
            """.format(
                title=html.escape(str(section["title"])),
                items="\n                ".join(item_markup),
            ).strip()
        )
    return "\n    ".join(cards)


def render_repository_cards(
    inventory: dict, *, base_path: str = "", limit: int | None = None
) -> str:
    cards = []
    repositories = inventory.get("repositories", [])
    if limit is not None:
        repositories = repositories[:limit]
    for entry in repositories:
        identity = entry.get("identity", {})
        name = repository_card_title(entry, identity)
        description = repository_card_description(entry)
        host = identity.get("host", "")
        owner = identity.get("owner", "")
        repo = identity.get("repo", "")
        label = f"{host}/{owner}/{repo}".strip("/")
        links = entry.get("links", {})
        summary = links.get("self", "#")
        trust = links.get("trust", "#")
        query = query_input_href(base_path, entry)
        aria_label = html.escape(label or str(name), quote=True)
        cards.append(
            """
            <article class="repo-card">
              <div class="repo-card__head">
                <p class="repo-card__eyebrow">Indexed repository</p>
                <h3>{name}</h3>
                <p class="repo-card__path">{label}</p>
              </div>
              <p class="repo-card__description">{description}</p>
              <div class="repo-card__links">
                <a href="{summary}" aria-label="Open {aria_label} summary">Summary</a>
                <a href="{trust}" aria-label="Open {aria_label} trust report">Trust</a>
                <a href="{query}" aria-label="Open {aria_label} query input data">Query input</a>
              </div>
            </article>
            """.format(
                name=html.escape(str(name)),
                label=html.escape(label),
                description=html.escape(str(description)),
                summary=html.escape(summary),
                trust=html.escape(trust),
                query=html.escape(query),
                aria_label=aria_label,
            ).strip()
        )
    return "\n".join(cards)


def render_lookup_panel(base_path: str) -> str:
    base_path_json = json.dumps(base_path)
    return f"""
      <div class="lookup-shell">
        <article class="lookup-card">
          <h3>Paste a repository URL or identity</h3>
          <p class="section__intro">Open the live hosted summary or trust surface directly from the current public index. The same public origin also powers the MCP <code>dotrepo.lookup</code> tool.</p>
          <form class="lookup-form" id="repo-lookup-form">
            <label class="lookup-field" for="repo-lookup-input">
              <span>Repository</span>
              <input id="repo-lookup-input" name="repository" type="text" placeholder="github.com/BurntSushi/ripgrep" autocomplete="off" spellcheck="false" required>
            </label>
            <div class="lookup-actions">
              <button class="cta cta--primary lookup-button" type="submit">Open summary</button>
              <button class="cta cta--secondary lookup-button" type="button" id="repo-lookup-trust">Open trust</button>
            </div>
            <p class="lookup-feedback" id="repo-lookup-feedback">Accepted inputs: <code>owner/repo</code>, <code>host/owner/repo</code>, a GitHub URL, or a hosted dotrepo summary or trust URL.</p>
          </form>
        </article>
        <article class="lookup-card">
          <h3>Examples</h3>
          <div class="endpoint-list">
            <div class="endpoint">
              <code>BurntSushi/ripgrep</code>
              <span>Defaults to <code>github.com</code> for shorthand input.</span>
            </div>
            <div class="endpoint">
              <code>github.com/astral-sh/uv</code>
              <span>Explicit host plus identity segments.</span>
            </div>
            <div class="endpoint">
              <code>https://github.com/pydantic/pydantic</code>
              <span>Full repository URL.</span>
            </div>
            <div class="endpoint">
              <code>https://dotrepo.org/v0/repos/github.com/BurntSushi/ripgrep/index.json</code>
              <span>Hosted summary or trust URL pasted back into the lookup box.</span>
            </div>
          </div>
        </article>
      </div>
      <script>
        (() => {{
          const basePath = {base_path_json};
          const form = document.getElementById("repo-lookup-form");
          const input = document.getElementById("repo-lookup-input");
          const feedback = document.getElementById("repo-lookup-feedback");
          const trustButton = document.getElementById("repo-lookup-trust");

          function trimRepoSuffix(value) {{
            return value.endsWith(".git") ? value.slice(0, -4) : value;
          }}

          function assertSegment(label, value) {{
            if (!value || value.includes("/")) {{
              throw new Error(`Invalid ${{label}} segment.`);
            }}
            return value;
          }}

          function parseLookupTarget(rawValue) {{
            const value = rawValue.trim();
            if (!value) {{
              throw new Error("Enter a repository URL or host/owner/repo.");
            }}

            if (value.includes("/v0/repos/")) {{
              const hostedMatch = value.match(/\\/v0\\/repos\\/([^/]+)\\/([^/]+)\\/([^/]+)\\/(?:index|trust)\\.json$/);
              if (hostedMatch) {{
                return {{
                  host: assertSegment("host", hostedMatch[1]),
                  owner: assertSegment("owner", hostedMatch[2]),
                  repo: assertSegment("repo", trimRepoSuffix(hostedMatch[3])),
                }};
              }}
            }}

            let parsedUrl = null;
            if (/^[a-z][a-z0-9+.-]*:\\/\\//i.test(value)) {{
              parsedUrl = new URL(value);
            }} else if (value.includes("/") && value.includes(".")) {{
              parsedUrl = new URL(`https://${{value.replace(/^\\/+/, "")}}`);
            }}

            if (parsedUrl) {{
              const pathSegments = parsedUrl.pathname.split("/").filter(Boolean);
              if (pathSegments.length < 2) {{
                throw new Error("Repository URLs must include owner and repo segments.");
              }}
              return {{
                host: assertSegment("host", parsedUrl.hostname),
                owner: assertSegment("owner", pathSegments[0]),
                repo: assertSegment("repo", trimRepoSuffix(pathSegments[1])),
              }};
            }}

            const segments = value.replace(/^\\/+|\\/+$/g, "").split("/").filter(Boolean);
            if (segments.length === 2) {{
              return {{
                host: "github.com",
                owner: assertSegment("owner", segments[0]),
                repo: assertSegment("repo", trimRepoSuffix(segments[1])),
              }};
            }}
            if (segments.length >= 3) {{
              return {{
                host: assertSegment("host", segments[0]),
                owner: assertSegment("owner", segments[1]),
                repo: assertSegment("repo", trimRepoSuffix(segments[2])),
              }};
            }}
            throw new Error("Use owner/repo, host/owner/repo, or a full repository URL.");
          }}

          function buildDestination(kind, target) {{
            const suffix = kind === "trust" ? "trust.json" : "index.json";
            return `${{basePath}}/v0/repos/${{encodeURIComponent(target.host)}}/${{encodeURIComponent(target.owner)}}/${{encodeURIComponent(target.repo)}}/${{suffix}}`;
          }}

          function openLookup(kind) {{
            try {{
              const target = parseLookupTarget(input.value);
              feedback.dataset.state = "ready";
              feedback.textContent = `Opening ${{kind}} for ${{target.host}}/${{target.owner}}/${{target.repo}}`;
              window.location.assign(buildDestination(kind, target));
            }} catch (error) {{
              feedback.dataset.state = "error";
              feedback.textContent = error instanceof Error ? error.message : "Lookup failed.";
            }}
          }}

          form.addEventListener("submit", (event) => {{
            event.preventDefault();
            openLookup("summary");
          }});

          trustButton.addEventListener("click", () => {{
            openLookup("trust");
          }});
        }})();
      </script>
    """.strip()


def render_repositories_index(inventory: dict, base_path: str) -> str:
    inventory_href = site_href(base_path, "/v0/repos/index.json")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='20' fill='%23141414'/%3E%3C/svg%3E">
  <title>Repositories · dotrepo</title>
  <meta name="description" content="Browse and search repositories in the current validated dotrepo public export.">
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f1e8;
      --paper-strong: #efe6d7;
      --ink: #16181b;
      --muted: #5c635d;
      --panel: rgba(255, 251, 244, 0.84);
      --line: rgba(54, 46, 28, 0.14);
      --accent: #116466;
      --accent-strong: #0d494b;
      --signal: #c4572e;
      --shadow: 0 18px 60px rgba(23, 27, 31, 0.12);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(17, 100, 102, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(196, 87, 46, 0.12), transparent 30%),
        linear-gradient(180deg, #fbf6ec 0%, var(--paper) 54%, var(--paper-strong) 100%);
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }}
    a {{ color: inherit; text-decoration: none; }}
    code {{ font-family: "SFMono-Regular", "JetBrains Mono", "Cascadia Code", monospace; }}
    .page {{ max-width: 1180px; margin: 0 auto; padding: 28px 18px 80px; }}
    .nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 30px;
    }}
    .brand {{ display: flex; align-items: baseline; gap: 12px; }}
    .brand__mark {{
      display: inline-flex;
      align-items: baseline;
      gap: 0.06em;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 1.4rem;
      font-weight: 500;
      letter-spacing: -0.01em;
    }}
    .brand__dot {{
      display: inline-block;
      width: 0.40em;
      height: 0.40em;
      border-radius: 50%;
      background: currentColor;
      flex-shrink: 0;
      translate: 0 -0.05em;
    }}
    .brand__tag {{
      font-size: 0.88rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .nav__links {{ display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 12px; }}
    .nav__links a {{
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.48);
    }}
    .nav__links a[aria-current="page"] {{
      background: linear-gradient(135deg, var(--accent) 0%, #0b4b5a 100%);
      color: white;
      border-color: transparent;
    }}
    .panel {{
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}
    .hero {{ padding: 34px; display: grid; gap: 16px; }}
    .eyebrow {{
      margin: 0;
      color: var(--accent-strong);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.78rem;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: clamp(2.8rem, 7vw, 5rem);
      line-height: 0.95;
      letter-spacing: -0.05em;
    }}
    .hero p {{ margin: 0; color: #273038; font-size: 1.08rem; line-height: 1.75; max-width: 46rem; }}
    .catalog {{ margin-top: 26px; padding: 30px; }}
    .catalog-tools {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: end;
    }}
    .search-field {{ display: grid; gap: 8px; }}
    .search-field span {{
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}
    .search-field input {{
      width: 100%;
      min-width: 0;
      padding: 14px 16px;
      border: 1px solid rgba(54, 46, 28, 0.16);
      border-radius: 8px;
      background: rgba(255, 251, 244, 0.94);
      color: var(--ink);
      font: inherit;
    }}
    .search-field input:focus {{ outline: 2px solid rgba(17, 100, 102, 0.3); outline-offset: 2px; }}
    .result-count {{ margin: 0; padding-bottom: 14px; color: var(--muted); white-space: nowrap; }}
    .repo-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .repo-card {{
      min-width: 0;
      padding: 22px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .repo-card[hidden] {{ display: none; }}
    .repo-card__eyebrow {{
      margin: 0 0 8px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--signal);
      font-size: 0.75rem;
      font-weight: 700;
    }}
    .repo-card__head h3 {{ margin: 0; font-size: 1.34rem; }}
    .repo-card__path {{
      margin: 6px 0 0;
      color: var(--muted);
      font-family: "SFMono-Regular", "JetBrains Mono", "Cascadia Code", monospace;
      font-size: 0.9rem;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .repo-card__description {{ margin: 14px 0 0; color: #30363c; line-height: 1.7; }}
    .repo-card__links {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 18px;
      font-weight: 700;
      color: var(--accent-strong);
    }}
    .no-results {{ margin: 22px 0 0; color: var(--muted); }}
    .footer {{
      margin-top: 28px;
      padding: 10px 2px 0;
      display: flex;
      flex-wrap: wrap;
      gap: 14px 22px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    @media (max-width: 980px) {{ .repo-grid {{ grid-template-columns: 1fr; }} }}
    .catalog-note {{
      margin: 16px 0 0;
      color: var(--muted);
      line-height: 1.6;
      font-size: 0.95rem;
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 56px; }}
      .hero, .catalog {{ padding: 22px; }}
      .nav {{ align-items: flex-start; flex-direction: column; }}
      .nav__links {{
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 4px;
      }}
      .nav__links a {{
        flex: 0 0 auto;
        padding: 8px 12px;
      }}
      .catalog-tools {{ grid-template-columns: 1fr; }}
      .result-count {{ padding-bottom: 0; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header(base_path, "repositories")}
    <section class="panel hero">
      <p class="eyebrow">Public inventory</p>
      <h1>Find a repository.</h1>
      <p>Search the current validated export by project, owner, host, or description, then open its summary, trust report, or static query-input data.</p>
    </section>
    <section class="panel catalog" data-inventory-url="{inventory_href}">
      <div class="catalog-tools">
        <label class="search-field" for="repository-search">
          <span>Search repositories</span>
          <input id="repository-search" type="search" placeholder="Try ripgrep, Python, or github.com/astral-sh/uv" autocomplete="off">
        </label>
        <p class="result-count" id="repository-result-count" aria-live="polite">Loading repository inventory...</p>
      </div>
      <div class="repo-grid" id="repository-grid" aria-live="polite"></div>
      <p class="no-results" id="repository-no-results" hidden>No repositories match this search.</p>
      <p class="catalog-note">Showing a capped result set for speed. Search by name, owner, host, or description to narrow the current validated export.</p>
      <noscript>
        <p class="catalog-note">JavaScript is required for the searchable catalog. The complete machine-readable inventory is available at <a href="{inventory_href}">/v0/repos/index.json</a>.</p>
      </noscript>
    </section>
    <footer class="footer">
      <span>Machine-readable inventory: <a href="{inventory_href}">/v0/repos/index.json</a></span>
      <span>Snapshot: <a href="{site_href(base_path, '/v0/meta.json')}">/v0/meta.json</a></span>
      <span>Source: <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a></span>
    </footer>
  </div>
  <script>
    (() => {{
      const RESULT_LIMIT = 60;
      const catalog = document.querySelector("[data-inventory-url]");
      const input = document.getElementById("repository-search");
      const grid = document.getElementById("repository-grid");
      const count = document.getElementById("repository-result-count");
      const noResults = document.getElementById("repository-no-results");
      const inventoryUrl = catalog.dataset.inventoryUrl;
      let repositories = [];

      function compactText(value, limit) {{
        const cleaned = String(value || "").trim().replace(/\\s+/g, " ");
        return cleaned.length > limit ? `${{cleaned.slice(0, limit - 1).trimEnd()}}...` : cleaned;
      }}

      function isLowSignalTitle(title) {{
        return ["a project", "sponsors", "project", "repository"].includes(String(title || "").trim().toLowerCase());
      }}

      function isLowSignalDescription(description) {{
        const normalized = String(description || "").trim().toLowerCase();
        return !normalized || normalized.endsWith("/readme.md") || ["readme", "readme.md"].includes(normalized);
      }}

      function normalizeEntry(entry) {{
        const identity = entry.identity || {{}};
        const host = String(identity.host || "");
        const owner = String(identity.owner || "");
        const repo = String(identity.repo || "");
        const fallbackName = repo || "unknown";
        const rawName = String(entry.name || "").trim();
        const name = rawName && !isLowSignalTitle(rawName) ? rawName : fallbackName;
        const rawDescription = String(entry.description || "").trim();
        const description = isLowSignalDescription(rawDescription)
          ? "Repository metadata exported from the validated dotrepo index."
          : compactText(rawDescription, 240);
        const label = [host, owner, repo].filter(Boolean).join("/");
        return {{
          identity: {{ host, owner, repo }},
          name,
          description,
          label,
          links: entry.links || {{}},
          searchIndex: [name, label, description].join(" ").toLowerCase(),
        }};
      }}

      function pathSegment(value) {{
        return encodeURIComponent(value);
      }}

      function queryInputHref(item) {{
        const identity = item.identity;
        if (!identity.host || !identity.owner || !identity.repo) {{
          return "#";
        }}
        return `{base_path}/query-input/${{pathSegment(identity.host)}}/${{pathSegment(identity.owner)}}/${{pathSegment(identity.repo)}}.json`;
      }}

      function makeLink(href, text, label) {{
        const link = document.createElement("a");
        link.href = href || "#";
        link.textContent = text;
        link.setAttribute("aria-label", label);
        return link;
      }}

      function renderCard(item) {{
        const article = document.createElement("article");
        article.className = "repo-card";

        const head = document.createElement("div");
        head.className = "repo-card__head";

        const eyebrow = document.createElement("p");
        eyebrow.className = "repo-card__eyebrow";
        eyebrow.textContent = "Indexed repository";

        const title = document.createElement("h3");
        title.textContent = item.name;

        const path = document.createElement("p");
        path.className = "repo-card__path";
        path.textContent = item.label;

        head.append(eyebrow, title, path);

        const description = document.createElement("p");
        description.className = "repo-card__description";
        description.textContent = item.description;

        const links = document.createElement("div");
        links.className = "repo-card__links";
        links.append(
          makeLink(item.links.self, "Summary", `Open ${{item.label}} summary`),
          makeLink(item.links.trust, "Trust", `Open ${{item.label}} trust report`),
          makeLink(queryInputHref(item), "Query input", `Open ${{item.label}} query input data`)
        );

        article.append(head, description, links);
        return article;
      }}

      function updateResults() {{
        const query = input.value.trim().toLowerCase();
        const matches = query
          ? repositories.filter((entry) => entry.searchIndex.includes(query))
          : repositories;
        const visible = matches.slice(0, RESULT_LIMIT);
        grid.replaceChildren(...visible.map(renderCard));
        const total = matches.length;
        const shown = visible.length;
        if (query) {{
          count.textContent = shown === total
            ? `${{total}} ${{total === 1 ? "repository" : "repositories"}}`
            : `Showing ${{shown}} of ${{total}} ${{total === 1 ? "repository" : "repositories"}}`;
        }} else {{
          count.textContent = shown === total
            ? `${{total}} repositories`
            : `Showing ${{shown}} of ${{total}} repositories`;
        }}
        noResults.hidden = total !== 0;

        const url = new URL(window.location.href);
        if (query) {{
          url.searchParams.set("q", query);
        }} else {{
          url.searchParams.delete("q");
        }}
        window.history.replaceState(null, "", url);
      }}

      input.addEventListener("input", updateResults);

      fetch(inventoryUrl)
        .then((response) => {{
          if (!response.ok) {{
            throw new Error(`Inventory request failed with ${{response.status}}.`);
          }}
          return response.json();
        }})
        .then((inventory) => {{
          repositories = Array.isArray(inventory.repositories)
            ? inventory.repositories.map(normalizeEntry)
            : [];
          const initialQuery = new URL(window.location.href).searchParams.get("q") || "";
          input.value = initialQuery;
          updateResults();
        }})
        .catch((error) => {{
          count.textContent = "Inventory unavailable";
          noResults.hidden = false;
          noResults.textContent = error instanceof Error ? error.message : "Repository inventory could not be loaded.";
        }});
    }})();
  </script>
</body>
</html>
"""


def render_writing_index(base_path: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='20' fill='%23141414'/%3E%3C/svg%3E">
  <title>Writing · dotrepo</title>
  <meta name="description" content="Essays, field reports, and research notes from the dotrepo project.">
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f1e8;
      --paper-strong: #efe6d7;
      --ink: #16181b;
      --muted: #5c635d;
      --panel: rgba(255, 251, 244, 0.84);
      --line: rgba(54, 46, 28, 0.14);
      --accent: #116466;
      --accent-strong: #0d494b;
      --signal: #c4572e;
      --shadow: 0 18px 60px rgba(23, 27, 31, 0.12);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(17, 100, 102, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(196, 87, 46, 0.12), transparent 30%),
        linear-gradient(180deg, #fbf6ec 0%, var(--paper) 54%, var(--paper-strong) 100%);
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 18px 80px;
    }}
    .nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 30px;
    }}
    .brand {{
      display: flex;
      align-items: baseline;
      gap: 12px;
    }}
    .brand__mark {{
      display: inline-flex;
      align-items: baseline;
      gap: 0.06em;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 1.4rem;
      font-weight: 500;
      letter-spacing: -0.01em;
    }}
    .brand__dot {{
      display: inline-block;
      width: 0.40em;
      height: 0.40em;
      border-radius: 50%;
      background: currentColor;
      flex-shrink: 0;
      translate: 0 -0.05em;
    }}
    .brand__tag {{
      font-size: 0.88rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .nav__links {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 12px;
    }}
    .nav__links a {{
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.48);
    }}
    .nav__links a[aria-current="page"] {{
      background: linear-gradient(135deg, var(--accent) 0%, #0b4b5a 100%);
      color: white;
      border-color: transparent;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}
    .hero {{
      padding: 34px;
      display: grid;
      gap: 16px;
    }}
    .eyebrow {{
      margin: 0;
      color: var(--accent-strong);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.78rem;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: clamp(2.8rem, 7vw, 5rem);
      line-height: 0.95;
      letter-spacing: -0.05em;
      max-width: 11ch;
    }}
    .hero p {{
      margin: 0;
      color: #273038;
      font-size: 1.08rem;
      line-height: 1.75;
      max-width: 44rem;
    }}
    .section {{
      margin-top: 26px;
      padding: 30px;
    }}
    .section h2 {{
      margin: 0;
      font-size: 0.84rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .repo-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .repo-card {{
      padding: 22px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .repo-card__eyebrow {{
      margin: 0 0 8px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--signal);
      font-size: 0.75rem;
      font-weight: 700;
    }}
    .repo-card__head h3 {{
      margin: 0;
      font-size: 1.34rem;
    }}
    .repo-card__path {{
      margin: 6px 0 0;
      color: var(--muted);
      font-family: "SFMono-Regular", "JetBrains Mono", "Cascadia Code", monospace;
      font-size: 0.9rem;
    }}
    .repo-card__description {{
      margin: 14px 0 0;
      color: #30363c;
      line-height: 1.7;
    }}
    .repo-card__links {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 18px;
      font-weight: 700;
      color: var(--accent-strong);
    }}
    .footer {{
      margin-top: 28px;
      padding: 10px 2px 0;
      display: flex;
      flex-wrap: wrap;
      gap: 14px 22px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    @media (max-width: 980px) {{
      .repo-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 56px; }}
      .hero,
      .section {{ padding: 22px; }}
      .nav {{ align-items: flex-start; flex-direction: column; }}
      .nav__links {{
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 4px;
      }}
      .nav__links a {{
        flex: 0 0 auto;
        padding: 8px 12px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header(base_path, "writing")}
    <section class="panel hero">
      <p class="eyebrow">Writing</p>
      <h1>Field reports from the protocol getting real.</h1>
      <p>Essays, research syntheses, and launch notes from dotrepo as the public surface, index, and agent-facing workflows get exercised in the open.</p>
    </section>
    <section class="panel section">
      <h2>Latest</h2>
      <div class="repo-grid">
        {render_writing_cards(base_path)}
      </div>
    </section>
    <footer class="footer">
      <span>Canonical public origin: <a href="https://dotrepo.org/">dotrepo.org</a></span>
      <span>Local review root: <a href="{site_href(base_path, '/')}">homepage</a></span>
      <span>Source: <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a></span>
    </footer>
  </div>
</body>
</html>
"""


def render_docs_index(base_path: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='20' fill='%23141414'/%3E%3C/svg%3E">
  <title>Docs · dotrepo</title>
  <meta name="description" content="First-party documentation entry for dotrepo: product status, trust model, public surface, maintainer flow, and index growth.">
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f1e8;
      --paper-strong: #efe6d7;
      --ink: #16181b;
      --muted: #5c635d;
      --panel: rgba(255, 251, 244, 0.84);
      --line: rgba(54, 46, 28, 0.14);
      --accent: #116466;
      --accent-strong: #0d494b;
      --signal: #c4572e;
      --shadow: 0 18px 60px rgba(23, 27, 31, 0.12);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(17, 100, 102, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(196, 87, 46, 0.12), transparent 30%),
        linear-gradient(180deg, #fbf6ec 0%, var(--paper) 54%, var(--paper-strong) 100%);
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 18px 80px;
    }}
    .nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 30px;
    }}
    .brand {{
      display: flex;
      align-items: baseline;
      gap: 12px;
    }}
    .brand__mark {{
      display: inline-flex;
      align-items: baseline;
      gap: 0.06em;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 1.4rem;
      font-weight: 500;
      letter-spacing: -0.01em;
    }}
    .brand__dot {{
      display: inline-block;
      width: 0.40em;
      height: 0.40em;
      border-radius: 50%;
      background: currentColor;
      flex-shrink: 0;
      translate: 0 -0.05em;
    }}
    .brand__tag {{
      font-size: 0.88rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .nav__links {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 12px;
    }}
    .nav__links a {{
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.48);
    }}
    .nav__links a[aria-current="page"] {{
      background: linear-gradient(135deg, var(--accent) 0%, #0b4b5a 100%);
      color: white;
      border-color: transparent;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}
    .hero {{
      padding: 34px;
      display: grid;
      gap: 16px;
    }}
    .eyebrow {{
      margin: 0;
      color: var(--accent-strong);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.78rem;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: clamp(2.8rem, 7vw, 5rem);
      line-height: 0.95;
      letter-spacing: -0.05em;
      max-width: 12ch;
    }}
    .hero p {{
      margin: 0;
      color: #273038;
      font-size: 1.08rem;
      line-height: 1.75;
      max-width: 46rem;
    }}
    .section {{
      margin-top: 26px;
      padding: 30px;
    }}
    .section h2 {{
      margin: 0;
      font-size: 0.84rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .doc-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .doc-item {{
      padding: 22px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .doc-item__head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }}
    .doc-item__head h3 {{
      margin: 0;
      font-size: 1.28rem;
    }}
    .doc-item__head span {{
      color: var(--signal);
      font-size: 0.78rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    .doc-item p {{
      margin: 14px 0 0;
      color: #30363c;
      line-height: 1.7;
    }}
    .doc-item a {{
      display: inline-flex;
      margin-top: 18px;
      font-weight: 700;
      color: var(--accent-strong);
    }}
    .footer {{
      margin-top: 28px;
      padding: 10px 2px 0;
      display: flex;
      flex-wrap: wrap;
      gap: 14px 22px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    @media (max-width: 980px) {{
      .doc-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 56px; }}
      .hero,
      .section {{ padding: 22px; }}
      .nav {{ align-items: flex-start; flex-direction: column; }}
      .nav__links {{
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 4px;
      }}
      .nav__links a {{
        flex: 0 0 auto;
        padding: 8px 12px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header(base_path, "docs")}
    <section class="panel hero">
      <p class="eyebrow">Docs</p>
      <h1>The first-party entry to the protocol, product, and live proof surface.</h1>
      <p>This page keeps the documentation front door on <code>dotrepo.org</code>. Detailed working docs still live in the repository for now, but the canonical entrypoint, public API links, and product framing stay first-party.</p>
    </section>
    {render_docs_cards(base_path)}
    <footer class="footer">
      <span>Canonical public origin: <a href="https://dotrepo.org/">dotrepo.org</a></span>
      <span>Live inventory: <a href="{site_href(base_path, '/v0/repos/index.json')}">/v0/repos/index.json</a></span>
      <span>Source: <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a></span>
    </footer>
  </div>
</body>
</html>
"""


def render_article_page(article: dict, base_path: str) -> str:
    tags = "".join(
        f'<span class="tag">{html.escape(str(tag))}</span>' for tag in article.get("tags", [])
    )
    title = html.escape(str(article["title"]))
    dek = html.escape(str(article["dek"]))
    published = html.escape(str(article["published"]))
    kicker = html.escape(str(article.get("kicker", "Writing")))
    summary = html.escape(str(article["summary"]))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='20' fill='%23141414'/%3E%3C/svg%3E">
  <title>{title} · dotrepo</title>
  <meta name="description" content="{summary}">
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f1e8;
      --paper-strong: #efe6d7;
      --ink: #16181b;
      --muted: #5c635d;
      --panel: rgba(255, 251, 244, 0.88);
      --line: rgba(54, 46, 28, 0.14);
      --accent: #116466;
      --accent-strong: #0d494b;
      --signal: #c4572e;
      --shadow: 0 18px 60px rgba(23, 27, 31, 0.12);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(17, 100, 102, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(196, 87, 46, 0.12), transparent 30%),
        linear-gradient(180deg, #fbf6ec 0%, var(--paper) 54%, var(--paper-strong) 100%);
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }}
    a {{ color: var(--accent-strong); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{
      font-family: "SFMono-Regular", "JetBrains Mono", "Cascadia Code", monospace;
      font-size: 0.92em;
    }}
    .page {{
      max-width: 960px;
      margin: 0 auto;
      padding: 28px 18px 80px;
    }}
    .nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 30px;
    }}
    .brand {{
      display: flex;
      align-items: baseline;
      gap: 12px;
    }}
    .brand__mark {{
      display: inline-flex;
      align-items: baseline;
      gap: 0.06em;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 1.4rem;
      font-weight: 500;
      letter-spacing: -0.01em;
    }}
    .brand__dot {{
      display: inline-block;
      width: 0.40em;
      height: 0.40em;
      border-radius: 50%;
      background: currentColor;
      flex-shrink: 0;
      translate: 0 -0.05em;
    }}
    .brand__tag {{
      font-size: 0.88rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .nav__links {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 12px;
    }}
    .nav__links a {{
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.48);
      color: inherit;
    }}
    .nav__links a[aria-current="page"] {{
      background: linear-gradient(135deg, var(--accent) 0%, #0b4b5a 100%);
      color: white;
      border-color: transparent;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}
    .article-hero,
    .article-body,
    .article-footer {{
      padding: 32px;
    }}
    .article-kicker {{
      margin: 0 0 12px;
      color: var(--accent-strong);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.78rem;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: clamp(2.9rem, 7vw, 5rem);
      line-height: 0.95;
      letter-spacing: -0.06em;
      max-width: 12ch;
    }}
    .article-dek {{
      margin: 16px 0 0;
      max-width: 46rem;
      color: #273038;
      font-size: 1.14rem;
      line-height: 1.75;
    }}
    .article-meta {{
      margin-top: 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      color: var(--muted);
      font-size: 0.97rem;
    }}
    .article-tags {{
      margin-top: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .tag {{
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid rgba(54, 46, 28, 0.08);
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .article-body {{
      margin-top: 24px;
      line-height: 1.8;
      font-size: 1.06rem;
    }}
    .article-body h2 {{
      margin: 2.5rem 0 0.9rem;
      font-size: 1.55rem;
      line-height: 1.2;
    }}
    .article-body h3 {{
      margin: 2rem 0 0.8rem;
      font-size: 1.18rem;
      line-height: 1.35;
    }}
    .article-body p,
    .article-body ul,
    .article-body ol,
    .article-body blockquote,
    .article-body .table-wrap {{
      margin: 1rem 0;
    }}
    .article-body ul,
    .article-body ol {{
      padding-left: 1.35rem;
    }}
    .article-body li + li {{
      margin-top: 0.45rem;
    }}
    .article-body blockquote {{
      padding: 18px 20px;
      border-left: 4px solid var(--accent);
      background: rgba(255, 255, 255, 0.7);
      border-radius: 16px;
      color: #273038;
    }}
    .article-body blockquote p {{
      margin: 0;
    }}
    .article-callout {{
      padding: 18px 20px;
      border-radius: 18px;
      background: linear-gradient(135deg, rgba(17, 100, 102, 0.08), rgba(196, 87, 46, 0.08));
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .article-callout p:first-child {{
      margin-top: 0;
    }}
    .article-callout p:last-child {{
      margin-bottom: 0;
    }}
    .table-wrap {{
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 680px;
      background: rgba(255, 255, 255, 0.7);
      border-radius: 18px;
      overflow: hidden;
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    th,
    td {{
      padding: 14px 16px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid rgba(54, 46, 28, 0.08);
    }}
    thead th {{
      background: rgba(17, 100, 102, 0.08);
      font-size: 0.86rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    tbody tr:last-child td {{
      border-bottom: 0;
    }}
    .article-footer {{
      margin-top: 24px;
      display: flex;
      flex-wrap: wrap;
      gap: 14px 24px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 56px; }}
      .article-hero,
      .article-body,
      .article-footer {{ padding: 22px; }}
      .nav {{ align-items: flex-start; flex-direction: column; }}
      .nav__links {{
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 4px;
      }}
      .nav__links a {{
        flex: 0 0 auto;
        padding: 8px 12px;
      }}
      table {{ min-width: 560px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header(base_path, "writing")}
    <article class="panel article-hero">
      <p class="article-kicker">{kicker}</p>
      <h1>{title}</h1>
      <p class="article-dek">{dek}</p>
      <div class="article-meta">
        <span>{published}</span>
        <span>dotrepo.org writing</span>
      </div>
      <div class="article-tags">{tags}</div>
    </article>
    <section class="panel article-body">
      {article["body_html"]}
    </section>
    <footer class="panel article-footer">
      <span><a href="{site_href(base_path, '/writing/')}">Back to writing</a></span>
      <span><a href="https://github.com/maxwellsantoro/dotrepo">Project source</a></span>
      <span><a href="{site_href(base_path, '/v0/repos/index.json')}">Live public index</a></span>
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    validate_first_party_document_links()
    input_dir = Path(args.input_dir)
    index_root = Path(args.index_root)
    meta = load_json(input_dir / "v0" / "meta.json")
    inventory = load_json(input_dir / "v0" / "repos" / "index.json")
    stats = load_optional_json(input_dir / "v0" / "stats.json")
    base_path = detect_site_base_path(inventory)
    progress = load_index_progress(index_root)

    snapshot_digest = str(meta.get("snapshotDigest", "unknown"))
    generated_at = str(meta.get("generatedAt", "unknown"))
    generated_at_human = format_timestamp_for_humans(generated_at)
    stale_after = meta.get("staleAfter")
    repository_count = inventory.get("repositoryCount", 0)
    first_query, first_query_input, query_example = build_query_example(input_dir, inventory)
    featured_trust = build_featured_trust_example(input_dir, inventory)
    homepage_snapshot_state = build_homepage_snapshot_state(meta, inventory)
    reviewed_or_better_count = progress["reviewedOrBetterCount"]
    imported_or_inferred_count = progress["importedOrInferredCount"]
    language_mix = str(progress["languageMix"])
    accepted_claim_count = progress["acceptedClaimCount"]
    accepted_claim_label = (
        "accepted claim example" if accepted_claim_count == 1 else "accepted claim examples"
    )
    stale_line = (
        f"<span>{html.escape(format_timestamp_for_humans(str(stale_after)))}</span>"
        if stale_after
        else "<span>not set</span>"
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='20' fill='%23141414'/%3E%3C/svg%3E">
  <title>dotrepo</title>
  <meta name="description" content="Reusable, trust-aware repository understanding for humans, tools, and agents.">
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f1e8;
      --paper-strong: #efe6d7;
      --ink: #16181b;
      --muted: #5c635d;
      --panel: rgba(255, 251, 244, 0.84);
      --panel-strong: #fff8ee;
      --line: rgba(54, 46, 28, 0.14);
      --accent: #116466;
      --accent-strong: #0d494b;
      --signal: #c4572e;
      --shadow: 0 18px 60px rgba(23, 27, 31, 0.12);
      --radius: 22px;
    }}
    * {{
      box-sizing: border-box;
    }}
    html {{
      scroll-behavior: smooth;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(17, 100, 102, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(196, 87, 46, 0.12), transparent 30%),
        linear-gradient(180deg, #fbf6ec 0%, var(--paper) 54%, var(--paper-strong) 100%);
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
    }}
    a {{
      color: inherit;
      text-decoration: none;
    }}
    code {{
      font-family: "SFMono-Regular", "JetBrains Mono", "Cascadia Code", monospace;
      font-size: 0.92em;
    }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 18px 80px;
    }}
    .nav {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 30px;
    }}
    .brand {{
      display: flex;
      align-items: baseline;
      gap: 12px;
    }}
    .brand__mark {{
      display: inline-flex;
      align-items: baseline;
      gap: 0.06em;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 1.4rem;
      font-weight: 500;
      letter-spacing: -0.01em;
    }}
    .brand__dot {{
      display: inline-block;
      width: 0.40em;
      height: 0.40em;
      border-radius: 50%;
      background: currentColor;
      flex-shrink: 0;
      translate: 0 -0.05em;
    }}
    .brand__tag {{
      font-size: 0.88rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .nav__links {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 12px;
    }}
    .nav__links a {{
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.48);
      transition: transform 180ms ease, background 180ms ease;
    }}
    .nav__links a:hover {{
      transform: translateY(-1px);
      background: rgba(255, 255, 255, 0.78);
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.9fr);
      gap: 26px;
      align-items: stretch;
    }}
    .panel {{
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}
    .hero__copy {{
      padding: 34px;
      position: relative;
      overflow: hidden;
    }}
    .hero__copy::after {{
      content: "";
      position: absolute;
      inset: auto -40px -50px auto;
      width: 180px;
      height: 180px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(196, 87, 46, 0.18), transparent 70%);
      pointer-events: none;
    }}
    .eyebrow {{
      margin: 0 0 14px;
      color: var(--accent-strong);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.78rem;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: clamp(3rem, 7vw, 5.6rem);
      line-height: 0.92;
      letter-spacing: -0.06em;
      max-width: 10ch;
    }}
    .hero__lede {{
      margin: 20px 0 0;
      max-width: 38rem;
      color: #273038;
      font-size: 1.12rem;
      line-height: 1.7;
    }}
    .cta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 26px;
    }}
    .cta {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 170px;
      padding: 14px 18px;
      border-radius: 14px;
      font-weight: 700;
      transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }}
    .cta:hover {{
      transform: translateY(-1px);
      box-shadow: 0 12px 24px rgba(17, 100, 102, 0.12);
    }}
    .cta--primary {{
      background: linear-gradient(135deg, var(--accent) 0%, #0b4b5a 100%);
      color: white;
    }}
    .cta--secondary {{
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid var(--line);
    }}
    .hero__meta {{
      padding: 28px;
      display: grid;
      gap: 14px;
      align-content: start;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.55), rgba(255, 248, 238, 0.9)),
        linear-gradient(135deg, rgba(17, 100, 102, 0.1), rgba(196, 87, 46, 0.08));
    }}
    .hero__meta h2,
    .section h2 {{
      margin: 0;
      font-size: 0.84rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .stat-grid {{
      display: grid;
      gap: 12px;
      margin-top: 4px;
    }}
    .stat-grid--wide {{
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      margin-top: 18px;
    }}
    .stat {{
      padding: 16px 18px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.76);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .stat strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 1.1rem;
    }}
    .stat span {{
      color: var(--muted);
      word-break: break-word;
    }}
    .section {{
      margin-top: 26px;
      padding: 30px;
    }}
    .section h3 {{
      margin: 0 0 10px;
      font-size: 1.35rem;
    }}
    .section__intro,
    .section__note {{
      margin: 12px 0 0;
      max-width: 48rem;
      color: var(--muted);
      line-height: 1.7;
    }}
    .section__note {{
      margin-top: 18px;
    }}
    .section__note a {{
      color: var(--accent-strong);
      font-weight: 700;
    }}
    .lookup-shell {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 16px;
      margin-top: 18px;
    }}
    .lookup-card {{
      min-width: 0;
      padding: 22px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .lookup-card h3 {{
      margin: 0;
      font-size: 1.35rem;
    }}
    .lookup-form {{
      display: grid;
      gap: 16px;
      margin-top: 18px;
    }}
    .lookup-field {{
      display: grid;
      gap: 8px;
    }}
    .lookup-field span {{
      font-size: 0.82rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 700;
    }}
    .lookup-field input {{
      width: 100%;
      padding: 16px 18px;
      border-radius: 14px;
      border: 1px solid rgba(54, 46, 28, 0.16);
      background: rgba(255, 251, 244, 0.92);
      color: var(--ink);
      font: inherit;
    }}
    .lookup-field input:focus {{
      outline: 2px solid rgba(17, 100, 102, 0.24);
      outline-offset: 2px;
    }}
    .lookup-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .lookup-button {{
      border: 0;
      cursor: pointer;
      font: inherit;
    }}
    .lookup-feedback {{
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .lookup-feedback[data-state="error"] {{
      color: var(--signal);
      font-weight: 700;
    }}
    .three-up {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .feature {{
      padding: 20px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .feature p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .api-grid {{
      min-width: 0;
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 16px;
      margin-top: 18px;
    }}
    .api-card {{
      min-width: 0;
      padding: 22px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .api-card p {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.7;
    }}
    .api-card pre {{
      margin: 14px 0 0;
      padding: 16px;
      overflow-x: auto;
      border-radius: 16px;
      background: #17191d;
      color: #f6f1e8;
      border: 1px solid rgba(54, 46, 28, 0.08);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
      line-height: 1.5;
    }}
    .api-card__caption {{
      margin-top: 14px;
      color: var(--muted);
      font-size: 0.96rem;
    }}
    .api-card__caption code {{
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .endpoint-list {{
      display: grid;
      gap: 12px;
    }}
    .endpoint {{
      min-width: 0;
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      align-items: center;
      padding: 14px 16px;
      border-radius: 14px;
      background: rgba(255, 251, 244, 0.88);
      border: 1px solid rgba(54, 46, 28, 0.08);
    }}
    .endpoint code {{
      min-width: 0;
      color: var(--accent-strong);
      font-weight: 600;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .lookup-card .endpoint code {{
      min-width: 0;
      flex: 1 1 100%;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .lookup-card .endpoint span {{
      min-width: 0;
    }}
    .endpoint span {{
      min-width: 0;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .endpoint--query {{
      align-items: flex-start;
    }}
    .endpoint--query code {{
      min-width: 0;
      flex: 1 1 100%;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .endpoint--query span {{
      min-width: 0;
      flex: 1 1 14rem;
    }}
    .repo-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .repo-card {{
      min-width: 0;
      padding: 22px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid rgba(54, 46, 28, 0.08);
      transition: transform 180ms ease, box-shadow 180ms ease;
    }}
    .repo-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 14px 28px rgba(23, 27, 31, 0.08);
    }}
    .repo-card__eyebrow {{
      margin: 0 0 8px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--signal);
      font-size: 0.75rem;
      font-weight: 700;
    }}
    .repo-card__head h3 {{
      margin: 0;
      font-size: 1.34rem;
    }}
    .repo-card__path {{
      margin: 6px 0 0;
      color: var(--muted);
      font-family: "SFMono-Regular", "JetBrains Mono", "Cascadia Code", monospace;
      font-size: 0.9rem;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .repo-card__description {{
      margin: 14px 0 0;
      color: #30363c;
      line-height: 1.7;
    }}
    .repo-card__links {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 18px;
      font-weight: 700;
      color: var(--accent-strong);
    }}
    .footer {{
      margin-top: 28px;
      padding: 10px 2px 0;
      display: flex;
      flex-wrap: wrap;
      gap: 14px 22px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    @media (max-width: 980px) {{
      .hero,
      .api-grid,
      .lookup-shell,
      .repo-grid,
      .three-up {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 720px) {{
      .page {{
        padding: 18px 14px 56px;
      }}
      .hero__copy,
      .hero__meta,
      .section {{
        padding: 22px;
      }}
      .nav {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .nav__links {{
        width: 100%;
        flex-wrap: nowrap;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 8px;
        padding-bottom: 4px;
      }}
      .nav__links a {{
        flex: 0 0 auto;
        padding: 8px 12px;
      }}
      .cta {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <script id="dotrepo-homepage-snapshot" type="application/json">{homepage_snapshot_state}</script>
  <div class="page">
    {render_site_header(base_path, "home")}

    <section class="hero">
      <div class="panel hero__copy">
        <p class="eyebrow">Live public surface</p>
        <h1>Repository understanding, made reusable.</h1>
        <p class="hero__lede">
          dotrepo is a trust contract for repository metadata. The important
          part is not that a <code>.repo</code> file exists. The important part
          is that hosted answers carry selection reason, provenance, and claim
          context instead of pretending repository metadata is conflict-free.
        </p>
        <div class="cta-row">
          <a class="cta cta--primary" href="{html.escape(featured_trust['trustUrl'])}">See the live trust handoff</a>
          <a class="cta cta--secondary" href="{site_href(base_path, '/v0/repos/index.json')}">Explore the public index</a>
          <a class="cta cta--secondary" href="{site_href(base_path, '/docs/')}">Read the docs</a>
          <a class="cta cta--secondary" href="https://github.com/maxwellsantoro/dotrepo">Read the code</a>
        </div>
      </div>

      <aside class="panel hero__meta">
        <h2>Growth and snapshot</h2>
        <div class="stat-grid">
          <div class="stat">
            <strong>{html.escape(str(repository_count))} repositories</strong>
            <span>Published in the current validated export.</span>
          </div>
          <div class="stat">
            <strong>{html.escape(str(reviewed_or_better_count))} reviewed or verified</strong>
            <span>{html.escape(str(imported_or_inferred_count))} records remain imported or inferred.</span>
          </div>
          <div class="stat">
            <strong>{html.escape(language_mix)}</strong>
            <span>Primary language-family mix in checked-in index records.</span>
          </div>
          <div class="stat">
            <strong>{html.escape(str(accepted_claim_count))} {accepted_claim_label}</strong>
            <span>Accepted maintainer-owned claim examples in the checked-in index.</span>
          </div>
          <div class="stat">
            <strong>{html.escape(generated_at_human)}</strong>
            <span>Snapshot generated at.</span>
          </div>
          <div class="stat">
            <strong><code>{html.escape(shorten_digest(snapshot_digest))}</code></strong>
            <span>Snapshot digest <code>{html.escape(snapshot_digest)}</code>.</span>
          </div>
          <div class="stat">
            <strong>Stale after</strong>
            {stale_line}
          </div>
        </div>
      </aside>
    </section>

    {render_pagedigest_stats_dashboard(stats, base_path)}

    <section class="panel section">
      <h2>Trust proof</h2>
      <p class="section__intro">
        The strongest live artifact on this site is not a generic field lookup. It is a claim-aware trust response that shows accepted maintainer state, preserved reviewed overlay context, and canonical handoff without silently flattening history away.
      </p>
      <div class="api-grid">
        <article class="api-card">
          <h3>{html.escape(featured_trust['name'])}</h3>
          <p><code>{html.escape(featured_trust['label'])}</code></p>
          <p>{html.escape(featured_trust['description'])}</p>
          <div class="endpoint-list">
            <div class="endpoint">
              <code>claim state: {html.escape(featured_trust['claimState'])}</code>
              <span>The current exported claim state for the selected record.</span>
            </div>
            <div class="endpoint">
              <code>handoff: {html.escape(featured_trust['handoff'])}</code>
              <span>The reviewed overlay remains visible while the accepted maintainer claim points to the canonical source of truth.</span>
            </div>
            <div class="endpoint">
              <code>confidence: {html.escape(featured_trust['trustConfidence'])}</code>
              <span>Provenance: {html.escape(featured_trust['provenance'])}</span>
            </div>
            <div class="endpoint">
              <code>{html.escape(featured_trust['notes'])}</code>
              <span>Selection stays explained instead of being reduced to a bare answer.</span>
            </div>
          </div>
          <div class="repo-card__links">
            <a href="{html.escape(featured_trust['summaryUrl'])}" aria-label="Open {html.escape(featured_trust['label'], quote=True)} summary">Summary</a>
            <a href="{html.escape(featured_trust['trustUrl'])}" aria-label="Open {html.escape(featured_trust['label'], quote=True)} trust report">Trust</a>
            <a href="{html.escape(featured_trust['queryUrl'])}" aria-label="Open {html.escape(featured_trust['label'], quote=True)} query input data">Query input</a>
          </div>
        </article>
        <article class="api-card">
          <h3>What the live trust surface returns</h3>
          <p>This excerpt comes from the current exported snapshot and keeps the handoff visible. That is the product proof most metadata layers cannot show.</p>
          <pre><code>{featured_trust['proofJson']}</code></pre>
          <p class="api-card__caption">Review path: <code>{html.escape(str(featured_trust['reviewPath'] or "unknown"))}</code> · Evidence path: <code>{html.escape(str(featured_trust['evidencePath'] or "unknown"))}</code></p>
        </article>
      </div>
    </section>

    <section class="panel section">
      <h2>Repo lookup</h2>
      <p class="section__intro">
        Paste a repository URL and jump straight to the hosted summary or trust
        surface. This keeps the human path aligned with the shipped
        <code>dotrepo.lookup</code> MCP tool instead of inventing a separate browse product.
      </p>
      {render_lookup_panel(base_path)}
    </section>

    <section class="panel section">
      <h2>Why dotrepo</h2>
      <div class="three-up">
        <article class="feature">
          <h3>For maintainers</h3>
          <p>Keep essential repository facts in one trustworthy layer instead of scattering them across README files, CI, platform settings, and tribal knowledge.</p>
        </article>
        <article class="feature">
          <h3>For users</h3>
          <p>Inspect what a project is, how it should be trusted, and where claims came from without cloning the index or reading every supporting file first.</p>
        </article>
        <article class="feature">
          <h3>For agents and tools</h3>
          <p>Query stable JSON and same-origin endpoints directly instead of guessing intent from prose, conventions, and partially structured repository surfaces.</p>
        </article>
      </div>
    </section>

    <section class="panel section">
      <h2>Docs</h2>
      <p class="section__intro">
        The public site now keeps the documentation entrypoint on the first-party domain. Detailed working docs still live in the repository, but the navigation no longer treats the site as a thin wrapper around GitHub.
      </p>
      <div class="three-up">
        <article class="feature">
          <h3>Product and status</h3>
          <p>Start with the project overview, install guide, and maintainer path before diving into RFC history or operator detail.</p>
        </article>
        <article class="feature">
          <h3>Protocol and trust</h3>
          <p>The trust model, public surface architecture, and roadmap explain how reusable facts remain honest: provenance, precedence, freshness, and visible conflict.</p>
        </article>
        <article class="feature">
          <h3>Autonomous index</h3>
          <p>The roadmap, index rules, and maintainer-claim docs show how evidence-backed overlays scale without confusing generated facts with maintainer authority.</p>
        </article>
      </div>
      <p class="section__note">
        Start at <a href="{site_href(base_path, '/docs/')}">the first-party docs landing page</a>.
      </p>
    </section>

    <section class="panel section">
      <h2>Interview-backed priorities</h2>
      <p class="section__intro">
        A 9-model, 12-session interview round on dotrepo's current shape converged on three
        priorities: grow coverage until checking dotrepo is the cheap default,
        preserve trust and freshness, and keep the core contract focused.
      </p>
      <div class="three-up">
        <article class="feature">
          <h3>Broaden coverage</h3>
          <p>Remote lookup has shipped. The next bar is broader ecosystem coverage with measurable field quality.</p>
        </article>
        <article class="feature">
          <h3>Automate the conveyor</h3>
          <p>Deterministic parsers do the common work, unresolved fields escalate through bounded model tiers, and machine gates publish or abstain without a routine human queue.</p>
        </article>
        <article class="feature">
          <h3>Keep it small</h3>
          <p>The trust model, freshness semantics, hosted lookup, and compact schema remain the differentiators. Discovery should be built on profile quality, not used to disguise its absence.</p>
        </article>
      </div>
      <p class="section__note">
        Read the on-site write-up:
        <a href="{site_href(base_path, '/writing/what-the-ais-think-about-dotrepo/')}">What the AIs Think About dotrepo</a>.
        Working repo notes remain in
        <a href="https://github.com/maxwellsantoro/dotrepo/blob/main/docs/ai-tool-interviews.md">docs/ai-tool-interviews.md</a>.
      </p>
    </section>

    <section class="panel section">
      <h2>Writing</h2>
      <p class="section__intro">
        Ongoing field reports, launch notes, and research syntheses from the protocol,
        public surface, and agent-facing product work.
      </p>
      <div class="repo-grid">
        {render_writing_cards(base_path)}
      </div>
    </section>

    <section class="panel section">
      <h2>Public API</h2>
      <div class="api-grid">
        <article class="api-card">
          <h3>Stable entry points</h3>
          <p>The public surface is export-first. Summary, trust, inventory, freshness, and query responses all come from the same validated snapshot family.</p>
          <div class="endpoint-list">
            <div class="endpoint">
              <code>{html.escape(site_href(base_path, '/v0/meta.json'))}</code>
              <span>Snapshot freshness and digest metadata.</span>
            </div>
            <div class="endpoint">
              <code>{html.escape(site_href(base_path, '/v0/repos/index.json'))}</code>
              <span>Repository inventory and navigation links.</span>
            </div>
            <div class="endpoint">
              <code>{html.escape(site_href(base_path, '/v0/repos/<host>/<owner>/<repo>/index.json'))}</code>
              <span>Per-repository summary surface.</span>
            </div>
            <div class="endpoint">
              <code>{html.escape(site_href(base_path, '/v0/repos/<host>/<owner>/<repo>/trust.json'))}</code>
              <span>Selection, provenance, and claim context.</span>
            </div>
            <div class="endpoint">
              <code>{html.escape(site_href(base_path, '/v0/repos/<host>/<owner>/<repo>/query?path=...'))}</code>
              <span>Same-origin trust-aware field queries.</span>
            </div>
            <div class="endpoint">
              <code>read-only / same-origin / claim-aware</code>
              <span>No mutation API, one canonical host, and trust context stays visible on every query path.</span>
            </div>
          </div>
        </article>
        <article class="api-card">
          <h3>What a query returns</h3>
          <p>The query route returns the selected value together with selection, trust, and conflict context. This truncated example is derived from the current exported snapshot.</p>
          <div class="endpoint endpoint--query">
            <code>{html.escape(first_query)}</code>
            <span>Hosted query route for <code>repo.description</code>; static preview data: <a href="{html.escape(first_query_input)}"><code>query-input JSON</code></a>.</span>
          </div>
          <pre><code>{query_example}</code></pre>
          <p class="api-card__caption">Full responses also include freshness, repository identity, and navigation links.</p>
        </article>
      </div>
    </section>

    <section class="panel section">
      <h2>Indexed repositories</h2>
      <p class="section__intro">A small sample from the current export. Use the repository catalog to search the complete index.</p>
      <div class="repo-grid">
        {render_repository_cards(inventory, base_path=base_path, limit=8)}
      </div>
      <p class="section__note"><a href="{site_href(base_path, '/repositories/')}">Browse all {html.escape(str(repository_count))} repositories</a></p>
    </section>

    <footer class="footer">
      <span>Canonical public origin: <a href="https://dotrepo.org/">dotrepo.org</a></span>
      <span>Homepage lookup resolves the same hosted surface used by MCP <code>dotrepo.lookup</code>.</span>
      <span>Staging remains the deployed <code>workers.dev</code> Worker.</span>
      <span>Source: <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a></span>
    </footer>
  </div>
</body>
</html>
"""

    write_text(input_dir / "index.html", document)
    write_text(input_dir / "docs" / "index.html", render_docs_index(base_path))
    write_text(
        input_dir / "repositories" / "index.html",
        render_repositories_index(inventory, base_path),
    )
    write_text(input_dir / "writing" / "index.html", render_writing_index(base_path))
    for article in ARTICLES:
        write_text(
            input_dir / "writing" / article["slug"] / "index.html",
            render_article_page(article, base_path),
        )
    write_text(input_dir / ".nojekyll", "")
    print(input_dir / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
