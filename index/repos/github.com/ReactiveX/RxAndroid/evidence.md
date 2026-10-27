# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from .github/workflows/build.yaml as `./gradlew build`.
- Inferred repo.test from build.gradle as `./gradlew test`.
- Imported docs.getting_started as `https://github.com/ReactiveX/RxJava/wiki/Getting-Started`. Explicit documentation link at README.md:68: Further details on building can be found on the RxJava [Getting Started][start] page of the wiki.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
