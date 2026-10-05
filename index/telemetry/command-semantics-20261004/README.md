# Command-source inspection receipt

This audit was triggered by the review of dotrepo commit
`8a923f8b23009a1de453b03abc56c8da294ee0b7`. Its bounded workload consists of
retained build/test assessments naming Make/Just sources, plus retained Go
compile-only or discovery test invocations. The record inputs are that commit's
index. Sources were fetched at each record's `x.github.head_sha`; no upstream
Makefile, Just recipe, or repository command was executed.

[`report.json`](report.json) owns the per-field findings, original values,
re-extracted candidates, dispositions, inspection time, source URLs, and source
hashes. `sources/` retains inspected upstream bytes. Unsupported syntax produces
an abstention; that result does not assert that the upstream task cannot work.
Existing intentional abstentions remain absent even when static extraction
finds a candidate. This measures preservation of source entrypoints, not
execution success, repository-wide scope, or independently correct answers.

Affected records' evidence appendices supersede historical import statements.
Changed or incorrectly sourced commands lose their prior assessments; prior
verified authority is downgraded where necessary. Record timestamps and
unrelated field assessments remain unchanged. Newly corrected values therefore
need fresh complete verification before the positive consumer policy can accept
them. This avoids carrying forward extraction certainty or making other facts
appear freshly inspected.

To reproduce against the original index inputs with the corrected CLI:

```bash
cargo build -p dotrepo-cli
uv run python scripts/audit_task_command_sources.py \
  --index-root /path/to/8a923f8b/index \
  --cli target/debug/dotrepo \
  --output /tmp/dotrepo-command-source-audit
cargo test -p dotrepo-core --test import_quality_gate
```

[`delivery-inspection.json`](delivery-inspection.json) retains read-only HTTP
and GitHub enforcement observations. Python's default User-Agent received
Cloudflare Error 1010 for deployed metadata; the deployment User-Agent received
HTTP 200 from the same local environment. Classic main-branch protection returned
404, while active branch rules and repository rulesets were empty. These
observations identify a deployment-fetch fix and an enforcement gap; they do
not establish a successful publication or a stable release.
