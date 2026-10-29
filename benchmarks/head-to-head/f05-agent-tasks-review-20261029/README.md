# F-05 source review disposition — October 29, 2026

This append-only addendum binds the original source freeze
`fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41`.
All 215 files declared by that freeze remain unchanged. The original gold,
requests, source bytes, classification and verifier remain historical evidence.
The machine-readable [disposition](disposition.json) retains exact
artifact hashes, upstream revision and source locators.

The independent reviewer identified a missing conditional prerequisite in
`go-01`. Microsoft TypeScript's pinned `CONTRIBUTING.md` at commit
`25f823dc198a00744b458a7bc6984359f0dd7cac`, lines 83–86, requires enabling
Git long paths on Windows. The original provisional tuple lists Git but omits
that condition and has no platform restriction. Its command, root directory and
repository-default `test:tsc` scope are otherwise source-supported.

The original status, `supported-source-alternative; independent review pending`,
is preserved as recorded. Before future campaign gold can treat this tuple as
complete, it must retain the Windows conditional prerequisite or explicitly
restrict and review the instruction's applicable platform. Do not cite the
original tuple as complete for unrestricted platforms. The source's global Git
configuration command was inspected as data; it was not executed.

The reviewer also found OpenHands' bin-suite alternative source-supported as the
derivation already disclosed in its gold. This does not establish a successful
execution, runtime completeness, an independent consumer result or launch readiness.

The finding was relayed by the coordinator and checked against retained bytes by
the original curator. This disposition is not a new independent review. Review
context independence and model pretraining exposure are not established by the
report. No upstream code, CI result, environment setup, model session or campaign
was executed, and no evaluated index was consulted.

Future campaign launch still requires independently reviewed gold and resolved
coverage, executable task oracles and controls, frozen environments and dependency
state, model/settings/budgets/costs, an immutable evaluated snapshot and policy,
and enforced randomized-session isolation. Preserve missing setup and unfavorable
outcomes. Incorporate this correction in separately versioned campaign gold;
do not rewrite the original packet.

For integrity, the original freeze hash and every declared file hash/size were
checked. The original unmodified verifier passes because this addendum lives in
an adjacent directory, outside its frozen inventory:

```bash
uv run python benchmarks/head-to-head/f05-agent-tasks-20261029/verify_source_freeze.py
```

No file was added to or modified inside the frozen source packet.
