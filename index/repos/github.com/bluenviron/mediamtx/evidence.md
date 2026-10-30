# Evidence

- Imported repository docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.test from .github/workflows/test.yml as `make test`.
- Left `repo.build` unset because root go.mod supplies only a conventional build candidate, not a repository-default build instruction.
- Imported repo.toolchain.min from go.mod as `1.27.0` (Go).
- Imported docs.root as `https://mediamtx.org/docs/kickoff/introduction`. Explicit documentation link at README.md:24: | [Install](https://mediamtx.org/docs/kickoff/install) | [Documentation](https://mediamtx.org/docs/kickoff/introduction) |
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
