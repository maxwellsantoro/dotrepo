# Project review follow-through — 2026-09-16

This dated report records the local changes and validation prompted by the project
review. README describes the product; ROADMAP remains the active strategy.
Nothing in this report claims that the local changes have been deployed or that
an external consumer has adopted dotrepo.

## Purpose and usefulness

The immediate product is reusable repository facts for agent orientation:
project metadata, execution commands, documentation, ownership, provenance, and
age. It helps avoid repeated discovery of these facts. Architecture research and
code changes still need source inspection. Native maintainer records provide
control; the overlay index permits consumption before maintainer adoption.

The README and homepage now lead with this concrete use, an actual profile,
lookup, and integration steps. Coverage limits and record age are visible.
Authority claims and maintainer workflows remain available below the lookup.

## Changes and evidence

| Review concern | Response |
| --- | --- |
| Export freshness concealed stale facts | Profile record age/status/source revision; independent freshness gate; 609/613 records re-crawled today |
| Routine refresh did not sustain coverage | Daily 50-record schedule, stale same-HEAD refresh, authoritative index membership, telemetry before validation, machine-gated automatic landing |
| Record-wide confidence hid field differences | Value- and timestamp-bound field assessments; unknown/unresolved states retained; unsupported legacy source attribution removed |
| Accuracy proof was too narrow | Added 123 cited upstream assertions across 32 preselected repositories; retained original 20 assertions; both pass |
| Buried-field errors were hidden by small regression sets | New blind 17-question/eight-project audit with three unindexed holdouts; original unfavorable result retained |
| Request estimates were described like agent savings | Modeled efficiency relabeled; benchmark now counts complete prefetch/fallback requests, response bytes, and whole-arm elapsed time |
| Adoption lacked external evidence | Generic integration package, explicit task policy, executable fallback benchmark, and outcome template; adoption remains unclaimed |

The new audit exposed two high-confidence Node command errors. The parser now
preserves actual script names (`compile`, `dist`, `bundle`, `test-all`) instead of
substituting `build` or a package-local test example. Checking 162 retained
package-manifest sources found five affected records; all five were re-crawled.
The client also requires fallback for explicitly inferred build/test commands.

Status counts now reflect machine assessments: 362 verified, 244 inferred, and
7 imported. Confidence/status counts are reported rather than rewarded with a
release floor. Accuracy, freshness, validity, conflicts, and completeness remain
gated. Ownership coverage was rebased from 118 to 116 after pinned upstream
checks found CODEOWNERS removed in sunnypilot, .NET MAUI, and Moby; another record
gained ownership. Exact revisions and rationale are in the coverage baseline.

## Results and limits

- Structured independent assertions: **123/123** across 32 repositories.
- Existing regression assertions: **20/20** across three repositories.
- Full-index task completeness: **60.4%**; field completeness: **78.41%**.
- Initial independent buried-field run: lookup-first **10/17** correct with
  **two high-confidence wrong answers**.
- Correction rerun: lookup-first **12/17** correct, one low-confidence wrong
  fallback answer, four abstentions, and zero high-confidence wrong answers.
  It used 84 HTTP requests and 170,463 decoded response bytes; the heuristic
  source baseline used 114 requests and 326,618 bytes.

The correction run reuses the discovered cases: it is regression evidence, not
new independent proof. The source baseline was heuristic, while dotrepo ran
locally. This does not establish superiority to a strong-model baseline, hosted
latency savings, billed token savings, net savings including index maintenance,
or external adoption. The indexed Spring Boot profile still supplies an inferred
Gradle test default rather than its documented aggregate check; the reference
client rejects that inferred command and falls back.

Four records remain honestly stale because upstream identities moved:
`prisma/prisma` → `prisma/orm`, `titanwings/colleague-skill` →
`titanwings/distilly`, `square/okhttp` → `lysine-dev/okhttp`, and
`coreybutler/nvm-windows` → `nvm-windows/nvm`. The crawler refuses to refresh old
identities with another identity's data. Identity migration remains separate
from factual refresh.

## Validation

- Rust workspace: **515 tests passed**; formatting and strict Clippy passed.
- Python: **228 tests passed**; Ruff checks and formatting passed.
- Canonical release gate passed with `--skip-vsix`: export contracts, index,
  coverage/quality/accuracy/freshness, Worker tests and dry run, public bundle,
  binary bundle, install smoke, and local hosted-query smoke. VSIX packaging was
  not run.
- Desktop (1440×1000) and mobile (390×844) checked with Playwright. Lookup opens
  the correct profile; invalid input reports an error. Homepage and efficiency
  page horizontal overflow were fixed. No application JavaScript errors were
  observed; the simple static preview logged a favicon 404 on a raw JSON page.
- Generic client smoke: pnpm accepted, inferred Spring Boot commands rejected,
  unindexed eza counted as a miss.

Artifacts: [initial benchmark](../../benchmarks/head-to-head/results/september-2026-09-16/report.md),
[correction benchmark](../../benchmarks/head-to-head/results/september-correction-2026-09-16/report.md),
[generic pilot](../consumer-pilot.md).

Deployment and the GitHub automation token/enablement/required checks must be
configured before the revised daily workflow can maintain the hosted surface.
No remote deployment, settings change, or external outreach was performed.

## Publication follow-through

The subsequent publication pass migrated all four moved identities after checking
that their old and new GitHub endpoints returned the same numeric repository ID.
Each destination was crawled before the old overlay was removed; the audit trail
is in `index/identity-migrations.json`. All 613 records now have current checks.
Current status counts are 361 verified, 245 inferred, and 7 imported.
The rewritten `nvm-windows/nvm` upstream has no root license and its GitHub license
endpoint returns 404, so license coverage was honestly rebased from 559 to 558.

The daily workflow uses the repository's built-in token. It explicitly dispatches
CI for an index-only PR, verifies the expected commit and public gate, publishes
that tested commit with a non-forced fast-forward, then explicitly dispatches
and verifies deployment. Failed or skipped checks cannot count as success.
Automatic public deployment now follows successful default-branch CI.
Python validation increased to 240 passing tests, including landing failure and
race checks. Remote deployment and enablement results are recorded in the task
that performs publication; the earlier local-only results above remain historical.

The full local canonical release gate also passed with VSIX packaging and install
smoke checks. Same-HEAD records become refresh-eligible at 14 days, leaving time
for the 13-day nominal rotation before the public 30-day age limit.
