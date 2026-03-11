# Claim fixture pack

This fixture pack covers the first maintainer-claim histories for Phase 1
validation and later read-only inspection work.

Current cases:

- `accepted-clean`: accepted claim with explicit canonical handoff links
- `pending-canonical`: accepted claim with no canonical handoff links yet
- `disputed`: unresolved claim that stays visibly disputed
- `rejected`: rejected claim with no handoff links
- `withdrawn`: withdrawn claim with no handoff links
- `corrected`: claim history amended through a later `corrected` event
- `invalid-history`: intentionally broken event ordering and state consistency

Each fixture is a standalone index root with:

- `repos/<host>/<owner>/<repo>/record.toml`
- `repos/<host>/<owner>/<repo>/evidence.md`
- `repos/<host>/<owner>/<repo>/claims/<claim-id>/claim.toml`
- zero or more `events/*.toml`

`expectations.json` is the checked-in summary of the current state and validity
expectation for each fixture. Later claim-inspection and workflow work should
reuse these cases rather than rebuilding ad hoc examples.

The workflow helper regression tests also treat `pending-canonical`,
`accepted-clean`, and `corrected` as golden outputs for the current
`claim-init` + `claim-event` command sequence.
