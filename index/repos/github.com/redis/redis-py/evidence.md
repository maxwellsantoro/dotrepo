# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred repo.build from .github/workflows/pypi-publish.yaml as `python -m build .`.
- Inferred repo.test from pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## 2026-10-06 bounded risk audit

Statically inspected source revision `27225cf0dcc683ce963437495b07ad7fdc83fc83` at `2026-10-06T04:07:21.224082Z`. Sources, hashes and all declared field dispositions are retained in [the audit receipt](../../../../telemetry/roadmap-risk-audit-2026-10-06.json).

- `repo.build`: source-present-context-missing. Workflow literally builds the root distribution with this command, after Python/tool setup. Retain as a packaging candidate rather than inferred scalar default.
- `repo.test`: wrong-default. Contribution guide declares invoke tests; tasks.py runs multiple selected fixture/standalone/cluster suites with required options. A raw inferred pytest invocation does not preserve this declared instruction.
- `docs.root`: wrong-documentation-root. README documentation badge declares the root stable documentation URL; examples.html is specifically the connection examples subpage.

Record age/status and unrelated facts/assessments remain unchanged. New source-grounded command/context assessments are newer than the record timestamp; the public exporter drops them until a coherent full-record recrawl. No upstream commands were executed, and no fresh pipeline verification or current-HEAD inspection is claimed. Absence is limited to the inspected sources.

This is an overlay record, not a maintainer-controlled canonical record.
