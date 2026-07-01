# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after model escalation: Multiple primary manifest-tier build commands exist for different languages (Rust and Python), preventing a single primary value selection.. Preserved 4 candidate command(s) in `repo.build_candidates` instead of discarding them.
- Left `repo.test` unset after model escalation: The candidates represent mutually exclusive language ecosystems (Rust vs Python); no single primary value can represent the repository as a whole.. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

Status dropped from a prior verified record because the following previously present field(s) regressed: repo.build, repo.test.
