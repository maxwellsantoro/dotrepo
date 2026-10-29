# Optional same-shell-call capture implementation — preparation only

The existing runtime now supports an optional frozen `eventCaptures` map. The
normal shell path remains when it is absent. Enabled repositories use one common
arm-neutral configuration and exact helper hash; no gold, scorer or correct-command
lookup is introduced. All commands remain agent choices. Client cancellation now
retains partial raw receipts and kills before waiting.

The host operation observes its fixed event-path baseline, container context and
explicit source/tool subset; runs the unchanged command; then boundedly exports
and checks the regular event file before returning control. Raw process/event
bytes and descriptor remain host-only. Provider display text may use replacement
decoding, but no exported byte/hash is derived from that display. Source/tool
observations and actual command/process/container/request/tool-call bindings are
retained with timestamps. Null tool hashes mean observation-only, not proof of a
source-owned build. Subset integrity is explicitly not whole-revision integrity.

The complete configuration keys and hard ceilings are frozen in `plan.json`.
No configuration enabling real execution was created. A single method deadline
begins before helper construction; each probe/process/export uses its remaining
budget. Byte/request bounds, failed/cancelled/missing/unsafe/changed/after-check
states remain visible. Missing files from ordinary commands never turn their
successful response into a failure. Unknown transfer accounting becomes null;
requests/time remain reported. Local cost is unmetered null. Capture elapsed is
whole-operation time, not a measured causal overhead.

Exact final focused checks:214Python tests covering runtime/capture/preparation,
Ruff check/format and owned diff whitespace. The controls include raw invalidUTF8,
method ordering, stale/absent/symlink/hardlink/special/oversize/changed/context/source/
tool/cap cases, deadline/request/byte limits, failed/cancelled process and export,
unknown transfer accounting, source-generated tool observations, session cleanup,
arm/config/default compatibility and no host artifact in provider response.
The first integration fake used a constant inspect name rather than the runtime's
randomized name; its failed receipt is retained and fixture corrected. Initial
Ruff fixture-import findings are retained separately. No actual Go,Node,Docker,
upstream task,network orprovider actions ran; existing trusted Python process
boundary controls use uv.

`source-bindings.json` binds the four owned code files and historical runtime
blob at baseline8a8da06d. Old runtime43fa/source decision/capture assessment hashes
remain historical and unchanged; resolve that source with Git rather than asking
the changed current path to match its old hash. `implementation.diff` contains the
complete tracked/new-file delta. Other workers' files and frozen results were not
edited.

This runtime still does not score a task or qualify an oracle. Independent review
and a posthoc descriptor/raw-artifact/source/setup/tool/effective-context adapter
remain required. It records base container context, source config and chosen
command; it does not directly prove effective child Go settings. Full required
source closure, default task scope and prospective skip policy belong to posthoc
checks. The current actual source-origin scorer remains failclosed. No actual
qualification, campaign, native outcome or execution authorization is minted.
