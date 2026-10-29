# Manual publication recovery, 2026-10-29

The scheduled refresh landed index commit
`53ed7c41baab8d82b1b686143148a2e3c5e6f243` after successful exact-commit CI
`40828059561`, but its publication receipt remained false because the landing
script treated a deployment-switch read failure as disabled. The enabled
operator setting was unchanged. Its actual scheduled receipt is preserved;
this recovery does not amend it or qualify an operating day.

The coordinator explicitly dispatched the existing public publication workflow
on the still-current default branch. Manual run
[`40829172646`](https://github.com/maxwellsantoro/dotrepo/actions/runs/40829172646)
completed successfully at that exact source commit, including eligibility,
archive, deployment and live smoke steps. `dispatch-request.json`,
`dispatch-response.json`, `run.json`, `jobs.json` and `source-ci.json` retain the
request and resulting evidence. Artifact metadata is retained without claiming
an independent download/hash verification of every publication artifact.

The subsequent public metadata read advertises snapshot
`00af1b0edf1b57526e0b53af7e32cf45ed8372d24362ea38478a948cb1679b45`
with source digest
`9db3b40e9a0ce7fe655971d480fa621004ff8b65009a05fb1898d876c73c04d9`.
The source digest was independently recomputed from the exact committed index
bytes and matches. The first attempt incorrectly sorted full path strings;
that failed assertion is retained in `source-digest-attempts.json`. The owning
Rust algorithm sorts `PathBuf` components; the corrected component-order
calculation and scope are retained in `source-digest-verification.json`.

`live-meta.json` and its HTTP receipt retain the observed public bytes, request
origin, status, headers, size and hash. This verifies the advertised source
digest, not the complete export identity or every public leaf. It does not
demonstrate source fact accuracy, a qualified scheduled streak, independent
adoption, or consumer benefit. Future workflow behavior still needs actual
scheduled publication receipts after the switch-reading fix is delivered.

The F-05 response capture remains bound to its earlier frozen snapshot; no
evaluation inputs were replaced by this new publication. `FREEZE.json` binds
this manual recovery packet without rewriting earlier observations.
