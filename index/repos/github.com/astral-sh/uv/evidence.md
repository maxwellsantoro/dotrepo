# Evidence

- Imported the repository name, description, docs root, and installation entry point from README.md and the published documentation.
- Imported `license = "MIT OR Apache-2.0"` from `Cargo.toml` and `pyproject.toml`.
- Imported `repo.build = "cargo build --profile no-debug --bin uv --bin uvx"` from `.github/workflows/build-dev-binaries.yml`, which is the concrete command the project uses to build development binaries across platforms.
- Inferred `repo.test = "cargo nextest run --workspace"` by normalizing the contributor guide's nextest recommendation and the CI workflow's nextest-based workspace runs into a simpler checked-in default. The record intentionally does not encode the full CI feature and environment matrix.
- Imported `owners.security_contact = "security@astral.sh"` from the organization security policy referenced by the repository SECURITY.md.
- No repository CODEOWNERS file was present in the crawled snapshot, so maintainer ownership remains unset.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
