from pathlib import Path
from xml.etree import ElementTree

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from public_site_discovery import publish_discovery


def test_discovery_has_canonical_social_and_versioned_sitemap(tmp_path):
    (tmp_path / "docs").mkdir()
    page = '<html><head><title>A &amp; B</title><meta name="description" content="Facts &amp; evidence"></head><body></body></html>'
    (tmp_path / "index.html").write_text(page)
    (tmp_path / "docs/index.html").write_text(page)
    publish_discovery(tmp_path, "/prefix")
    first = (tmp_path / "index.html").read_bytes()
    publish_discovery(tmp_path, "/prefix")
    assert (tmp_path / "index.html").read_bytes() == first
    text = (tmp_path / "docs/index.html").read_text()
    assert text.count('rel="canonical"') == 1
    assert 'href="https://dotrepo.org/prefix/docs/"' in text
    assert 'property="og:title" content="A &amp; B"' in text
    assert 'name="twitter:card" content="summary"' in text
    sitemap = (tmp_path / "sitemap.xml").read_text()
    tree = ElementTree.fromstring(sitemap)
    assert len(tree) == 2
    assert [p.read_text() for p in (tmp_path / "sitemaps").glob("*.xml")] == [sitemap]
    assert (
        "Sitemap: https://dotrepo.org/prefix/sitemap.xml" in (tmp_path / "robots.txt").read_text()
    )
