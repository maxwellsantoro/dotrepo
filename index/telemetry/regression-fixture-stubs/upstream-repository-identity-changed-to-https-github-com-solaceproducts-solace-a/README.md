# upstream-repository-identity-changed-to-https-github-com-solaceproducts-solace-a

This stub was generated from recurring autonomous index failure telemetry.

- failure class: `infrastructure`
- ecosystem: `unknown`
- fixture: not eligible — this is an environmental provider/infrastructure/writeback defect that a source fixture cannot reproduce
- observed runs: 2
- fingerprint: `upstream repository identity changed to https://github.com/SolaceProducts/solace-agent-mesh; refusing writeback under...`
- repositories: `github.com/SolaceLabs/solace-agent-mesh`

## Materialization Checklist

Only fixture-eligible stubs should be materialized. Environmental failures are
tracked here for operator awareness, not converted into source fixtures.

- Capture the smallest repository source fixture that reproduces this failure:
  `uv run python scripts/materialize_regression_fixture.py --stub index/telemetry/regression-fixture-stubs/upstream-repository-identity-changed-to-https-github-com-solaceproducts-solace-a`
  Add `--repo <host/owner/repo>` when the stub lists multiple repositories.
- Confirm or edit the generated `expectation.json` so it pins the fixed behavior.
- Add the deterministic parser, evidence, or validation fix in `dotrepo-core`.
- Run the runnable regression harness: `cargo test -p dotrepo-core --test regression_fixture_pack`
- Remove this stub once the checked-in runnable fixture guards the fix.
