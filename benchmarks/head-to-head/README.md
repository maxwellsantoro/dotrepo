# dotrepo-bench

A falsifiable head-to-head: does querying **dotrepo** actually beat a competent
**GitHub API + README** agent at answering the factual questions coding agents
ask about a repository — on accuracy, honesty, and tokens?

This exists because the case for dotrepo currently rests on asserted metrics
("fetches avoided", "tokens avoided") from a system talking to itself. This
turns the claim into a measurement that can come out *against* dotrepo. That is
the point. If dotrepo can't clear the bar here, the bar found something real.

## What it measures

Two arms answer the same fixed question set over the same repos:

- **github** — structured facts from the REST API (high confidence) + real
  README/SECURITY/CONTRIBUTING scraping for buried facts (heuristic by default,
  optional `--extractor llm`). A deliberately fair baseline, not a strawman.
- **dotrepo** — one `/v0/batch/query` call per repo, reading each field's value
  **and its declared confidence and provenance** out of the response.

Every answer is scored into one of four buckets, not two:

| outcome | meaning |
|---|---|
| correct | value present and matches gold |
| abstained | no value / honest "unknown" |
| wrong (hedged) | wrong, but confidence was low/medium |
| **confidently wrong** | wrong value asserted at **high** confidence |

The headline metric is the **confidently-wrong rate**, because that is the exact
failure your trust-model work targets: a confidently-wrong field bypasses
escalation and a downstream agent acts on it. A benchmark that only reports
accuracy hides it.

Results also break out **buried fields** (build cmd, test cmd, security contact,
MSRV) separately from GitHub-native fields, because the buried set is dotrepo's
entire reason to exist. A win is: **higher buried accuracy AND fewer
confidently-wrong answers AND fewer tokens.** Miss any of the three and it isn't
paying rent.

## Run it

```bash
# live run (needs a token: unauthenticated GitHub is 60 req/hr and will starve)
GITHUB_TOKEN=$(gh auth token) uv run --with requests --with pyyaml python -m bench.run \
  --gold gold.yaml --arms github,dotrepo --base-url https://dotrepo.org --out results

# stronger baseline: let an LLM read the READMEs instead of regex.
# Local runs automatically load dotrepo/.env; OPENROUTER_API_KEY is preferred.
# This intentionally fails closed if no provider key is configured; it never
# silently falls back to the heuristic extractor.
uv run --with requests --with pyyaml python -m bench.run \
  --gold gold.yaml --arms github,dotrepo --extractor llm \
  --base-url https://dotrepo.org --out results/llm-2026-07-05
```

Set `OPENROUTER_MODEL` to override the OpenRouter model for this benchmark; if
unset, it reuses `DOTREPO_ADJUDICATION_API_MODEL` and then
`DOTREPO_ADJUDICATION_MODEL`. Set `DOTREPO_BENCH_LOAD_DOTENV=0` to disable
automatic `.env` loading. Anthropic direct remains available via
`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` when no OpenRouter key is present. Keep
keys out of committed fixtures and shell history.

Output: `results/report.md` (the table) and `results/results.json` (every
per-field row with value, confidence, source, bytes, latency — auditable).

### Frozen fixtures (reproducible artifact)

```bash
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml --cache-mode freeze
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml --cache-mode replay
```

Commit the fixture dir and a regression becomes a frozen record you can diff and
re-audit — the same discipline as freezing a failing pipeline record.

### First live run

`results/live-2026-07-04/` is the first curated live run: five indexed repos
(`fd`, `ripgrep`, `uv`, `bat`, `ruff`), GitHub-native facts from the GitHub API,
and buried facts curated from upstream README/CONTRIBUTING/SECURITY/toolchain
files. The run freezes both arms' HTTP responses under
`results/live-2026-07-04/fixtures/` so the report is auditable.

Headline result: dotrepo used materially fewer tokens and slightly beat the
naive GitHub+docs baseline on buried-field accuracy, but it did **not** win the
full benchmark because coverage was lower and one GitHub-native field was
confidently wrong: `sharkdp/fd` `repo.description` returned language-link text
(`[中文] [한국어]`) at high confidence. That is precisely the failure mode this
harness is meant to make visible.

`results/fixcheck-2026-07-05/` reruns the same gold against a local export after
the crawler fix that treats GitHub-native description as a deterministic
constraint on suspect README extraction. The fd description row is corrected and
dotrepo's confidently-wrong count drops from 1 to 0. This is a fix-confirmation
run, not a new adoption or thesis-validating benchmark.

### First LLM-docs baseline

`results/llm-2026-07-05/` runs the same curated gold with the GitHub arm's
`--extractor llm` path. Local runs automatically load `dotrepo/.env`, so this
uses the existing OpenRouter setup by default instead of a separate Anthropic
credential. The result is sharper than the naive-regex baseline: dotrepo still
loses overall to GitHub-native structured fields, but on buried fields dotrepo
scores 44.4% vs 22.2% and has 0 confidently-wrong buried answers vs 2 for the
LLM-docs baseline. The two LLM confidently-wrong buried answers are `bat`
`security_contact` and `ruff` `test`.

