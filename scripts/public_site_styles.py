"""Shared public-site chrome, including navigation that stays visible on mobile."""

SITE_CHROME = """<style>
  :root { --paper:#f6f1e8; --paper-strong:#efe6d7; --ink:#16181b;
    --muted:#5c635d; --line:rgba(54,46,28,.14); --accent:#116466;
    --accent-strong:#0d494b; --panel:rgba(255,251,244,.84); --radius:22px; }
  * { box-sizing:border-box; }
  body { margin:0; color:var(--ink); font-family:"Avenir Next","Segoe UI","Helvetica Neue",sans-serif;
    background:radial-gradient(circle at top left,rgba(17,100,102,.18),transparent 34%),
      radial-gradient(circle at top right,rgba(196,87,46,.12),transparent 30%),
      linear-gradient(180deg,#fbf6ec,var(--paper) 54%,var(--paper-strong)); }
  .page { max-width:1180px; margin:0 auto; padding:28px 18px 80px; }
  .nav { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:30px; }
  .brand { display:flex; align-items:baseline; gap:12px; }
  .brand__mark { display:inline-flex; align-items:baseline; gap:.06em; color:var(--ink); text-decoration:none;
    font-family:ui-monospace,monospace; font-size:1.4rem; font-weight:500; }
  .brand__dot { display:inline-block; width:.4em; height:.4em; border-radius:50%; background:currentColor; }
  .brand__tag { font-size:.88rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
  .nav__links { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:12px; }
  .nav__links a { display:inline-flex; align-items:center; padding:10px 14px; border:1px solid var(--line);
    border-radius:999px; background:rgba(255,255,255,.48); color:var(--ink); text-decoration:none; }
  .nav__links a[aria-current="page"] { background:var(--accent); color:white; }
  a:focus-visible, button:focus-visible, input:focus-visible, summary:focus-visible {
    outline:3px solid var(--accent); outline-offset:4px; }
  .hero h1 { font-family:"Iowan Old Style","Palatino Linotype","Book Antiqua",Palatino,serif;
    font-size:clamp(2.25rem,4.6vw,4rem); line-height:1.04; letter-spacing:-.045em; }
  @media(max-width:720px) {
    .page { padding:18px 14px 48px; }
    .nav { flex-direction:column; align-items:flex-start; }
    .nav .nav__links { width:100%; flex-wrap:wrap; justify-content:flex-start; overflow:visible; gap:8px; }
    .nav .nav__links a { padding:10px 12px; }
    .brand { flex-wrap:wrap; gap:8px; }
  }
  @media(prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } * { transition:none !important; } }
</style>"""
