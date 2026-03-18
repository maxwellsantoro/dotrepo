# v1.0 Go / No-Go Checklist

Use this as the release-decision sheet for `dotrepo 1.0.0`.

## Decision rule

Go when all of the following are true:

1. Hosted public output is the default documented public story.
2. Release-style install is clearly the normal path.
3. One live accepted maintainer claim exists in the live `index/`.
4. The shipped-surface docs can honestly stop calling dotrepo "not production-hardened."

No-go if any of those are still only true in proof artifacts, staged CI output,
or contributor-only workflows.

## 1. Hosted public output is the default public story

Pass when:

- primary docs and release notes describe the hosted/static surface as the
  normal public consumption path
- public examples point to hosted URLs first
- the Cloudflare deployment is described as downstream of the same exported
  tree and accepted public contract users are meant to rely on

Fail signs:

- core docs still describe the deployed public origin mainly as an adjacent
  proof artifact
- release notes emphasize downloadable artifacts more than the hosted surface
- reviewing the public tree still reads like an internal verification step

Related docs:

- [`docs/public-export-workflow.md`](./public-export-workflow.md)
- [`docs/public-surface.md`](./public-surface.md)
- [`docs/public-release-note.md`](./public-release-note.md)

## 2. Release-style install is clearly the normal path

Pass when:

- [`docs/install.md`](./install.md) and integration docs consistently prefer
  tagged release bundles and the `.vsix`
- source builds are framed as development-only
- CI smoke checks cover release-style CLI/LSP/MCP installation paths
- VS Code guidance defaults to installed binaries rather than workspace-local
  overrides

Fail signs:

- the happy path still requires cloning the repo and running `cargo build`
- VS Code docs still read primarily like contributor setup docs
- packaging is tested, but install/use is not

Related docs:

- [`docs/install.md`](./install.md)
- [`editors/vscode/README.md`](../editors/vscode/README.md)

## 3. One live accepted maintainer claim exists in the live index

Pass when:

- at least one repository in the checked-in `index/` has a live accepted
  maintainer claim
- that claim is exported through the normal public JSON path
- public summary and trust output visibly explain the claim context behind the
  selected record
- if the first example is a bootstrap maintainer-owned claim, `review.md` says
  so explicitly instead of implying independent review

Fail signs:

- the only successful claim path remains the staged CI/operator-gate artifact
- public claim-aware behavior is still demonstrated only on copied or fixture
  cases
- the repo cannot point to one live index entry that completed the full review
  flow

Related docs:

- [`docs/maintainer-claim-review-workflow.md`](./maintainer-claim-review-workflow.md)
- [`index/README.md`](../index/README.md)
- [`docs/current-status.md`](./current-status.md)

## 4. The "not production-hardened" framing can be removed honestly

Pass when:

- [`docs/current-status.md`](./current-status.md) and the main release-facing
  docs no longer need the "not production-hardened" hedge to describe the
  shipped `1.0.0` surface
- the release checklist, CI, docs, and hosted surface all describe the same
  normal release path
- the release decision can be defended without leaning on "proof-only" framing
  for the main product story

Fail signs:

- the product story is still split between a "real public surface" and a
  separate "proof surface"
- core docs still require caveats to explain what is truly shipped
- reviewers still have to infer the release bar from multiple partially aligned
  docs

Related docs:

- [`PLAN.md`](../PLAN.md)
- [`docs/current-status.md`](./current-status.md)
- [`docs/public-release-checklist.md`](./public-release-checklist.md)

## API versioning note

Do not couple the public API version to the repo release number.

For `dotrepo 1.0.0`, keeping public `apiVersion = "v0"` is the lower-risk path
unless there is an intentional breaking wire change. The public API version
tracks wire compatibility, not release branding.

Related docs:

- [`docs/public-api-compatibility.md`](./public-api-compatibility.md)
- [`rfcs/0016-public-index-site-and-query-api.md`](../rfcs/0016-public-index-site-and-query-api.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)

## Release sentence

Ship `dotrepo 1.0.0` when the hosted `v0` public surface is the default
documented product path, release-style installation is the normal tested path,
one live accepted maintainer claim exists in the live index, and the docs no
longer need proof-only or not-production-hardened caveats for the shipped
surface.
