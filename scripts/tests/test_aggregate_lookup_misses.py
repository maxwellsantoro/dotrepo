from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "aggregate_lookup_misses.py"
SPEC = importlib.util.spec_from_file_location("aggregate_lookup_misses", SCRIPT)
agg = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(agg)


def test_parse_prefixed_log_line() -> None:
    line = (
        'info: DOTREPO_LOOKUP_MISS {"host":"github.com","owner":"acme","repo":"widgets",'
        '"route":"query","ts":"2026-07-08T00:00:00Z"}'
    )
    parsed = agg.parse_line(line)
    assert parsed is not None
    assert parsed["identity"] == "github.com/acme/widgets"


def test_build_report_ranks_top_misses() -> None:
    misses = [
        {"host": "github.com", "owner": "a", "repo": "one", "identity": "github.com/a/one", "route": "query"},
        {"host": "github.com", "owner": "a", "repo": "one", "identity": "github.com/a/one", "route": "query"},
        {"host": "github.com", "owner": "b", "repo": "two", "identity": "github.com/b/two", "route": "batch"},
    ]
    report = agg.build_report(misses, top=10)
    assert report["missCount"] == 3
    assert report["uniqueIdentities"] == 2
    assert report["topMisses"][0]["identity"] == "github.com/a/one"
    assert report["topMisses"][0]["count"] == 2
