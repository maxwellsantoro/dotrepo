"""Human repository view over the existing public profile contract."""

import html
from urllib.parse import quote

from public_site_styles import SITE_CHROME


def repository_href(base_path: str, identity: dict) -> str:
    label = "/".join(identity[key] for key in ("host", "owner", "repo"))
    return base_path.rstrip("/") + "/repository/?repo=" + quote(label, safe="")


def render_repository_page(base_path: str, header: str) -> str:
    base = html.escape(base_path.rstrip("/"), quote=True)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Repository profile · dotrepo</title>
<meta name="description" content="Inspect repository facts, execution scope, evidence, age and missing answers.">
{SITE_CHROME}
<style>
  a {{ color:var(--accent-strong); text-underline-offset:.2em; }}
  p, dd, code {{ overflow-wrap:anywhere; }}
  h1 {{ margin:0; overflow-wrap:anywhere; }} h2 {{ margin-top:0; }}
  .panel {{ padding:28px; border:1px solid var(--line); border-radius:var(--radius); background:var(--panel); margin:20px 0; }}
  .hero p, .muted {{ color:var(--muted); line-height:1.6; }}
  .eyebrow {{ text-transform:uppercase; letter-spacing:.14em; font-size:.8rem; font-weight:700; color:var(--accent-strong); }}
  .fact-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }}
  .fact {{ min-width:0; border-top:2px solid var(--line); padding-top:18px; }}
  .fact h3 {{ margin:0 0 12px; }} .fact p {{ line-height:1.6; }}
  .fact-value {{ white-space:pre-wrap; font-family:ui-monospace,monospace; }}
  .fact-meta {{ font-size:.9rem; color:var(--muted); }}
  .actions {{ display:flex; flex-wrap:wrap; gap:14px; align-items:center; }}
  .actions a {{ padding:10px 0; }}
  .lookup-form {{ display:flex; flex-wrap:wrap; gap:12px; align-items:end; }}
  label {{ display:grid; gap:8px; flex:1; min-width:180px; }}
  input, button {{ font:inherit; border:1px solid var(--line); border-radius:10px; padding:12px; }}
  input {{ width:100%; background:white; min-width:0; }}
  button {{ background:var(--accent); color:white; cursor:pointer; }}
  pre {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
  [hidden] {{ display:none !important; }}
  @media(max-width:720px) {{ .fact-grid {{ grid-template-columns:1fr; }} .panel {{ padding:22px; }} }}
</style></head><body><div class="page" data-site-base="{base}">
{header}
<main>
  <section class="panel hero">
    <p class="eyebrow">Repository profile</p>
    <h1 id="repository-title">Inspect a repository.</h1>
    <p id="repository-status" role="status" aria-live="polite">Enter a repository to see its available facts and evidence.</p>
    <form id="profile-lookup" class="lookup-form">
      <label>Repository<input id="profile-repository" placeholder="owner/repo or a repository URL" required></label>
      <button type="submit">Look up repository</button>
    </form>
    <div class="actions" id="profile-links"></div>
  </section>
  <section id="profile-missing" class="panel" hidden>
    <h2>Repository not indexed</h2>
    <p>Coverage is partial. A missing profile does not mean the repository does not exist.
      Inspect the upstream documentation, or try another repository above.</p>
    <p><a href="{base}/repositories/">Browse indexed repositories</a></p>
  </section>
  <div id="profile-content" hidden>
    <section class="panel"><h2>What is known</h2>
      <p>Recorded facts help with orientation. Missing, stale, conflicting or insufficient answers require upstream inspection.
        Confidence describes the assessment; it is not permission to execute a command.</p>
      <div id="profile-facts" class="fact-grid"></div>
    </section>
    <section id="execution-candidates" class="panel" hidden><h2>Other execution candidates</h2>
      <p>These are alternatives with their own scope. They are not selected repository defaults.</p>
      <div id="candidate-facts" class="fact-grid"></div>
    </section>
    <section id="trust" class="panel"><h2>Trust, age and conflicts</h2>
      <p id="profile-trust"></p><p id="profile-age"></p>
      <p>Verified means pipeline checks resolved against inspected evidence. It does not imply human review,
        complete instructions or independent correctness. Export time does not refresh the facts.</p>
      <div id="profile-conflicts"></div>
    </section>
  </div>
  <noscript><p class="panel">Enable JavaScript for this view, or use the <a href="{base}/v0/repos/index.json">JSON inventory</a>.</p></noscript>
</main></div><script type="module" src="{base}/assets/repository.js"></script></body></html>'''
