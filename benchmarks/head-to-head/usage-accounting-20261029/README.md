# Adjudication usage accounting — October 29

Missing native token usage previously became zero in the sidecar, HTTP provider
and batch aggregation. A failed or unreported call could therefore appear to
have a complete zero cost. The correction preserves unknown totals through the
adjudication path, reporting the known subtotal, unknown-call count and explicit
completeness. Explicit provider zero and a no-call zero remain known.

Legacy called numeric records remain readable as reported subtotals; they do not
gain completeness evidence. Missing subprocess receipts can leave the call count
unknown too. Incomplete usage cannot establish token-threshold or scheduled-run
qualification. Malformed usage is distinguished from ordinary missing usage.

Independent review exposed a second defect in the first implementation: batch
normalization repaired contradictory subtotals and invalid unknown-call counts
into apparently complete evidence. Three raw cases that failed strict validation
then passed both cost and streak gates. The successor correction retains bounded
invalidity evidence and propagates that invalidity through aggregation. All three
cases now fail both gates. The original failed review remains preserved.

## Evidence retrieval

[manifest.json](manifest.json) binds all four author/review phases and the
[evidence archive](evidence.tar.gz). The archive contains 72 regular files,
641,212 expanded bytes, including original freezes, patches, source bindings,
counterexamples and check logs. Its SHA-256 is
`b2520efeb29a4d32d833b41349eb826ab7875001f3ffd0a283a000a836eddb62`.
The integration step verified every original freeze binding, every archive entry
and a complete archive readback. Raw observations are packaged together to keep
intermediate receipts out of the main source layout; no historical bytes changed.

The final independent review passes 31 original positive controls, 12 additional
malformed variants, four valid/legacy variants and 124 maintained Python tests.
The author also retained Rust ladder/call-cap controls and eight owned HTTP usage
variants. The coordinator's integrated Python suite passes 980 tests. These are
local controls, not live model observations or production cost measurements.

## Compatibility and limits

The public Rust adjudication response/error and escalation-report `tokens_used`
fields change from `u64` to `Option<u64>`. JSON `tokensUsed` is nullable; consumers
must distinguish it from an explicitly reported zero. Subtotal, unknown-call and
completeness fields accompany it. No `.repo` or MCP protocol version changes.

Model routes, prompts, confidence, authority and attempted-call limits are
unchanged. There is no new token or dollar cap, and the independent synthesis
accounting path is outside this correction. No provider or external HTTP calls
were made by these controls. Quality, consumer benefit and sustained operational
evidence remain separate gates.
