"""Canonical/social metadata and content-addressed sitemap for generated pages."""

import hashlib
import html
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

ORIGIN = "https://dotrepo.org"
START = "<!-- dotrepo:discovery:start -->"
END = "<!-- dotrepo:discovery:end -->"


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ""
        self.description = "Repository facts with evidence, trust, and explicit fallback."

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content", self.description)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def publish_discovery(root: Path, base_path: str = "") -> None:
    urls = []
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith(("v0/", "query-input/")):
            continue
        route = relative.removesuffix("index.html")
        canonical = ORIGIN + base_path.rstrip("/") + "/" + quote(route, safe="/")
        urls.append(canonical)
        text = path.read_text()
        if START in text and END in text:
            before, rest = text.split(START, 1)
            text = before + rest.split(END, 1)[1].removeprefix("\n")
        metadata = PageMetadata()
        metadata.feed(text)
        title = html.escape(metadata.title.strip(), quote=True)
        description = html.escape(metadata.description, quote=True)
        url = html.escape(canonical, quote=True)
        tags = f'''{START}
  <link rel="canonical" href="{url}">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23116466'/%3E%3Ccircle cx='16' cy='16' r='6' fill='%23fbf5e9'/%3E%3C/svg%3E">
  <meta property="og:url" content="{url}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="dotrepo">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <style>
    * {{ box-sizing: border-box; }}
    time, .proof-card dd, .lookup-example dd {{ overflow-wrap: anywhere; min-width: 0; }}
    .cta-row {{ align-items: stretch; }}
    .cta-row .cta {{ display: inline-flex; align-items: center; justify-content: center; }}
    a:focus-visible, button:focus-visible, input:focus-visible {{ outline: 3px solid #116466; outline-offset: 4px; }}
    @media (max-width: 480px) {{ .cta-row {{ display: grid; grid-template-columns: 1fr; }} }}
  </style>
{END}'''
        if "</head>" not in text:
            raise ValueError(f"generated HTML has no head: {relative}")
        path.write_text(text.replace("</head>", tags + "\n</head>", 1))
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "".join(f"  <url><loc>{html.escape(url)}</loc></url>\n" for url in urls)
    sitemap += "</urlset>\n"
    digest = hashlib.sha256(sitemap.encode()).hexdigest()
    (root / "sitemaps").mkdir(exist_ok=True)
    (root / "sitemaps" / f"{digest}.xml").write_text(sitemap)
    (root / "sitemap.xml").write_text(sitemap)
    (root / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {ORIGIN}{base_path.rstrip('/')}/sitemap.xml\n"
    )
