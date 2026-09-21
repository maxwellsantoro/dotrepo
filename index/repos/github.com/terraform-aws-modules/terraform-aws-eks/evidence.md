# Evidence

- Imported repository name and docs entry points from README.md.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `terraform-aws-eks` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.getting_started; rejected `https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html` because AWS EKS guide is explicitly external documentation, not module setup instructions. Source: [README.md:29](https://github.com/terraform-aws-modules/terraform-aws-eks/blob/48a429f63cf96361ea2f4b42677d0cc8a9a656e0/README.md#L29). No replacement was established by this correction.
- Downgraded prior `verified` status to `inferred`: the withheld documentation field remains unresolved; prior verification is not inherited.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
