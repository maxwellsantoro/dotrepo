# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@openai/codex-core-agent-team` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from codex-rs/Cargo.toml as `cargo build --workspace`.
- Imported repo.test from justfile as `just test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `codex-rs/Cargo.toml` as `cargo build --workspace`. Component command lacks repository-default scope and working directory.

## 2026-10-04 command semantics correction

The preceding import and auto-promotion entries are historical and superseded for the fields below. Pinned sources were inspected statically; upstream task recipes were not executed. This does not establish task correctness or refresh other facts. Prior affected field assessments were removed, and verified authority was superseded where necessary.

- repo.test: `just test` -> withheld (inspected `justfile`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).

## 2026-10-06 bounded command/documentation source inspection

Inspected retained upstream revision `da18000cae9884ab45f83b2d07fbd5a220a1de39` for `repo.build`, `repo.test`, and `docs.root`. Source instructions were treated as data. No upstream commands, model calls, or external documentation-page execution occurred. This field inspection preserves the existing record timestamp `2026-09-16T16:35:21.055416Z`, status `inferred`, and all unrelated facts. New assessments do not imply whole-record reinspection; the public timestamp-binding gate may withhold them until a coherent full recrawl.

- `repo.build`: correct-default-abstention-with-supported-component-candidate. Documented Rust workspace entrypoint requires codex-rs; not a repository-wide scalar default. Action: preserve scalar null; add value-bound codex-rs component candidate.
- `repo.test`: correct-default-abstention-with-supported-component-candidate. Documented Rust workspace entrypoint requires codex-rs; not a repository-wide scalar default. Action: preserve scalar null; add value-bound codex-rs component candidate.
- `docs.root`: missing-supported. README explicitly declares Codex Documentation; no external page fetched or inferred from hostname. Action: set docs.root to https://developers.openai.com/codex, source README.md.

Retained source files used in the bounded inspection (URLs are pinned to the recorded revision; hashes cover raw bytes):

- [README.md](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/README.md) — SHA-256 `ba4e1f69ff48386e72a9c5e1edaf76aad64a475c2d51af79ccba6d1128261ba7`.
- [justfile](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/justfile) — SHA-256 `69006391c914824d51d49ac7b1ec45caabb6df6a636fb59277fdbe02daf17d36`.
- [package.json](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/package.json) — SHA-256 `0d0a78ff2f703abad442de6e99e127076ad40f85912692a82ec21d968944b368`.
- [docs/install.md](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/docs/install.md) — SHA-256 `1126ec733921878a40720e139ba7be88e325ecf9fa5b113de2cc636bc71a1f5a`.
- [docs/contributing.md](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/docs/contributing.md) — SHA-256 `205b46a2a743aaec47ea46ef7787dfae72eaa9dee4529fba4c635109c8cada9a`.
- [codex-rs/Cargo.toml](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/codex-rs/Cargo.toml) — SHA-256 `fafacfe0e21232efaf578c060d88afedf3608a43c6f2cfe7ba863b5367df56ef`.
- [codex-rs/rust-toolchain.toml](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/codex-rs/rust-toolchain.toml) — SHA-256 `570656042681cfd8795403a455baf9a33035331a07db0645e866bbcea89a3d64`.
- [scripts/just-shell.py](https://raw.githubusercontent.com/openai/codex/da18000cae9884ab45f83b2d07fbd5a220a1de39/scripts/just-shell.py) — SHA-256 `444d6b328d44abf6453b77b6acce2a0c881fc162ff30b20f352c85067797fbe9`.

All conventional missing-file probes and pinned tree listings are retained in the dated remainder audit source receipt. Not-found describes inspected source scope, not universal absence. Codex candidates retain codex-rs scope including documented Windows 11 via WSL2 support. Candidate ordering and record status were not promoted.

This is an external overlay inspection, not a maintainer-controlled canonical record.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
