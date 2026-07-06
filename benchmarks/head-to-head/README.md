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
per-field row with value, confidence, source, bytes, latency, cohort, and gold
evidence — auditable).

### Independent gold and frozen holdouts

`gold.independent.yaml` is the benchmark's independence check. It contains
eight indexed repositories that do not appear in the original curated sample
and five repositories that were absent from the index at snapshot `45f13d33`.
Every scored answer cites an upstream maintainer-controlled URL, locator, and
check date; buried-field sources are pinned to exact upstream commits. The file
fails closed at load time if a scored value lacks that evidence.

```bash
GITHUB_TOKEN=$(gh auth token) uv run --with requests --with pyyaml python -m bench.run \
  --gold gold.independent.yaml --arms github,dotrepo --extractor llm \
  --base-url https://dotrepo.org \
  --cache-mode freeze \
  --cache-dir results/independent-holdout-2026-07-06/fixtures \
  --out results/independent-holdout-2026-07-06
```

The baseline probes common real-world source variants (`README.rst`,
`.github/SECURITY.md`, `.github/CONTRIBUTING.md`, package manifests, Go
modules, Makefiles, and justfiles) rather than treating non-`README.md` projects
as undocumented. Replay mode fails closed on a missing frozen response, so an
"offline" rerun cannot silently touch the network.

Freeze mode also records each parsed LLM value and confidence under a key that
binds the provider, model, and exact prompt. Replay therefore makes no model or
HTTP calls and fails closed if either frozen input is missing. Network and model
latency remain properties of the original live run; replay validates answers and
scores, not historical timing.

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

`results/expanded-10-before-command-filter-2026-07-05/` expands the curated
gold set from five to ten indexed repositories (`starship`, `hyper`, `cobra`,
`vite`, and `tokio` added) and intentionally captures the next unflattering
signal: dotrepo had four confidently-wrong buried command rows. The witnesses
were release/maintenance workflow commands and target/feature/doc-specific
Cargo invocations (`starship` `npm run build`, `hyper` feature-only build, and
`tokio` Fortanix/doc-only commands) masquerading as canonical clean-checkout
build/test instructions.

`results/expanded-10-command-filter-2026-07-05/` confirms the command-filter
fix in isolation: those four confidently-wrong buried rows drop to zero, with
one remaining honest abstention for `tokio`'s README-only MSRV.

`results/expanded-10-msrv-2026-07-05/` is the fix-confirmation run after
filtering noncanonical workflow filenames, rejecting selector-specific Cargo
workflow commands unless the selector is itself part of the gold command, and
importing explicit README "current MSRV" statements when no manifest
`rust-version` exists. On the ten-repo set, dotrepo scores 100.0% overall,
100.0% buried, 100.0% coverage, and 0 confidently-wrong answers.

`results/llm-expanded-10-msrv-2026-07-05/` reruns the stronger OpenRouter-backed
GitHub+LLM-docs baseline against that expanded ten-repo surface. GitHub+LLM
scores 70.6% overall and 34.2% on buried fields, with three confidently-wrong
buried answers (`bat` security contact, `ruff` test command, and `ruff`
toolchain). dotrepo scores 100.0% overall and buried, 0 confidently-wrong, and
uses roughly half the approximate wire-token count. This is still a curated
sample, not adoption, but it is the first larger head-to-head where dotrepo
clears the accuracy, honesty, and token bars simultaneously.

### Independent-gold result

`results/independent-holdout-2026-07-06/` is the first result whose gold was
curated without consulting dotrepo records, crawler evidence, or query output.
The baseline used OpenRouter model `google/gemma-4-26b-a4b-it`; the model name,
parsed outputs, HTTP inputs, and scoring evidence are all frozen with the result.
It reverses the earlier perfect-score story on the cohort that matters:

- On the eight independently curated **indexed** repos, GitHub+LLM scores 90.2%
  overall accuracy versus dotrepo's 80.3%, with one confidently-wrong answer
  versus dotrepo's two.
- On indexed **buried fields**, GitHub+LLM scores 71.4% versus dotrepo's 42.9%,
  with one confidently-wrong answer versus two. dotrepo therefore does not
  clear the benchmark's accuracy or honesty bars on independent gold, despite
  using about one third of the aggregate wire tokens.
- On the five frozen **unindexed holdouts**, dotrepo answers 0/35 scored
  questions and has zero confidently-wrong answers. That is the desired trust
  behavior: no overlay means clean abstention, not degraded guessing.

The surviving dotrepo witnesses are concrete: Serde publishes
`cargo test --workspace` instead of the maintainer's nightly unstable full-suite
command, and Requests publishes an unrelated `python-maint@redhat.com` address
instead of its GitHub draft-advisory reporting path. The baseline's surviving
witnesses are also retained: it selects Django's JavaScript-only Grunt test
instead of the documented tox suite, and treats `cargo install just` as Just's
clean-checkout build command.

Acceptable alternatives in the gold are explicit and evidenced (for example,
`just test` and the broader `just ci`). They were audited before the final
score, and the frozen model outputs were rescored rather than regenerated. The
result is intentionally unflattering: holdout trust behavior passes, but the
independent indexed thesis result does not.

### Offline self-test

```bash
uv run --with pyyaml python seed_fixtures.py
uv run --with requests --with pyyaml python -m bench.run --gold gold.fixture.yaml --cache-mode replay --cache-dir results/fixtures
```

The seeded scenario makes dotrepo confidently wrong on one field on purpose; the
report should show `confidently wrong (count) | 1` for the dotrepo arm. If it
doesn't, the scorer is broken.

## Curating gold

`gold.yaml` ships with the original curated starter set. Fill or revise buried
fields from each repo's **own docs**, not memory — the experiment is only as
honest as the gold. Leave a field `null` when the upstream docs do not expose a
canonical answer; null fields are excluded from scoring.

For thesis claims, prefer the stricter `gold.independent.yaml` shape: freeze
index membership and upstream revisions, identify indexed and unindexed
cohorts, cite evidence for every scored value, and list multiple accepted values
when maintainer sources document genuinely equivalent commands. Never turn a
holdout abstention into an accuracy failure; read its answer rate and
confidently-wrong count instead.

## One assumption to verify

dotrepo's public docs guarantee per-result confidence + provenance but don't pin
the exact JSON keys of the `/v0/batch/query` envelope. `bench/arms/dotrepo_arm.py`
tries a priority list (`VALUE_KEYS`/`CONF_KEYS`/`PROV_KEYS`). Run one live
`curl "$BASE/v0/batch/query?repo=github.com/sharkdp/fd&path=repo.description"`,
confirm the keys, and pin them there if needed. Nothing else depends on the shape.
