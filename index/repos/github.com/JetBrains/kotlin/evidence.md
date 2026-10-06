# Evidence

- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from build.gradle.kts as `./gradlew build`.
- Inferred repo.test from build.gradle.kts as `./gradlew test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## 2026-10-06 pinned-source command/documentation correction

Inspected the retained upstream revision `9303195be9d766b7f617e3b091612138fd80bc05` for this six-case frozen risk-audit remainder. Prior import notes above are historical; the corrections below supersede their build/test/documentation-root associations. Record age, status, record-wide trust, and unrelated facts are retained. This source inspection did not execute upstream commands or measure task completion.

| Field | Disposition | Source-preserving decision |
| --- | --- | --- |
| `repo.build` | wrong | Root applies Gradle base, check depends on a test task that always throws. Withhold the generic build; documented dist/install and scoped aggregates are examples, not a verified repository default. |
| `repo.test` | wrong | The exact root test task unconditionally throws and tells users to select aggregate *Test tasks. Do not manufacture an aggregate command. |
| `docs.root` | evidence-gap | ReadMe labels kotlinlang.org Kotlin Site, separately linking tutorial/API leaves. The website URL is not an explicit documentation-root declaration. |

Execution contexts retain source entrypoints, scope, working directory and prerequisite descriptions. Candidates without a complete value-bound assessment remain unassessed; they are not usable answers merely because their source contains a command.

### Retained source receipts

Source bytes were fetched at the exact revision above, bounded to 2 MiB per response. The dated coordinator audit receipt retains HTTP statuses, body hashes, and bounded missing-path observations. Successful source reads for this record:

- [`ReadMe.md`](https://raw.githubusercontent.com/JetBrains/kotlin/9303195be9d766b7f617e3b091612138fd80bc05/ReadMe.md): HTTP 200, 9442 bytes, SHA-256 `b44833a121639a8a88ae5abd60830d443db71916516e447532b2d1a37412b94a`.
- [`build.gradle.kts`](https://raw.githubusercontent.com/JetBrains/kotlin/9303195be9d766b7f617e3b091612138fd80bc05/build.gradle.kts): HTTP 200, 34832 bytes, SHA-256 `86a87a9fc9f06b1f5f77289e56e0faed47d58d508ff2a8daf49085dc1df213fc`.
- [`settings.gradle.kts`](https://raw.githubusercontent.com/JetBrains/kotlin/9303195be9d766b7f617e3b091612138fd80bc05/settings.gradle.kts): HTTP 200, 54485 bytes, SHA-256 `2e8d37008f8154b1404f576e22cba54ddb5790ce3247054a7f7aebdb54593f42`.
- [`gradle.properties`](https://raw.githubusercontent.com/JetBrains/kotlin/9303195be9d766b7f617e3b091612138fd80bc05/gradle.properties): HTTP 200, 11547 bytes, SHA-256 `9c45f879c78026b77a62252cf81da6c1d369eae62a7ba62db8f5066e39375495`.
- [`gradle/wrapper/gradle-wrapper.properties`](https://raw.githubusercontent.com/JetBrains/kotlin/9303195be9d766b7f617e3b091612138fd80bc05/gradle/wrapper/gradle-wrapper.properties): HTTP 200, 399 bytes, SHA-256 `056c65c82e3fb1432d0a12aa0b95d3b1fd917b6884065fbfbbbfd85af01cd4e8`.
- [`docs/contributing.md`](https://raw.githubusercontent.com/JetBrains/kotlin/9303195be9d766b7f617e3b091612138fd80bc05/docs/contributing.md): HTTP 200, 6398 bytes, SHA-256 `29a952d3c141b82552e20b9d29bbd8c035e94b1736b02ff9e08154eb8b5c53c8`.
- [`gradlew`](https://raw.githubusercontent.com/JetBrains/kotlin/9303195be9d766b7f617e3b091612138fd80bc05/gradlew): HTTP 200, 8656 bytes, SHA-256 `a5a5c199ba02189ae8c46a334223371a20599d9c298ef65e7540ede4a3f72d59`.

Field/object bindings were obtained from the actual Rust query serializer. Repository-scoped object values omit `component`; component candidates retain it. New or changed field assessments use the actual 2026-10-06 inspection timestamp. The retained record.generated_at and record status do not represent a whole-record refresh: timestamp-incoherent partial assessments are withheld by the public exporter until a complete reassessment.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
