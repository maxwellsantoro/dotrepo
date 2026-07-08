from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "render_intent_quality_scorecard.py"
SPEC = importlib.util.spec_from_file_location("render_intent_quality_scorecard", SCRIPT)
scorecard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(scorecard)


def write_record(
    root: Path,
    repo: str,
    *,
    languages: list[str],
    build: str | None = "cargo build",
    test: str | None = "cargo test",
    security: str | None = None,
    candidates: bool = False,
) -> None:
    path = root / "repos" / "github.com" / "example" / repo
    path.mkdir(parents=True)
    lines = [
        'schema = "dotrepo/v0.1"',
        "",
        "[record]",
        'mode = "overlay"',
        'status = "verified"',
        "",
        "[repo]",
        f'name = "{repo}"',
        'description = "Example"',
        f"languages = {languages!r}".replace("'", '"'),
    ]
    if build:
        lines.append(f'build = "{build}"')
    if test:
        lines.append(f'test = "{test}"')
    if candidates:
        lines.extend(
            [
                "",
                "[[repo.build_candidates]]",
                'command = "cargo build"',
                'ecosystem = "Rust"',
                'source = "Cargo.toml"',
            ]
        )
    lines.extend(["", "[owners]"])
    if security:
        lines.append(f'security_contact = "{security}"')
    (path / "record.toml").write_text("\n".join(lines) + "\n")


def test_scorecard_tracks_execution_abstention(tmp_path: Path) -> None:
    write_record(tmp_path, "complete", languages=["Rust"], security="sec@example.com")
    write_record(
        tmp_path,
        "polyglot",
        languages=["Python", "Rust"],
        build=None,
        test=None,
        candidates=True,
    )

    records = scorecard.load_index_records(tmp_path)
    report = scorecard.build_scorecard(
        records,
        missing_budgets=scorecard.DEFAULT_MAX_MISSING_RATE,
        incorrect_budget=0.05,
        factual=None,
        generated_at="2026-07-08T00:00:00Z",
    )

    assert report["recordCount"] == 2
    execution = report["intents"]["execution"]
    assert execution["correctAbstentionCount"] == 1
    assert execution["completeCount"] >= 1
    assert "overview" in report["intents"]
    assert report["schema"] == "dotrepo/intent-quality-scorecard/v0.1"


def test_markdown_renders_intent_table(tmp_path: Path) -> None:
    write_record(tmp_path, "only", languages=["Go"])
    records = scorecard.load_index_records(tmp_path)
    report = scorecard.build_scorecard(
        records,
        missing_budgets=scorecard.DEFAULT_MAX_MISSING_RATE,
        incorrect_budget=0.05,
        factual=None,
        generated_at="2026-07-08T00:00:00Z",
    )
    markdown = scorecard.render_markdown(report)
    assert "| execution |" in markdown
    assert "Intent quality scorecard" in markdown
