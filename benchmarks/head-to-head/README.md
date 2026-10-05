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
  **and available confidence and provenance** out of the response.

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
entire reason to exist. The original comparison asks for higher buried accuracy, fewer confidently wrong
answers, and less transferred context. Wire bytes divided by four are payload
estimates, not billed model tokens. A net task-cost claim additionally requires
actual model usage, upstream fallback, and allocated index maintenance.

## Run it

Run these commands from `benchmarks/head-to-head/`; `uv` discovers the repository
environment. Frozen result directories are historical artifacts; choose a new
output directory for a fresh run. Create a new scratch root for these examples;
copy reviewed run artifacts into a new dated directory only after the run.

```bash
BENCH_RUN_ROOT=$(mktemp -d /tmp/dotrepo-bench.XXXXXX)

# live run (needs a token: unauthenticated GitHub is 60 req/hr and will starve)
GITHUB_TOKEN=$(gh auth token) uv run --with requests --with pyyaml python -m bench.run \
  --gold gold.yaml --arms github,dotrepo --base-url https://dotrepo.org \
  --out "$BENCH_RUN_ROOT/live"

# stronger baseline: let an LLM read the READMEs instead of regex.
# Local runs automatically load dotrepo/.env; OPENROUTER_API_KEY is preferred.
# This intentionally fails closed if no provider key is configured; it never
# silently falls back to the heuristic extractor.
uv run --with requests --with pyyaml python -m bench.run \
  --gold gold.yaml --arms github,dotrepo --extractor llm \
  --base-url https://dotrepo.org --out "$BENCH_RUN_ROOT/llm"
```

Set `OPENROUTER_MODEL` to override the OpenRouter model for this benchmark; if
unset, it reuses `DOTREPO_ADJUDICATION_MODEL` and then
`DOTREPO_ADJUDICATION_API_MODEL`. Set `DOTREPO_BENCH_LOAD_DOTENV=0` to disable
automatic `.env` loading. Anthropic direct remains available via
`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` when no OpenRouter key is present. Keep
keys out of committed fixtures and shell history.

The current local primary is `openai/gpt-6-luna`; explicit alternatives include
`qwen/qwen3.8-flash`, `z-ai/glm-5.3-flash`,
and `google/gemini-3.8-flash`. The benchmark shares reviewed request settings
with the adjudication sidecar, including reasoning support, total output budgets,
and required parameter support. New model cache keys also bind those settings.
Per-call usage logs report billed tokens and cost when provided, including failed
answers; these logs do not change historical wire-byte estimates into token costs.
The direct Anthropic fallback defaults to `claude-sonnet-5-5`, with adaptive
thinking and low effort. Historical frozen results retain their original models.

