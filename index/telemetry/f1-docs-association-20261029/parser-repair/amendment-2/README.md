# Bare URL ownership amendment

Independent review of amendment 1 reproduced a remaining owner bypass under a
documentation heading: a physical bare-URL line could ignore trailing prose
qualifying it as another project's integration. The review's after/FREEZE.json
retains the actual failing CLI observation and exact prior source.

The coordinator narrowed that branch to compare the whole rendered paragraph
(after one list marker) with the bare destination. Navigation, explicit docs
declarations and their cached paragraph decisions retain their own branches.
The new unit control rejects trailing, wrapped-list and preceding third-party
subjects, while preserving standalone, list and explicit-own-intro bare URLs.

Documentation tests, both unchanged fixture gates, formatting and CLI build
passed. A stable CLI copy is bound for independent review. This is a regression
repair of bounded lexical association logic, not general semantic ownership or
target validation. Full integrated gates and independent after-review follow
separately. No upstream/native command, Docker, network or model call occurred.
All earlier freezes remain unchanged.
