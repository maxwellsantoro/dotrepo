# Amendment 1: preserve provider Low confidence through the sidecar

The independent review identified a real boundary defect: for any non-null context
selection, `normalize_response` assigned Medium even when the provider explicitly
returned Low. That conversion hid Low from the unchanged core rejection and
bounded escalation checks. `before-reproduction.json` retains the exact owned
synthetic before case, and `before/` preserves both original Python source files.
No provider call occurred to reproduce it.

The production change caps only a High non-null context selection to Medium.
Explicit Low and Medium remain unchanged. A null response retains the provider's
confidence; the unchanged core context path still leaves abstention Unresolved.
Tuple/source/citations, token accounting, scalar behavior, model assignments,
request bounds and all Rust code are unchanged.

Three parameterized selection regressions cover Low/Medium/High; one additional
case covers Low abstention. All 28 focused sidecar tests, including the owned
loopback/mocked provider case, and Ruff check/format pass. Exact commands and logs
are in `checks.json`. `before-after-controls.json` independently loads the retained
before module and current module as owned Python code and shows only Low changes
from Medium to Low; all other normalized fields remain identical. The existing
Rust Low rejection/remaining-call ladder is source-bound in `code-bindings.json`;
no Rust test rerun or actual provider execution was needed for this Python fix.

The original author packet at FREEZE
`9cff9fe402a545300eefd17c61afc155b51c2607dcf8ab249c0222aefcaa420e`
remains unchanged. This child does not claim that the original subject passed
review. The defect is bound by the exact original source copies and our retained
before/after reproduction. The independent reviewer will bind its finding and
this successor separately; no future-review hash is required in this author
subject. Independent after-review and coordinator combined gates
remain required. Source-completeness qualification, record authority, native task
execution, external model calls and consumer-benefit claims remain absent.
