"""Execute only controlled Rake fixtures; importer assertions live in Rust."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("rake") is None, reason="Rake executable unavailable")
@pytest.mark.parametrize("fixture", ["rake-if-modifier", "rake-unless-modifier", "rake-if-block"])
def test_conditional_declarations_do_not_create_a_test_target(fixture):
    rakefile = ROOT / "crates/dotrepo-core/tests/fixtures/import" / fixture / "Rakefile"
    result = subprocess.run(
        ["rake", "-f", str(rakefile), "test"], text=True, capture_output=True, timeout=20
    )
    assert result.returncode != 0
    assert "Don't know how to build task 'test'" in result.stderr
