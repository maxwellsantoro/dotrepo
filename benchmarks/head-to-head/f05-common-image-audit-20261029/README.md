# Independent common-image filesystem audit — 2026-10-29

The exported final filesystem of exact local image
`sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092`
contains no observed operational user credential, nonempty protected-content
alias, known task-source archive or unexplained task-specific exact-file match
within this bounded audit. Packaged format strings, public test/example key
material, system account databases, licenses and generic tiny file overlaps are
retained with explicit dispositions. This is not universal secret/encoding
absence proof, live qualification or permission to run a campaign. No descriptor
or cache audit flag changed.

The plan was frozen **before any daemon operation** in
[plan-freeze.json](plan-freeze.json), SHA-256
`ab94fe058c5aa02323893784358a2aa0d75a8a520b686361c4abf48364f543ad`.
It binds the executed [audit_image.py](audit_image.py), 51-file/82-digest protected
set and known source-archive hashes. The source image/preparation/review packets
remain unchanged. This reviewer has prior source/development context; this is an
independent filesystem assessment, not fresh blind qualification.

## Actual operations and bounds

The only daemon operations were exact image inspect; unique stopped container
create/inspect; streaming export; owned-container removal; and independent absence
inspect. The container was **never started**. No `docker start` or `exec`, upstream
code, package fetch, network/provider/model call, index/profile body read, host
mount/socket/credential provision or VM change occurred. The configured container
was nonroot, readonly, network none, capabilities dropped and no-new-privileges,
with no mounts. Its pre-export state had `Running=false` and zero `StartedAt`.

[export-receipt.json](export-receipt.json) records **1,937,748,992 bytes**, **48,155
members** and **43.52 seconds**, below the frozen 4 GiB / 200,000-member / ten-minute
limits. The private scratch tar is retained at its declared path with mode 0600;
no host extraction occurred. Its SHA-256 is
`d8de699302fac90a58280e0757c22a7aa82a2c40d48d72ab2c8ffc7c933681d6`.
[cleanup-check.json](cleanup-check.json) and separate command receipts show
successful removal and subsequent inspect failure for the exact owned name.

The inventory records every path/type/mode/UID/GID, each regular-file hash and all
link targets: **40,642 regular files**, **4,943 directories**, **2,564 symlinks**,
and **six hardlinks**. The regular files total 1,902,710,429 bytes. All six hardlinks
resolve to retained hashed regular targets. The source image configuration and
five layer IDs match the preparation's retained inspect receipt; recipe/input
bindings are in [construction-bindings.json](construction-bindings.json).

## Underlying paths and content checks

Unlike the prior tmpfs-masked probe, the export exposes the final image's actual
underlying directories. `/workspace` is absent; `/tmp` and `/home` are empty;
`/root` contains only `.bashrc` and `.profile`. Their hashes are retained and no
credential-named assignment was recognized by the bounded static check.

The five primary credential-path candidates are system `passwd`, `group`,
`shadow`, `gshadow` and an empty distributed npm `.npmrc`. All 18 shadow and 39
gshadow password fields are locked; passwd/group contain only placeholder fields.
No password/key value was printed or separately retained. These dispositions and
hardlink resolution appear in [dispositions.json](dispositions.json).

A supplemental streaming path/PEM marker check found 22 candidate files. Explicit
[credential-material-dispositions.json](credential-material-dispositions.json)
classifies them as distributed ELF/static-library format strings, the `file`
recognition database, npm configuration documentation/definitions, a Perl
credential-handling code module, or Go toolchain source/test/example material.
Packaged fixture/example key markers are acknowledged, not silently described as
absent or treated as operational user secrets. This is a bounded origin/format
assessment, not a complete secret detector. Marker values were never emitted.

Every regular file received raw protected-digest comparison. **250 valid JSON
files** also received the supplied canonical encoding check. Exactly **15 files
above 16 MiB** were excluded from canonical parsing, listed in
[canonical-exclusions.json](canonical-exclusions.json); they still received raw
hash checks. The other 40,377 regular files were non-JSON/invalid for canonical
parsing. There were **zero nonempty protected matches** and **105 innocuous empty
matches** to absent profile bodies. The supplied protected input remains digest
only; no actual gold/oracle/profile body was read.

No known raw/compressed task-source archive digest matched. A supplemental
comparison with 12 frozen complete-source inventories found six nonempty image
matches: four redistributed Python/Apache licenses, one generic empty JSON value
and one newline. The two tiny values were independently byte-verified. All are
explicitly disposed in [source-content-overlaps.json](source-content-overlaps.json);
blanket source-file hash refusal would misclassify these shared bytes.

## Verification and limits

[verify_export.py](verify_export.py) independently reread the scratch export,
verified its complete hash, rehashed every regular file and checked all member
metadata, plan/input/receipt/source-inventory bindings, account-field predicates,
tiny shared values, stopped state and cleanup. Its result is retained in
[offline-verification.json](offline-verification.json). Ruff and formatting passed
for all four owned Python files, and whitespace checks passed. Preflight unused
imports and the marker postprocessor's initially unclassified static-library/man
paths were corrected before the final respective evidence; no daemon execution
or export failure was overwritten.

This audit covers the merged final filesystem, not deleted/opaque raw historical
layer payloads. Exact and canonical digests do not detect every partial, semantic,
encoded or encrypted secret/source copy. Future access/policy/consumer/scorer
artifacts remain outside the supplied protected set. Toolchain public test data
can contain key examples without being a host credential. No task test/build,
image task equivalence, offline cache/setup completeness or consumer benefit was
established. Costs remain unknown, not zero. The coordinator must make any next
qualified-descriptor decision explicitly against this scope and the final inputs.
