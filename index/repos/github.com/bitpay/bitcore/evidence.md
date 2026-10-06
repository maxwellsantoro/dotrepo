# Evidence

- Imported repository name from README.md.
- Imported repo.build from package.json as `npm run build`.
- Imported repo.toolchain.min from package.json as `22` (Node.js).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 bounded command/documentation source inspection

Inspected retained upstream revision `ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4` for `repo.build`, `repo.test`, and `docs.root`. Source instructions were treated as data. No upstream commands, model calls, or external documentation-page execution occurred. This field inspection preserves the existing record timestamp `2026-09-16T16:21:24.075434Z`, status `verified`, and all unrelated facts. New assessments do not imply whole-record reinspection; the public timestamp-binding gate may withhold them until a coherent full recrawl.

- `repo.build`: present-supported-context-gap. Root package build invokes docker build -t bitcore-node .; Dockerfile copies the monorepo and runs npm ci, whose postinstall bootstraps and compiles packages. The wrapper exists, but current accepted scalar lacks Docker/toolchain context. Action: retain scalar wrapper; add exact root context and renewed value-bound assessment without changing record age.
- `repo.test`: correct-default-abstention-with-supported-component-candidate. No root generic test script exists. The root manifest and CI provide per-package test wrappers with Docker services and environment bindings. A package test must not become a whole-monorepo scalar. Action: preserve root scalar null; scoped test remains unassessed because required environment bindings are not represented by the current execution-context protocol.
- `docs.root`: wrong-unsupported-association. https://bitcore.io/ is the retained homepage, but the pinned root README does not declare it as documentation. The inspected component README declares repository-local API guides instead. No mutable external page was treated as semantic proof. Action: withhold docs.root; retain homepage unchanged; assess null only against actually inspected sources.

Retained source files used in the bounded inspection (URLs are pinned to the recorded revision; hashes cover raw bytes):

- [README.md](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/README.md) — SHA-256 `c04512fc30ed129e843769c7e71a71e237051a1af0e85cffa63dee62f6d0f9d7`.
- [CONTRIBUTING.md](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/CONTRIBUTING.md) — SHA-256 `515d36c812b23b128e01d5b8018ee7f9965335df7bd2e612381fce43a8dddd41`.
- [package.json](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/package.json) — SHA-256 `80d1afe86351e8986bea99b04dd920c6498ab54b75da6e243f35335dddba7a1a`.
- [Dockerfile](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/Dockerfile) — SHA-256 `a6bbc946107ed5ef80d6654e5da2c7ca19285259d4180a6c410a888bd50c3d8b`.
- [ci.sh](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/ci.sh) — SHA-256 `faaa7d1c24f1e253776f3de82bbdb203d0892638de54fbf779be7f582ed3027d`.
- [lerna.json](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/lerna.json) — SHA-256 `8bd63db9079fd5b3427eace3f6b8fd234b4dcd41c35c8638847d9a45678d241b`.
- [.circleci/config.yml](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/.circleci/config.yml) — SHA-256 `994ab4786633dd7a5f4c26ba812b106d5d11123a0363ccb24b6e7968bbe75cd1`.
- [packages/bitcore-node/README.md](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/packages/bitcore-node/README.md) — SHA-256 `5c8842b2ac5826e12e0960c464e9b9ffe0e348fa9cc2e67e10497bb7acf22ee2`.
- [docker-compose.test.base.yml](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/docker-compose.test.base.yml) — SHA-256 `5b6a6f8460d28ee3f6000e01de0e0032df3d1ea3c0839799654de32f1056b1a6`.
- [docker-compose.test.ci.yml](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/docker-compose.test.ci.yml) — SHA-256 `946484568b092fd5c966678b1775bfb6ff6f423a4e2a568aab903dabb0ddd53a`.
- [packages/bitcore-node/package.json](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/packages/bitcore-node/package.json) — SHA-256 `532fe4a8b94d08634055b8ac4cb2ce09a680a9a679cae56c53aa14bf202dbfa8`.
- [packages/bitcore-node/docs/api-documentation.md](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/packages/bitcore-node/docs/api-documentation.md) — SHA-256 `6e9f766d1e5f1e6e6bb81b84a3df252edc09a0314f6334183826b022d51e7881`.
- [packages/bitcore-node/docs/sockets-api.md](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/packages/bitcore-node/docs/sockets-api.md) — SHA-256 `0aa0a7ea6c7693c12fc224ae07ea079e3db7874523517ec5c84254542249c1f5`.
- [packages/bitcore-node/docs/wallet-guide.md](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/packages/bitcore-node/docs/wallet-guide.md) — SHA-256 `71112ee2edd5d2ea411ed312c946aed2087f9007c07fdd8010b8e6fa2ea8e6b3`.
- [.docker/rippled.Dockerfile](https://raw.githubusercontent.com/bitpay/bitcore/ea86af5f3e1049d0ee1469fd0cd1fa34c2a579c4/.docker/rippled.Dockerfile) — SHA-256 `c13f0bb69034e9e27505931f233a466ca16eb82e2d9bd5eb87d7e2cf44e14b68`.

All conventional missing-file probes and pinned tree listings are retained in the dated remainder audit source receipt. Not-found describes inspected source scope, not universal absence. Bitcore component tests remain unassessed because required external environment bindings are not fully represented. Candidate ordering and record status were not promoted.

This is an external overlay inspection, not a maintainer-controlled canonical record.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
