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
export GITHUB_TOKEN=ghp_...
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml --arms github,dotrepo \
  --base-url https://dotrepo.org --out results

# stronger baseline: let an LLM read the READMEs instead of regex
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml --extractor llm --out results
```

Output: `results/report.md` (the table) and `results/results.json` (every
per-field row with value, confidence, source, bytes, latency — auditable).

### Frozen fixtures (reproducible artifact)

```bash
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml --cache-mode freeze
uv run --with requests --with pyyaml python -m bench.run --gold gold.yaml --cache-mode replay
```

Commit the fixture dir and a regression becomes a frozen record you can diff and
re-audit — the same discipline as freezing a failing pipeline record.

### Offline self-test

```bash
uv run --with pyyaml python seed_fixtures.py
uv run --with requests --with pyyaml python -m bench.run --gold gold.fixture.yaml --cache-mode replay --cache-dir results/fixtures
```

The seeded scenario makes dotrepo confidently wrong on one field on purpose; the
report should show `confidently wrong (count) | 1` for the dotrepo arm. If it
doesn't, the scorer is broken.

## Curating gold

`gold.yaml` ships with GitHub-native fields for a few repos and buried fields
left `null` (excluded until curated). Fill buried fields from each repo's **own
docs**, not memory — the experiment is only as honest as the gold. Add repos
that are in the dotrepo index so both arms have something to answer.

## One assumption to verify

dotrepo's public docs guarantee per-result confidence + provenance but don't pin
the exact JSON keys of the `/v0/batch/query` envelope. `bench/arms/dotrepo_arm.py`
tries a priority list (`VALUE_KEYS`/`CONF_KEYS`/`PROV_KEYS`). Run one live
`curl "$BASE/v0/batch/query?repo=github.com/sharkdp/fd&path=repo.description"`,
confirm the keys, and pin them there if needed. Nothing else depends on the shape.
