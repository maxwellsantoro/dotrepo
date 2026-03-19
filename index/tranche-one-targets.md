# Seed Index Tranche-One Target List

This doc turns Epic 7 from a backlog heading into an execution list.

It defines the first deliberate growth tranche for the checked-in overlay index:

- current checked-in seed index: 5 repositories
- tranche-one target: 50 reviewed overlay records
- language floor: visible coverage across Rust, TypeScript/JavaScript, Python,
  and Go
- standard: every merged record still has to satisfy
  [`index/review-checklist.md`](review-checklist.md)

These are planning targets, not pre-approved overlays. Each entry still needs a
reviewable `record.toml`, `evidence.md`, and index validation before merge.

## Selection rubric

Every tranche-one candidate was chosen using the same filters:

- agents encounter the repo often in real coding or ops tasks
- metadata is likely high-value because build, test, docs, ownership, security,
  or workspace shape are expensive to infer reliably
- the tranche stays visibly cross-language instead of drifting back into a
  Rust-only proof surface
- the first 10 records are chosen for high payoff without forcing the entire
  program to start on the largest monorepos first

## Already in the checked-in seed index

These repos are already present and are not part of the 50-target tranche:

- `github.com/BurntSushi/ripgrep`
- `github.com/cli/cli`
- `github.com/maxwellsantoro/ries-rs`
- `github.com/sharkdp/bat`
- `github.com/sharkdp/fd`

## Tranche-one target list

### Rust (12)

