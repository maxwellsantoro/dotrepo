# Evidence

- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 pinned-source command/documentation correction

Inspected the retained upstream revision `dc86ef8dd8fbe8564fb7453c03f5b738da3450bb` for this six-case frozen risk-audit remainder. Prior import notes above are historical; the corrections below supersede their build/test/documentation-root associations. Record age, status, record-wide trust, and unrelated facts are retained. This source inspection did not execute upstream commands or measure task completion.

| Field | Disposition | Source-preserving decision |
| --- | --- | --- |
| `repo.build` | missing-supported | CONTRIBUTING.adoc declares the projects-scoped install wrapper; preserve it as a component candidate, withhold a scalar and assessment while platform prerequisites remain incomplete. |
| `repo.test` | missing-supported | CONTRIBUTING.adoc and CI declare the projects test wrapper covering JVM/Android/KMP JVM tests, not examples or macOS-native tests. Preserve wrapper and component scope; prerequisites remain unassessed. |
| `docs.root` | evidence-gap | README labels this URL Official Website; its separate setup-page leaf does not establish a documentation root. Withhold the unsupported association and preserve repo.homepage. |

Execution contexts retain source entrypoints, scope, working directory and prerequisite descriptions. Candidates without a complete value-bound assessment remain unassessed; they are not usable answers merely because their source contains a command.

### Retained source receipts

Source bytes were fetched at the exact revision above, bounded to 2 MiB per response. The dated coordinator audit receipt retains HTTP statuses, body hashes, and bounded missing-path observations. Successful source reads for this record:

- [`README.md`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/README.md): HTTP 200, 5577 bytes, SHA-256 `bed360a226569b644d2ed59d9930232ccdc7158a29c70092a95f40cfc46ec60d`.
- [`CONTRIBUTING.adoc`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/CONTRIBUTING.adoc): HTTP 200, 2505 bytes, SHA-256 `7f890d6ef45fa37384e3413c495e27139a576dd706461ca34211aad047e240b5`.
- [`.github/workflows/build.yml`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/.github/workflows/build.yml): HTTP 200, 1166 bytes, SHA-256 `6e551d1ef43334e44f8a4f363e7d999eadf0acea1748016aed3103d792175fe5`.
- [`projects/build.gradle.kts`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/build.gradle.kts): HTTP 200, 1685 bytes, SHA-256 `2cd7ceb43f46316ed20256406e5d2a86b49eba421c63abfb8f949fb020b0cdde`.
- [`projects/settings.gradle.kts`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/settings.gradle.kts): HTTP 200, 1777 bytes, SHA-256 `2a2c882a064ef02815c9871f8f530a5c8f374dadea00d087dc43e3f9ce15ed71`.
- [`projects/gradlew`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/gradlew): HTTP 200, 5916 bytes, SHA-256 `929621eb733dd908f10a8b4c145b61e987f191199b3b32dfbb9b14fcf8c16894`.
- [`projects/install.sh`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/install.sh): HTTP 200, 66 bytes, SHA-256 `c99c7246b0608e07b72aa92c274e933c8e302a0034ea7aaf4afe769d8fdde5ec`.
- [`projects/test.sh`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/test.sh): HTTP 200, 278 bytes, SHA-256 `c3fc00e66f6a7238d05e82e687af38694d39de63b7a4b7203b3827a06e314449`.
- [`projects/gradle.properties`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/gradle.properties): HTTP 200, 583 bytes, SHA-256 `dd858676d995a021677b3f7a3671bb8aba16f4d8e91624a05ebe0f18259bbe40`.
- [`projects/gradle/wrapper/gradle-wrapper.properties`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/gradle/wrapper/gradle-wrapper.properties): HTTP 200, 233 bytes, SHA-256 `97c948908878136f54fa8baab8e4603d1fbd286314743d298cea0630d8170ec2`.
- [`.github/actions/prepare-env/action.yml`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/.github/actions/prepare-env/action.yml): HTTP 200, 411 bytes, SHA-256 `fa90e728389f52ee8a13d63cd2177f9e3ad076286ec34fa17bc1543ed72ef533`.
- [`projects/gradle/libs.versions.toml`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/gradle/libs.versions.toml): HTTP 200, 5684 bytes, SHA-256 `7cfac2b9cd9bda2f53424f32906d7f67d5f0582873cba16ef504730710db9fce`.
- [`projects/android/koin-android/build.gradle.kts`](https://raw.githubusercontent.com/InsertKoinIO/koin/dc86ef8dd8fbe8564fb7453c03f5b738da3450bb/projects/android/koin-android/build.gradle.kts): HTTP 200, 1784 bytes, SHA-256 `f196fe5ab0d429c07f722ab13ff398f449f84468af0f318aaf930716a9a8957b`.

Field/object bindings were obtained from the actual Rust query serializer. Repository-scoped object values omit `component`; component candidates retain it. New or changed field assessments use the actual 2026-10-06 inspection timestamp. The retained record.generated_at and record status do not represent a whole-record refresh: timestamp-incoherent partial assessments are withheld by the public exporter until a complete reassessment.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
