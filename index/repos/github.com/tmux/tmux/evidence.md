# Evidence

- Imported repository metadata from README.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## 2026-10-06 pinned-source command/documentation correction

Inspected the retained upstream revision `e880cf63e0a9fe095d7c5d313761520fb1a8653c` for this six-case frozen risk-audit remainder. Prior import notes above are historical; the corrections below supersede their build/test/documentation-root associations. Record age, status, record-wide trust, and unrelated facts are retained. This source inspection did not execute upstream commands or measure task completion.

| Field | Disposition | Source-preserving decision |
| --- | --- | --- |
| `repo.build` | correct-abstention | Checkout build requires sh autogen.sh followed by ./configure && make, with source-declared native dependencies. The compound source instruction is unsupported as a scalar; do not split it into a manufactured default. |
| `repo.test` | missing-supported | Regression workflow runs make from regress after a prepared build; publish a repository-scoped nested-cwd candidate, preserving the Linux build preparation rather than a root scalar. |
| `docs.root` | missing-supported | README explicitly declares other documentation in the project wiki. |

Execution contexts retain source entrypoints, scope, working directory and prerequisite descriptions. Candidates without a complete value-bound assessment remain unassessed; they are not usable answers merely because their source contains a command.

The assessed `make` candidate is specifically the Ubuntu 24.04 regression configuration in the pinned workflow, executed from `regress` after its native build preparation. It remains a candidate with repository coverage and nested cwd, not a root scalar default.

### Retained source receipts

Source bytes were fetched at the exact revision above, bounded to 2 MiB per response. The dated coordinator audit receipt retains HTTP statuses, body hashes, and bounded missing-path observations. Successful source reads for this record:

- [`README`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/README): HTTP 200, 2231 bytes, SHA-256 `9fb75e6c7f10c25b73e41b8214336d0dc2acfbe4c99984514ccaf7327192d53e`.
- [`Makefile.am`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/Makefile.am): HTTP 200, 6064 bytes, SHA-256 `0aaf8af33a44aa7d5159935e4185ffd92d93ed990ef8d334ef9a4d96c92986a0`.
- [`configure.ac`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/configure.ac): HTTP 200, 27108 bytes, SHA-256 `b59ee2b0d0f5bf92340e65109e2b0566341c50788fe978d6d113274feb96cf2a`.
- [`.travis.yml`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/.travis.yml): HTTP 200, 1525 bytes, SHA-256 `772c099c6e87ef796bb7fc73a94b73098d147bebf9493d668c11d74835601f0d`.
- [`regress/Makefile`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/regress/Makefile): HTTP 200, 875 bytes, SHA-256 `c7646659bf6cedfd1e2c1bcb1f81563519f098df6b9b7fedd4e2c61d78736248`.
- [`autogen.sh`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/autogen.sh): HTTP 200, 377 bytes, SHA-256 `e1ba7ff34373031bff06bd20069f95014d4a2131f015af04a5a5c9a041606f70`.
- [`.github/workflows/regress.yml`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/.github/workflows/regress.yml): HTTP 200, 2153 bytes, SHA-256 `550c9a2616366ba0832b32d8829032a34cdd5952c6ec2c326b31acb0409a397c`.
- [`.github/travis/build.sh`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/.github/travis/build.sh): HTTP 200, 382 bytes, SHA-256 `017d2ff8a3cac931f8717b866133cd786f647785574fc9975e2fb5bc67aee727`.
- [`.github/travis/before-install.sh`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/.github/travis/before-install.sh): HTTP 200, 457 bytes, SHA-256 `950b2d8683ba9a2c75a2d6ac70cffe7ce79be7468c224d6ab4dd79592c046055`.
- [`.github/CONTRIBUTING.md`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/.github/CONTRIBUTING.md): HTTP 200, 2099 bytes, SHA-256 `90ce34c6231e247de12ae43e9fe1842c9875ec7d017c690d5527d4028a4456f9`.
- [`regress/alerts.sh`](https://raw.githubusercontent.com/tmux/tmux/e880cf63e0a9fe095d7c5d313761520fb1a8653c/regress/alerts.sh): HTTP 200, 10753 bytes, SHA-256 `31881218cad2010e65e8271d098130a7c8a44211f6bae352174ee4313b2f4ea8`.

Field/object bindings were obtained from the actual Rust query serializer. Repository-scoped object values omit `component`; component candidates retain it. New or changed field assessments use the actual 2026-10-06 inspection timestamp. The retained record.generated_at and record status do not represent a whole-record refresh: timestamp-incoherent partial assessments are withheld by the public exporter until a complete reassessment.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