| Priority | Repo | Why now | Sources |
|---|---|---|---|
| 1 | [`tokio-rs/tokio`](https://github.com/tokio-rs/tokio) | Foundational async runtime; feature flags, workspace layout, and MSRV are high-value metadata. | [GitHub](https://github.com/tokio-rs/tokio) · [crates.io](https://crates.io/crates/tokio) |
| 2 | [`serde-rs/serde`](https://github.com/serde-rs/serde) | Serialization is everywhere; derive split and companion crates are easy to misread. | [GitHub](https://github.com/serde-rs/serde) · [crates.io](https://crates.io/crates/serde) |
| 3 | [`clap-rs/clap`](https://github.com/clap-rs/clap) | Common CLI foundation with feature and derive semantics that benefit from explicit metadata. | [GitHub](https://github.com/clap-rs/clap) · [crates.io](https://crates.io/crates/clap) |
| 4 | [`seanmonstar/reqwest`](https://github.com/seanmonstar/reqwest) | TLS backend and async or blocking mode are exactly the kind of details agents guess wrong. | [GitHub](https://github.com/seanmonstar/reqwest) · [crates.io](https://crates.io/crates/reqwest) |
| 5 | [`tokio-rs/axum`](https://github.com/tokio-rs/axum) | Common service framework with nontrivial example, release, and workspace shape. | [GitHub](https://github.com/tokio-rs/axum) · [crates.io](https://crates.io/crates/axum) |
| 6 | [`launchbadge/sqlx`](https://github.com/launchbadge/sqlx) | DB backend, compile-time checks, and TLS selection are painful to infer. | [GitHub](https://github.com/launchbadge/sqlx) · [crates.io](https://crates.io/crates/sqlx) |
| 7 | [`hyperium/hyper`](https://github.com/hyperium/hyper) | Core HTTP plumbing repo where version-sensitive usage and docs topology matter. | [GitHub](https://github.com/hyperium/hyper) · [crates.io](https://crates.io/crates/hyper) |
| 8 | [`tokio-rs/tracing`](https://github.com/tokio-rs/tracing) | Observability crate family with companion packages and instrumentation patterns. | [GitHub](https://github.com/tokio-rs/tracing) · [crates.io](https://crates.io/crates/tracing) |
| 9 | [`rustls/rustls`](https://github.com/rustls/rustls) | TLS provider choice and platform/security posture are high-signal metadata. | [GitHub](https://github.com/rustls/rustls) · [crates.io](https://crates.io/crates/rustls) |
| 10 | [`rust-lang/cargo`](https://github.com/rust-lang/cargo) | Build and test entrypoint for almost every Rust repo; contributor workflow is operationally important. | [GitHub](https://github.com/rust-lang/cargo) · [Cargo Book](https://doc.rust-lang.org/cargo/) |
| 11 | [`rust-lang/rust-analyzer`](https://github.com/rust-lang/rust-analyzer) | Dominant Rust language server with nontrivial workspace and build conventions. | [GitHub](https://github.com/rust-lang/rust-analyzer) · [Book](https://rust-analyzer.github.io/book/) |
| 12 | [`rust-lang/rustfmt`](https://github.com/rust-lang/rustfmt) | Formatting policy, nightly or stable behavior, and config semantics are useful metadata. | [GitHub](https://github.com/rust-lang/rustfmt) · [Book](https://rust-lang.github.io/rustfmt/) |

### TypeScript / JavaScript (13)

| Priority | Repo | Why now | Sources |
|---|---|---|---|
| 1 | [`microsoft/TypeScript`](https://github.com/microsoft/TypeScript) | Core compiler and language-service repo that agents see constantly. | [GitHub](https://github.com/microsoft/TypeScript) · [Docs](https://www.typescriptlang.org/docs/) |
| 2 | [`nodejs/node`](https://github.com/nodejs/node) | Ubiquitous runtime with complex build matrix and docs split. | [GitHub](https://github.com/nodejs/node) · [Docs](https://nodejs.org/en/docs) |
| 3 | [`npm/cli`](https://github.com/npm/cli) | Default package manager CLI with workspace and publish behavior worth surfacing explicitly. | [GitHub](https://github.com/npm/cli) · [Docs](https://docs.npmjs.com/cli/v11/) |
| 4 | [`vercel/next.js`](https://github.com/vercel/next.js) | Common framework repo with monorepo and canary or stable complexity. | [GitHub](https://github.com/vercel/next.js) · [Docs](https://nextjs.org/docs) |
| 5 | [`vitejs/vite`](https://github.com/vitejs/vite) | High-frequency tool where plugin and workspace semantics matter. | [GitHub](https://github.com/vitejs/vite) · [Docs](https://vite.dev/) |
| 6 | [`eslint/eslint`](https://github.com/eslint/eslint) | Canonical linting repo with rule, config, and Node support nuance. | [GitHub](https://github.com/eslint/eslint) · [Docs](https://eslint.org/) |
| 7 | [`microsoft/playwright`](https://github.com/microsoft/playwright) | Browser automation repo with heavy install, browser, and test-surface metadata. | [GitHub](https://github.com/microsoft/playwright) · [Docs](https://playwright.dev/) |
| 8 | [`pnpm/pnpm`](https://github.com/pnpm/pnpm) | Modern package manager with store and workspace semantics agents often misstate. | [GitHub](https://github.com/pnpm/pnpm) · [Docs](https://pnpm.io/) |
| 9 | [`facebook/react`](https://github.com/facebook/react) | Ubiquitous UI library repo with nontrivial package graph and release channels. | [GitHub](https://github.com/facebook/react) · [Docs](https://react.dev/) |
| 10 | [`vitest-dev/vitest`](https://github.com/vitest-dev/vitest) | Common test runner whose Vite and browser-mode coupling is useful metadata. | [GitHub](https://github.com/vitest-dev/vitest) · [Docs](https://vitest.dev/) |
| 11 | [`prettier/prettier`](https://github.com/prettier/prettier) | Formatter behavior, plugin support, and config resolution are high-value and under-documented in many repos. | [GitHub](https://github.com/prettier/prettier) · [Docs](https://prettier.io/) |
| 12 | [`storybookjs/storybook`](https://github.com/storybookjs/storybook) | Component-doc infra repo with heavy framework-matrix and addon complexity. | [GitHub](https://github.com/storybookjs/storybook) · [Docs](https://storybook.js.org/) |
| 13 | [`denoland/deno`](https://github.com/denoland/deno) | Alternative runtime with unusual build, release, and toolchain conventions that benefit from explicit metadata. | [GitHub](https://github.com/denoland/deno) · [Docs](https://docs.deno.com/) |

### Python (13)

| Priority | Repo | Why now | Sources |
|---|---|---|---|
| 1 | [`fastapi/fastapi`](https://github.com/fastapi/fastapi) | Common default for new APIs and agent-built backends. | [GitHub](https://github.com/fastapi/fastapi) · [Docs](https://fastapi.tiangolo.com/) |
| 2 | [`pydantic/pydantic`](https://github.com/pydantic/pydantic) | Core validation layer with v1/v2 behavior that agents need to handle correctly. | [GitHub](https://github.com/pydantic/pydantic) · [Docs](https://docs.pydantic.dev/) |
| 3 | [`django/django`](https://github.com/django/django) | Canonical full-stack web repo with settings, migrations, and app-structure complexity. | [GitHub](https://github.com/django/django) · [Docs](https://docs.djangoproject.com/) |
| 4 | [`psf/requests`](https://github.com/psf/requests) | Ubiquitous HTTP client where version and security posture matter. | [GitHub](https://github.com/psf/requests) · [Docs](https://requests.readthedocs.io/en/latest/) |
| 5 | [`astral-sh/uv`](https://github.com/astral-sh/uv) | New default packaging and project-management surface with workspace and install nuance. | [GitHub](https://github.com/astral-sh/uv) · [Docs](https://docs.astral.sh/uv/) |
| 6 | [`astral-sh/ruff`](https://github.com/astral-sh/ruff) | Fast-growing lint and format tool with config and rule-selection complexity. | [GitHub](https://github.com/astral-sh/ruff) · [Docs](https://docs.astral.sh/ruff/) |
| 7 | [`pytest-dev/pytest`](https://github.com/pytest-dev/pytest) | Test runner with plugin, marker, and invocation semantics that matter in real repos. | [GitHub](https://github.com/pytest-dev/pytest) · [Docs](https://docs.pytest.org/en/stable/) |
| 8 | [`numpy/numpy`](https://github.com/numpy/numpy) | Foundational scientific-computing repo with compiled-dependency and source-build complexity. | [GitHub](https://github.com/numpy/numpy) · [Docs](https://numpy.org/doc/) |
| 9 | [`pandas-dev/pandas`](https://github.com/pandas-dev/pandas) | Another core data repo where optional deps and source-install behavior are useful to surface. | [GitHub](https://github.com/pandas-dev/pandas) · [Docs](https://pandas.pydata.org/docs/) |
| 10 | [`sqlalchemy/sqlalchemy`](https://github.com/sqlalchemy/sqlalchemy) | ORM and SQL toolkit repo where dialect and compatibility details matter. | [GitHub](https://github.com/sqlalchemy/sqlalchemy) · [Docs](https://docs.sqlalchemy.org/20/) |
| 11 | [`psf/black`](https://github.com/psf/black) | Formatter defaults, notebook support, and stability policy are useful metadata. | [GitHub](https://github.com/psf/black) · [Docs](https://black.readthedocs.io/en/stable/) |
| 12 | [`scikit-learn/scikit-learn`](https://github.com/scikit-learn/scikit-learn) | Standard ML repo with heavy version and compiled-dependency constraints. | [GitHub](https://github.com/scikit-learn/scikit-learn) · [Docs](https://scikit-learn.org/stable/) |
| 13 | [`pallets/flask`](https://github.com/pallets/flask) | Still one of the most common Python web frameworks and a strong contrast to Django/FastAPI. | [GitHub](https://github.com/pallets/flask) · [Docs](https://flask.palletsprojects.com/) |

### Go (12)

| Priority | Repo | Why now | Sources |
|---|---|---|---|
| 1 | [`kubernetes/kubernetes`](https://github.com/kubernetes/kubernetes) | Default mega-repo for orchestration with sprawling build, test, and codegen surface. | [GitHub](https://github.com/kubernetes/kubernetes) · [Docs](https://kubernetes.io/docs/home/) |
| 2 | [`hashicorp/terraform`](https://github.com/hashicorp/terraform) | Canonical IaC repo and a frequent agent touchpoint in infra tasks. | [GitHub](https://github.com/hashicorp/terraform) · [Docs](https://developer.hashicorp.com/terraform/docs) |
| 3 | [`docker/cli`](https://github.com/docker/cli) | Common container-workflow CLI where install/build/test behavior matters. | [GitHub](https://github.com/docker/cli) · [Docs](https://docs.docker.com/reference/cli/docker/) |
| 4 | [`prometheus/prometheus`](https://github.com/prometheus/prometheus) | Ubiquitous monitoring server with split concerns across Go code, web assets, and release flow. | [GitHub](https://github.com/prometheus/prometheus) · [Docs](https://prometheus.io/docs/introduction/overview/) |
| 5 | [`helm/helm`](https://github.com/helm/helm) | Standard Kubernetes packaging CLI with plugin and release semantics worth surfacing. | [GitHub](https://github.com/helm/helm) · [Docs](https://helm.sh/docs/) |
| 6 | [`hashicorp/vault`](https://github.com/hashicorp/vault) | Security and secrets repo with operational modes that are hard to infer casually. | [GitHub](https://github.com/hashicorp/vault) · [Docs](https://developer.hashicorp.com/vault/docs) |
| 7 | [`caddyserver/caddy`](https://github.com/caddyserver/caddy) | Common proxy/web-server repo with deep module and config-model complexity. | [GitHub](https://github.com/caddyserver/caddy) · [Docs](https://caddyserver.com/docs/) |
| 8 | [`traefik/traefik`](https://github.com/traefik/traefik) | High-frequency ingress and container-infra repo with multiple deployment modes. | [GitHub](https://github.com/traefik/traefik) · [Docs](https://doc.traefik.io/traefik/) |
| 9 | [`grafana/loki`](https://github.com/grafana/loki) | Common observability repo with distributed components and non-obvious build/test boundaries. | [GitHub](https://github.com/grafana/loki) · [Docs](https://grafana.com/docs/loki/latest/) |
| 10 | [`hashicorp/consul`](https://github.com/hashicorp/consul) | Platform-infra repo with security, runtime, and deployment nuance. | [GitHub](https://github.com/hashicorp/consul) · [Docs](https://developer.hashicorp.com/consul/docs) |
| 11 | [`kubernetes/client-go`](https://github.com/kubernetes/client-go) | High-frequency client library repo with staging-mirror and auth/plugin complexity. | [GitHub](https://github.com/kubernetes/client-go) · [Docs](https://kubernetes.io/docs/reference/using-api/client-libraries/) |
| 12 | [`spf13/cobra`](https://github.com/spf13/cobra) | Core Go CLI framework with command-tree and contributor conventions worth surfacing. | [GitHub](https://github.com/spf13/cobra) · [Docs](https://cobra.dev/) |

## Suggested first 10 overlays

Start with the highest-payoff repos that are important, varied, and tractable
enough to build review momentum before the biggest monorepos dominate the queue.

1. `tokio-rs/tokio`
2. `fastapi/fastapi`
3. `microsoft/TypeScript`
4. `hashicorp/terraform`
5. `astral-sh/uv`
6. `vitejs/vite`
7. `pydantic/pydantic`
8. `serde-rs/serde`
9. `helm/helm`
10. `caddyserver/caddy`

This order is deliberate:

- it touches all four languages immediately
- it includes build/test/doc-heavy repos without starting on the absolute
  largest maintenance burdens like `kubernetes/kubernetes` or `nodejs/node`
- it gives the seed index both library and tool coverage early

## Execution guardrails

- Do not let one language dominate the merge queue for more than one short batch.
- Prefer 2 to 3 moderate-complexity wins before each giant monorepo.
- Every new overlay still needs reviewable build and test evidence, not just a
  popularity story.
- Use [`index/review-checklist.md`](review-checklist.md) for every contribution,
  even when the target repo is already on this list.
