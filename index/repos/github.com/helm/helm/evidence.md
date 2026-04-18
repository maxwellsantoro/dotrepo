# Evidence

- Imported the repository name, description, docs root, and quick-start entry point from README.md.
- Imported `repo.build = "make"` and `repo.test = "make test"` from the official developer setup docs and the repository Makefile. `make test` intentionally includes style checks plus unit tests.
- Cross-checked the Makefile's lower-level Go build/test commands, but the default record keeps the maintainers' higher-level documented workflow instead of encoding implementation details.
- Imported `owners.security_contact = "cncf-helm-security@lists.cncf.io"` from CONTRIBUTING.md and the repository SECURITY.md entry point.
- Imported `owners.maintainers` from the repository OWNERS file. No root CODEOWNERS file was present in the crawled snapshot.
- README and CONTRIBUTING.md both state that `main` is Helm v4 development and unstable, while the stable Helm v3 line lives on `dev-v3`; that branch context is preserved in the trust notes.
- Acceptance tests depend on the separate `helm/acceptance-testing` repository and are not the default `repo.test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
