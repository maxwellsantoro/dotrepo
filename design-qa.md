# Public visual family QA — 2026-11-03

final result: passed

Visual truth: selected Lazy Collective concept
`libfile_74e1eca4b8d08191bae24cdcb132c434`, materialized as
`../lazy-collective-build-20261103/references/collective-memory.png`.
There is no separate pixel-exact DotRepo mock. The approved goal is shared
typography, palette, rules and controls while preserving DotRepo's practical
repository journeys. The parent `design-qa.md` records the normalized combined
target/render comparison and all five fidelity surfaces.

Rendered evidence in `../lazy-collective-build-20261103/evidence/`:
`dotrepo-desktop-final-verified.jpg` at 1440 × 1000 and
`dotrepo-mobile-final-verified.jpg` at 390 × 844, density 1, homepage top, light
theme. `dotrepo-docs-mobile-final.jpg` inspects the focused onboarding controls;
the first path is visible within an 844px viewport. Current code retains public
data, catalog, profile, docs, writing and efficiency URL ownership.

Georgia headings, system body/mono, cream/evergreen/ochre, plain rules and flat
controls establish the family. Existing content, code examples and data controls
remain text/HTML. No illustration replacement is required on this focused product
site. Shared CSS is self-hosted and pinned with a SHA receipt.

Corrections during QA: CSS/module MIME types on the local query server; inherited
small-label contrast from 4.32:1 to the shared darker ochre; explicit main focus
for skip links. Final rendered text sampling found no contrast failures on home,
docs, writing, an article and efficiency. Mobile/desktop routes have one main,
one h1 and no observed horizontal overflow; narrow 320px docs also passed.

Known repository lookup, explicit missing-profile fallback, catalog filtering,
zero results and pagination passed in the actual query server. Evidence, age,
unknown fields and execution limits remained visible. Final working previews
showed no unexpected console errors. Online lookup requires a connection; the
offline browser-navigation probe reached the browser's normal network-error
surface, not a demonstrated offline lookup cache.

The complete public/release gate including VSIX, operator gate, 1217 Python tests,
Rust workspace tests, formatting/lint, dependency policy and parity checks passed
locally. See the retained build receipt for exact inputs and failed setup attempts.
Local macOS checks do not establish remote CI or Linux/Windows runtime matrix
results. No publication or production delivery occurred.
