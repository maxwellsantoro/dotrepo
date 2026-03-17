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

## Maintainer claim checks

- `python3 scripts/check_operator_claim_gate.py --output-root operator-gate` passes when claim workflow, handoff, or claim-aware public-export semantics changed.
- Claim directories live under `repos/<host>/<owner>/<repo>/claims/<claim-id>/`.
- `claim.toml` and `events/*.toml` tell the same story as the latest reviewer decision.
- Event sequence numbers are contiguous and append-only.
- Accepted claims without canonical links remain `pending_canonical`; they do not imply canonical authority early.
- Bootstrap maintainer-owned accepted claims say so explicitly in `review.md` instead of implying independent review.
- Accepted or corrected claims with canonical links point at the expected `.repo` or canonical mirror path.
- Rejected, withdrawn, and disputed outcomes remain visible instead of being flattened away.
- `cargo run -p dotrepo-cli -- --root index claim <claim-dir>` and `cargo run -p dotrepo-cli -- validate-index --index-root index` both reflect the same current state.

## Quick reject signals

- `evidence.md` only says "from the repo" or "from GitHub" without naming a specific source.
- Build or test commands appear in `record.toml` but the evidence does not explain where they came from.
- `security_contact = "unknown"` appears without an explanation.
- The overlay reads like a generated summary instead of a reviewable claim trail.
