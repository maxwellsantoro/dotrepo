# Optional event capture — independent before-review

One concrete transport finding remains in the original frozen subject: after a
child closes both pipes but remains alive, the final wait throws TimeoutExpired,
drops the returned raw timeout receipt and leaves the child alive. The owned local
POSIX reproduction requested 0.05s and threw after 1.008s; the reviewer killed and
reaped that fixture. No Docker, upstream, network or provider action ran.

The wait pattern is inherited from the baseline, but the new optional capture path
relies on it for its deadline/cleanup guarantees. `review.json` gives the smallest
fix and successor controls. Root took production ownership for that narrow fix;
this packet freezes the original before finding and never blesses later bytes.
`reproduce_eof.py` is an owned local fixture only and supports fresh output paths
and an optional raw-byte prefix for successor retention checks.

Other static boundaries are recorded in `source-inspection.json`: optional/default
compatibility, no hidden command gate, same-call sequence, explicit source/tool
subset, bounded raw artifacts and unqualified posthoc status. This is not a complete
passed-review artifact. Independent successor controls/review remain required.
Current actual oracle, task and campaign admission stay open/false.
