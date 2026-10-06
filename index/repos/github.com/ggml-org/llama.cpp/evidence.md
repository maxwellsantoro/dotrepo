# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from Makefile as `make build`.
- Inferred repo.test from pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## 2026-10-04 command semantics correction

The preceding import and auto-promotion entries are historical and superseded for the fields below. Pinned sources were inspected statically; upstream task recipes were not executed. This does not establish task correctness or refresh other facts. Prior affected field assessments were removed, and verified authority was superseded where necessary.

- repo.build: `make build` -> withheld (inspected `Makefile`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).

## 2026-10-06 bounded command-source checkpoint

Statically inspected pinned revision `05f2dcfdba3879c55f735efa0f124b1a56f7ed11` at `2026-10-06T04:00:48.158597Z`. Sources and hashes are retained in [the checkpoint receipt](../../../../telemetry/roadmap-factual-checkpoint-2026-10-06.json). No upstream command was executed.

- `repo.build` remains unset: pinned `Makefile` contains an unconditional build-system-change error, not a build target. `docs/build.md` documents backend alternatives; no backend is silently selected as the default.
- A CPU build candidate preserves `cmake --build build --config Release` and the preceding `cmake -B build` as an explicit prerequisite. Root working directory is established by the documented clone/cd procedure; `CMakeLists.txt` requires CMake 3.14 and C/C++ languages. Candidate scope is repository, with backend choice explicit.
- `repo.test = "python -m pytest"` was removed. `pyproject.toml` declares pytest only as a development dependency; CMake test declarations do not establish that Python invocation as the repository test entrypoint. This is a correct abstention for the inspected sources, not a universal no-tests claim.

Record `generated_at`, status and unrelated field assessments are unchanged. The new command/context assessments are newer than that factual record timestamp and do not rejuvenate the whole record; the current public exporter/reference consumer consequently withholds them until a full-record crawl produces coherent evidence. This checkpoint does not establish current upstream HEAD or runtime correctness.

This is an overlay record, not a maintainer-controlled canonical record.
