# Source provisioning delivery observations — October 29

[PR 186](https://github.com/maxwellsantoro/dotrepo/pull/186) merged as
`4b0d769d424118d063c0fffbb793c422edb88478` after exact-head CI
[`40833642133`](https://github.com/maxwellsantoro/dotrepo/actions/runs/40833642133)
passed at `d76581560e88e92d9a0298c2c7fc94e28c44542d`. Every selected job passed,
including Linux and Windows native boundary checks and the aggregate `ci-gate`.
Main's subsequent CI
[`40834078203`](https://github.com/maxwellsantoro/dotrepo/actions/runs/40834078203)
also passed at the merge commit. The two skipped jobs were excluded by the
classifier. The root coordinator checked strict required `ci-gate` and admin
enforcement before merging; no branch-setting change or bypass was used.

The preceding main publication
[`40832172884`](https://github.com/maxwellsantoro/dotrepo/actions/runs/40832172884)
completed at source `91643102c6083fda66827f68e43a06e7cdc8cec8`, including immutable
archive, deployment and live smoke steps. The retained public metadata advertises
snapshot `ee516ee3d493d5c307f07dfd71275355c540bb65f1ee3bd20eae654344d87f32`.
An independent calculation over all 2,406 exact committed regular index files,
excluding `.crawler-state.toml` and using Rust path-component order, matches its
advertised source digest
`ed72bdd4700acf529595fcf1266f3edbd6944f24c1bb1098cbd6c37a21339ca4`.

This is a source-digest check and retained workflow observation. It does not
recompute the full public export identity or independently inspect every public
leaf. The publication observation belongs to the preceding source commit;
PR 186's source merge and CI are recorded separately from its later deployment.
No observation here qualifies the original publication-skipped scheduled day,
independent adoption, a paid agent campaign or consumer benefit. The F-05 response
capture keeps its earlier immutable snapshot.

Raw PR/run/job metadata, the bounded public HTTP read and the digest calculation
are bound by `FREEZE.json`. Later observations must be appended rather than
rewriting these receipts.
