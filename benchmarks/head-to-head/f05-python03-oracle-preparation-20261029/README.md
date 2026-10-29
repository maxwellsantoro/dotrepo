# Python-03 source scope and oracle preparation

This packet proposes that the maintained **full aggregate product suite** is
applicable to the frozen `youtube_dl` primary-package task at
`956b8c585591b401a543e409accb163eeaaa1193`. It keeps the selected package and task
unchanged. A separate component-only command is unnecessary: the maintainer
explicitly documents full test routes, the package manifest includes extractors,
downloaders and postprocessors, and the aggregate tests import these parts of the
product. This is source support for the intended suite, not proof that every
product behavior is covered or that an executable instruction is ready.

`scope-disposition.json` is a **prospective, unaccepted interpretation**. The
original frozen gold remains `unresolved`, and the original oracle remains a
source-grounded draft. Their byte bindings are in `input-bindings.json`; neither
is rewritten. The task still needs independent review and explicit acceptance
of this interpretation before any run. The author has prior F-05 context and has
read the original curator follow-up and challenger/root source decisions; this
is not a fresh blind independent gold review.

## Applicable routes and scope

The smallest documented full-suite candidate is the upstream command
`python -m unittest discover` from the repository root. The Makefile explicitly
uses `nosetests --verbose test`; `make test` additionally runs flake8. These are
source command strings, not commands run by this packet. A future contained
Python runner must respect the repository's uv tooling policy while preserving
upstream suite semantics. Exact interpreter/runner versions remain unfrozen.
CI's choice of PyNose for newer Python is useful source evidence, not a pinned
installation or compatibility result.

The full intended suite includes core **and** download/extractor/product tests.
It does not require every CI interpreter/platform matrix combination. A future
CI-partition alternative must independently reconcile the union to the frozen
full native manifest and obtain both partitions' outcomes. The download job's
`continue-on-error` is not a completion oracle. Downloader-only, the documented
single download-test file, default tox, offline targets, or one CI partition
cannot substitute for the selected primary-package scope.

## Source-defined limits and unresolved execution

`exclusion-proposal.json` identifies exactly three source-default SOCKS stand-in
methods and four optional-proxy-configuration methods. With unmodified source
and the committed defaults (no local parameter file and no proxy overrides),
they do not exercise the real proxy behavior. They may be prospectively accepted
as explicitly excluded behavior while retaining their actual terminal test
statuses. They are not observed proxy tests or general permission to ignore
skips. Enabling/configuring those behaviors instead needs its own prerequisite
and network freeze. The proposal is unaccepted; no observed outcome exists.

By contrast, `test_download.py:180-182` reports network exhaustion and returns;
unittest may report a pass although the required download test did not obtain
its outcome. This remains noncompletion. Unknown or unexpected skips/returns,
external-resource failures, missing phases and incomplete collection also remain
unresolved. `source-skip-candidates.json` records 20 syntactic sites, **not** a
case count, exhaustive runtime skip audit or approved allowlist. Extractor flags,
test-definition skip values, optional external downloader/FFmpeg availability,
SSL/Brotli and other platform conditions require exact pre-run assessment.
Source-defined broken-test skips exclude behavior; they never prove it passed.

The existing network-none Rust/Node/Go environment cannot establish the live
product/download default outcomes. A concrete Python environment, supported
runtime capabilities, valid HOME, writable fixtures/output space, dependency and
parameter state, network permissions/endpoints, resource limits and accounting
must be frozen separately. Build-only pandoc/zip requirements must not be
silently treated as prerequisites for the direct test route. No credentials,
proxy services, interpreter versions or resource numbers are invented here.

## Smallest defensible completion oracle

`oracle-requirements.json` specifies the needed bounded independent observer; it
is **not an executable runner or scorer**. Before a test attempt, separately
freeze a native full-suite collection manifest with source locations and dynamic
extractor/test identity mappings. Collection executes imports and has not
occurred here. The native case count is null. The empty state rejects readiness.

A future observer must reconcile full test lifecycles and suite completion,
classify test-body outcomes separately from setup/collection/infrastructure and
network failures, and attribute hidden early-return source sites to the active
test identity. It must retain exact accepted exclusions/skips separately from
exercised behavior. An actual complete failing suite can obtain a test outcome;
a green summary, listing, arbitrary skipped suite or unknown failure phase
cannot. Merely searching for a warning string is insufficient evidence of full
observation. Runner compatibility, source-site observation and meaningful
positive/negative runtime controls remain implementation gates. Hidden
oracle/scoring data must stay outside the eventual agent environment.

## Evidence and local checks

The already retained full archive is SHA256
`836cb208ff4ff481e5b9879fc3c10de793e7f8bca247e645661de1e233f63aa6`:
981 regular files, 6,945,071 expanded bytes, with all member hashes and the exact
path set matched to the frozen inventory. The acquisition receipt records no
missing LFS/submodules or links; this packet makes no fresh network provenance
claim. Selected source bytes, 18 exact hash/line excerpts, 32 test-directory Python
AST parses and input bindings are retained. AST parsing executes no upstream
imports or test bodies and supplies no native test count.

Recheck only trusted local source data (from the repository root):

```sh
uv run --offline --no-sync python benchmarks/head-to-head/f05-python03-oracle-preparation-20261029/verify_source.py
uv run --offline --no-sync ruff check --no-cache benchmarks/head-to-head/f05-python03-oracle-preparation-20261029/prepare_disposition.py benchmarks/head-to-head/f05-python03-oracle-preparation-20261029/verify_source.py
uv run --offline --no-sync ruff format --check --no-cache benchmarks/head-to-head/f05-python03-oracle-preparation-20261029/prepare_disposition.py benchmarks/head-to-head/f05-python03-oracle-preparation-20261029/verify_source.py
```

`source-controls.json` retains the initial check and six rejected source/readiness
counterexamples: changed source, changed excerpt, shifted span, invented case,
missing proxy configuration and empty native manifest. These are source controls,
not native oracle qualification. `prepare_disposition.py` created excerpts and
input bindings using exclusive outputs; do not rerun it over this frozen packet.
All other JSON dispositions are authored source assessments, not measured results.

No source acquisition, package installation, upstream Python execution,
container/daemon action, native collection, provider/model call or evaluated
index/profile lookup occurred. There is no setup, task, cache, campaign or
consumer-benefit admission and no authorization for subsequent execution.