Read this as a first signal, not a settled win: the buried set is still tiny,
the LLM prompt is deliberately narrow, and dotrepo's lower coverage remains
visible. But it is now testing against a real model-reading-docs baseline, not
regex in disguise.

`results/aliascheck-2026-07-05/` is the fix-confirmation run after adding public
query aliases for the obvious GitHub-native paths agents ask for:
`repo.language` maps to the dominant `repo.languages.0`, and `repo.archived`
maps to `x.github.archived`. The run uses the same curated gold against a local
patched `dotrepo-public-query` server. That moves dotrepo from 47.5% to 72.5%
overall accuracy and from 57.5% to 82.5% coverage while preserving 0
confidently-wrong answers. The buried-field thesis result is unchanged in
shape: dotrepo remains ahead on buried accuracy and confidently-wrong count, but
minimum-toolchain coverage is still absent and needs a real schema/crawler
feature rather than another alias.

`results/toolchain-2026-07-05/` is the fix-confirmation run after adding that
real schema/crawler feature: optional `[repo.toolchain] min = "..."` extracted
from conservative root metadata such as Cargo `rust-version`, Python
`requires-python`, Node `engines.node`, and Go `go` directives. The run uses a
local patched `dotrepo-public-query` server against refreshed index records for
the same five repos. It moves dotrepo from 72.5% to 82.5% overall accuracy, from
82.5% to 95.0% coverage, and from 44.4% to 66.7% buried-field accuracy while
preserving 0 confidently-wrong answers. All five `min_toolchain` rows are now
correct; the remaining misses are command-precision misses or honest test
abstentions.

`results/commands-2026-07-05/` is the fix-confirmation run after improving
command precision on the actual defects surfaced by `toolchain-2026-07-05/`.
The crawler now materializes CONTRIBUTING files, README/CONTRIBUTING command
extraction is section-aware, documented env-prefixed test commands are
normalized to safe command strings, selector-specific `cargo nextest run ...`
examples publish the canonical runner command, and specialized benchmark/fuzz
workflows no longer masquerade as canonical build/test instructions. On the
same five-repo gold set, dotrepo moves from 82.5% to 97.5% overall accuracy,
from 66.7% to 100.0% buried-field accuracy, and from 95.0% to 100.0% coverage,
while preserving 0 confidently-wrong answers. The only remaining miss is a
GitHub-native `bat` description wording mismatch; all buried build/test,
security-contact, and toolchain rows are correct.

`results/description-constraint-2026-07-05/` is the fix-confirmation run after
making the GitHub crawler treat structured GitHub repository descriptions as
the source of truth for overlay `repo.description`, instead of preserving a
README-derived sentence whenever it had token overlap. This closes the remaining
`bat` description miss without special casing that repository: the on-disk
record now publishes GitHub's `A cat(1) clone with wings.` summary, while the
evidence keeps the README-sourced build/test/security/toolchain provenance
separate. On the same five-repo gold set, dotrepo reaches 100.0% overall
accuracy, 100.0% precision, 100.0% coverage, and 0 confidently-wrong answers.

`results/llm-description-constraint-2026-07-05/` reruns the stronger
OpenRouter-backed `--extractor llm` GitHub baseline against the same patched
local query surface. This is the cleanest current head-to-head: GitHub+LLM docs
scores 65.0% overall with 2 confidently-wrong buried answers, while dotrepo
scores 100.0% overall, 100.0% buried, 0 confidently-wrong, and less than half
the approximate wire-token count.

### Offline self-test

```bash
uv run --with pyyaml python seed_fixtures.py
uv run --with requests --with pyyaml python -m bench.run --gold gold.fixture.yaml --cache-mode replay --cache-dir results/fixtures
```

The seeded scenario makes dotrepo confidently wrong on one field on purpose; the
report should show `confidently wrong (count) | 1` for the dotrepo arm. If it
doesn't, the scorer is broken.

## Curating gold

`gold.yaml` ships with a small curated starter set. Fill or revise buried fields
from each repo's **own docs**, not memory — the experiment is only as honest as
the gold. Add repos that are in the dotrepo index so both arms have something to
answer. Leave a field `null` when the upstream docs do not expose a canonical
answer; null fields are excluded from scoring.

## One assumption to verify

dotrepo's public docs guarantee per-result confidence + provenance but don't pin
the exact JSON keys of the `/v0/batch/query` envelope. `bench/arms/dotrepo_arm.py`
tries a priority list (`VALUE_KEYS`/`CONF_KEYS`/`PROV_KEYS`). Run one live
`curl "$BASE/v0/batch/query?repo=github.com/sharkdp/fd&path=repo.description"`,
confirm the keys, and pin them there if needed. Nothing else depends on the shape.
