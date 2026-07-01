# Evidence

- Imported repository name and description from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `Cargo.toml` and `package.json` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `package.json` suggested conflicting test commands.
- Discovered related relation to github.com/maxwellsantoro/ries-rs from Cargo.toml repository.
- Discovered related relation to github.com/clsn/ries from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `cargo build --features wasm --locked` from `.github/workflows/ci.yml` after deterministic escalation.
- Left `repo.test` unset after model escalation: The candidates represent mutually exclusive ecosystems (Rust vs Node.js); no single primary value can be selected for a single repository.. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

Status dropped from a prior verified record because the following previously present field(s) regressed: repo.test.
