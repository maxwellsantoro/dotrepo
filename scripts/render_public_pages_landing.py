#!/usr/bin/env python3

import argparse
import html
import json
from pathlib import Path

from public_site_content import ARTICLES


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
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path}")
    return json.loads(path.read_text())


def shorten_digest(value: str) -> str:
    if len(value) <= 20:
        return value
    return f"{value[:12]}...{value[-10:]}"


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


def build_query_example(input_dir: Path, inventory: dict) -> tuple[str, str]:
    repositories = inventory.get("repositories", [])
    if not repositories:
        return "#", html.escape(json.dumps({"path": "repo.description"}, indent=2))

    summary = load_repository_surface(input_dir, repositories[0], "index.json")
    selection = summary.get("selection", {})
    selected_record = selection.get("record", {})
    record = selected_record.get("record", {})
    trust = record.get("trust", {})
    query_url = summary.get("links", {}).get("queryTemplate", "#").replace(
        "{dot_path}", "repo.description"
    )
    example = {
        "path": "repo.description",
        "value": summary.get("repository", {}).get("description"),
        "selection": {
            "reason": selection.get("reason"),
            "recordStatus": record.get("status"),
            "trust": {
                "confidence": trust.get("confidence"),
                "provenance": trust.get("provenance", []),
                "notes": trust.get("notes"),
            },
            "evidencePath": selected_record.get("artifacts", {}).get("evidencePath"),
        },
        "conflicts": summary.get("conflicts", []),
    }
    return query_url, html.escape(json.dumps(example, indent=2))


def render_site_header(active: str | None = None) -> str:
    links = [
        ("home", "/", "Home"),
        ("writing", "/writing/", "Writing"),
        ("github", "https://github.com/maxwellsantoro/dotrepo", "GitHub"),
        ("docs", "https://github.com/maxwellsantoro/dotrepo/blob/main/README.md", "Docs"),
        ("inventory", "/v0/repos/index.json", "Inventory"),
        ("snapshot", "/v0/meta.json", "Snapshot"),
    ]
    items = []
    for key, href, label in links:
        current = ' aria-current="page"' if active == key else ""
        items.append(f'<a href="{href}"{current}>{label}</a>')
    return """
    <header class="nav" aria-label="Top navigation">
      <div class="brand">
        <a class="brand__mark" href="/">dotrepo</a>
        <span class="brand__tag">open metadata protocol</span>
      </div>
      <nav class="nav__links">
        {items}
      </nav>
    </header>
    """.format(items="\n        ".join(items)).strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def render_writing_cards() -> str:
    cards = []
    for article in ARTICLES:
        path = f"/writing/{article['slug']}/"
        companion_url = article.get("companion_url")
        companion_link = (
            f'<a href="{html.escape(str(companion_url))}">Companion essay</a>'
            if companion_url
            else ""
        )
        links = [f'<a href="{html.escape(path)}">Read article</a>']
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


def render_repository_cards(inventory: dict) -> str:
    cards = []
    for entry in inventory.get("repositories", []):
        identity = entry.get("identity", {})
        name = entry.get("name") or identity.get("repo") or "unknown"
        description = entry.get("description") or "No description exported yet."
        host = identity.get("host", "")
        owner = identity.get("owner", "")
        repo = identity.get("repo", "")
        label = f"{host}/{owner}/{repo}".strip("/")
        links = entry.get("links", {})
        summary = links.get("self", "#")
        trust = links.get("trust", "#")
        query = links.get("queryTemplate", "#").replace("{dot_path}", "repo.description")
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
                <a href="{summary}">Summary</a>
                <a href="{trust}">Trust</a>
                <a href="{query}">Query</a>
              </div>
            </article>
            """.format(
                name=html.escape(str(name)),
                label=html.escape(label),
                description=html.escape(str(description)),
                summary=html.escape(summary),
                trust=html.escape(trust),
                query=html.escape(query),
            ).strip()
        )
    return "\n".join(cards)


def render_writing_index() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
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
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.05em;
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
      .nav__links {{ justify-content: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header("writing")}
    <section class="panel hero">
      <p class="eyebrow">Writing</p>
      <h1>Field reports from the protocol getting real.</h1>
      <p>Essays, research syntheses, and launch notes from dotrepo as the public surface, index, and agent-facing workflows get exercised in the open.</p>
    </section>
    <section class="panel section">
      <h2>Latest</h2>
      <div class="repo-grid">
        {render_writing_cards()}
      </div>
    </section>
    <footer class="footer">
      <span>Canonical public origin: <a href="https://dotrepo.org/">dotrepo.org</a></span>
      <span>Source: <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a></span>
    </footer>
  </div>
</body>
</html>
"""


