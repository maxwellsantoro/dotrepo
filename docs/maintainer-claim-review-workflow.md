# Maintainer Claim Review Workflow

This doc describes the first Git-native maintainer-claim review loop for index
operators.

It assumes:
- the index root is available locally
- the target repository already exists under `repos/<host>/<owner>/<repo>/`
- reviewers use the current CLI helpers rather than hand-editing claim files by
  default

This workflow is intentionally narrow. It supports durable claim artifacts,
append-only review history, and explicit handoff recording before any public
submission product exists.

The binary-level CLI contract tests in
`crates/dotrepo-cli/tests/claim_command_contract.rs` exercise the accepted,
corrected, and invalid-history paths described here.
For one-command operator validation, run
`python3 scripts/check_operator_claim_gate.py --output-root operator-gate`.

## Current command surface

The current reviewer workflow uses:

- `dotrepo claim-init` to scaffold a draft claim directory
- `dotrepo claim-event` to append audit events and update current claim state
- `dotrepo claim` to inspect one claim directory
- `dotrepo validate-index` to confirm the index still passes structural and
  claim-history validation

Reviewers should still write the substantive review note content in `review.md`
manually when they choose to keep reviewer notes beside the claim.

## End-to-end loop

All examples below assume the index root is `index/`.

### 1. Scaffold the draft claim

```bash
cargo run -p dotrepo-cli -- --root index claim-init \
  --host github.com \
  --owner acme \
  --repo widget \
  --claim-id 2026-03-18-maintainer-claim-01 \
  --claimant-name "Acme maintainers" \
  --asserted-role maintainer \
  --record-source https://github.com/acme/widget \
  --canonical-repo-url https://github.com/acme/widget \
  --review-md
```

This creates:

- `repos/github.com/acme/widget/claims/<claim-id>/claim.toml`
- `repos/github.com/acme/widget/claims/<claim-id>/events/`
- optional `review.md`

The scaffolded claim starts in `draft`.

### 2. Submit the claim for review

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind submitted \
  --actor claimant \
  --summary "Submitted maintainer claim."
```

This appends `events/0001-submitted.toml` and updates `claim.state` to
`submitted`.

### 3. Mark active review

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind review-started \
  --actor index-reviewer \
  --summary "Started maintainer authority review."
```

This appends `events/0002-review-started.toml` and updates `claim.state` to
`in_review`.

### 4. Inspect and validate during review

Use both the claim-centric and index-wide checks:

```bash
cargo run -p dotrepo-cli -- --root index claim \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01

cargo run -p dotrepo-cli -- validate-index --index-root index
```

The first command shows current state, claimant, target, derived handoff, and
event history. The second confirms the claim directory still satisfies layout,
identity, event ordering, and handoff rules.

The operator gate script writes inspectable reports for the accepted, corrected,
and invalid-history fixture paths under `operator-gate/`, and it stages one
real seed overlay handoff through `public export`, so the release bar is not
just "tests pass" but "the documented reviewer and public surfaces still look
right."

### 5. Record the terminal review outcome

#### Accept, pending canonical

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind accepted \
  --actor index-reviewer \
  --summary "Accepted claim pending canonical publication."
```

With no canonical paths, the accepted claim remains `pending_canonical`.

#### Accept with explicit canonical handoff

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind accepted \
  --actor index-reviewer \
  --summary "Accepted claim after identity review." \
  --canonical-record-path .repo \
  --canonical-mirror-path repos/github.com/acme/widget/record.toml
```

This records canonical handoff links and makes the derived handoff
`superseded`.

#### Reject

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind rejected \
  --actor index-reviewer \
  --summary "Rejected claim pending additional evidence."
```

#### Dispute

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind disputed \
  --actor index-reviewer \
  --summary "Marked disputed pending maintainer identity clarification."
```

#### Withdraw

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind withdrawn \
  --actor claimant \
  --summary "Withdrew claim until canonical publication is ready."
```

### 6. Correct a prior outcome without rewriting history

Corrections append a new event. They do not delete earlier review outcomes.

If the correction changes the current state, set `--corrected-state` explicitly:

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind corrected \
  --corrected-state accepted \
  --actor index-reviewer \
  --summary "Corrected earlier rejection after evidence review."
```

If the correction also completes canonical handoff, include canonical paths in
the same command:

```bash
cargo run -p dotrepo-cli -- --root index claim-event \
  repos/github.com/acme/widget/claims/2026-03-18-maintainer-claim-01 \
  --kind corrected \
  --corrected-state accepted \
  --actor index-reviewer \
  --summary "Linked accepted claim to canonical artifacts." \
  --canonical-record-path .repo \
  --canonical-mirror-path repos/github.com/acme/widget/record.toml
```

## Outcome quick reference

| Outcome | Command shape | Result |
| --- | --- | --- |
| `submitted` | `claim-event --kind submitted` | Moves `draft -> submitted` |
| `in_review` | `claim-event --kind review-started` | Moves `submitted -> in_review` |
| `accepted` | `claim-event --kind accepted` | Records accepted claim; no canonical paths means `pending_canonical` |
| `superseded` handoff | `claim-event --kind accepted --canonical-*` | Records accepted claim plus canonical links |
| `rejected` | `claim-event --kind rejected` | Keeps explicit rejection in audit history |
| `disputed` | `claim-event --kind disputed` | Keeps disagreement explicit |
| `withdrawn` | `claim-event --kind withdrawn` | Records claimant withdrawal without deleting history |
| `corrected` | `claim-event --kind corrected [--corrected-state ...]` | Amends current state or handoff without rewriting prior events |

## Current guardrails

- `claim-init` refuses to overwrite an existing claim directory unless forced.
- Even with `--force`, `claim-init` refuses to overwrite any claim directory that
  already contains event history.
- `claim-event` writes append-only event files with deterministic sequence-based
  names.
- Canonical handoff links are only accepted when the resulting claim state is
  `accepted`.
- `corrected` events may amend current state, but they still preserve prior
  outcome events.

## Still intentionally manual or deferred

- claimant identity proof and external verification
- public maintainer submission UX
- automatic canonical `.repo` generation from accepted claims
- automatic review-note generation
- public site or API presentation of claim history

This is an operator workflow first, not a public product flow.
