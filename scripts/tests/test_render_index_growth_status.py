import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "render_index_growth_status.py"
SPEC = importlib.util.spec_from_file_location("render_index_growth_status", SCRIPT)
growth_status = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(growth_status)


def write_record(
    root: Path,
    owner: str,
    repo: str,
    *,
    status: str,
    confidence: str,
    languages: list[str],
    build: str | None = "make build",
    test: str | None = "make test",
    security: str | None = "security@example.com",
) -> None:
    record_dir = root / "repos" / "github.com" / owner / repo
    record_dir.mkdir(parents=True)
    lines = [
        'schema = "dotrepo/v0.1"',
        "",
        "[record]",
        'mode = "overlay"',
        f'status = "{status}"',
        f'source = "https://github.com/{owner}/{repo}"',
        "",
        "[record.trust]",
        f'confidence = "{confidence}"',
        'provenance = ["imported"]',
        "",
        "[repo]",
        f'name = "{repo}"',
        f'description = "{repo} description"',
        f'homepage = "https://github.com/{owner}/{repo}"',
        "languages = [",
    ]
    lines.extend(f'    "{language}",' for language in languages)
    lines.append("]")
    if build is not None:
        lines.append(f'build = "{build}"')
    if test is not None:
        lines.append(f'test = "{test}"')
    lines.extend(["", "[owners]"])
    if security is not None:
        lines.append(f'security_contact = "{security}"')
    (record_dir / "record.toml").write_text("\n".join(lines) + "\n")
    (record_dir / "evidence.md").write_text("# Evidence\n")


def test_summarize_reports_tranche_and_quality_queue(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    targets_file = tmp_path / "targets.txt"
    targets_file.write_text("# Rust\nowner/alpha\n# Go\nowner/beta\n")
    write_record(
        index_root,
        "owner",
        "alpha",
        status="verified",
        confidence="high",
        languages=["Rust"],
    )
    write_record(
        index_root,
        "owner",
        "beta",
        status="inferred",
        confidence="medium",
        languages=["Go"],
        build=None,
        test=None,
        security="unknown",
    )

    summary = growth_status.summarize(index_root, targets_file, max_items=5)

    assert summary["totalRecords"] == 2
    assert summary["tranche"]["presentCount"] == 2
    assert summary["tranche"]["coverageByGroup"]["Rust"] == {"target": 1, "present": 1}
    assert summary["languageFamilyCounts"] == {"Rust": 1, "Go": 1}
    assert summary["qualitySignals"]["lowerConfidenceQueue"] == 1
    assert summary["nextQualityTargets"][0]["identity"] == "github.com/owner/beta"


def test_malformed_toml_exits_with_path(tmp_path: Path) -> None:
    record_dir = tmp_path / "index" / "repos" / "github.com" / "owner" / "bad"
    record_dir.mkdir(parents=True)
    record_path = record_dir / "record.toml"
    record_path.write_text('schema = "dotrepo/v0.1"\n[record\n')

    with pytest.raises(SystemExit) as exc:
        growth_status.summarize(tmp_path / "index", tmp_path / "targets.txt", max_items=5)

    assert "failed to parse TOML" in str(exc.value)
    assert str(record_path) in str(exc.value)
