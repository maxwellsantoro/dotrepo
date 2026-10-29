# Evidence

- Imported repository name from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from README.md as `cargo build --release --features 'pcre2'`.
- Imported repo.test from README.md as `cargo test --all`.
- Imported repo.toolchain.min from Cargo.toml as `1.96` (Rust).
- Discovered related relation to github.com/BurntSushi/ripgrep from Cargo.toml repository.
- Discovered related relation to github.com/BurntSushi/linux from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.


## Partial command-scope correction — October 28, 2026

The extraction and auto-promotion notes above are historical. `repo.build` is withheld: Optional PCRE2 feature build, not the general build: the guide separately gives cargo build --release in the clone/directory setup block.

The general build block includes `git clone` and `cd ripgrep`; this partial correction does not guess a context-free replacement. Record age, GitHub metadata, the separately documented test command, unrelated facts and assessments are unchanged. Record status is now imported with medium record confidence. The new null assessment was inspected at 2026-10-29T02:34:17.631297Z and is newer than the record timestamp, so the public exporter withholds it until a coherent refresh. Sources and dispositions are retained in `index/telemetry/public-surface-review-20261028/command-scope-corrections.json`. No upstream command was executed.
