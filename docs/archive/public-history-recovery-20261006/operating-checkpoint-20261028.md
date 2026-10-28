# Archive operating checkpoint — October 28, 2026

Recovery, publication, and live historical retrieval passed. This receipt adds
operating evidence to the frozen October 6 recovery plan; it does not alter the
original log, source pins, byte anchors, or study results. Times below are UTC.

## Source and recovery

[PR #173](https://github.com/maxwellsantoro/dotrepo/pull/173) separated manual
archive recovery from ordinary deployment enablement and refreshed the compatible
Wrangler lockfile. The account owner completed R2 setup. The first live
[recovery attempt](https://github.com/maxwellsantoro/dotrepo/actions/runs/40622733315)
passed original-exporter reconstruction and all retained anchors, then failed on
Cloudflare HTTP 500 after upload progress reached 44%. It did not commit the
archive log or deploy a replacement snapshot.

[PR #174](https://github.com/maxwellsantoro/dotrepo/pull/174) bounded uploads into
paced batches and added explicit transient-error retries. Its 639 Python tests,
Ruff checks, parity checks, actual public-export integration gate, and selected
[PR CI](https://github.com/maxwellsantoro/dotrepo/actions/runs/40629414741)
passed. [Merged-source CI](https://github.com/maxwellsantoro/dotrepo/actions/runs/40629617296)
passed separately.

The successful [recovery run](https://github.com/maxwellsantoro/dotrepo/actions/runs/40629616916)
rebuilt the original exporters, reconstructed twelve historical snapshots, and
validated the five retained published-body anchors before uploading. It reported
29,521 object writes and completed the final archive-log write at
`2026-10-28T06:59:25Z`. The successful recovery artifact is
[retained with the workflow](https://github.com/maxwellsantoro/dotrepo/actions/runs/40629616916/artifacts/12798032654).
Its artifact SHA-256 is
`f2f125d4fd438afdea6706bc5091288ffc5fca37fc3e95aa1fe8ac370181946f`.
All twelve reconstructed manifest hashes also match the first attempt's retained
validated receipt. Artifacts supplement the persistent R2 archive.

## Publication and live verification

Publication used default-branch revision
`cc5e6c686be0be50dbe3ac67e6caf0ceac86b955`, including the subsequent autonomous
index refresh. Its exact-commit
[CI](https://github.com/maxwellsantoro/dotrepo/actions/runs/40642416921)
and [PR validation](https://github.com/maxwellsantoro/dotrepo/actions/runs/40642417720)
passed `ci-gate` before deployment was enabled.

[Publication run](https://github.com/maxwellsantoro/dotrepo/actions/runs/40647524482)
completed archive upload, Worker deployment with `SNAPSHOT_ARCHIVE`, and live
smoke on `https://dotrepo.org`. Smoke passed the homepage, metadata, file manifest,
inventory, append-only log, stats, query, batch, search, compare, relations, and
24 sampled manifest leaves against the staged public export.

An additional live check at `2026-10-28T07:21:42.347637+00:00` observed:

- `generatedAt`: `2026-10-28T07:04:16.061815309Z`
- `staleAfter`: `2026-11-04T07:04:16.061815309Z`
- `snapshotId`: `f7207bee9d5f8b93517b92115cfa87349328cdebcfd44a42d40efe3b95546fce`
- `snapshotDigest`: `38b9204aceb354f00241233348834cfc1361c19f4dad8d03d224e8a2fba52c3c`
- Thirteen history entries, preserving all twelve frozen entries unchanged.
- Every historical manifest body matching its successful reconstruction hash,
  and a representative public leaf matching each manifest's byte count/hash.
- All five retained original-body anchors matching their recorded hashes.
- The oldest snapshot manifest served with
  `x-dotrepo-snapshot-source: archive`, proving retrieval after static edge eviction.
- Direct public access to the current snapshot's private `query-input` returned 404.

| Historical snapshot | Live manifest SHA-256 | Response source |
| --- | --- | --- |
| `bb0d60a0643e59a6440de4bfc129ab8e3291364cc2251e2d33cccd26f27b1fa2` | `3416f8e0064cc59ff11326fd7c386fee798ab5012236822121cb2e8b29cb65cd` | archive |
| `a0d35df2a73a6face527ccf5a65399defcbae8785ebfd3f3b48917db1e130479` | `b441316ab43995d08d438ba73bcd85a029b574e5ac8998e6c4e32ef1cbd92f08` | archive |
| `ebb5ce5750c656794c0d8c2b93837ef4cd085cb7ca74c31e6bf5eba80a49c62e` | `aed081ff4e7fef74bdef730173a656a42be4c1b2025663be86001c3bd4e163c2` | archive |
| `ed6e31ffa157cd6c96e8ff907a97ce1f707e059784e417b2bbf87ffaba931488` | `4e17d54c9a7c66822a1a2829992b53d99a1e1e2bc13046d926496b45eceb536e` | archive |
| `8384e75929143cbe8a6d8fb27e375d5863eb9c591105765eba1402783336b4cd` | `af784c29c97efb07cee4f739b63d07b60a0aac64c491b01c41b6cf7d654f92f8` | archive |
| `b45a0060153d48067ebf5634402fadf453442e375a7cbb05d55a26e1b310250a` | `f58060e759038cbc1b8322d31a8498d908966d1fad0b622bc89f9c9516945d8b` | archive |
| `499901c89901a9ebacac3ea575bb33a6dabc3b724305b5cf667e6a8ac99ef4ec` | `baf438db41ac3e734f16041239a7e2fe0b0c035ad00c269bb6d28e636cba674c` | archive |
| `75707322809f36bee39edf66ce1011143b2ac62bf0cac158b7f94f8279eab35d` | `646acd3753664397231ecc3826f1d6dc446a42755cd64620ea1a435f2c012ba3` | archive |
| `d178d9ab643022b5484bc439f61d8a9b190379bc1af1644ed3face66ef9512a6` | `35612e4da8cbcbe3f6f294eb9f31fdfedde58e45486b15d9043cb0706502cdfb` | archive |
| `dbcd4783904e34b5f0a5b38a90fddf3093dd12e73ac3d9c13cc153ecd473e53e` | `f36f6ff77f8b5cb81c7688c55bdd32b201e0c40d26bc5b802eb6f0f7fb81a99d` | archive |
| `e85d22cb06ceefa82ba7a328040dc9528a708da6fc391ddabe0c0b38e9409550` | `c82c27d85564b851e57029c4315419d6cf3c9a7423e20db2830798041c8714b1` | archive |
| `a4e07e9651b9a1e0d6ce291b6648894f8adcbe97e5a4ddc79b1f5b01400c249b` | `9cc6f576da337c4f60479f7adfac54ab8ded138ba68850c5ef09bc00c65dd1dd` | no archive header |

## Evidence limits and continuing operation

These are dated recovery, deployment, and retrieval observations. Original source
pins and deterministic reconstruction do not independently establish every
historical byte; only the five declared retained-body anchors provide that
independent corroboration. Export freshness is separate from factual record age,
semantic correctness, independent consumer use, and sustained availability.

`CLOUDFLARE_PUBLIC_DEPLOY_ENABLED=true` was restored after successful recovery.
Keep restoration, complete-history checks, matching Worker bindings, record-age
gates, and live smoke enforced on subsequent deployments. Archive retrieval and
freshness remain continuing operating obligations.
