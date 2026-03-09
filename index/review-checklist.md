# Seed Index Review Checklist

Use this checklist when reviewing overlay contributions for the seed index.

## Structural checks

- `record.toml` exists in the expected `repos/<host>/<owner>/<repo>/` path.
- `evidence.md` exists beside `record.toml`.
- `record.mode = "overlay"`.
- `record.source` matches the index path identity.
- `repo.homepage`, when it is also a repository URL, matches that same identity.
- `cargo run -p dotrepo-cli -- validate-index` is clean or only emits understood warnings.

## Evidence checks

- The evidence says what was imported directly and names the upstream source.
- The evidence says what was inferred and explains the reasoning path.
- The evidence explains where `repo.build` came from.
- The evidence explains where `repo.test` came from.
- The evidence explains any intentional `unknown` placeholders, especially security contacts.
- The evidence ends with the overlay disclaimer.

## Trust checks

- The record status and `record.trust.provenance` match the story told in `evidence.md`.
- Imported claims do not sound maintainer-verified unless the source justifies that wording.
- Inferred claims are not presented as canonical facts.
- Non-reference trust vocabulary, if present, is preserved deliberately and not introduced casually.

## Quick reject signals

- `evidence.md` only says "from the repo" or "from GitHub" without naming a specific source.
- Build or test commands appear in `record.toml` but the evidence does not explain where they came from.
- `security_contact = "unknown"` appears without an explanation.
- The overlay reads like a generated summary instead of a reviewable claim trail.
