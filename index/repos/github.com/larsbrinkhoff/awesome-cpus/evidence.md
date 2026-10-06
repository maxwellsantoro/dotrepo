# Evidence

- Imported repository name from README.md.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `awesome-cpus` from `GitHub API` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 pinned-source command/documentation correction

Inspected the retained upstream revision `fbd37421105fc591cb26f72fe9d13c35fb340ea9` for this six-case frozen risk-audit remainder. Prior import notes above are historical; the corrections below supersede their build/test/documentation-root associations. Record age, status, record-wide trust, and unrelated facts are retained. This source inspection did not execute upstream commands or measure task completion.

| Field | Disposition | Source-preserving decision |
| --- | --- | --- |
| `repo.build` | correct-abstention | The root is a collection of CPU documentation/submodules; no repository-default build is declared in inspected conventional sources. |
| `repo.test` | missing-supported | Travis declares sh tests.sh. Preserve the wrapper as an unassessed candidate: it alters Git state and piped loops do not reliably propagate error() exit status. No test outcome or execution reliability is claimed. |
| `docs.root` | correct-abstention | README is a bibliography of CPU documentation, not a declaration of a separate project documentation root. |

Execution contexts retain source entrypoints, scope, working directory and prerequisite descriptions. Candidates without a complete value-bound assessment remain unassessed; they are not usable answers merely because their source contains a command.

### Retained source receipts

Source bytes were fetched at the exact revision above, bounded to 2 MiB per response. The dated coordinator audit receipt retains HTTP statuses, body hashes, and bounded missing-path observations. Successful source reads for this record:

- [`README.md`](https://raw.githubusercontent.com/larsbrinkhoff/awesome-cpus/fbd37421105fc591cb26f72fe9d13c35fb340ea9/README.md): HTTP 200, 1868 bytes, SHA-256 `048398b174455b1a6ef1aa842dd65c04e949e2a2aa1bb16e6ff303050c8bb9b4`.
- [`CONTRIBUTING.md`](https://raw.githubusercontent.com/larsbrinkhoff/awesome-cpus/fbd37421105fc591cb26f72fe9d13c35fb340ea9/CONTRIBUTING.md): HTTP 200, 536 bytes, SHA-256 `d7ab747328c18c1b0ad6bed88e25e8209e9ddbb327b67ee2f7a219ba45f0faa1`.
- [`tests.sh`](https://raw.githubusercontent.com/larsbrinkhoff/awesome-cpus/fbd37421105fc591cb26f72fe9d13c35fb340ea9/tests.sh): HTTP 200, 1152 bytes, SHA-256 `08e2e38423688cc532eece16a02c05cbff0f0f71d009fb414ec4bb41555e43ba`.
- [`.travis.yml`](https://raw.githubusercontent.com/larsbrinkhoff/awesome-cpus/fbd37421105fc591cb26f72fe9d13c35fb340ea9/.travis.yml): HTTP 200, 20 bytes, SHA-256 `ff8dcbc7ffa18085972e697f76e376f0c37c42b30fac9efa23ff3871b6e58c0d`.
- [`.gitmodules`](https://raw.githubusercontent.com/larsbrinkhoff/awesome-cpus/fbd37421105fc591cb26f72fe9d13c35fb340ea9/.gitmodules): HTTP 200, 518 bytes, SHA-256 `af07e50f9c06542aad826dd7f1a3ee625593c903bb227b81aeee0d019282166c`.

Field/object bindings were obtained from the actual Rust query serializer. Repository-scoped object values omit `component`; component candidates retain it. New or changed field assessments use the actual 2026-10-06 inspection timestamp. The retained record.generated_at and record status do not represent a whole-record refresh: timestamp-incoherent partial assessments are withheld by the public exporter until a complete reassessment.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
