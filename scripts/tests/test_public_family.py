import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from public_site_styles import ASSETS, publish_family_assets, render_site_chrome


def test_pinned_family_asset_is_exported_without_a_remote_dependency(tmp_path):
    publish_family_assets(tmp_path)
    target = tmp_path / "assets/lazy-collective/v1"
    css = (target / "family.css").read_bytes()
    receipt = json.loads((target / "UPSTREAM.json").read_text())
    assert css == (ASSETS / "family.css").read_bytes()
    assert receipt["sha256"] == hashlib.sha256(css).hexdigest()
    assert receipt["version"] == "1.0.0"
    assert b"fonts.googleapis.com" not in css


def test_family_stylesheet_preserves_non_root_hosting_path():
    assert 'href="/dotrepo/assets/lazy-collective/v1/family.css"' in render_site_chrome("/dotrepo/")
    assert 'href="/assets/lazy-collective/v1/family.css"' in render_site_chrome()
