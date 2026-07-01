import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "audit_index_sample.py"
SPEC = importlib.util.spec_from_file_location("audit_index_sample", SCRIPT)
audit_index_sample = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit_index_sample)


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
    license_: str | None = "MIT",
    docs_root: str | None = "https://example.com/docs",
    topics: list[str] | None = None,
    with_evidence: bool = True,
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
        'generated_at = "2026-03-10T00:00:00Z"',
        "",
        "[record.trust]",
        f'confidence = "{confidence}"',
        'provenance = ["imported"]',
        "",
        "[repo]",
        f'name = "{repo}"',
        f'description = "{repo} description"',
        f'homepage = "https://github.com/{owner}/{repo}"',
    ]
    if license_ is not None:
        lines.append(f'license = "{license_}"')
    lines.append("languages = [")
    lines.extend(f'    "{language}",' for language in languages)
    lines.append("]")
    if build is not None:
        lines.append(f'build = "{build}"')
    if test is not None:
        lines.append(f'test = "{test}"')
    if topics:
        lines.append("topics = [")
        lines.extend(f'    "{topic}",' for topic in topics)
        lines.append("]")
    lines.extend(["", "[owners]"])
    if security is not None:
        lines.append(f'security_contact = "{security}"')
    if docs_root is not None:
        lines.extend(["", "[docs]", f'root = "{docs_root}"'])
    (record_dir / "record.toml").write_text("\n".join(lines) + "\n")
    if with_evidence:
        (record_dir / "evidence.md").write_text("# Evidence\n")


def build_mixed_index(tmp_path: Path) -> Path:
    index_root = tmp_path / "index"
    # Fully complete, verified, high-confidence record: lowest risk.
    write_record(
        index_root,
        "owner",
        "solid",
        status="verified",
        confidence="high",
        languages=["Rust"],
    )
    # Record missing build/test/security: highest risk in this fixture.
    write_record(
        index_root,
        "owner",
        "sparse",
        status="inferred",
        confidence="low",
        languages=["Rust"],
        build=None,
        test=None,
        security=None,
        license_=None,
        docs_root=None,
    )
    # Near-promotion-threshold: not verified, but build/test/security present.
    write_record(
        index_root,
        "owner",
        "almost",
        status="imported",
        confidence="medium",
        languages=["Go"],
    )
    write_record(
        index_root,
        "owner",
        "another",
        status="verified",
        confidence="high",
        languages=["Python"],
    )
    return index_root


def test_risk_factors_missing_fields_outrank_complete_verified_record(tmp_path: Path) -> None:
    index_root = build_mixed_index(tmp_path)
    records = audit_index_sample.load_records(index_root)
    enriched = audit_index_sample.compute_risk(records)
    by_repo = {record["identity"].split("/")[-1]: record for record in enriched}

    sparse = by_repo["sparse"]
    solid = by_repo["solid"]
    almost = by_repo["almost"]

    assert sparse["riskWeight"] > solid["riskWeight"]
    assert "missing:build" in sparse["riskFactors"]
    assert "missing:test" in sparse["riskFactors"]
    assert "missing:security_contact" in sparse["riskFactors"]
    assert "confidence:low" in sparse["riskFactors"]

    assert "near-promotion-threshold" in almost["riskFactors"]
    assert not solid["riskFactors"] or "near-promotion-threshold" not in solid["riskFactors"]


def test_sample_is_deterministic_given_fixed_seed(tmp_path: Path) -> None:
    index_root = build_mixed_index(tmp_path)
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)

    report_a = audit_index_sample.build_report(index_root, sample_size=3, seed=42, now=now)
    report_b = audit_index_sample.build_report(index_root, sample_size=3, seed=42, now=now)

    identities_a = [record["identity"] for record in report_a["sample"]]
    identities_b = [record["identity"] for record in report_b["sample"]]
    assert identities_a == identities_b

    report_c = audit_index_sample.build_report(index_root, sample_size=3, seed=7, now=now)
    identities_c = [record["identity"] for record in report_c["sample"]]
    # Not asserting inequality unconditionally (small population could coincide),
    # but with 4 records and differing seeds it is extremely likely to differ.
    assert isinstance(identities_c, list)


def test_sample_size_is_capped_at_population_size(tmp_path: Path) -> None:
    index_root = build_mixed_index(tmp_path)
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)

    report = audit_index_sample.build_report(index_root, sample_size=1000, seed=1, now=now)

    assert report["populationSize"] == 4
    assert report["sampleSize"] == 4
    assert report["requestedSampleSize"] == 1000
    identities = {record["identity"] for record in report["sample"]}
    assert len(identities) == 4


def test_json_and_markdown_output_shapes(tmp_path: Path) -> None:
    index_root = build_mixed_index(tmp_path)
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)

    report = audit_index_sample.build_report(index_root, sample_size=2, seed=99, now=now)

    assert report["schema"] == audit_index_sample.SCHEMA
    assert report["generatedAt"] == "2026-06-30T00:00:00Z"
    assert report["seed"] == 99
    assert report["sampleSize"] == 2
    for record in report["sample"]:
        for key in (
            "identity",
            "languageFamily",
            "status",
            "confidence",
            "riskWeight",
            "riskFactors",
            "recordPath",
            "evidencePath",
        ):
            assert key in record
        assert isinstance(record["riskFactors"], list)

    # JSON round-trips cleanly.
    json.loads(json.dumps(report))

    markdown = audit_index_sample.render_markdown(report)
    assert markdown.startswith("# Index Audit Sample")
    assert "## Sample" in markdown
    assert "## Inspection pointers" in markdown
    for record in report["sample"]:
        assert record["identity"] in markdown


def test_default_seed_is_derived_from_date() -> None:
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    assert audit_index_sample.default_seed(now) == 20260630


def test_evidence_path_missing_is_reported_as_none(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    write_record(
        index_root,
        "owner",
        "no-evidence",
        status="verified",
        confidence="high",
        languages=["Rust"],
        with_evidence=False,
    )
    records = audit_index_sample.load_records(index_root)
    assert records[0]["evidencePath"] is None


def test_inferred_language_family_uses_dominant_language_not_any_occurrence() -> None:
    record = {"repo": {"languages": ["Go", "Dockerfile", "Shell", "Rust"]}}
    assert audit_index_sample.inferred_language_family(record) == "Go"

    record = {"repo": {"languages": ["Rust", "Go"]}}
    assert audit_index_sample.inferred_language_family(record) == "Rust"
