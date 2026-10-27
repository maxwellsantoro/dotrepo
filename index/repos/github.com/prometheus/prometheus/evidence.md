# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@prometheus/default-maintainers` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Ignored component-scoped commands from `web/ui/mantine-ui/package.json` as repository defaults.
- Left `repo.build` unset because `CONTRIBUTING.md` and `README.md` suggested conflicting build commands.
- Imported repo.test from CONTRIBUTING.md as `make test`.
- Imported repo.toolchain.min from go.mod as `1.26.10` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `make build` from `README.md` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
