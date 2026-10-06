# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.test from Makefile as `make test-unit`.
- Discovered related relation to github.com/rbenv/rbenv from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 pinned-source command/documentation correction

Inspected the retained upstream revision `676b71e7b52d1a094c6659213c23649b9e290455` for this six-case frozen risk-audit remainder. Prior import notes above are historical; the corrections below supersede their build/test/documentation-root associations. Record age, status, record-wide trust, and unrelated facts are retained. This source inspection did not execute upstream commands or measure task completion.

| Field | Disposition | Source-preserving decision |
| --- | --- | --- |
| `repo.build` | correct-abstention | README presents native Bash extension compilation as optional; no repository-default build is established. |
| `repo.test` | wrong | test-unit runs core tests only. test/README declares test the whole host suite, and the root Makefile retains all four suite prerequisites and Bats setup. Replace the scoped scalar with the full wrapper and bind context. |
| `docs.root` | correct-abstention | README links a Commands Reference leaf and a test README, but does not declare a separate documentation root. Preserve abstention rather than promote a leaf to whole-project docs. |

Execution contexts retain source entrypoints, scope, working directory and prerequisite descriptions. Candidates without a complete value-bound assessment remain unassessed; they are not usable answers merely because their source contains a command.

`make test` preserves the Makefile dependency graph for core, Python-Build, Pyenv-Binary and Pyenv-Link tests and Bats acquisition. The independently assessed context retains complete checkout/tool prerequisites, macOS preparation, and the unfiltered host suite. The optional native-extension and Docker variants are not promoted into this default.

### Retained source receipts

Source bytes were fetched at the exact revision above, bounded to 2 MiB per response. The dated coordinator audit receipt retains HTTP statuses, body hashes, and bounded missing-path observations. Successful source reads for this record:

- [`README.md`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/README.md): HTTP 200, 32290 bytes, SHA-256 `3d83dcee608ddc47d1189b98b93d383612d7b9761eec229adfe3d9483018f18f`.
- [`CONTRIBUTING.md`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/CONTRIBUTING.md): HTTP 200, 6494 bytes, SHA-256 `547e4a1c8fb02b68dcda02491d0b79d1da1b55c41099c140dfff233a1404b0b9`.
- [`Makefile`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/Makefile): HTTP 200, 7904 bytes, SHA-256 `2d45a20d93302e69ed9ec9eba4325957e4dee98b53eff7de625a3e730652b1ea`.
- [`test/run`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/test/run): HTTP 200, 237 bytes, SHA-256 `2a6b2ed3ac36026fd1e865617ba6754bdf3d4ec837df19d1ef3400e4d78367e7`.
- [`COMMANDS.md`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/COMMANDS.md): HTTP 200, 11758 bytes, SHA-256 `7723dc4692a7640d4e7b04722a595f2e0f53e4079954c30d0134e1e12df40738`.
- [`src/configure`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/src/configure): HTTP 200, 954 bytes, SHA-256 `272556deea4dedf65462d55125239072d7fd92d592c9a824aa183703d22116e8`.
- [`test/README.md`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/test/README.md): HTTP 200, 1189 bytes, SHA-256 `0d2c6153002ece5328fc03f43e1695b29f914b85394de0b1c40153b2e17ded04`.
- [`.github/workflows/pyenv_tests.yml`](https://raw.githubusercontent.com/pyenv/pyenv/676b71e7b52d1a094c6659213c23649b9e290455/.github/workflows/pyenv_tests.yml): HTTP 200, 998 bytes, SHA-256 `f34e24d83fc40170345378b44d5cc5366152460b6a3c6fab9b2952292999bb8d`.

Field/object bindings were obtained from the actual Rust query serializer. Repository-scoped object values omit `component`; component candidates retain it. New or changed field assessments use the actual 2026-10-06 inspection timestamp. The retained record.generated_at and record status do not represent a whole-record refresh: timestamp-incoherent partial assessments are withheld by the public exporter until a complete reassessment.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
