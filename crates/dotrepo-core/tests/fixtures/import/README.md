This fixture pack captures the current import surface for `README.md`, `CODEOWNERS`,
and `SECURITY.md`.

Cases:
- `full-signals`: happy-path `.github` surfaces with imported name, description, owners, and security contact.
- `badge-heavy-readme`: README badges and images before the first real title and description, plus a root `SECURITY.md` URL.
- `setext-heading-readme`: setext-style README heading plus a wrapped paragraph description.
- `html-heading-readme`: centered HTML heading and paragraph tags that still carry real project metadata.
- `inline-html-wrapper-readme`: inline HTML wrapper around the heading and description on the same line.
- `docs-nav-readme`: title followed by a docs/getting-started nav line that should not become the repo description.
- `docs-label-readme`: explicit documentation/getting-started label lines that should become docs entry points rather than prose description.
- `root-conventional-files`: root-level `CODEOWNERS` and `SECURITY.md`, with title imported but description inferred.
- `description-only-readme`: README description with no heading, so name is inferred from the directory.
- `security-markdown-link`: `SECURITY.md` exposes a contact channel through markdown link syntax rather than raw tokens.
- `security-reference-link`: `SECURITY.md` exposes a reporting mailbox through reference-style markdown links.
- `security-html-anchor`: `SECURITY.md` exposes a reporting mailbox through an HTML anchor tag.
- `security-mailto-query`: `SECURITY.md` uses a `mailto:` link with query parameters that should still resolve to the mailbox.
- `security-contact-unknown`: `SECURITY.md` exists but does not expose a parseable email or URL.
- `no-conventional-surfaces`: no importable conventional files, so the plan falls back entirely to inferred defaults.
- `mixed-codeowners`: repo-wide `CODEOWNERS` ownership plus narrower team overrides, preserving a primary team signal without flattening narrower owners.
- `team-heavy-codeowners`: broad multi-team `CODEOWNERS` patterns that should preserve owner candidates while leaving `owners.team` unset.

Execution-context cases pin an intentionally small documentation subset. A
`Repository build` / `Repository tests` heading declares repository coverage;
`Component build: packages/ui` / `Component tests: packages/ui` declares the
component explicitly. One shell fence must begin with `cd .` or the exact
component directory. Preparatory install/sync lines become source-backed
prerequisite descriptions. `Prerequisites: none.` is required to emit an empty
list; missing setup text alone is not evidence of no prerequisites. These
instructions remain candidates, including repository-scoped instructions; they
are never promoted into scalar defaults by context extraction.

The `context-*` cases cover root/component success, missing declarations,
incorrect or escaping directories, unresolved parameters, incompatible setup
claims, prose and other-section prerequisites, and ambiguous instruction
sequences. Exact candidates and complete contexts are pinned in
`expectations.json`. `docs-setup-dependent-test` verifies that the scalar parser
also preserves prerequisite boundaries by abstaining. The
`context-ries-source-excerpt` control retains the real Python-development block
from the inspected public ries-rs source. Its `PROVENANCE.json` binds the excerpt
to the upstream pin; environment activation and undeclared scope remain
unsupported rather than being flattened into a complete instruction.

The four `docs-source-*` cases retain complete, byte-preserved README files from
pinned risk-audit sources, with retrieval URLs, source hashes and revisions in
`PROVENANCE.json`. SoundRedux's live demo, jassics' absent portal declaration, and
VibeVoice's project/demo page remain withheld as documentation roots. Redis's
explicit linked documentation badge identifies the stable documentation root;
its connection-options examples link remains a leaf, rather than replacing the
root. Native import continues to omit external documentation URLs, while overlay
import preserves the declared external target.
