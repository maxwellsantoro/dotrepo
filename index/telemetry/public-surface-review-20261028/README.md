# October 28 public-surface correction packet

This dated packet retains the evidence used to address the public audit.
It is static source inspection and local implementation evidence, not an
independent consumer study or proof that production has deployed these changes.

- [Documentation re-extraction](doc-command-reextraction.json) freezes the
  inspected high-confidence documentation command queue, pinned revisions,
  source hashes and original re-extraction outcomes. Source bytes live under
  `sources/`; upstream commands are evidence and were not executed.
- [Scope corrections](command-scope-corrections.json) records each withheld
  scalar, its source and reason. It also preserves the source-supported
  Prometheus answer despite an isolated re-extraction miss.
- [Frozen importer controls](frozen-import-controls.json) replays corrected
  fields through the actual importer, records source-code hashes and verifies
  the rejected values are not selected again. The crawler has a separate
  source-pinned refresh/writeback regression for the uv failure.
- [Stable 1.0.4 publication receipt](release-1.0.4-verification.json) is an
  unchanged copy of the published release asset, retrieved for recommendation
  promotion. It records the tag, artifacts, crate provenance and Linux/macOS
  installations. These are the original release checks, not new installations
  performed by this audit.

The corrections preserve each record's original generation timestamp, GitHub
metadata, unrelated values and field assessments. The partially inspected
records are downgraded to imported/medium confidence. New null assessments are
newer than the original record timestamp, so the public exporter withholds them
until a coherent refresh. Historical extraction evidence is retained above an
explicit correction note in each record's evidence file.

The command queue is bounded to retained high-confidence extracted README and
contribution-guide fields. Re-extraction agreement does not establish semantic
correctness for every unchanged answer, and this packet does not cover every
indexed execution field or close the roadmap's population-quality gate.

Website changes are generated from source: a human profile/miss page over the
existing API, explicit context gaps, pinned GitHub source links, wrapped mobile
navigation, consistent measurement-page chrome and a current source-inspection
walkthrough. Stable/package guidance and future release/registry copy are also
updated. A source merge does not replace an existing crate or registry entry;
publication and deployed smoke checks remain separate outcome gates.
