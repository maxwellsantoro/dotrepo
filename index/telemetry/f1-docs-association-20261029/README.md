# F1 documentation association audit — October 29, 2026

Both declared fields were corrected from contextually scoped links to source-supported project entrypoints. Whole-record automated verification was withdrawn on both records. This was a two-field source-association audit, not a fresh whole-repository crawl, maintainer review, documentation-version validation or consumer measurement.

| Identity / field | Previous association | Applied value |
| --- | --- | --- |
| realm/SwiftLint / docs.root | MegaLinter's SwiftLint integration setup | `https://realm.github.io/SwiftLint/index.html` |
| minio/minio / docs.getting_started | MinIO Client mc quickstart | Immutable MinIO README at revision `7aac2a2c5b7c882e68c1ce017d8256be2feea27f`, fragment `#install-from-source` |

`assessments.json` owns exact values, source passages, reasons and before/after hashes. `corrections.patch` is the precise live-record delta. Both changed records are imported overlays with medium record trust; no reviewed, canonical or verified status was minted. The original factual `generated_at`, x.github metadata, all uninspected facts and all other field-evidence entries remain unchanged. Only the selected documentation field is freshly value/time/source bound. Original evidence is an exact prefix of the appended evidence, including historical auto-promotion text; the dated appendix explicitly supersedes that claim.

## Declaration, authority and acquisition

Before any upstream lookup, `declaration.json` declared only SwiftLint docs.root and Minio docs.getting_started from the existing eligible-risk sample. Selection flags were not correctness labels. The before-lookup freeze SHA256 is `7ecd77079b56e9bd467f6d782ba9d8614e342dc3be19f6e193516ab0a73eadcb`; it retains both original record/evidence pairs, status, authority, selected values and value-bound assessments. Both were automated verified overlays, without local native/reviewed/canonical authority or claim files. Their source/path identities match. Old hashes were rechecked immediately before writing.

Eight explicit read-only acquisition operations were used out of twelve permitted: two purpose-built GitHub repository metadata calls, two exact Git commit metadata calls, two base64 README file calls, and two bounded HTTP GETs for SwiftLint's documentation navigation. All six GitHub responses and timing envelopes are retained under `requests/`. The connector does not expose wire request/traffic totals; eight counts the explicit operations, not invented internal HTTP overhead. The two direct HTTP GETs disabled automatic redirects, capped each body at 2 MiB, and both returned 200 without following a redirect. No crawl, source/package acquisition beyond these files, provider call or upstream command execution occurred.

The README files were decoded without whitespace normalization, hashed and independently matched to Git blob SHA-1 values from the immutable contents responses. Commit metadata supplies the pinned commit/tree identity. This is file-at-ref/API evidence, not a reconstructed whole Git tree or a claim that either inspected revision is the current default-branch tip. The record-pinned revisions and factual ages remain explicit.

## SwiftLint disposition

At revision `ec4691d9e813a1d3358e82917326b56b0a71d3c9`, README lines 482–487 describe MegaLinter as an aggregator that embeds SwiftLint, then point to **its** integration setup instructions. The old URL remains potentially useful for that named integration task; its label does not establish SwiftLint's project documentation root.

README lines 606–607 separately declare the Rule Directory. Its retained target page links `index.html` through the documentation header and breadcrumb. That index identifies SwiftLintCore 0.65.1 Docs, links this repository, and renders the SwiftLint overview. The replacement is the exact resolved declared navigation URL. This association rests on source wording and navigation/content evidence, not a matching domain. Both target bodies, hashes, status, URL, headers and observation times are retained under `targets/` and `requests/`.

The target is mutable. Its source-commit/release parity is not established by the page's displayed version or Last-Modified header. The correction establishes its role as the project documentation entrypoint, without asserting installed-version compatibility or the truth/completeness of every page.

## MinIO disposition

At revision `7aac2a2c5b7c882e68c1ce017d8256be2feea27f`, README lines 139–153 explicitly scope the old Quickstart Guide link to the separate MinIO Client mc. That is useful connectivity guidance, but a client quickstart is not the server repository's getting-started entrypoint.

The same README states at lines 23–24 that it provides source-build/baremetal deployment instructions; lines 59–89 give Install from Source and standalone-server startup. Line 99 explicitly references `#install-from-source`. The replacement resolves that fragment against the exact immutable README URL already fetched through GitHub, rather than inventing an external server quickstart URL or selecting a broad documentation index. Its role follows the server instructions and source anchor, not domain identity.

The README marks this repository unmaintained; existing archived metadata is retained. The source's commands and example credentials were read as documentation data and were never executed. This correction neither recommends deployment nor establishes runtime success, support or security.

## Checks and durability

The existing local first-party validator binary SHA256 `b9cd73236bca71ecf4fb7aa06bfe131b1ecc41a9b0fdfb43de579fb6d24ce0d0` returned `index valid`, exit0. No Cargo build was run. Its command/output/hash receipt is under `checks/`; integrated validation on the final commit remains coordinator-owned.

TOML checks verify exact replacement valueJson bindings, unchanged factual dates/x.github/other fields and evidence rows, permitted status/trust downgrades, unchanged source bytes and exact original evidence prefixes. Whitespace checks passed, with packet-local attributes preserving raw upstream source/HTML formatting. No frozen benchmark/evaluation gold or older telemetry was changed.

Two first-party README-only import replays reproduce the old selections in this existing parser. `parser-replay.json` and its exact inputs/outputs are extraction diagnostics, not full crawler refreshes or upstream test runs. Therefore these data corrections alone do not prevent recurrence or act as tombstones. `regression-proposal.json` proposes contextual integration-subject and client/server quickstart controls, including positive custom-domain/client-project cases; shared parser, fixtures and expectations remain untouched. No domain blacklist, generic client-word veto or prose-based executable policy is proposed.

Remaining gates are independent source/patch review, integrated index/public-surface checks for the exact landed state, and a separate source-context parser-policy/regression fix for the demonstrated recurrence. Whole-record age and uninspected facts were not refreshed. These two identities are outside the declared E1/F05 study identities, and no study evaluation output was consulted.
