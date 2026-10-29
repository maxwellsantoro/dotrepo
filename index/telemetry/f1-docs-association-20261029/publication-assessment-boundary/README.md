# Public assessment timestamp boundary follow-up

Append-only follow-up to the unchanged parent FREEZE.json (SHA256 2a4b40f7e5cfc35d796fe6e2f0d15a9ecaf40aa80ffd20cabc4d13190aa2f3ed). No original frozen files or live records changed in this follow-up.

The existing local CLI successfully exported an isolated index containing copies of the two corrected records. Both corrected documentation facts appear in the profiles with imported status and unchanged record dates. Neither new documentation field assessment appears in public `fieldEvidence`. The stored fresh `checkedAt` differs from the preserved `record.generated_at`, so `public/evidence.rs:48-54` withholds the assessment. Query evidence uses the same filtered map (`query_field_evidence`). Other historical assessments whose times still equal the record date remain exported; this follow-up does not reassess those facts.

No backdating or refresh of uninspected facts occurred. The fresh, value-bound assessment remains stored in the record and appended evidence; publication carries the corrected fact without that assessment. A future public assessment timestamp contract is a separate decision.

`execution.json` binds the existing binary and exact command; `checks.json` records value/date/assessment observations and the initial verifier camelCase-key error. Two profiles are retained verbatim; `export-output-hashes.json` binds every generated file before other temporary generated outputs were removed. No Cargo, network, third-party code, or live deployment occurred. This receipt covers the existing binary, not a newly built current-head binary.
