# Third-party material in benchmarks

The repository's MIT [license](../LICENSE) covers dotrepo's own code and data. It does
**not** cover the upstream source excerpts kept under `benchmarks/` as frozen
benchmark evidence: copied files under `**/sources/github.com/<owner>/<repo>/`,
`**/repository-source/`, `**/npm-source/` and similar capture directories. Those
files remain the work of their authors under their upstream licenses, at the
commits recorded beside them (`_commit.json`, acquisition manifests). They are
included unmodified, as partial excerpts, only so that benchmark runs can be
inspected and replayed.

Licenses below are as reported by the GitHub API on 2026-11-04 for each
repository's default branch. The captured commit's license governs; check the
upstream repository before reusing any excerpt.

| Upstream repository | License |
| --- | --- |
| [`666ghj/MiroFish`](https://github.com/666ghj/MiroFish) | AGPL-3.0 |
| [`agalwood/Motrix`](https://github.com/agalwood/Motrix) | Other (GitHub reports no SPDX match; see upstream LICENSE) |
| [`beego/beego`](https://github.com/beego/beego) | Other (GitHub reports no SPDX match; see upstream LICENSE) |
| [`ComposioHQ/awesome-claude-skills`](https://github.com/ComposioHQ/awesome-claude-skills) | **No license published upstream** |
| [`deepseek-ai/deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness) | MIT |
| [`docker/compose`](https://github.com/docker/compose) | Apache-2.0 |
| [`docling-project/docling`](https://github.com/docling-project/docling) | MIT |
| [`Eugeny/tabby`](https://github.com/Eugeny/tabby) | MIT |
| [`golang/go`](https://github.com/golang/go) | BSD-3-Clause |
| [`golang/website`](https://github.com/golang/website) | BSD-3-Clause |
| [`GyulyVGC/sniffnet`](https://github.com/GyulyVGC/sniffnet) | Apache-2.0 |
| [`hashicorp/vault`](https://github.com/hashicorp/vault) | Business Source License 1.1 (GitHub: Other) |
| [`home-assistant/core`](https://github.com/home-assistant/core) | Apache-2.0 |
| [`iced-rs/iced`](https://github.com/iced-rs/iced) | MIT |
| [`infiniflow/ragflow`](https://github.com/infiniflow/ragflow) | Apache-2.0 |
| [`keras-team/keras`](https://github.com/keras-team/keras) | Apache-2.0 |
| [`microsoft/TypeScript`](https://github.com/microsoft/TypeScript) | Apache-2.0 |
| [`OpenHands/OpenHands`](https://github.com/OpenHands/OpenHands) | MIT |
| [`openinterpreter/openinterpreter`](https://github.com/openinterpreter/openinterpreter) | Apache-2.0 |
| [`pixijs/pixijs`](https://github.com/pixijs/pixijs) | MIT |
| [`RocketChat/Rocket.Chat`](https://github.com/RocketChat/Rocket.Chat) | Other (GitHub reports no SPDX match; see upstream LICENSE) |
| [`storytold/photocraft`](https://github.com/storytold/photocraft) | Apache-2.0 |
| [`tauri-apps/tauri`](https://github.com/tauri-apps/tauri) | Apache-2.0 |
| [`ultralytics/ultralytics`](https://github.com/ultralytics/ultralytics) | AGPL-3.0 |
| [`vuejs/core`](https://github.com/vuejs/core) | MIT |
| [`warpdotdev/warp`](https://github.com/warpdotdev/warp) | AGPL-3.0 |
| [`yangshun/tech-interview-handbook`](https://github.com/yangshun/tech-interview-handbook) | MIT |
| [`ytdl-org/youtube-dl`](https://github.com/ytdl-org/youtube-dl) | Unlicense |
| [`zellij-org/zellij`](https://github.com/zellij-org/zellij) | MIT |

npm package excerpts under `head-to-head/f05-go01-launch-closure-audit-20261029/npm-source/`:

| Package | Version | License (from its `package.json`) |
| --- | --- | --- |
| `esbuild` | 0.28.2 | MIT |
| `dprint` | 0.57.4 | MIT |
| `hereby` | 1.15.2 | MIT |
| `tinyexec` | 1.3.1 | MIT |
| `@vscode/vsce-sign` | 2.1.0 | Microsoft license ("SEE LICENSE IN LICENSE.txt"); `LICENSE.txt` was not captured |

Anonymized excerpts (for example `independent-scope-review/sources/python-01`)
come from the same upstream set; their task manifests record the repository.

## Open items

These need an owner decision, not a silent fix, because removing them changes
retained evidence:

- `ComposioHQ/awesome-claude-skills` publishes no license, so redistributing its
  README is not licensed. Remove it or obtain permission.
- `@vscode/vsce-sign` is distributed under Microsoft's own terms, and the
  captured files omit `LICENSE.txt`. Confirm that redistribution is permitted.
- AGPL-3.0 (`666ghj/MiroFish`, `ultralytics/ultralytics`, `warpdotdev/warp`) and
  BUSL-1.1 (`hashicorp/vault`) excerpts may be redistributed with their notices,
  but they are not MIT. This notice is that statement; do not copy them into code.
- Upstream `LICENSE` files were generally not captured alongside the excerpts.
