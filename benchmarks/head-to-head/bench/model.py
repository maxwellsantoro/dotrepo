"""Core data model and scoring.

The scoring is the point of this harness. Most metadata benchmarks score
correct/incorrect and stop. That hides the failure mode dotrepo's own trust
model cares about: a *confidently wrong* answer is worse than an honest "I don't
know", because a downstream agent acts on it without escalating. So every answer
lands in one of four buckets, and the headline metric is the confidently-wrong
rate, not raw accuracy.
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Optional


class Outcome(str, enum.Enum):
    CORRECT = "correct"                    # value present and matches gold
    ABSTAINED = "abstained"                # no value / explicit unknown
    WRONG_HEDGED = "wrong_hedged"          # wrong value, but confidence low/medium
    CONFIDENTLY_WRONG = "confidently_wrong"  # wrong value asserted at high confidence
    NO_GOLD = "no_gold"                    # gold answer not curated yet; excluded from scores


# Which fields GitHub exposes structurally vs. which are "buried" in prose/other
# files. dotrepo's entire thesis is that the buried set is where it earns its
# keep, so the report breaks results out by this axis.
class FieldClass(str, enum.Enum):
    GITHUB_NATIVE = "github_native"   # license, language, homepage, archived, owner...
    BURIED = "buried"                 # build cmd, test cmd, security contact, MSRV...


@dataclass
class Field:
    id: str
    prompt: str                  # human-readable question
    field_class: FieldClass
    match: str                   # "categorical" | "spdx" | "command" | "bool" | "url"
    dotrepo_path: Optional[str]  # dot-path for /v0/batch/query, or None
    github_hint: str             # how the github arm should try to answer


@dataclass
class GoldItem:
    repo: str                    # "github.com/sharkdp/fd"
    field_id: str
    gold: Optional[str]          # curated truth; None => NO_GOLD (excluded)
    note: str = ""


@dataclass
class Answer:
    value: Optional[str]         # None => abstained
    confidence: Optional[str]    # "high" | "medium" | "low" | None
    source: str = ""             # provenance string for audit
    bytes_over_wire: int = 0     # payload bytes this answer cost
    latency_ms: float = 0.0
    raw: Optional[dict] = field(default=None, repr=False)


# ---- normalization + matching -------------------------------------------------

_WS = re.compile(r"\s+")

# Minimal SPDX alias table. Extend as gold set grows.
_SPDX = {
    "mit license": "MIT", "mit": "MIT",
    "apache license 2.0": "Apache-2.0", "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
    "bsd 3-clause": "BSD-3-Clause", "bsd-3-clause": "BSD-3-Clause",
    "gnu general public license v3.0": "GPL-3.0", "gpl-3.0": "GPL-3.0", "gplv3": "GPL-3.0",
    "mozilla public license 2.0": "MPL-2.0", "mpl-2.0": "MPL-2.0",
    "the unlicense": "Unlicense", "unlicense": "Unlicense",
    "isc": "ISC", "isc license": "ISC",
    "mit or apache-2.0": "MIT OR Apache-2.0", "apache-2.0 or mit": "MIT OR Apache-2.0",
}


def _norm(s: str) -> str:
    return _WS.sub(" ", s.strip().lower())


def _spdx(s: str) -> str:
    n = _norm(s)
    return _SPDX.get(n, s.strip())


def values_match(match: str, got: str, gold: str) -> bool:
    """True if `got` should count as the gold answer under this field's rule."""
    if got is None or gold is None:
        return False
    if match == "spdx":
        return _spdx(got).lower() == _spdx(gold).lower()
    if match == "bool":
        truthy = {"true", "yes", "1", "archived", "unmaintained"}
        falsy = {"false", "no", "0", "active", "maintained"}
        g1 = _norm(got); g2 = _norm(gold)
        b1 = (g1 in truthy) - (g1 in falsy)
        b2 = (g2 in truthy) - (g2 in falsy)
        return b1 == b2 and b1 != 0
    if match == "url":
        strip = lambda u: _norm(u).rstrip("/").replace("https://", "").replace("http://", "").replace("www.", "")
        return strip(got) == strip(gold)
    if match == "command":
        # order-independent token containment: gold tokens must appear in got
        gt = set(_norm(got).replace("`", "").split())
        gd = set(_norm(gold).replace("`", "").split())
        core = {t for t in gd if t not in {"the", "a", "run", "then", "&&", "|"}}
        return core.issubset(gt) and len(core) > 0
    # categorical (default): normalized substring either direction
    a, b = _norm(got), _norm(gold)
    return a == b or a in b or b in a


def score_answer(field: Field, ans: Answer, gold: Optional[str]) -> Outcome:
    if gold is None:
        return Outcome.NO_GOLD
    if ans.value is None or _norm(ans.value) in {"", "unknown", "n/a", "none", "null"}:
        return Outcome.ABSTAINED
    if values_match(field.match, ans.value, gold):
        return Outcome.CORRECT
    # wrong value: severity gated on confidence
    if (ans.confidence or "").lower() == "high":
        return Outcome.CONFIDENTLY_WRONG
    return Outcome.WRONG_HEDGED
