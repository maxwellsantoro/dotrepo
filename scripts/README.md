# scripts/

Automation, release-packaging, and index-operation tooling for dotrepo. These
scripts support the Rust toolchain and public index; they are not part of the
published crates.

## Requirements

These scripts are **standard-library only** — they have no third-party
dependencies beyond the locked development tools.

- **Python >= 3.12** is required (the packaging scripts use modern f-string syntax).
- Create and sync the repository environment, then run through `uv`:

  ```bash
  uv venv
  uv sync --dev
  uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate --skip-vsix
  ```

The canonical invocations (with their exact flags) are documented in
[`../AGENTS.md`](../AGENTS.md) under **Commands** and in the relevant files
under [`../docs/`](../docs/).

## What lives here

| Area | Scripts |
|------|---------|
| Release & packaging | `check_release_gate.py`, `package_public_export.py`, `package_release_binaries.py`, `package_vscode_extension.py`, `public_site_content.py` |
| Autonomous index batch | `run_autonomous_index_batch.py`, `adjudication_openrouter_sidecar.py`, `check_autonomous_telemetry_gate.py`, `materialize_regression_fixture.py`, `test_adjudication_env.py` |
| Review-batch planning | `plan_refresh_review_batches.py`, `plan_seed_review_batches.py`, `plan_index_growth_tranche.py`, `select_review_batch.py`, `render_review_batch_pull_request.py`, `render_seed_review_summary.py`, `render_refresh_plan_summary.py` |
| Public surface | `render_public_pages_landing.py`, `render_index_growth_status.py`, `check_public_profile_coverage.py`, `build_public_lookup_workload.py`, `measure_public_lookup_efficiency.py`, `measure_public_factual_accuracy.py`, `diff_public_export_files.py`, `smoke_cloudflare_public_deploy.py`, `sync_cloudflare_public_snapshot.py` |
| Operator gates | `check_operator_claim_gate.py` |
| Shell helpers | `recrawl-batch.sh`, `use_runner_node22.sh` |

Shared fixtures live under `scripts/fixtures/` and tests under `scripts/tests/`.
