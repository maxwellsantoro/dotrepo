# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md.
- Imported repo.build from package.json as `npm run build`.
- Imported repo.test from composer.json as `composer run-script test`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `invoiceninja` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 pinned-source command/documentation correction

Inspected the retained upstream revision `f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc` for this six-case frozen risk-audit remainder. Prior import notes above are historical; the corrections below supersede their build/test/documentation-root associations. Record age, status, record-wide trust, and unrelated facts are retained. This source inspection did not execute upstream commands or measure task completion.

| Field | Disposition | Source-preserving decision |
| --- | --- | --- |
| `repo.build` | wrong | npm run build invokes Vite for resources assets; it is not a full Laravel application build. Preserve a resources component candidate, unassessed because locked dependency/toolchain preparation for this invocation is not declared. |
| `repo.test` | wrong | Composer test is a valid PHP wrapper, but the retained scalar omits the application/services setup and backend scope. Preserve an unassessed PHP application candidate; upstream CI needs environment/license/service bindings and a different sharded wrapper. |
| `docs.root` | wrong | CONTRIBUTING explicitly labels invoiceninja.github.io Documentation; the retained invoiceninja.com value is the product homepage. |

Execution contexts retain source entrypoints, scope, working directory and prerequisite descriptions. Candidates without a complete value-bound assessment remain unassessed; they are not usable answers merely because their source contains a command.

### Retained source receipts

Source bytes were fetched at the exact revision above, bounded to 2 MiB per response. The dated coordinator audit receipt retains HTTP statuses, body hashes, and bounded missing-path observations. Successful source reads for this record:

- [`README.md`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/README.md): HTTP 200, 8617 bytes, SHA-256 `fb1f30f7a0020cb8a64b7a6b5aee938d6da4e5258cbb9c54a56d0f63668ec8b0`.
- [`CONTRIBUTING.md`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/CONTRIBUTING.md): HTTP 200, 7729 bytes, SHA-256 `9ea40cec1c17f3b9bc1103157d3e4e62bc4014e7d3b23bef4841deff92c5fac6`.
- [`package.json`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/package.json): HTTP 200, 1881 bytes, SHA-256 `5fd36496922c458bb302b5344e8bc699c02f770f714c472b0fc9ae34445e52a1`.
- [`composer.json`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/composer.json): HTTP 200, 7625 bytes, SHA-256 `94df6653a921bc214fb474cb6c18489aaf94d9b53b7e3b321fe0e33c2d6ce00d`.
- [`phpunit.xml`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/phpunit.xml): HTTP 200, 1517 bytes, SHA-256 `7d4799ce024076ce0db5d4b4baf9e505f0429afa49019524b19bb68d56ff6ff3`.
- [`.env.ci`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/.env.ci): HTTP 200, 743 bytes, SHA-256 `95951d419a91e027cfca6d628d7e1312048bf87be712d9f4a5b8b9598e5506ae`.
- [`vite.config.ts`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/vite.config.ts): HTTP 200, 4235 bytes, SHA-256 `c8fc492da51e0e14db5bae6b783731237c54f17155d3cd144ff8d9975bda022a`.
- [`tests/e2e/README.md`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/tests/e2e/README.md): HTTP 200, 14749 bytes, SHA-256 `bd60703607dab41d0c829cc12ebf1cb912e674b36065c52fbd09ab53ae9c759f`.
- [`playwright.config.ts`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/playwright.config.ts): HTTP 200, 2764 bytes, SHA-256 `e747fca7fb100b98cfd03b773a700669cd71f1388c79be0b0c4c71ae5f43b58c`.
- [`.github/workflows/phpunit.yml`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/.github/workflows/phpunit.yml): HTTP 200, 4053 bytes, SHA-256 `6c7b8bf7e1bfbdb838f46f88862e9692b9dc8e9081cb9e2dfe1fe2b1adfff68b`.
- [`.github/workflows/react_release.yml`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/.github/workflows/react_release.yml): HTTP 200, 6809 bytes, SHA-256 `ac9e8d1243a006e18f353cd92e81f6bd89e9ca33eaa034f75a21efb0fa888a60`.
- [`config/database.php`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/config/database.php): HTTP 200, 8801 bytes, SHA-256 `d43aaeb799222b7f8ffacda06e130d4f2beb5200736c9dbabf6aa406855bf114`.
- [`tests/ci`](https://raw.githubusercontent.com/invoiceninja/invoiceninja/f1ffa5f9989afbed4e7dc80b5c0cc18944335ffc/tests/ci): HTTP 200, 1759 bytes, SHA-256 `10d73f994c1d5cbd386f3da8ec510acdf9fb1b9018680e473529b69aaf29f3d2`.

Field/object bindings were obtained from the actual Rust query serializer. Repository-scoped object values omit `component`; component candidates retain it. New or changed field assessments use the actual 2026-10-06 inspection timestamp. The retained record.generated_at and record status do not represent a whole-record refresh: timestamp-incoherent partial assessments are withheld by the public exporter until a complete reassessment.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
