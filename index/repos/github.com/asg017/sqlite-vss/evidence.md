# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.test from Makefile as `make test`.
- Discovered related relation to github.com/asg017/sqlite-vec from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.getting_started; rejected `https://huggingface.co/blog/getting-started-with-embeddings#1-embedding-a-dataset` because third-party embeddings tutorial is not a sqlite-vss getting-started guide. Source: [README.md:34](https://github.com/asg017/sqlite-vss/blob/8d3c6ff2fca651104563779a0d927ea4fba40347/README.md#L34). No replacement was established by this correction.
- Downgraded prior `verified` status to `inferred`: the withheld documentation field remains unresolved; prior verification is not inherited.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
