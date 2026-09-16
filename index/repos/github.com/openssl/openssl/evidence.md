# Evidence

- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.test from .github/workflows/ci.yml as `! make test TESTS="test_external_gost_engine"`.
- Discovered related relation to github.com/openssl/openssl from README cross-link.
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
