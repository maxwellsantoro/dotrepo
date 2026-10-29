# Go01 owned source-registry observation, 2026-10-29

The single authorized owned-helper attempt completed with an uncompiled source
registry. All 29 expected owned unit IDs (8 top-level tests and 21 children)
passed, the owned helper built, and its CLI exited 0. Only the three owned module
files were compiled. The target project's selected source bytes were JSON/base64
stdin data outside that module.

The bounded receiver accepts the retained 526,407-byte single gzip member,
expanding to 2,263,226 bytes with 104 packages and 6,031 source-derived declarations:
5,966 tests, 48 benchmarks, 6 fuzz targets, zero examples, and 11 TestMain
functions. No implemented source-discovery diagnostic triggered. The full output
is retained losslessly in `evidence/registry.gz`; the hash-bound corrected receiver
reconstructs it. `full-diagnostics.json` preserves all 104 package states, counts,
and diagnostics. Absence of diagnostics does not prove semantic completeness,
compile validity, runtime cases, TestMain behavior, or test success.

`partial-crosscheck.json` preserves the corrected comparator's complete result:
25 packages that previously reached native listing pass and 18 no-test diagnostic
packages match, with no differences. All 61 failed native-listing packages remain
source-only and unvalidated. These are listing observations, not passing tests.
The previous native compiler-killed observations and unknown cause remain intact;
this helper observation neither repairs nor replaces that failed attempt.

## Preservation and static verification

`origin-ledger.json` binds 84 exact copies (2,630,782 bytes): the complete closed
runtime directory, authorization closure, outer log, source/review bindings,
corrected receiver/comparator, and prior native-listing inputs. The original
runtime FREEZE binds 63 payload files (674,724 bytes); its own inclusion yields
64 files (684,341 bytes). No raw binary stream was decoded as text.

Full owned unit stdout, before/after owned module tar inventories, exact daemon
argv and stdout/stderr bytes are in `evidence/`. The original full target inventory
and 732 native JSON listing events are copied to `bindings/native/`, bound by the
unchanged native result FREEZE `f2588d3ee2bdee8c5b40d5f5a328d72dd07c0f093fd6e36904a9dcecec5256a2`.
The new verifier reconstructs every partial observation from that full stream.
The 21,446,036-byte JSON input is not duplicated in Git; the original local input,
its exact SHA, complete selected-file hashes and immutable helper subject remain
checked through the frozen runtime authorization closure.

Run only local Python data checks:

```sh
uv run python -B benchmarks/head-to-head/f05-go01-source-registry-result-20261029/verify.py
uv run python -B benchmarks/head-to-head/f05-go01-source-registry-result-20261029/controls.py
```

The verifier imports hash-bound pure runtime/receiver functions, checks the exact
source/review/authorization closure, all 18 daemon receipts and lossless streams,
owned-only provisioning, exact unit identities, image/environment/isolation,
output caps, before/after inventories, accounting, and cleanup. It does not invoke
a process, daemon, Go tool, provider, or network. Nine synthetic controls include
loss of an owned child case, CRC mutation with updated receipt hash, lost failed
package/diagnostic rows, unsafe inspect data, and fabricated qualification or
independent-absence claims. Initial verifier/control development failures are
preserved in `development-observations.json`; no historical evidence was edited.

## Limits

The same-attempt receipts show 18 daemon calls, 12.74485570890829 elapsed seconds,
0.21799820801243186 cleanup seconds, force-removal success, inspect absence, and
an empty responsive name list. There is no separate independent absence receipt.
The coordinator supplied the outer exit-0 outcome and exact outer stdout log;
no complete outer shell argv receipt was supplied. Monetary costs remain null;
source curation, image preparation, model, review and maintenance effort are not
allocated into a consumer cost comparison.

The helper used the audited Linux/arm64 image, CGO disabled, GOWORK off and empty
owned caches. The target CGO-enabled/workspace selection context remains input
data, not the helper compilation environment. This packet changes no task,
corpus, oracle, collection gate or global cache admission. Target compile validity,
complete native collection, task outcome and campaign admission remain false.
The author previously authored the runtime and earlier result packets; this is a
known-development operator observation, not a fresh holdout or consumer-benefit
measurement. Independent result review is a separate gate.
