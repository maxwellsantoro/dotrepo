# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from Justfile as `just build`.
- Imported repo.test from CONTRIBUTING.md as `pytest tests/unit/ -v`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- Imported docs.root as `https://github.com/OpenMined/PySyft/blob/dev/docs/workflow.md`. Explicit documentation link at README.md:20: - [Workflow](https://github.com/OpenMined/PySyft/blob/dev/docs/workflow.md) — End-to-end privacy-preserving data analysis workflow
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-04 command semantics correction

The preceding import and auto-promotion entries are historical and superseded for the fields below. Pinned sources were inspected statically; upstream task recipes were not executed. This does not establish task correctness or refresh other facts. Prior affected field assessments were removed, and verified authority was superseded where necessary.

- repo.build: `just build` -> withheld (inspected `Justfile`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).
