#!/usr/bin/env python3

import argparse
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the dotrepo homepage for an exported public tree."
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
    first_query = "#"
    if repositories:
        first_query = (
            repositories[0]
            .get("links", {})
            .get("queryTemplate", "#")
            .replace("{dot_path}", "repo.description")
        )

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
        <a href="https://github.com/maxwellsantoro/dotrepo">GitHub</a>
        <a href="https://github.com/maxwellsantoro/dotrepo/blob/main/README.md">Docs</a>
        <a href="./v0/repos/index.json">Inventory</a>
        <a href="./v0/meta.json">Snapshot</a>
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
          </div>
        </article>
        <article class="api-card">
          <h3>Ground rules</h3>
          <p>dotrepo is a metadata layer, not a replacement for project materials. Public responses stay read-only, trust-aware, and explicit about provenance.</p>
          <div class="endpoint-list">
            <div class="endpoint">
              <code>read-only</code>
              <span>No mutation or submission API on the public surface.</span>
            </div>
            <div class="endpoint">
              <code>same-origin</code>
              <span>Inventory, trust, and query links resolve on one canonical host.</span>
            </div>
            <div class="endpoint">
              <code>claim-aware</code>
              <span>Canonical, imported, inferred, reviewed, and verified states stay visible.</span>
            </div>
          </div>
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

    (input_dir / "index.html").write_text(document)
    (input_dir / ".nojekyll").write_text("")
    print(input_dir / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
