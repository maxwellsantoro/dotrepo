# Partial-correction trust amendment

The first frozen F1 correction intentionally preserved status/trust metadata.
Coordinator review found that this retained an inappropriate whole-record
verification claim on xi-editor and rime-cloverpinyin after adding documentation
answers that the prior inspection had missed.

This append-only amendment changes those two records from `verified` to
`imported`, sets record confidence to medium, removes current `verified`
provenance and replaces the old all-fields-resolved note with the partial
inspection limit. It preserves `generated_at`, all field values/assessments and
unrelated metadata. The field inspection has not become a whole-record refresh.

`receipt.json` binds the first correction outputs to the amended records.
Before/after records and evidence notes are retained. The original correction
freeze is unchanged and describes its own intermediate state. This amendment
does not mint maintainer authority or claim another execution/accuracy result.
