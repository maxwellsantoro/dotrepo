# failed-to-decode-github-response-https-api-github-com-repos-segment-boneyard-nig

This stub was generated from recurring autonomous index failure telemetry.

- failure class: `infrastructure`
- ecosystem: `unknown`
- fixture: not eligible — this is an environmental provider/infrastructure/writeback defect that a source fixture cannot reproduce
- observed runs: 4
- fingerprint: `failed to decode GitHub response https://api.github.com/repos/segment-boneyard/nightmare`
- repositories: `github.com/segment-boneyard/nightmare`

## Materialization Checklist

Only fixture-eligible stubs should be materialized. Environmental failures are
tracked here for operator awareness, not converted into source fixtures.

- Capture the smallest repository source fixture that reproduces this failure:
  `uv run python scripts/materialize_regression_fixture.py --stub index/telemetry/regression-fixture-stubs/failed-to-decode-github-response-https-api-github-com-repos-segment-boneyard-nig`
  Add `--repo <host/owner/repo>` when the stub lists multiple repositories.
- Confirm or edit the generated `expectation.json` so it pins the fixed behavior.
- Add the deterministic parser, evidence, or validation fix in `dotrepo-core`.
- Run the runnable regression harness: `cargo test -p dotrepo-core --test regression_fixture_pack`
- Remove this stub once the checked-in runnable fixture guards the fix.
