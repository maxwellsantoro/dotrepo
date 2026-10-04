# scripts/

Automation, release-packaging, and index-operation tooling for dotrepo. These
scripts support the Rust toolchain and public index; they are not part of the
published crates.

## Requirements

Most runtime scripts use the standard library; upstream accuracy capture uses
`requests`, and tests/benchmarks use additional packages from the locked
development environment. Sync that environment rather than assuming every
script is dependency-free. Node-based packaging and Worker checks also require
the runtime documented in their respective guides.

- **Python >= 3.12** is required (the packaging scripts use modern f-string syntax).
- Create and sync the repository environment, then run through `uv`:

  ```bash
  uv venv
  uv sync --dev --locked
  uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate --skip-vsix
  ```

The canonical invocations (with their exact flags) are documented in
[the contributing guide](../CONTRIBUTING.md), [agent guidance](../AGENTS.md),
and the task-specific [documentation map](../docs/README.md).

## Coordinated use

Run focused script tests while implementing a lane; the coordinator runs the
integrated gates from [CONTRIBUTING](../CONTRIBUTING.md#local-checks). Use separate
output roots for concurrent gate runs. Batch, telemetry, archive, and landing
scripts mutate shared state: assign one owner or partition repository identities
and state paths before concurrent execution. Read-only reports can run separately.

## What lives here

| Area | Scripts |
|------|---------|
| Release & packaging | `check_release_gate.py`, `check_release_version.py`, `check_toolchain_manifest_parity.py`, `check_ci_gate.py`, `package_public_export.py`, `package_release_binaries.py`, `package_vscode_extension.py`, `public_site_content.py` |
| Autonomous index batch | `run_autonomous_index_batch.py`, `adjudication_openrouter_sidecar.py`, `check_autonomous_telemetry_gate.py`, `materialize_regression_fixture.py`, `test_adjudication_env.py` |
| Review-batch planning | `plan_refresh_review_batches.py`, `plan_seed_review_batches.py`, `plan_index_growth_tranche.py`, `select_review_batch.py`, `render_review_batch_pull_request.py`, `render_seed_review_summary.py`, `render_refresh_plan_summary.py` |
| Public surface | `fetch_pagedigest_baseline.py`, `render_public_pages_landing.py`, `render_index_growth_status.py`, `check_public_profile_coverage.py`, `check_public_quality_dashboard.py`, `build_public_lookup_workload.py`, `measure_public_lookup_efficiency.py`, `measure_public_factual_accuracy.py`, `diff_public_export_files.py`, `smoke_cloudflare_public_deploy.py`, `sync_cloudflare_public_snapshot.py` |
| Quality scorecards | `render_intent_quality_scorecard.py`, `render_coverage_gaps.py`, `render_unit_cost_report.py`, `measure_public_policy_coverage.py`, `check_public_record_freshness.py`, `aggregate_lookup_misses.py`, `export_lookup_miss_demand.py` |
| Audit sampling | `audit_index_sample.py` (read-only, local-only; see [audit cadence](../docs/factual-crawl-automation.md#audit-cadence)) |
| Operator gates and landing | `check_operator_claim_gate.py`, `land_autonomous_index.py`, `refresh_stale_index.py` |
| Shell helpers | `recrawl-batch.sh`, `use_runner_node22.sh` |
| Shared modules | `language_family.py` (dominant-language ecosystem classifier), `process_resources.py` (CPU/RSS sampling for crawl subprocesses), `public_site_content.py`, `openrouter_request_policy.py` (model settings, schemas, price limits, and usage preservation) |

Shared fixtures live under `scripts/fixtures/` and tests under `scripts/tests/`.
Scripts may import sibling modules from this directory (add `scripts/` to
`sys.path` when loaded via `importlib` in tests).
