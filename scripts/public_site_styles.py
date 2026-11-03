"""Product layout over the pinned, independently vendored Lazy Collective family."""

import html
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "public_assets/lazy-collective/v1"


def publish_family_assets(output: Path) -> None:
    destination = output / "assets/lazy-collective/v1"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("family.css", "UPSTREAM.json"):
        (destination / name).write_bytes((ASSETS / name).read_bytes())


def render_site_chrome(base_path: str = "") -> str:
    href = html.escape(base_path.rstrip("/") + "/assets/lazy-collective/v1/family.css", quote=True)
    return f'<link rel="stylesheet" href="{href}">\n' + SITE_CHROME


SITE_CHROME = """<style>
  :root { --paper:var(--lc-paper); --paper-strong:var(--lc-paper-deep); --ink:var(--lc-ink);
    --muted:var(--lc-muted); --line:var(--lc-rule); --accent:var(--lc-green);
    --accent-strong:var(--lc-green-dark); --signal:var(--lc-ochre); --panel:transparent; --radius:0; }
  body { background:var(--lc-paper); color:var(--lc-ink); font-family:var(--lc-body); }
  .page { max-width:1280px; margin:0 auto; padding:28px 32px 60px; }
  .nav { display:flex; align-items:center; justify-content:space-between; gap:24px;
    margin-bottom:30px; padding-bottom:22px; border-bottom:2px solid var(--accent); }
  .brand { display:flex; align-items:baseline; flex-wrap:wrap; gap:6px 16px; }
  .brand__mark { color:var(--ink); text-decoration:none; font:700 2.2rem/1.1 var(--lc-display); letter-spacing:-.05em; }
  .brand__tag { font-size:.8rem; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); }
  .nav__links { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:4px 12px; }
  .nav__links a { display:inline-flex; align-items:center; min-height:44px; padding:8px 4px;
    border:0; border-radius:0; background:transparent; color:var(--ink); text-decoration:none; }
  .nav__links a:hover { background:transparent; text-decoration:underline; transform:none; }
  .nav__links a[aria-current="page"] { color:var(--accent); background:transparent;
    text-decoration:underline; text-decoration-thickness:2px; text-underline-offset:6px; }
  h1, h2, h3, .hero h1 { font-family:var(--lc-display); }
  .hero h1 { font-size:clamp(2.4rem,4.5vw,4rem); line-height:1.06; letter-spacing:-.045em; max-width:20ch; }
  .hero { gap:38px; }
  .panel { box-shadow:none; backdrop-filter:none; border:0; border-radius:0; background:transparent; }
  .hero__copy { padding:32px 0; }
  .hero__copy::after { display:none; }
  .hero__lede { color:var(--ink); font-size:1.15rem; line-height:1.55; }
  .hero__meta, .lookup-example { background:transparent; padding:28px 0; border-top:2px solid var(--accent); }
  .cta { min-height:48px; border-radius:9px; box-shadow:none; }
  .cta:hover { transform:none; box-shadow:none; }
  .cta--primary { background:var(--accent); color:white; }
  .cta--primary:hover { background:var(--accent-strong); }
  .cta--secondary { background:transparent; border:1px solid var(--line); color:var(--accent-strong); }
  .section { padding:30px 0; border-top:1px solid var(--line); }
  .section h2, .hero__meta h2 { font-size:1.7rem; color:var(--ink); letter-spacing:-.03em; text-transform:none; }
  .stat, .feature, .api-card, .repo-card { box-shadow:none; }
  .stat { border-radius:0; background:transparent; }
  .family-context { max-width:1216px; margin:0 auto 40px; padding:22px 0; border-top:1px solid var(--line); color:var(--muted); font-size:.9rem; }
  .family-context a { color:var(--accent-strong); }
  @media(max-width:720px) {
    .page { padding:20px 18px 40px; }
    .nav { flex-direction:column; align-items:flex-start; gap:10px; margin-bottom:22px; }
    .nav .nav__links { width:100%; justify-content:flex-start; overflow:visible; gap:0 14px; }
    .nav .nav__links a { padding:7px 0; }
    .brand__mark { font-size:1.9rem; }
    .hero { gap:20px; }
    .hero__copy, .lookup-example, .section { padding:22px 0; }
    .hero h1 { font-size:2.6rem; }
    .family-context { margin-inline:18px; }
  }
</style>"""
