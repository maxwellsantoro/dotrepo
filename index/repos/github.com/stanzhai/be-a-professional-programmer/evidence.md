# Evidence

- Imported repository docs entry points from README.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.root; rejected `http://hadoop.readthedocs.org/en/latest/` because Hadoop resource in a reading list is not documentation for this collection. Source: [README.md:163](https://github.com/stanzhai/be-a-professional-programmer/blob/ad207abd04286568354f2a533979ebdd8906eaa0/README.md#L163). No replacement was established by this correction.
- Downgraded prior `verified` status to `inferred`: the withheld documentation field remains unresolved; prior verification is not inherited.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
