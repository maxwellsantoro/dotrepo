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
    install.write_text(install.read_text().replace("--version 1.0.3", "--version 1.0.2"))
    assert "installation commands" in check(tmp_path)[0]