def render_article_page(article: dict) -> str:
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
      color: inherit;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.05em;
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
      .nav__links {{ justify-content: flex-start; }}
      table {{ min-width: 560px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {render_site_header("writing")}
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
      <span><a href="/writing/">Back to writing</a></span>
      <span><a href="https://github.com/maxwellsantoro/dotrepo">Project source</a></span>
      <span><a href="/v0/repos/index.json">Live public index</a></span>
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    meta = load_json(input_dir / "v0" / "meta.json")
    inventory = load_json(input_dir / "v0" / "repos" / "index.json")

    snapshot_digest = str(meta.get("snapshotDigest", "unknown"))
    generated_at = str(meta.get("generatedAt", "unknown"))
    stale_after = meta.get("staleAfter")
    repository_count = inventory.get("repositoryCount", 0)
    repositories = inventory.get("repositories", [])
    first_query, query_example = build_query_example(input_dir, inventory)

    stale_line = (
        f"<span>{html.escape(str(stale_after))}</span>" if stale_after else "<span>not set</span>"
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>dotrepo</title>
  <meta name="description" content="Trust-aware metadata for software repositories. dotrepo serves a live public JSON surface and query API for humans, tools, and agents.">
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
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.05em;
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
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 16px;
      margin-top: 18px;
    }}
    .api-card {{
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
    .endpoint-list {{
      display: grid;
      gap: 12px;
    }}
    .endpoint {{
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
      color: var(--accent-strong);
      font-weight: 600;
    }}
    .endpoint span {{
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
        justify-content: flex-start;
      }}
      .cta {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="nav" aria-label="Top navigation">
      <div class="brand">
        <span class="brand__mark">dotrepo</span>
        <span class="brand__tag">open metadata protocol</span>
      </div>
      <nav class="nav__links">
        <a href="/writing/">Writing</a>
        <a href="https://github.com/maxwellsantoro/dotrepo">GitHub</a>
        <a href="https://github.com/maxwellsantoro/dotrepo/blob/main/README.md">Docs</a>
        <a href="/v0/repos/index.json">Inventory</a>
        <a href="/v0/meta.json">Snapshot</a>
      </nav>
    </header>

    <section class="hero">
      <div class="panel hero__copy">
        <p class="eyebrow">Live public surface</p>
        <h1>Trust-aware metadata for software repositories.</h1>
        <p class="hero__lede">
          dotrepo gives maintainers, users, tools, and coding agents one
          structured view of a repository without flattening projects into
          scraped sludge. The public JSON tree and same-origin query route on
          this site are built from the reviewed export snapshot below.
        </p>
        <div class="cta-row">
          <a class="cta cta--primary" href="./v0/repos/index.json">Explore the public index</a>
          <a class="cta cta--secondary" href="{html.escape(first_query)}">Try a live query</a>
          <a class="cta cta--secondary" href="https://github.com/maxwellsantoro/dotrepo">Read the code</a>
        </div>
      </div>

      <aside class="panel hero__meta">
        <h2>Snapshot status</h2>
        <div class="stat-grid">
          <div class="stat">
            <strong>{html.escape(str(repository_count))} repositories</strong>
            <span>Published in the current reviewed export.</span>
          </div>
          <div class="stat">
            <strong>{html.escape(generated_at)}</strong>
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
      <h2>Interview-backed priorities</h2>
      <p class="section__intro">
        A 12-model interview round on dotrepo's current shape converged on three
        next steps: grow the index until checking it is cheap, expose remote
        lookup through MCP, and keep the public surface narrow while that work lands.
      </p>
      <div class="three-up">
        <article class="feature">
          <h3>Seed the index</h3>
          <p>Near-term usefulness comes from a broader reviewed overlay set, not another round of protocol ornamentation. The next tranche should span Rust, TypeScript, Python, and Go.</p>
        </article>
        <article class="feature">
          <h3>Add remote lookup</h3>
          <p>The public HTTP shape already supports repo-first lookup. The missing ergonomic layer is an MCP tool that takes a URL or identity and resolves against the hosted surface without cloning first.</p>
        </article>
        <article class="feature">
          <h3>Keep it small</h3>
          <p>The trust model, freshness semantics, and live query route are the differentiators. Search, mutation, and heavier editor product work should stay subordinate until the data and lookup path are stronger.</p>
        </article>
      </div>
      <p class="section__note">
        Read the on-site write-up:
        <a href="/writing/what-the-ais-think-about-dotrepo/">What the AIs Think About dotrepo</a>.
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
        {render_writing_cards()}
      </div>
    </section>

    <section class="panel section">
      <h2>Public API</h2>
      <div class="api-grid">
        <article class="api-card">
          <h3>Stable entry points</h3>
          <p>The public surface is export-first. Summary, trust, inventory, freshness, and query responses all come from the same reviewed snapshot family.</p>
          <div class="endpoint-list">
            <div class="endpoint">
              <code>/v0/meta.json</code>
              <span>Snapshot freshness and digest metadata.</span>
            </div>
            <div class="endpoint">
              <code>/v0/repos/index.json</code>
              <span>Repository inventory and navigation links.</span>
            </div>
            <div class="endpoint">
              <code>/v0/repos/&lt;host&gt;/&lt;owner&gt;/&lt;repo&gt;/index.json</code>
              <span>Per-repository summary surface.</span>
            </div>
            <div class="endpoint">
              <code>/v0/repos/&lt;host&gt;/&lt;owner&gt;/&lt;repo&gt;/trust.json</code>
              <span>Selection, provenance, and claim context.</span>
            </div>
            <div class="endpoint">
              <code>/v0/repos/&lt;host&gt;/&lt;owner&gt;/&lt;repo&gt;/query?path=...</code>
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
          <div class="endpoint">
            <code>{html.escape(first_query)}</code>
            <span>Example live query for <code>repo.description</code>.</span>
          </div>
          <pre><code>{query_example}</code></pre>
          <p class="api-card__caption">Full responses also include freshness, repository identity, and navigation links.</p>
        </article>
      </div>
    </section>

    <section class="panel section">
      <h2>Indexed repositories</h2>
      <div class="repo-grid">
        {render_repository_cards(inventory)}
      </div>
    </section>

    <footer class="footer">
      <span>Canonical public origin: <a href="https://dotrepo.org/">dotrepo.org</a></span>
      <span>Staging remains the deployed <code>workers.dev</code> Worker.</span>
      <span>Source: <a href="https://github.com/maxwellsantoro/dotrepo">github.com/maxwellsantoro/dotrepo</a></span>
    </footer>
  </div>
</body>
</html>
"""

    write_text(input_dir / "index.html", document)
    write_text(input_dir / "writing" / "index.html", render_writing_index())
    for article in ARTICLES:
        write_text(
            input_dir / "writing" / article["slug"] / "index.html",
            render_article_page(article),
        )
    write_text(input_dir / ".nojekyll", "")
    print(input_dir / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
