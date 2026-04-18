# Evidence

- Imported the repository name, description, homepage, and docs entry points from README.md.
- Imported `repo.build = "make install"` and `repo.test = "make"` from the contributor docs and Makefile. The contributor guide explicitly recommends `make install` for local setup and `make` as the standard local checks entry point.
- Cross-checked `.github/workflows/ci.yml`, which runs more granular `uv`-based jobs in CI, but the default record keeps the maintainers' simpler documented workflow instead of encoding CI internals.
- Imported `license = "MIT"` and the canonical package description from `pyproject.toml`.
- Imported `owners.security_contact = "https://github.com/pydantic/pydantic/security/advisories/new"` from the published GitHub security policy flow. No repository SECURITY.md or CODEOWNERS file was present in the crawled snapshot.
- The contributor docs call out `uv`, `make`, and Rust as prerequisites, but dotrepo does not yet expose a dedicated environment/toolchain field on the public surface.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
