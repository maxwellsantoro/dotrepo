import importlib.util
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

    def test_repository_catalog_is_searchable(self) -> None:
        inventory = {
            "repositoryCount": 2,
            "repositories": [inventory_entry("alpha"), inventory_entry("beta")],
        }

        rendered = public_pages.render_repositories_index(inventory, "")

        self.assertIn('id="repository-search"', rendered)
        self.assertIn('id="repository-result-count"', rendered)
        self.assertEqual(rendered.count('data-search-index="'), 2)
        self.assertIn("card.hidden = !matches", rendered)


if __name__ == "__main__":
    unittest.main()
