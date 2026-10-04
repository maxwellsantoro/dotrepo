# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.test from .github/workflows/ci.yml as `pip install pytest pytest-xdist`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Scoped command correction — 2026-10-04

Inspected `.github/workflows/ci.yml` and its three dependency requirement files
at upstream commit `8e7158b2beb8c8269b1b322601214083afc5607f`:
[pinned CI source](https://github.com/google-deepmind/sonnet/blob/8e7158b2beb8c8269b1b322601214083afc5607f/.github/workflows/ci.yml).
The retained source capture and audit disposition live in
`benchmarks/command-audit-2026-10-04/sonnet/`.

The previous `repo.test = "pip install pytest pytest-xdist"` installs dependencies;
it does not run tests. Removed that scalar and its value-bound September
assessment. The actual CI invocation is
`pytest -n auto sonnet --ignore=sonnet/src/conformance/`. It runs from the checkout
root, targets the `sonnet` directory, and explicitly excludes conformance tests.
Retained it as a component candidate, with the workflow's Ubuntu/Python matrix,
requirement files, repository installation, and pytest/xdist setup as prerequisites.
Root execution is inferred from checkout without a `path` input and the absence
of directory overrides under GitHub's
[workspace semantics](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
It is not an assessed repository-default test command or proof of successful execution.

This check covers the command context only. Record-wide `generated_at`, prior
host metadata (including `x.github.head_sha`), confidence, and other field
assessments retain their earlier snapshot and age. The historical import bullets
above describe the superseded inference, not current command authority.
