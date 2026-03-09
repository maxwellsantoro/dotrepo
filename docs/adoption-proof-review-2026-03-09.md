# Adoption-proof review

Date: March 9, 2026

This is an early closeout review of the proof-of-adoption board, written on
March 9, 2026. It answers the same questions the end-of-month review is meant
to answer, but with the evidence available now rather than waiting for a later
calendar checkpoint.

## Did import quality improve?

Yes.

Evidence:
- the reusable fixture pack at `crates/dotrepo-core/tests/fixtures/import/`
  now covers README, CODEOWNERS, and `SECURITY.md` edge cases instead of only
  temp-dir happy-path tests
- README import now handles setext headings, HTML headings, and wrapped first
  paragraphs
- owner and security extraction now handle markdown security links and a single
  clear CODEOWNERS team signal
- the machine-readable quality gate at
  `crates/dotrepo-core/tests/import_quality_gate.rs` now fails on regressions in
  imported sources, inferred fields, trust notes, and overlay evidence text

## Did the seed index become a better proof surface?

Yes.

Evidence:
- `index/README.md` now includes an explicit evidence rubric, a starter
  template, and a named showcase set
- the current showcase entries are:
  - `index/repos/github.com/BurntSushi/ripgrep/`
  - `index/repos/github.com/cli/cli/`
  - `index/repos/github.com/sharkdp/bat/`
  - `index/repos/github.com/sharkdp/fd/`
- `index/review-checklist.md` turns the rubric into a repeatable reviewer tool
  instead of leaving quality judgment implicit

## Is there now one crisp maintainer path?

Yes.

Evidence:
- `docs/maintainer-happy-path.md` documents one canonical local loop
- the example repo at `examples/native-minimal/` exercises that loop directly
- `examples/native-minimal/.github/workflows/dotrepo-check.yml` now runs
  `validate`, `query`, `trust`, `doctor`, and `generate --check`

## Are CLI and MCP semantics still aligned?

Yes.

Evidence:
- `dotrepo-core` now exposes shared structured reports for validate, query,
  trust, generate-check, and import-preview
- the CLI validate, query, trust, and generate-check paths now delegate to
  those shared reports
- the MCP server serializes those same reports as tool `structuredContent`
- parity tests in `crates/dotrepo-mcp/src/main.rs` compare MCP outputs directly
  against the shared core reports for the canonical maintainer scenarios

## What constraint is next?

The next real constraint is no longer import quality in the abstract. It is
maintainer authority handoff and conflict visibility.

Reason:
- the repo now has better bootstrap quality, a clearer maintainer loop, and a
  more explicit evidence standard
- the remaining protocol risk is social and semantic: how canonical records
  replace or coexist with overlays once the ecosystem loop starts working

That is why the next contract work should focus on claim, supersede, and
conflict surfacing semantics before any full maintainer claim product flow.
