# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.test from Makefile as `make test`.
- Discovered related relation to github.com/anthropics/claude-code from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `awesome-claude-code` from `GitHub API` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.root; rejected `https://code.claude.com/docs/` because Claude Code product documentation is not documentation for this resource collection. Source: [README.md:7](https://github.com/hesreallyhim/awesome-claude-code/blob/99950f262f91a5ccff512f5fe982e54a70c2e32f/README.md#L7). No replacement was established by this correction.
- Downgraded prior `verified` status to `inferred`: the withheld documentation field remains unresolved; prior verification is not inherited.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
