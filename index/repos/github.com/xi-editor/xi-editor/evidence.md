# Evidence

- Imported repository name from README.md.
- Ignored component-scoped commands from `rust/Cargo.toml` as repository defaults.
- Discovered related relation to github.com/lapce/lapce from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## October 29 source-bound correction

The import observations above are historical. This bounded audit inspected only the fields below; other values, field assessments, record generation time, GitHub metadata and existing trust metadata were preserved. No upstream command was executed.

- `docs.root`: retained exact declaration `http://xi-editor.github.io/xi-editor/docs.html`. Contributor guide explicitly declares a project documentation index; README independently links this GitHub Pages site. docs/_config.yml has an older abishov.com URL, so preserve that source discrepancy rather than deriving the root from config. Exact source-declared URL retained; bounded live target status/redirect/content observations are retained separately in index/telemetry/operating-readiness-20261029/f1-corrections. Target content is mutable and does not establish source-version parity.
  - Source: https://github.com/xi-editor/xi-editor/blob/a2dea3059312795c77caadc639df49bf8a7008eb/.github/CONTRIBUTING.md lines 23–27; SHA-256 `1b6f389dcb8fa4085418ea05a7a6124b81c44a340b2ca292ebac462d3a6617ab`.
  - Source: https://github.com/xi-editor/xi-editor/blob/a2dea3059312795c77caadc639df49bf8a7008eb/README.md lines 87–90; SHA-256 `6681f1c1d56642f12480da7e3c68d97fb7e530793be9c56dd07f0a7da168c746`.
  - Source: https://github.com/xi-editor/xi-editor/blob/a2dea3059312795c77caadc639df49bf8a7008eb/docs/_config.yml lines 1–6; SHA-256 `e158c2656123af4baef1b8d7cc2f4f9472724e02545f76c9ea77ab02c28c7711`.

Frozen source-only assessment: `index/telemetry/operating-readiness-20261029/f1-source-assessments.json`; source freeze SHA-256 `779bf4cea196f16ff3f16526e71321367f351fe0a2f5eaeea166099fe8b10d98`. New field checks use their own time; this does not refresh the whole record.

Coordinator trust amendment (2026-10-29): withdraw the previous whole-record verified label after this partial documentation correction. Source-assessed fields do not reverify unrelated fields; record generated_at and unrelated values remain unchanged.
