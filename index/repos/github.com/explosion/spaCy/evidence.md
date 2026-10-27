# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from .github/workflows/tests.yml as `python -m build --sdist`.
- Imported repo.test from Makefile as `make test`.
- Imported docs.root as `https://spacy.io/usage`. Explicit documentation link at README.md:116: [documentation](https://spacy.io/usage).
- Imported docs.getting_started as `https://spacy.io/usage#section-quickstart`. Explicit documentation link at README.md:255: [quickstart widget](https://spacy.io/usage#section-quickstart) to get the right
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
