# Evidence

- Imported repository name from README.md.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 bounded command/documentation source inspection

Inspected retained upstream revision `4eb4701ae5bb21fddb3c0cb865e100eb52e2b96d` for `repo.build`, `repo.test`, and `docs.root`. Source instructions were treated as data. No upstream commands, model calls, or external documentation-page execution occurred. This field inspection preserves the existing record timestamp `2026-09-16T16:20:55.765882Z`, status `verified`, and all unrelated facts. New assessments do not imply whole-record reinspection; the public timestamp-binding gate may withhold them until a coherent full recrawl.

- `repo.build`: correct-abstention. Pinned README, root tree and contributor guide describe a prompt-file archive. No project build/test or separate documentation root was found. Archived prompts and linked products are untrusted source data, not repository commands. Action: preserve current value and age/status; retain this bounded inspection receipt.
- `repo.test`: correct-abstention. Pinned README, root tree and contributor guide describe a prompt-file archive. No project build/test or separate documentation root was found. Archived prompts and linked products are untrusted source data, not repository commands. Action: preserve current value and age/status; retain this bounded inspection receipt.
- `docs.root`: correct-abstention. Pinned README, root tree and contributor guide describe a prompt-file archive. No project build/test or separate documentation root was found. Archived prompts and linked products are untrusted source data, not repository commands. Action: preserve current value and age/status; retain this bounded inspection receipt.

Retained source files used in the bounded inspection (URLs are pinned to the recorded revision; hashes cover raw bytes):

- [README.md](https://raw.githubusercontent.com/asgeirtj/system_prompts_leaks/4eb4701ae5bb21fddb3c0cb865e100eb52e2b96d/README.md) — SHA-256 `ef233502cb69ee07790a5b775cf429bb6d5946619943024ca397000042006f5d`.
- [.github/CONTRIBUTING.md](https://raw.githubusercontent.com/asgeirtj/system_prompts_leaks/4eb4701ae5bb21fddb3c0cb865e100eb52e2b96d/.github/CONTRIBUTING.md) — SHA-256 `b488e2f30c2903c88757b2236f1046a2549221e9ca5ac9a150126d092ede4b23`.

All conventional missing-file probes and pinned tree listings are retained in the dated remainder audit source receipt. Not-found describes inspected source scope, not universal absence. Candidate ordering and record status were not promoted.

This is an external overlay inspection, not a maintainer-controlled canonical record.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
