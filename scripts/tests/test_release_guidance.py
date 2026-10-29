import shutil
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_release_guidance import check


def test_release_guidance_detects_and_repairs_prose_drift(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "Cargo.toml",
        "crates/dotrepo-core/src/adoption.rs",
        "docs/install.md",
        "docs/distribution.md",
        "README.md",
        "docs/release-compatibility.md",
        "index/telemetry/public-surface-review-20261028/release-1.0.4-verification.json",
        "docs/public-factual-accuracy-benchmark.md",
        "scripts/fixtures/public_upstream_accuracy_baseline.json",
        "benchmarks/head-to-head/upstream-2026-10-27/workload.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    assert check(tmp_path) == []
    install = tmp_path / "docs/install.md"
    install.write_text(install.read_text().replace("2.0.0-rc.1", "2.0.0-alpha.0"))
    benchmark = tmp_path / "docs/public-factual-accuracy-benchmark.md"
    benchmark.write_text(benchmark.read_text().replace("119 independently", "123 independently"))
    assert len(check(tmp_path)) == 2
    assert check(tmp_path, write=True) == []
    assert check(tmp_path) == []
    install.write_text(install.read_text().replace("--version 1.0.4", "--version 1.0.2"))
    assert "installation commands" in check(tmp_path)[0]
    adoption = tmp_path / "crates/dotrepo-core/src/adoption.rs"
    adoption.write_text(adoption.read_text().replace('"1.0.4"', '"1.0.3"'))
    assert any("publication/install receipt" in error for error in check(tmp_path))


def test_package_readme_links_are_checked_in_package_context(tmp_path):
    root = Path(__file__).resolve().parents[2]
    # Reuse the normal metadata tree while substituting one isolated package.
    for relative in (
        "Cargo.toml",
        "crates/dotrepo-core/src/adoption.rs",
        "docs/install.md",
        "docs/distribution.md",
        "docs/public-factual-accuracy-benchmark.md",
        "scripts/fixtures/public_upstream_accuracy_baseline.json",
        "benchmarks/head-to-head/upstream-2026-10-27/workload.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    package = tmp_path / "crates/example"
    package.mkdir()
    (package / "Cargo.toml").write_text('[package]\nname="example"\nreadme="README.md"\n')
    (package / "README.md").write_text("[Install](docs/install.md)\n")
    assert any("must be absolute" in error for error in check(tmp_path))
    (package / "README.md").write_text("[Install](https://example.com/install)\n")
    assert check(tmp_path) == []
