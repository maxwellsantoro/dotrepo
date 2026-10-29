# Append-only nested Go skip correction

`counterexample.json` retains the original oracle's false positive: a skipped
`TestOne/child` followed by passing `TestOne` was incorrectly accepted because
only top-level skips were collected. The revised oracle rejects skips at any
depth while retaining its top-level expected-coverage comparison.

`freeze.json` binds the original implementation, revised implementation and
counterexample before future upstream execution. Three positive and eleven
negative synthetic native-format controls pass. No upstream commands or model
calls were made for this correction. The original four-task packet is unchanged.
The independent reviewer found no skipped events at any depth in Vault's retained
93-test run, so that result does not need re-execution for this correction.
