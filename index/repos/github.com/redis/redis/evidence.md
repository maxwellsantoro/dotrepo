# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from .github/workflows/ci.yml as `make REDIS_CFLAGS='-Werror' BUILD_TLS=yes`.
- Inferred repo.test from .github/workflows/ci.yml as `make SANITIZER=address REDIS_CFLAGS='-Werror -DDEBUG_ASSERTIONS -DREDIS_TEST' BUILD_TLS=module`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
