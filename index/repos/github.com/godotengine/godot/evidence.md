# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Inferred repo.build from .github/workflows/android_builds.yml as `./gradlew :editor:assembleAndroidAndroidTest :editor:assembleAndroidDebug -Pperform_signing=true`.
- Inferred repo.test from .github/workflows/android_builds.yml as `./gradlew :editor:assembleAndroidAndroidTest :editor:assembleAndroidDebug -Pperform_signing=true`.
- Discovered related relation to github.com/godotengine/godot from README cross-link.
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
