### Gate timings

Status: passed; wall time: 64.41 seconds.

| Stage | Seconds | Status |
| --- | ---: | --- |
| cargo run -p dotrepo-cli -- validate-index | 0.96 | passed |
| cargo run -p dotrepo-cli -- --root . validate | 0.40 | passed |
| cargo test -p dotrepo-core --test import_quality_gate --test public_export_fixture_pack --test public_query_fixture_pack --test public_error_fixture_pack --test public_freshness_semantics --test public_contract_compatibility | 10.94 | passed |
| cargo run --release -p dotrepo-cli -- public export --index-root index --out-dir /private/tmp/dotrepo-docs-context-release-gate-20261029/public --base-path / --generated-at 2026-10-29T09:08:50Z --stale-after 2026-10-30T09:08:50Z | 15.64 | passed |
| uv run python scripts/check_public_record_freshness.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --max-stale-or-unknown-rate 0.1 --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/public-record-freshness.json | 0.12 | passed |
| uv run python scripts/render_public_pages_landing.py --input /private/tmp/dotrepo-docs-context-release-gate-20261029/public | 0.37 | passed |
| uv run python scripts/check_public_profile_coverage.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --min-profiles 613 --min-high-signal 0 --min-high-signal-ratio 0.0 --max-conflict-rate 0.0 --max-malformed-profiles 0 --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/public-profile-coverage.json --output-md /private/tmp/dotrepo-docs-context-release-gate-20261029/public-profile-coverage.md --min-signal hasBuild=328 --min-signal hasDocs=165 --min-signal hasLicense=558 --min-signal hasOwnershipSignal=110 --min-signal hasSecurityContact=205 --min-signal hasTest=323 | 0.14 | passed |
| uv run python scripts/check_public_quality_dashboard.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --min-profiles 613 --max-generic-field-hits 8 --max-duplicated-description-values 1 --max-duplicate-description-records 2 --max-bad-looking-records 9 --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/public-quality-dashboard.json --output-md /private/tmp/dotrepo-docs-context-release-gate-20261029/public-quality-dashboard.md | 0.12 | passed |
| uv run python scripts/measure_public_policy_coverage.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/public-policy-coverage.json --output-md /private/tmp/dotrepo-docs-context-release-gate-20261029/public-policy-coverage.md | 0.19 | passed |
| uv run python scripts/plan_index_growth_tranche.py --candidate-file /Users/maxwell/projects/agent/dotrepo/index/tranche-two-targets.txt --target-count 0 --min-selected 0 --current-high-signal 347 --milestone-high-signal-target 500 --min-planned-high-signal-capacity 347 --output-targets /private/tmp/dotrepo-docs-context-release-gate-20261029/index-growth-targets.txt --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/index-growth-plan.json --output-md /private/tmp/dotrepo-docs-context-release-gate-20261029/index-growth-plan.md | 0.08 | passed |
| uv run python scripts/build_public_lookup_workload.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --mode research --limit 0 --output /private/tmp/dotrepo-docs-context-release-gate-20261029/public-lookup-workload.json | 0.05 | passed |
| uv run python scripts/measure_public_lookup_efficiency.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --index-root index --workload /private/tmp/dotrepo-docs-context-release-gate-20261029/public-lookup-workload.json --generated-at 2026-10-29T09:08:50Z --min-tasks 2452 --min-repositories 613 --min-task-hit-rate 0.47 --min-field-hit-rate 0.71 --max-dotrepo-to-scrape-proxy-ratio 2.43 --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/public-lookup-efficiency.json --output-md /private/tmp/dotrepo-docs-context-release-gate-20261029/public-lookup-efficiency.md --min-intent-hit-rate documentation=0.24 --min-intent-hit-rate execution=0.466 --min-intent-hit-rate overview=0.74 --min-intent-hit-rate security=0.35 | 0.75 | passed |
| uv run python scripts/render_public_efficiency_page.py --input /private/tmp/dotrepo-docs-context-release-gate-20261029/public --benchmark /private/tmp/dotrepo-docs-context-release-gate-20261029/public-lookup-efficiency.json | 0.36 | passed |
| uv run python scripts/measure_public_factual_accuracy.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --workload scripts/fixtures/public_factual_accuracy_workload.json --generated-at 2026-10-29T09:08:50Z --min-assertions 20 --min-repositories 3 --min-accuracy-rate 1.0 --max-missing-rate 0.0 --max-mismatch-rate 0.0 --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/public-factual-accuracy.json --output-md /private/tmp/dotrepo-docs-context-release-gate-20261029/public-factual-accuracy.md | 0.04 | passed |
| uv run python scripts/measure_public_factual_accuracy.py --public-root /private/tmp/dotrepo-docs-context-release-gate-20261029/public --workload benchmarks/head-to-head/upstream-2026-10-27/workload.json --min-assertions 119 --min-repositories 31 --min-accuracy-rate 1.0 --max-missing-rate 0 --max-mismatch-rate 0 --output-json /private/tmp/dotrepo-docs-context-release-gate-20261029/independent-upstream-accuracy.json --output-md /private/tmp/dotrepo-docs-context-release-gate-20261029/independent-upstream-accuracy.md | 0.05 | passed |
| uv run python scripts/check_release_guidance.py | 0.05 | passed |
| node scripts/check_public_links.mjs /private/tmp/dotrepo-docs-context-release-gate-20261029/public | 0.36 | passed |
| uv run python scripts/sync_cloudflare_public_snapshot.py --input /private/tmp/dotrepo-docs-context-release-gate-20261029/public --output /Users/maxwell/projects/agent/dotrepo/cloudflare/hosted-query/public-snapshot | 5.07 | passed |
| uv run python scripts/package_public_export.py --input /private/tmp/dotrepo-docs-context-release-gate-20261029/public --output-dir /private/tmp/dotrepo-docs-context-release-gate-20261029/public-bundle | 1.50 | passed |
| npm ci | 2.66 | passed |
| npm test | 1.48 | passed |
| npm run deploy:dry-run | 3.36 | passed |
| cargo build --release -p dotrepo-cli --bins -p dotrepo-lsp -p dotrepo-mcp | 14.45 | passed |
| uv run python scripts/package_release_binaries.py --bin-dir target/release --output-dir /private/tmp/dotrepo-docs-context-release-gate-20261029/release-bundle --target aarch64-apple-darwin | 1.11 | passed |
| npm ci | 0.71 | passed |
| npm run build | 0.14 | passed |
| npm run package:vsix -- --output /private/tmp/dotrepo-docs-context-release-gate-20261029/vsix/dotrepo-vscode-v1.0.0.vsix | 0.18 | passed |
| verify public metadata and files | 0.28 | passed |
| release install and stdio smoke tests | 1.09 | passed |
| Cloudflare Worker smoke test | 1.24 | passed |
