# Agent guide

Quick orientation for AI agents working in this repo. **Do not duplicate normative prose here** — link to canonical docs ([docs/README.md](./docs/README.md)).

## What this is

`pagedigest` v1.0: a JSON manifest at `/.well-known/pagedigest.json` with monotonic `site_rev` / per-URL `rev` and optional `sha256` digests. One-line pitch: [README.md](./README.md).

| Question | Canonical doc |
|----------|----------------|
| Wire format & consumer algorithm | [SPEC.md](./SPEC.md) |
| Publisher/consumer obligations | [CONTRACT.md](./CONTRACT.md) |
| Digest churn & post-deploy reconcile | [CONTENT_HYGIENE.md](./CONTENT_HYGIENE.md) |
| Priorities & v1.0 path | [ROADMAP.md](./ROADMAP.md) |
| Release gates | [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) |

## Repo map

```
implementations/rust-generator/   # Publisher CLI (pagedigest-generator)
implementations/python-consumer/  # Consumer library (fetch, diff, audit, check_site)
packages/astro/                   # SSG integration (static HTML subset)
packages/cli/                     # npx launcher for release binaries
integrations/scrapy/              # Experimental Scrapy consumer (CI offline tests)
test-vectors/                     # Conformance fixtures; index in index.json
tools/                            # validate_vectors, smokes, reconcile, verify, hygiene
site/                             # Dogfood static site + emitted manifest
site-state/                       # Committed generator state for dogfood only
docs/                             # Ecosystem, templates, IANA drafts, archive
pagedigest.schema.json            # Validation aid; SPEC is normative boundary
```

## Before finishing any change

```bash
./tools/run_checks.sh
```

Requires [uv](https://docs.astral.sh/uv/) and Rust/Cargo. CI runs the same script (`.github/workflows/ci.yml`).

Focused runs:

```bash
uv run --project implementations/python-consumer --extra dev --locked python tools/validate_vectors.py
cd implementations/python-consumer && uv run --locked python -m unittest discover -s tests -v
cd implementations/rust-generator && cargo test --locked
```

## Implementation notes (easy to get wrong)

- **Revisions never decrease.** Rollback content still bumps `rev` / `site_rev` ([SPEC.md](./SPEC.md) §4.1).
- **URL keys** are byte-exact, pre-redirect, origin-relative (`/about` ≠ `/about/`).
- **Digests** are over identity-encoded **served** bytes, not necessarily on-disk build artifacts. Generator hashes files; live audits need [CONTENT_HYGIENE.md](./CONTENT_HYGIENE.md) reconcile pipeline.
- **Malformed manifests** → consumer fallback, not hard failure ([SPEC.md](./SPEC.md) §5.3).
- **Partial manifests:** omitted URLs are not implicitly unchanged unless `coverage.mode` is `complete`.
- **Schema ≠ full conformance.** Apply SPEC text in addition to `pagedigest.schema.json`.

When changing protocol behavior: update **SPEC** if normative, add/adjust **test-vectors**, extend **python-consumer** validation/diff tests (`tests/test_vectors.py`).

## Shipped vs planned

| Shipped in repo | Planned ([ROADMAP.md](./ROADMAP.md)) |
|-----------------|--------------------------------------|
| Rust generator (`cargo install pagedigest`, `npx pagedigest`, and release binaries) | |
| Python consumer (`pip install pagedigest`) | |
| Astro integration (`npm install @pagedigest/astro`) | Additional SSG plugins |
| Conformance vectors + CI | IANA short-form `rel` (extension URI works today) |

Publisher digests: generate → deploy → `tools/reconcile_served_digests.py --apply` → verify. Version matrix: [README.md](./README.md#version-matrix).

Do not document planned install paths as available without updating [README.md](./README.md) and [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md).

## Editing conventions

- **Stay focused.** Match existing style; no drive-by refactors.
- **Keep docs DRY.** README = front door; SPEC = normative; hygiene/ops = CONTENT_HYGIENE; gates = RELEASE_CHECKLIST; phases = ROADMAP. Link instead of copy.
- **Avoid new top-level markdown** unless necessary; prefer `docs/` for supplementary material.
- **Generator binary:** `pagedigest-generator`; the npm launcher command is `pagedigest`.

## Task → where to work

| Task | Start here |
|------|------------|
| Generator behavior / URL keys | `implementations/rust-generator/src/main.rs` |
| Consumer fetch/diff/audit | `implementations/python-consumer/pagedigest/core.py` |
| New manifest fixture | `test-vectors/` + `index.json` + `tools/validate_vectors.py` |
| Post-deploy digest tooling | `tools/reconcile_served_digests.py`, `tools/verify_over_wire_digests.py` |
| Dogfood site | `site/`, regenerate manifest via generator, `site-state/` |
| Producer case study | [docs/DOGFOOD_TEMPLATE.md](./docs/DOGFOOD_TEMPLATE.md) |

## License

MIT. Protocol spec is not a legal contract; [CONTRACT.md](./CONTRACT.md) is explanatory.
