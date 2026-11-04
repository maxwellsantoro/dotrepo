"""Shared Lazy Collective source-status vocabulary for retained findings.

`current`: every declared source still has the bound bytes. `changed`: a declared
source now has different bytes. `unknown`: a source is missing, failed, out of
scope, uninspected, or its bound body is no longer retained. Source status says
nothing about whether a finding is true; requirement outcomes are a separate axis.

The executable definition is PageDigest's test-vectors/source-status/vectors.json,
vendored here as scripts/tests/fixtures/source-status-vectors.json.
"""

from __future__ import annotations

from collections.abc import Iterable


def source_state(bound: str, observed: str | None, bound_body_retained: bool = True) -> str:
    """One declared source: unknown if unobserved, changed if bytes differ."""
    if observed is None:
        return "unknown"
    if observed != bound:
        return "changed"
    return "current" if bound_body_retained else "unknown"


def source_status(states: Iterable[str]) -> str:
    """Combine per-source states: any changed wins, then unknown, else current."""
    states = list(states)
    if not states:
        return "unknown"
    if "changed" in states:
        return "changed"
    return "unknown" if "unknown" in states else "current"
