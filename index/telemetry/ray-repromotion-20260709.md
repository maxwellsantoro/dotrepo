# Ray re-promotion disposition — 2026-07-09

Identity: `github.com/ray-project/ray`

## Prior state

- Status `inferred`, confidence `medium` after a refresh that triggered the
  downgrade guard: previously present `repo.test` was no longer selected.
- Record kept high-value imported owners/security/toolchain metadata and
  honest absence of `repo.build` / `repo.test` for a large polyglot monorepo.

## Disposition

- Ran `dotrepo promotion-report --index-root index --apply --limit 1`.
- Scoring: high-confidence present for identity fields; high-confidence absent
  for build/test (no inventing commands). Eligible for verified auto-publish.
- Result: status `verified`, confidence `high`, provenance includes `verified`.
- Evidence append: `## Auto-promotion` section from the promotion apply path.

## Follow-ups (not blocking verified)

- Coverage-gap recrawl only if future evidence yields a single honest package
  entrypoint (Makefile/tox/CI primary workflow) without inventing completeness.
- Do not treat missing build/test as a demotion trigger when absence is scored
  high-confidence.
