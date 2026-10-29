# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Imported repo.build from Makefile as `make build`.
- Imported repo.test from Makefile as `make test`.
- Imported repo.toolchain.min from go.mod as `1.24.0` (Go).
- Imported docs.getting_started as `https://docs.min.io/community/minio-object-store/reference/minio-mc.html#quickstart`. Explicit documentation link at README.md:153: Follow the MinIO Client [Quickstart Guide](https://docs.min.io/community/minio-object-store/reference/minio-mc.html#quickstart) for further instructions.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.


## Bounded F1 documentation association correction — 2026-10-29

Earlier import and auto-promotion paragraphs above are retained as historical evidence. This dated correction supersedes the selected `docs.getting_started` value and withdraws the whole-record verified claim.

- Previous value: `https://docs.min.io/community/minio-object-store/reference/minio-mc.html#quickstart`. Its source association is to the named integration/client task, not this repository documentation entrypoint.
- Corrected value: `https://github.com/minio/minio/blob/7aac2a2c5b7c882e68c1ce017d8256be2feea27f/README.md#install-from-source`.
- Source: https://github.com/minio/minio/blob/7aac2a2c5b7c882e68c1ce017d8256be2feea27f/README.md, revision `7aac2a2c5b7c882e68c1ce017d8256be2feea27f`, README SHA256 `aae99b6e35489bb26bfba4290ac567861d123230d1831562b6aee8c1363aead3`, Git blob `84e49277432b54d5e84de2a5be59c75950746d37`.
- Assessment: Pinned README lines 139-153 explicitly scopes the old Quickstart Guide link to the separate MinIO Client mc. For this server repository, README lines 23-24 declares that the README supplies source-build and baremetal deployment instructions, lines 59-89 provides Install from Source and standalone-server startup, and line 99 explicitly links #install-from-source. The replacement resolves that declared fragment against the exact immutable README URL. This is server getting-started documentation, not proof that commands execute or that the unmaintained project is currently supported.
- Target/source observations: The replacement uses the exact GitHub README content already fetched at the pinned commit, with its explicitly referenced #install-from-source fragment. No additional mutable external target was selected or fetched. The README marks the repository unmaintained; the existing archived metadata is retained.
- Field evidence checked at `2026-10-29T08:36:31.832479Z` and bound to the exact replacement value. Raw sources, request timings, before/after hashes, limitations and dispositions: `index/telemetry/f1-docs-association-20261029/`.
- Record downgraded from automated verified to imported with medium record trust. Remaining fields were not reinspected, their old evidence timestamps are retained, and `generated_at = 2026-10-04T07:53:35.951591156Z` is unchanged; this does not reset whole-record factual age. No upstream command execution or maintainer review was performed.

This is an overlay record, not a maintainer-controlled canonical record.
