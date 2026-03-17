#!/usr/bin/env python3

import argparse
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a minimal landing page for a dotrepo public export tree."
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


def render_repository_links(inventory: dict) -> str:
    entries = inventory.get("repositories", [])
    items = []
    for entry in entries:
        identity = entry.get("identity", {})
        name = entry.get("name") or identity.get("repo") or "unknown"
        host = identity.get("host", "")
        owner = identity.get("owner", "")
        repo = identity.get("repo", "")
        summary = entry.get("links", {}).get("self", "#")
        trust = entry.get("links", {}).get("trust", "#")
        label = f"{host}/{owner}/{repo}".strip("/")
        items.append(
            "<li>"
            f"<strong>{html.escape(str(name))}</strong> "
            f"<span>{html.escape(label)}</span> "
            f"<a href=\"{html.escape(summary)}\">index.json</a> "
            f"<a href=\"{html.escape(trust)}\">trust.json</a>"
            "</li>"
        )
    return "\n".join(items)


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    meta = load_json(input_dir / "v0" / "meta.json")
    inventory = load_json(input_dir / "v0" / "repos" / "index.json")

    snapshot_digest = meta.get("snapshotDigest", "unknown")
    generated_at = meta.get("generatedAt", "unknown")
    stale_after = meta.get("staleAfter")
    repository_count = inventory.get("repositoryCount", 0)
    repositories_html = render_repository_links(inventory)

    stale_html = (
        f"<p><strong>Stale after:</strong> {html.escape(str(stale_after))}</p>"
        if stale_after
        else ""
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>dotrepo public export</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f1e8;
      --ink: #1f2933;
      --muted: #52606d;
      --card: #fffdf7;
      --line: #d9d0bf;
      --accent: #9f3a13;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: radial-gradient(circle at top, #fff7ea 0%, var(--bg) 55%, #efe6d5 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 880px;
      margin: 0 auto;
      padding: 48px 20px 72px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 16px 40px rgba(31, 41, 51, 0.08);
    }}
    h1, h2 {{
      margin: 0 0 12px;
      line-height: 1.1;
    }}
    h1 {{
      font-size: clamp(2rem, 6vw, 3.4rem);
      letter-spacing: -0.04em;
    }}
    h2 {{
      font-size: 1.1rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    p, li {{
      font-size: 1rem;
      line-height: 1.6;
    }}
    a {{
      color: var(--accent);
    }}
    ul {{
      padding-left: 1.2rem;
    }}
    .meta {{
      display: grid;
      gap: 8px;
      margin: 18px 0 24px;
      color: var(--muted);
    }}
    .links {{
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      margin: 18px 0 0;
    }}
    .links a {{
      font-weight: 600;
    }}
	    .repo-list {{
	      margin-top: 28px;
	    }}
	    .repo-list li + li {{
	      margin-top: 10px;
	    }}
	    .repo-list span {{
	      color: var(--muted);
	      margin-right: 8px;
	    }}
	    .lede {{
	      font-size: 1.08rem;
	      max-width: 44rem;
	    }}
	  </style>
	</head>
	<body>
	  <main>
	    <section class="card">
	      <h2>Hosted Static Surface</h2>
	      <h1>dotrepo public export</h1>
	      <p class="lede">Trustworthy repository metadata for humans, tools, and agents. This site serves the exported read-only JSON tree directly, and the JSON contracts remain the source of truth.</p>
	      <div class="meta">
	        <p><strong>Generated at:</strong> {html.escape(str(generated_at))}</p>
	        <p><strong>Snapshot digest:</strong> <code>{html.escape(str(snapshot_digest))}</code></p>
	        {stale_html}
	        <p><strong>Repositories:</strong> {html.escape(str(repository_count))}</p>
	      </div>
	      <div class="links">
	        <a href="./v0/meta.json">meta.json</a>
	        <a href="./v0/repos/index.json">repos/index.json</a>
	        <a href="https://github.com/maxwellsantoro/dotrepo">GitHub repo</a>
	        <a href="https://github.com/maxwellsantoro/dotrepo/blob/main/README.md">README</a>
	      </div>
	      <section class="repo-list">
	        <h2>Repository endpoints</h2>
        <ul>
          {repositories_html}
        </ul>
      </section>
    </section>
  </main>
</body>
</html>
"""

    (input_dir / "index.html").write_text(document)
    (input_dir / ".nojekyll").write_text("")
    print(input_dir / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
