from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH_ROOT = REPO_ROOT / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH_ROOT))

from bench.arms.base import Http  # noqa: E402
from bench.arms.github_arm import DOC_PATHS, GitHubArm  # noqa: E402
from bench.cache import ReplayCacheMiss, ResponseCache  # noqa: E402
from bench.fields import FIELDS_BY_ID  # noqa: E402
from bench.model import Answer, Outcome, score_answer, values_match  # noqa: E402
from bench.run import load_gold, run, summarize  # noqa: E402


def test_independent_gold_has_evidence_and_frozen_cohorts() -> None:
    items = load_gold(str(BENCH_ROOT / "gold.independent.yaml"))

    assert len({item.repo for item in items}) == 13
    assert {item.cohort for item in items} == {"indexed_independent", "holdout_unindexed"}
    assert all(
        item.gold is None or all(item.evidence.get(key) for key in ("url", "locator", "checked_at"))
        for item in items
    )


def test_gold_accepts_evidenced_alternatives_and_version_equivalence() -> None:
    test_field = FIELDS_BY_ID["test"]
    outcome = score_answer(
        test_field,
        Answer("python -m pytest", "high"),
        ["tox", "python -m pytest"],
    )

    assert outcome == Outcome.CORRECT
    assert values_match("version", 'rust-version = "1.70"', "1.70.0")
    assert not values_match("version", "1.71", "1.70.0")


def test_categorical_matching_ignores_markdown_and_smart_quote_artifacts() -> None:
    assert values_match(
        "categorical",
        "Serde *ser*ializes Rust’s data structures",
        "Serde serializes Rust's data structures",
    )
    assert values_match(
        "categorical",
        "Flask is a lightweight [WSGI] framework",
        "lightweight WSGI framework",
    )


def test_summary_breaks_results_out_by_cohort() -> None:
    rows = [
        {
            "outcome": "correct",
            "field_class": "buried",
            "cohort": "indexed_independent",
            "bytes": 10,
            "latency_ms": 2,
        },
        {
            "outcome": "abstained",
            "field_class": "buried",
            "cohort": "holdout_unindexed",
            "bytes": 5,
            "latency_ms": 1,
        },
    ]

    result = summarize(rows)

    assert result["by_cohort"]["indexed_independent"]["accuracy"] == 1.0
    assert result["by_cohort"]["holdout_unindexed"]["coverage"] == 0.0
    assert result["by_cohort"]["holdout_unindexed"]["by_class"]["buried"]["n"] == 1


def test_replay_cache_miss_fails_closed_without_network(tmp_path: Path) -> None:
    http = Http(cache=ResponseCache(str(tmp_path), "replay"))

    with pytest.raises(RuntimeError, match="replay cache miss"):
        http.get("https://example.invalid/not-frozen")


def test_runner_does_not_convert_replay_cache_miss_to_abstention() -> None:
    class MissingReplayArm:
        name = "missing-replay"

        def prefetch(self, repo: str) -> None:
            raise ReplayCacheMiss(f"replay cache miss: {repo}")

        def configuration(self) -> dict:
            return {}

    gold = load_gold(str(BENCH_ROOT / "gold.fixture.yaml"))

    with pytest.raises(ReplayCacheMiss, match="replay cache miss"):
        run(gold, MissingReplayArm())


def test_llm_replay_cache_is_prompt_and_model_specific(tmp_path: Path) -> None:
    provider = "openrouter"
    model = "example/model"
    prompt = "extract the canonical test command"
    writer = ResponseCache(str(tmp_path), "freeze")
    key = GitHubArm._llm_cache_key(provider, model, prompt)
    writer.put(key, 200, '{"value": "tox", "confidence": "high"}')

    arm = GitHubArm(Http(cache=ResponseCache(str(tmp_path), "replay")), extractor="llm")

    assert arm._cached_llm_result(provider, model, prompt) == ("tox", "high")
    with pytest.raises(RuntimeError, match="replay cache miss"):
        arm._cached_llm_result(provider, model, "a different prompt")


def test_github_baseline_probes_real_world_source_variants() -> None:
    assert "README.rst" in DOC_PATHS["readme"]
    assert ".github/SECURITY.md" in DOC_PATHS["security"]
    assert ".github/CONTRIBUTING.md" in DOC_PATHS["contributing"]
    assert DOC_PATHS["package"] == ("package.json",)
    assert DOC_PATHS["go_mod"] == ("go.mod",)
    assert "Justfile" in DOC_PATHS["justfile"]