Output: `<out>/report.md` (the table) and `<out>/results.json` (every
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
  --cache-dir "$BENCH_RUN_ROOT/independent/fixtures" \
  --out "$BENCH_RUN_ROOT/independent"
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
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml \
  --cache-mode freeze --cache-dir "$BENCH_RUN_ROOT/frozen/fixtures" \
  --out "$BENCH_RUN_ROOT/frozen"
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml \
  --cache-mode replay --cache-dir "$BENCH_RUN_ROOT/frozen/fixtures" \
  --out "$BENCH_RUN_ROOT/replay"
```

Commit the fixture dir and a regression becomes a frozen record you can diff and
re-audit — the same discipline as freezing a failing pipeline record.

### Historical curated runs

The July curated runs exposed parser defects and confirmed fixes on the same
cases. Their original reports and frozen inputs remain intact; perfect scores
after those fixes are regression evidence, not generalization or adoption proof.
Later independent-gold results below take precedence for thesis evaluation.

| Report | Purpose |
| --- | --- |
| [live-2026-07-04](results/live-2026-07-04/report.md) | Initial five-repository live result, including a confidently wrong description |
| [fixcheck-2026-07-05](results/fixcheck-2026-07-05/report.md) | Description regression fix |
| [aliascheck-2026-07-05](results/aliascheck-2026-07-05/report.md) | Install-alias confirmation |
| [llm-2026-07-05](results/llm-2026-07-05/report.md) | Stronger source baseline |
| [toolchain-2026-07-05](results/toolchain-2026-07-05/report.md) | Minimum-toolchain extraction |
| [commands-2026-07-05](results/commands-2026-07-05/report.md) | Command precision fixes |
| [description-constraint-2026-07-05](results/description-constraint-2026-07-05/report.md) | GitHub-description reconciliation |
| [llm-description-constraint-2026-07-05](results/llm-description-constraint-2026-07-05/report.md) | Same curated gold with model baseline |
| [expanded-10-before-command-filter-2026-07-05](results/expanded-10-before-command-filter-2026-07-05/report.md) | Expanded curated set exposing four confidently wrong commands |
| [expanded-10-command-filter-2026-07-05](results/expanded-10-command-filter-2026-07-05/report.md) | Command-filter regression confirmation |
| [expanded-10-msrv-2026-07-05](results/expanded-10-msrv-2026-07-05/report.md) | Expanded-set toolchain regression confirmation |
| [llm-expanded-10-msrv-2026-07-05](results/llm-expanded-10-msrv-2026-07-05/report.md) | Expanded curated set with model baseline |

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

Replay the checked-in synthetic fixtures without regenerating their inputs.
`seed_fixtures.py` rewrites `results/fixtures` and `gold.fixture.yaml`; reserve it
for intentional fixture maintenance.

```bash
uv run --with requests --with pyyaml python -m bench.run --gold gold.fixture.yaml \
  --cache-mode replay --cache-dir results/fixtures --out "$BENCH_RUN_ROOT/self-test"
```

The synthetic scenario makes dotrepo confidently wrong on one field on purpose; the
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

## Envelope and confidence interpretation

The public batch-query envelope is pinned by
[the compatibility contract](../../docs/public-api-compatibility.md). The legacy
`dotrepo` arm still tolerates several value/confidence/provenance locations;
inspect retained raw responses when evaluating a deployment. Some locations
read record-wide trust, which is not per-field correctness evidence. Missing
confidence stays unknown, and the policy-aware `lookup-first` arm uses the
stricter reference consumer rather than treating a high-status label as acceptance.

## Complete lookup-first path

For execution semantics and observed task outcomes, use the separate
[paired task scorer and controlled rehearsal](task-fixtures/README.md). It binds
participant-supplied logs to a frozen workload and reports completion, accepted
wrong instructions, failed attempts, fallback, and actual/unknown costs. Its
operator controls do not establish independent task benefit. The factual-answer
benchmark below remains unchanged and does not execute commands.

The current [own-project study](results/own-projects-2026-10-04/README.md) uses
eight preregistered build/test tasks in the maintainer's four substantive other
public projects. It requests real immutable profiles and executes fixed
source-grounded commands in fresh checkouts. Source selection is manual;
operator outcomes do not establish autonomous-agent performance or external
adoption. Its transport boundary excludes package-manager traffic and unallocated
preparation costs, so it cannot establish total task-cost savings.

The `lookup-first` arm uses the generic consumer's identity, record-age, conflict,
and required-field policy. Rejected fields trigger the GitHub baseline and include
its work. Both arms use the same extractor setting. No returned command is run.

```bash
uv run python -m bench.run --gold gold.independent.yaml \
  --arms github,lookup-first --extractor heuristic --base-url https://dotrepo.org \
  --out "$BENCH_RUN_ROOT/consumer-pilot"
```

`transport.request_count` and `transport.response_bytes` count actual HTTP work,
including prefetched responses and fallback. `elapsedMs` measures the whole arm.
`cache_hits` must be reported separately; replay timings are not live latency.
The legacy per-field latency excludes model inference, and bytes divided by four
is only a payload estimate. Actual model usage and allocated maintenance costs
are unknown unless supplied by a consumer pilot; do not report net cost savings
from these numbers alone. This is an in-repository experiment, not adoption.

## Independent structured-metadata audit

`metadata-sample.txt` freezes 32 identities selected by a salted SHA-256 ordering
before upstream capture and evaluation. `scripts/capture_upstream_accuracy_sample.py`
reads only primary GitHub metadata to create a separate cited workload and frozen
source extracts. This audit tests description, license where SPDX is known,
visibility, and archived status. It does not establish build/test/security accuracy;
the independent buried-field cohort remains a separate report.

## September buried-field audit

`gold.september.yaml` freezes 17 command/security-contact answers for eight
preselected projects, citing exact upstream commits. Five projects were indexed
and three were unindexed. The gold was frozen before examining dotrepo answers.
The sample covers ecosystem variety; it is small and not statistically representative.

`results/september-2026-09-16/` retains the initial result, including two
high-confidence script errors in pnpm. This was a heuristic source baseline, not
a repeat of the July strong-model comparison. It used live upstream HTTP, a local
dotrepo server, and no response cache. Those different network locations prevent
using its wall times as a hosted latency comparison.

The `transport` block counts all requests and decoded response bytes, including
prefetch and fallback, while `elapsedMs` times the whole arm. Prefer those over
legacy per-field payload/latency allocations. Model token usage and allocated
maintenance cost remain unmeasured. A correction rerun against this same gold is
regression evidence, not another independent result.

`results/september-correction-2026-09-16/` is that correction rerun. Script-name
preservation fixed the two high-confidence errors; the generic client now falls
back on explicitly inferred commands. Lookup-first answered 12/17 correctly,
with one low-confidence wrong fallback answer and four abstentions. It made
84 HTTP requests versus the source baseline's 114, with 170,463 versus 326,618
decoded response bytes. These are measurements of this small heuristic/local
experiment, not evidence of external adoption or net production savings.
