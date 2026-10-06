# Risk-weighted source audit — 2026-10-06

Eight identities were declared before upstream inspection from the frozen seed `20261006` risk sample, choosing the first eight cases with a build/test/documentation value. This covers Rust, Go, Python, JavaScript and prose repositories. All 24 declared fields have dispositions; this is not independent population accuracy or a consumer-task rerun.

| Identity | Build | Test | Documentation root |
| --- | --- | --- | --- |
| `github.com/astral-sh/ruff` | correct-abstention | supported | supported |
| `github.com/nitrictech/nitric` | correct-abstention | supported | supported |
| `github.com/facebookresearch/pytorch3d` | correct-abstention | missing-supported-answer | supported |
| `github.com/redis/redis-py` | source-present-context-missing | wrong-default | wrong-documentation-root |
| `github.com/socketio/socket.io` | missing-supported-candidate | missing-supported-candidate | supported |
| `github.com/microsoft/VibeVoice` | unsupported-inference | unsupported-inference | unsupported-documentation-association |
| `github.com/jassics/security-study-plan` | correct-abstention | correct-abstention | unsupported-documentation-association |
| `github.com/andrewngu/sound-redux` | supported | correct-abstention | wrong-documentation-association |

Before correction, 15/24 scalar fields were present and 11 passed the reference scalar policy. The source audit found two accepted documentation-role errors: SoundRedux’s live application demo and redis-py’s examples leaf selected over its explicitly declared documentation root. Two other accepted documentation associations lacked a sufficient declaration: jassics’ unreferenced external site and VibeVoice’s project/demos page. These unsupported associations are evidence gaps, not a demonstrated contamination or reachability failure.

The raw redis-py pytest default also failed source-preserving wrapper selection, but policy had already refused that inferred command. It now retains the documented `invoke tests` wrapper with development and Docker prerequisites. The distribution build is kept as an explicitly prepared packaging candidate. VibeVoice’s inferred build/pytest defaults are withheld. PyTorch3D’s linked contribution guide supplied a previously missing root unittest instruction. Socket.IO’s all-workspace compile/test procedures remain candidates rather than promoting a nested example into defaults. Ruff and Nitric test wrappers and SoundRedux’s npm build remain source-supported, with preparation/context retained.

After correction, 10/24 scalar fields remain present and five pass scalar policy: the five supported documentation roots. Fresh command/context/candidate assessments are newer than the unchanged record timestamps, so the actual Rust exporter drops them and the actual contextual consumer withholds all 16 build/test requests. Before correction it also selected zero contextual instructions. Scalar-policy acceptance, contextual selection and static source truth are separate measurements; no runtime test was performed.

Current public record-age freshness passes: 616 fresh, zero stale/unknown, oldest age 19 days, no overdue repositories. Record ages/statuses, GitHub metadata, unrelated facts and assessments were asserted unchanged. Every new retained value/context assessment was checked against the actual TOML value. Index validation, public export, freshness and actual reference-consumer checks pass.

Sources/revisions/hashes, every before/after value and policy decision, semantic reasons, candidate/context bindings and per-ecosystem/intent counts are retained in [the JSON receipt](roadmap-risk-audit-2026-10-06.json). The source files remain addressable by immutable upstream revision URLs. Twelve risk-sample identities and the wider source-inspection queue remain open. A coherent full-record recrawl is required before fresh contextual acceptance; this audit does not close F2 population quality, runtime execution correctness or independent usefulness.


Integration corrected an assessment-binding defect: the initial Python comparison normalized an absent `component` to `null`, while the core serializer omits that key. Every newly assessed field across both packets was queried through the actual Rust CLI; 11 bindings were corrected. Real record ages/statuses remain unchanged. In a disposable copy where only record timestamps match the new assessments, the actual exporter retains all 39 assessments and the actual consumer selects the 11 supported contextual instructions. These are serialization/selection controls, not upstream task execution. Details are in the machine-readable receipt.
