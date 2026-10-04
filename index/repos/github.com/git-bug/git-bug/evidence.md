# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from CONTRIBUTING.md as `make`.
- Imported repo.test from CONTRIBUTING.md as `make test`.
- Imported repo.toolchain.min from go.mod as `1.26.0` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Scoped description correction (2026-10-04)

- Rechecked the GitHub API `description` at
  `2026-10-04T04:39:56.238632+00:00` from
  `https://api.github.com/repos/git-bug/git-bug`. It now states
  `Distributed, offline-first bug tracker integrated in git`.
- Retained the independent source capture in
  `benchmarks/head-to-head/upstream-2026-10-04/git-bug--git-bug.json`.
  The September source capture and accuracy workload remain unchanged.
- Corrected only `repo.description`, removed its prior value-bound assessment,
  and downgraded prior verified authority to imported. The record timestamp and
  other field assessments retain their original September source-inspection age;
  this scoped API check is not a full recrawl or a new verification.
