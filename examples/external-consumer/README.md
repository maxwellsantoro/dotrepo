# External consumer reference client

Generic agent integration package for a measured external pilot. It hits the hosted
dotrepo public API **before** any scrape/clone fallback and surfaces
trust / status / freshness.

See [`docs/external-consumer-integration.md`](../../docs/external-consumer-integration.md)
for the acceptance checklist this example implements.

## Quick start

```bash
# Live hosted lookup (optional network)
uv run python examples/external-consumer/lookup_before_scrape.py \
  https://github.com/BurntSushi/ripgrep \
  github.com/acme/does-not-exist-dotrepo-probe \
  --miss-log /tmp/lookup-misses.log \
  --output-json /tmp/consumer-results.json

# Aggregate client-recorded misses the same way as Worker logs
uv run python scripts/aggregate_lookup_misses.py \
  --input /tmp/lookup-misses.log \
  --output-md /tmp/lookup-miss-report.md
```

## Acceptance mapping

| Criterion | How this client meets it |
| --- | --- |
| Hosted lookup before clone | `fetch_profile` calls `/v0/repos/.../profile.json` by default |
| Trust / freshness surfaced | Printed and included in JSON output |
| Honest missing fields | `missing_fields` list; no invented build/test commands |
| Countable 404 | `miss=true` + optional `DOTREPO_LOOKUP_MISS` log lines |
| External adoption | Not claimed; this package is an in-repository reference |

Live non-operator production traffic remains an operations follow-up once a
third-party framework adopts this pattern.

## Task-specific fallback

```bash
uv run python examples/external-consumer/lookup_before_scrape.py \
  github.com/BurntSushi/ripgrep --require repo.build --require repo.test \
  --max-record-age-days 30 --output-json /tmp/task-results.json
```

Use `usable`, not `hit`, to decide whether the requested task can use the profile.
The policy rejects stale or unknown record age, identity mismatch, conflicts,
missing required values, and suspect/unresolved field assessments. It never runs
returned commands. The caller implements source fallback.

The [pilot guide](../../docs/consumer-pilot.md) and
[pilot-report.example.json](pilot-report.example.json) define the handoff and
outcome telemetry. Unknown costs stay null. External adoption needs an independent
team's deployment and outcomes, not execution of this example by the operator.

When a requested build/test field is explicitly marked `inferred`, the reference
policy requires source fallback. A conventional tool default is not enough to
confirm a repository-specific command. The client never executes commands.

## Positive command acceptance

The reference consumer accepts a requested primary build/test command only when
it is a nonempty string with an explicit `present`, `extracted`, high-confidence
field assessment, a nonempty source, and a check timestamp matching the record.
Missing, invalidated, malformed, unspecified, inferred, or weaker assessments
require upstream fallback. Record-wide confidence and maintainer status do not
substitute for this contract; no maintainer-authority exemption is implemented.
Unsupported response versions and non-string requested values also require
fallback. Acceptance is metadata suitability, not permission to execute a command.
The benchmark leaves field confidence unknown when absent.

Policy coverage is published on the efficiency page and in its linked JSON.
It distinguishes value presence, policy acceptance, independently established
correctness, and completed tasks. The last two remain unmeasured in the coverage
report; they require the existing benchmark and independent pilot evidence.
