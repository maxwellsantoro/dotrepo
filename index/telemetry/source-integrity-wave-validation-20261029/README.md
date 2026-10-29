# Source integrity and Go build evidence integration checks

This wave keeps module-only conventional Go build candidates diagnostic and
filters them from scalar selection and adjudication. The independently reproduced
explicit-conflict finding was fixed without relaxing existing workflow context
blocks. It also adds a private mechanical source-attachment verifier: fresh
verification failures make candidates unresolved, while valid bindings retain
only their existing medium confidence and independent completeness uncertainty.

Final combined Rust formatting, workspace Clippy, dependency policy and workspace
tests passed, as did standalone alias formatting/locked check and release/toolchain
parity. The Python suite passed 850 tests. Complete release packaging, including
VSIX, exporter/consumer controls and Worker smoke, and the operator gate passed.
Ruff runs on an isolated selected-index export with its cache disabled. A final
public gate covers the completed index telemetry after this packet is frozen;
its receipt stays outside the index to avoid self-modifying input. Exact-head CI
and both native platform jobs remain merge prerequisites.

The first full Rust run exposed the old Testify canary's metadata-only build
expectation. Root intentionally replaced it with an explicit absence assertion,
keeping all captured source and frozen benchmark/gold bytes unchanged. A narrow
regression run passed. The next formatting check caught the newly added assertion
layout; root formatted that test and the final full run passed. Earlier failed
logs and check receipts remain here. Author/reviewer packets separately retain
the earlier compile, expectation-order and reproduced eligibility failures.

Source-only Keras installation findings do not establish complete test setup.
The source-only Go-01 oracle remains unaccepted, with missing native collection
and dynamic skip/source conditions; its synthetic controls cannot establish an
actual task outcome. These implementation/integrity checks close neither E2
fresh held-out qualification nor F-05 consumer benefit, independent use,
publication, or the qualified scheduled window.
