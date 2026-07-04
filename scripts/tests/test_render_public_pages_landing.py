import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "render_public_pages_landing.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("render_public_pages_landing", SCRIPT)
public_pages = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(public_pages)


def write_record(root: Path, owner: str, repo: str, status: str, language: str) -> None:
    record_dir = root / "repos" / "github.com" / owner / repo
    record_dir.mkdir(parents=True)
    (record_dir / "record.toml").write_text(
        "\n".join(
            [
                'schema = "dotrepo/v0.1"',
                "",
                "[record]",
                'mode = "overlay"',
                f'status = "{status}"',
                "",
                "[repo]",
                f'name = "{repo}"',
                f'languages = ["{language}"]',
                "",
            ]
        )
    )


def inventory_entry(repo: str) -> dict:
    root = f"/v0/repos/github.com/example/{repo}"
    return {
        "identity": {"host": "github.com", "owner": "example", "repo": repo},
        "name": repo,
        "description": f"Description for {repo}",
        "links": {
            "self": f"{root}/index.json",
            "trust": f"{root}/trust.json",
            "queryTemplate": f"{root}/query?path={{dot_path}}",
        },
    }


class PublicPageRendererTests(unittest.TestCase):
    def test_first_party_document_links_exist(self) -> None:
        public_pages.validate_first_party_document_links()

    def test_index_progress_distinguishes_status_from_presence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_root = Path(temp_dir) / "index"
            write_record(index_root, "example", "imported", "imported", "Rust")
            write_record(index_root, "example", "inferred", "inferred", "Python")
            write_record(index_root, "example", "reviewed", "reviewed", "Go")
            write_record(index_root, "example", "verified", "verified", "TypeScript")

            progress = public_pages.load_index_progress(index_root)

        self.assertEqual(progress["reviewedOrBetterCount"], 2)
        self.assertEqual(progress["importedOrInferredCount"], 2)

    def test_homepage_repository_cards_can_be_bounded(self) -> None:
        inventory = {
            "repositories": [inventory_entry(f"repo-{index}") for index in range(12)]
        }

        rendered = public_pages.render_repository_cards(inventory, limit=8)

        self.assertEqual(rendered.count('class="repo-card"'), 8)
        self.assertIn("repo-7", rendered)
        self.assertNotIn("repo-8", rendered)
        self.assertIn("Query input", rendered)
        self.assertIn('aria-label="Open github.com/example/repo-0 summary"', rendered)

    def test_repository_catalog_is_searchable(self) -> None:
        inventory = {
            "repositoryCount": 2,
            "repositories": [inventory_entry("alpha"), inventory_entry("beta")],
        }

        rendered = public_pages.render_repositories_index(inventory, "")

        self.assertIn('id="repository-search"', rendered)
        self.assertIn('id="repository-result-count"', rendered)
        self.assertIn('data-inventory-url="/v0/repos/index.json"', rendered)
        self.assertIn("fetch(inventoryUrl)", rendered)
        self.assertIn("const RESULT_LIMIT = 60", rendered)
        self.assertIn("queryInputHref(item)", rendered)
        self.assertNotIn('data-search-index="', rendered)

    def test_pagedigest_dashboard_renders_export_economics(self) -> None:
        rendered = public_pages.render_pagedigest_stats_dashboard(
            {
                "pagedigest": {
                    "recordsCovered": 3066,
                    "recordsNeedingFetch": 31,
                    "fetchesAvoided": 3035,
                    "bytesCovered": 42_500_000,
                    "bytesAvoided": 41_200_000,
                    "estimatedTokensAvoided": 9_800_000,
                    "siteRev": 3,
                    "manifestBytes": 850_000,
                    "generated": "2026-07-03T01:15:11Z",
                }
            },
            "",
        )

        self.assertIn("PageDigest dogfood", rendered)
        self.assertIn("3,066 tracked records", rendered)
        self.assertIn("31 needing fetch", rendered)
        self.assertIn("3,035 fetches avoided", rendered)
        self.assertIn("39.3 MB avoided", rendered)
        self.assertIn("~9.8M tokens avoided", rendered)
        self.assertIn("site_rev 3", rendered)
        self.assertIn("/v0/stats.json", rendered)

    def test_pagedigest_dashboard_handles_missing_stats(self) -> None:
        rendered = public_pages.render_pagedigest_stats_dashboard({}, "")

        self.assertIn("first stats-bearing", rendered)
        self.assertIn("/v0/stats.json", rendered)

    def test_health_json_summarizes_public_surface_coherence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            public_root = Path(temp_dir)
            (public_root / "v0/repos").mkdir(parents=True)
            (public_root / "v0/snapshots/abc123/repos").mkdir(parents=True)
            (public_root / ".well-known").mkdir()
            meta = {
                "apiVersion": "v0",
                "generatedAt": "2026-07-03T12:00:00Z",
                "snapshotId": "abc123",
                "snapshotDigest": "abc123def456",
                "paths": {"inventory": "/dotrepo/v0/snapshots/abc123/repos/index.json"},
            }
            inventory = {
                "repositoryCount": 1,
                "repositories": [inventory_entry("alpha")],
            }
            stats = {
                "latest": {
                    "snapshotId": "abc123",
                    "snapshotDigest": "abc123def456",
                    "repositoryCount": 1,
                },
                "pagedigest": {"siteRev": 2, "recordsCovered": 1},
            }
            files = {
                "freshness": {"snapshotDigest": "abc123def456"},
                "files": [
                    {
                        "path": "v0/snapshots/abc123/repos/index.json",
                        "bytes": 42,
                        "sha256": "a" * 64,
                    }
                ],
            }
            pagedigest = {
                "version": 1,
                "site_rev": 2,
                "entries": {"/v0/repos/github.com/example/alpha/index.json": {"rev": 1}},
            }
            (public_root / "index.html").write_text("<!doctype html>")
            (public_root / "v0/meta.json").write_text(json.dumps(meta))
            (public_root / "v0/repos/index.json").write_text(json.dumps(inventory))
            (public_root / "v0/stats.json").write_text(json.dumps(stats))
            (public_root / "v0/files.json").write_text(json.dumps(files))
            (public_root / ".well-known/pagedigest.json").write_text(json.dumps(pagedigest))

            health = public_pages.build_public_health(public_root, meta, inventory, stats)

        self.assertIs(health["ok"], True)
        self.assertEqual(health["canonicalOrigin"], "https://dotrepo.org")
        self.assertEqual(health["snapshotId"], "abc123")
        self.assertEqual(health["reposIndexCount"], 1)
        self.assertEqual(health["statsRepositoryCount"], 1)
        self.assertEqual(health["pagedigestSiteRev"], 2)
        self.assertEqual(health["checkedAt"], "2026-07-03T12:00:00Z")
        self.assertEqual(len(health["homepageDigest"]), 64)


if __name__ == "__main__":
    unittest.main()
