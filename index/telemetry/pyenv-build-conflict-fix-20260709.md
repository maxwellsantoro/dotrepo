# pyenv build-conflict fix — 2026-07-09

## Symptom

`github.com/pyenv/pyenv` was `verified` but `promotion-report` re-scored it
**ineligible** with:

`repo.build: unresolved — intra-tier conflict left field unset during import`

Crawl auto-promotion still treated the record as high-confidence absent and
eligible, so status and re-score disagreed.

## Root cause

1. Workflow extraction matched `apt install … make build-essential` as a build
   command because substring checks treated `build-essential` like `make build`.
2. Two such lines from different workflows produced a **conflict note**.
3. Both commands failed shell-safety sanitize (`;`), so verification scored
   **high-confidence absent** (no *safe* candidates).
4. `score_index_record_for_promotion` still read the conflict note → Unresolved.

## Fix (code)

- `first_matching_workflow_command`: skip host package managers; token-aware
  `make` task matching (`build` / `all` as whole targets only).
- `resolve_unique_command_candidate`: only shell-safe commands participate in
  unique/conflict resolution.
- `score_import_fields`: if trust notes still claim a command conflict, score
  Unresolved (aligned with promotion re-score).

## Index disposition

- Updated pyenv `record.toml` notes + `evidence.md` to honest absence of build
  (host package install, not conflict).
- Live recrawl deferred on GitHub API 502 during this session; re-crawl when
  API is healthy to refresh `generated_at` / head SHA only.
