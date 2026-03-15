# dotrepo Seed Index

This directory is a seed version of a standalone `dotrepo/index` repository.

It exists to make the public-index model concrete early:
- contributors can add overlay records before maintainers adopt dotrepo natively
- CI can validate index-specific contribution rules
- agents and tools can point at a real index layout instead of only RFC text
- the seed tree can model what high-quality evidence-backed overlays should look like

## Layout

Each record lives under:

```text
index/
  repos/
    <host>/
      <owner>/
        <repo>/
          record.toml
          evidence.md
```

## Day-one rules

- v0.1 seed-index entries use `record.mode = "overlay"`.
- The checked-in seed index remains overlay-only until dotrepo has a real
  reviewed maintainer handoff it is willing to publish for a live repository.
- `record.toml` must pass `dotrepo validate`.
- `evidence.md` must exist beside every `record.toml`.
- `record.source` must resolve to the same `<host>/<owner>/<repo>` path used by the index entry.
- `repo.homepage`, when it is a repository URL, must match that same identity.
- `validate-index` fails on structural and identity errors, and warns when public-index records use non-reference trust vocabulary or thin evidence.
- `evidence.md` should say what was imported, what was inferred, where build and test commands came from, and why any `unknown` placeholders are intentional.

## Evidence rubric

Reference-quality `evidence.md` files should make review easy, not force a reviewer
to reverse-engineer where claims came from.

At minimum, every overlay evidence file should:
- state what was imported directly and name the upstream source
- state what was inferred and explain the reasoning path
- explain where `repo.build` came from, even when the answer is "inferred from project layout"
- explain where `repo.test` came from, even when the answer is "inferred from project layout"
- explain why any intentional `unknown` placeholders remain, especially security contacts
- end with the reminder that the record is an overlay, not a maintainer-controlled canonical record

Reference-quality evidence should also:
- prefer source-specific citations over vague phrases like "from the repo"
- group related imported claims when they come from the same source
- avoid making inferred claims sound maintainer-verified
- make it obvious when a field is absent because the source material did not justify a stronger claim

## Starter template

Use [`index/evidence-template.md`](evidence-template.md) as the starting point for new
overlay entries, then replace each placeholder with repository-specific evidence.

Reviewers can use [`index/review-checklist.md`](review-checklist.md) as the short
PR checklist when deciding whether an overlay is strong enough to merge.
For maintainer-claim review, use
[`docs/maintainer-claim-review-workflow.md`](../docs/maintainer-claim-review-workflow.md)
as the end-to-end operator loop.
That workflow currently stages one copied seed entry through claim handoff and
`public export` in CI instead of checking a proof-only accepted claim into the
live seed index.

## Reference examples

These current seed-index entries are the reference-quality examples for v0.1:
- [`github.com/BurntSushi/ripgrep`](repos/github.com/BurntSushi/ripgrep/) shows a trust-aware overlay with inferred build and test commands plus an intentional `unknown` security contact.
- [`github.com/cli/cli`](repos/github.com/cli/cli/) shows a heavily imported overlay with build, test, license, and security claims tied to specific upstream sources.
- [`github.com/sharkdp/bat`](repos/github.com/sharkdp/bat/) shows a curated Rust overlay with maintainer handles, imported development commands, and explicit security reporting evidence.
- [`github.com/sharkdp/fd`](repos/github.com/sharkdp/fd/) shows the same evidence standard on a second repository with similar project shape, so contributors can compare patterns across examples.

These entries should be strong enough to serve as model contributions for future
overlay submissions, not just as structurally valid records.

## Local validation

Run:

```bash
cargo run -p dotrepo-cli -- validate-index
```

CI runs the same command in pull requests and in the primary-branch validation
workflow.
