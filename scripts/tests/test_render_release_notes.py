import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_release_notes import render  # noqa: E402


def test_release_notes_select_version_and_explain_channels(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[workspace.package]\nversion="2.0.0-rc.1"\n')
    owner = tmp_path / "crates/dotrepo-core/src/adoption.rs"
    owner.parent.mkdir(parents=True)
    owner.write_text('pub const DEFAULT_CI_RELEASE_VERSION: &str = "1.0.4";')
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n\nFuture changes.\n\n## 1.0.4 — date\n\nContained writes. [Details](docs/install.md).\n"
    )
    stable = render(tmp_path, "1.0.4")
    assert "Stable release 1.0.4" in stable and "Contained writes." in stable
    assert "Future changes." not in stable
    assert "](https://github.com/maxwellsantoro/dotrepo/blob/main/docs/install.md)" in stable
    assert "cargo install dotrepo-mcp --version 1.0.4 --locked" in stable
    preview = render(tmp_path, "2.0.0-rc.2")
    assert "Preview release" in preview and "stable **1.0.4**" in preview
    assert "Future changes." in preview
    assert "--version 2.0.0-rc.2" in preview
