# Captured-revision license and notice audit — November 4, 2026

This audit replaces default-branch guesses with exact captured revisions.
`inventory.json` records the retained source binding, pinned root listing,
Git blob identity, SHA-256 and size of each recovered notice. All 39 GitHub
license/notice files reproduce their pinned Git blob identities, including
TypeScript CRLF bytes. `npm/inventory.json` binds six exact package versions to
registry integrity and recovered licenses; downloads were inspected without
installation or package execution. One canonical Apache-2.0 text is also bound
to the captured Composio README's explicit declaration. The five original npm captures plus the
image's npm version used 3,075,056 archive bytes.

`captures.json` maps 52 tracked capture roots / 530 retained files to upstream
revisions or package/image provenance. Original captures are unchanged.
`go-image-bindings.json` additionally checks all ten retained Go image files
against the resolved Go 1.27.3 commit. The two image npm/npx files are short shell
wrappers, not byte-identical npm CLI sources; their image provenance remains
separate. Embedded excerpts in narrative/JSON are not independently inventoried.

The captured Composio README expressly declares Apache-2.0 (lines 495–499),
with individual-skill exceptions. The earlier missing-root-file classification
was wrong; its README hold is closed and canonical Apache text is now included.

The text inventory is a provenance result, not legal clearance. Per-directory,
per-file, third-party and package exceptions still apply. In particular, the old
default-branch table missed dual-license texts and the captured OpenInterpreter
Apache-2.0 notice. No frozen benchmark or negative result was rewritten.

| Upstream | Captured revision | Recovered root text / observation |
| --- | --- | --- |
| `666ghj/MiroFish` | [`7657031ac011`](https://github.com/666ghj/MiroFish/tree/7657031ac01184afe2cb220f5ee3545573b5e843) | [AGPL-3.0 text](666ghj/MiroFish/7657031ac01184afe2cb220f5ee3545573b5e843/LICENSE) |
| `ComposioHQ/awesome-claude-skills` | [`be2a406907db`](https://github.com/ComposioHQ/awesome-claude-skills/tree/be2a406907dbc61b73e6827ded415c96139d13a2) | [README declares Apache-2.0; canonical text added](inventory.json) |
| `Eugeny/tabby` | [`467ce8ebfa46`](https://github.com/Eugeny/tabby/tree/467ce8ebfa467fb88cf6d154c9a5891e3d3647f0) | [MIT text](Eugeny/tabby/467ce8ebfa467fb88cf6d154c9a5891e3d3647f0/LICENSE) |
| `GyulyVGC/sniffnet` | [`ab4bf739d464`](https://github.com/GyulyVGC/sniffnet/tree/ab4bf739d46448436cb68933bb8260ee264449d5) | [Apache-2.0 and MIT texts](GyulyVGC/sniffnet/ab4bf739d46448436cb68933bb8260ee264449d5/LICENSE-APACHE) |
| `OpenHands/OpenHands` | [`2875056f93d6`](https://github.com/OpenHands/OpenHands/tree/2875056f93d6eebcd887f64ae557258a7b0b0108) | [MIT text](OpenHands/OpenHands/2875056f93d6eebcd887f64ae557258a7b0b0108/LICENSE) |
| `RocketChat/Rocket.Chat` | [`7a174fd05604`](https://github.com/RocketChat/Rocket.Chat/tree/7a174fd05604dac39af95f76ea9db73db2b3ca5f) | [MIT with directory/third-party exceptions](RocketChat/Rocket.Chat/7a174fd05604dac39af95f76ea9db73db2b3ca5f/LICENSE) |
| `agalwood/Motrix` | [`6aae74432187`](https://github.com/agalwood/Motrix/tree/6aae74432187f689ffa0c8019f942ee2cb2cf91a) | [MIT text](agalwood/Motrix/6aae74432187f689ffa0c8019f942ee2cb2cf91a/LICENSE) |
| `beego/beego` | [`939cfde380bb`](https://github.com/beego/beego/tree/939cfde380bb9f15844ad633b84f037f7da21584) | [Apache-2.0 notice](beego/beego/939cfde380bb9f15844ad633b84f037f7da21584/LICENSE) |
| `deepseek-ai/deepseek-harness` | [`f3803c96974a`](https://github.com/deepseek-ai/deepseek-harness/tree/f3803c96974ad4a94195fb97e5c637e9c2a3afe3) | [MIT text](deepseek-ai/deepseek-harness/f3803c96974ad4a94195fb97e5c637e9c2a3afe3/LICENSE) |
| `docker/compose` | [`343bb382d219`](https://github.com/docker/compose/tree/343bb382d2192b88d84af49971bb5cb99bee268c) | [Apache-2.0 and NOTICE](docker/compose/343bb382d2192b88d84af49971bb5cb99bee268c/LICENSE) |
| `docling-project/docling` | [`9051777f9e42`](https://github.com/docling-project/docling/tree/9051777f9e420fa3a37df77425b08f22d0bf5981) | [MIT text](docling-project/docling/9051777f9e420fa3a37df77425b08f22d0bf5981/LICENSE) |
| `go-delve/delve` | [`62cd2d423c6a`](https://github.com/go-delve/delve/tree/62cd2d423c6a85991e49d6a70cc5cb3e97d6ceef) | [MIT text](go-delve/delve/62cd2d423c6a85991e49d6a70cc5cb3e97d6ceef/LICENSE) |
| `golang/go` | [`430d19f07a57`](https://github.com/golang/go/tree/430d19f07a57ee5ed4e3b1a04b0ab54dd5a24487) | [BSD-style text](golang/go/430d19f07a57ee5ed4e3b1a04b0ab54dd5a24487/LICENSE) |
| `golang/website` | [`b8d34bbe2d9e`](https://github.com/golang/website/tree/b8d34bbe2d9e230cc70ce3e4272dc651f494a188) | [BSD-style text](golang/website/b8d34bbe2d9e230cc70ce3e4272dc651f494a188/LICENSE) |
| `hashicorp/vault` | [`352089582444`](https://github.com/hashicorp/vault/tree/352089582444ea84feb03bc97eda97b35729e8ec) | [BUSL-1.1 with captured parameters; hold](hashicorp/vault/352089582444ea84feb03bc97eda97b35729e8ec/LICENSE) |
| `home-assistant/core` | [`cde3969919b9`](https://github.com/home-assistant/core/tree/cde3969919b9bd540b2dd75b7aa84a908acbdbfe) | [Apache-2.0 text](home-assistant/core/cde3969919b9bd540b2dd75b7aa84a908acbdbfe/LICENSE.md) |
| `iced-rs/iced` | [`cd04b74ca707`](https://github.com/iced-rs/iced/tree/cd04b74ca7073766f654535d6e72c452ef749d07) | [MIT text](iced-rs/iced/cd04b74ca7073766f654535d6e72c452ef749d07/LICENSE) |
| `infiniflow/ragflow` | [`9a71c10b090e`](https://github.com/infiniflow/ragflow/tree/9a71c10b090eaca9930df186dd0f9c15ee34a2ce) | [Apache-2.0 text](infiniflow/ragflow/9a71c10b090eaca9930df186dd0f9c15ee34a2ce/LICENSE) |
| `keras-team/keras` | [`7efab4a60f59`](https://github.com/keras-team/keras/tree/7efab4a60f5930fa81b0db15ed4ec6e4925e0c45) | [Apache-2.0 text](keras-team/keras/7efab4a60f5930fa81b0db15ed4ec6e4925e0c45/LICENSE) |
| `microsoft/TypeScript` | [`25f823dc198a`](https://github.com/microsoft/TypeScript/tree/25f823dc198a00744b458a7bc6984359f0dd7cac) | [Apache-2.0 and NOTICE](microsoft/TypeScript/25f823dc198a00744b458a7bc6984359f0dd7cac/LICENSE.txt) |
| `openinterpreter/openinterpreter` | [`ac1fcc8fe57a`](https://github.com/openinterpreter/openinterpreter/tree/ac1fcc8fe57aba51fcc3c79afd57a0883237fe87) | [Apache-2.0 and NOTICE](openinterpreter/openinterpreter/ac1fcc8fe57aba51fcc3c79afd57a0883237fe87/LICENSE) |
| `pixijs/pixijs` | [`2e8cacbe1ed4`](https://github.com/pixijs/pixijs/tree/2e8cacbe1ed4ed0fc31d5b59b9895c811ac0e003) | [MIT text](pixijs/pixijs/2e8cacbe1ed4ed0fc31d5b59b9895c811ac0e003/LICENSE) |
| `storytold/photocraft` | [`5f9b4391874a`](https://github.com/storytold/photocraft/tree/5f9b4391874aabc9deb2fcb905267613e4d93ec8) | [Apache-2.0, MIT and NOTICE](storytold/photocraft/5f9b4391874aabc9deb2fcb905267613e4d93ec8/LICENSE-APACHE) |
| `tauri-apps/tauri` | [`548a3692f594`](https://github.com/tauri-apps/tauri/tree/548a3692f59405aeb239c5b63fa589824eee51e8) | [Apache-2.0, MIT and SPDX texts](tauri-apps/tauri/548a3692f59405aeb239c5b63fa589824eee51e8/LICENSE-APACHE-2.0) |
| `ultralytics/ultralytics` | [`922563eab42b`](https://github.com/ultralytics/ultralytics/tree/922563eab42b778445e55a2edbabb6974eed8e4b) | [AGPL-3.0 text](ultralytics/ultralytics/922563eab42b778445e55a2edbabb6974eed8e4b/LICENSE) |
| `vuejs/core` | [`05db7e807be8`](https://github.com/vuejs/core/tree/05db7e807be841e6f343d0237669669b18c89d4d) | [MIT text](vuejs/core/05db7e807be841e6f343d0237669669b18c89d4d/LICENSE) |
| `warpdotdev/warp` | [`5a55a2aca773`](https://github.com/warpdotdev/warp/tree/5a55a2aca77339ad75637bed650352369ee7fcb9) | [AGPL-3.0 and MIT texts; file scope needs decision](warpdotdev/warp/5a55a2aca77339ad75637bed650352369ee7fcb9/LICENSE-AGPL) |
| `yangshun/tech-interview-handbook` | [`e1d28e8886c0`](https://github.com/yangshun/tech-interview-handbook/tree/e1d28e8886c0b6ff3e50da991ce0e895134ddc59) | [MIT text](yangshun/tech-interview-handbook/e1d28e8886c0b6ff3e50da991ce0e895134ddc59/LICENSE) |
| `ytdl-org/youtube-dl` | [`956b8c585591`](https://github.com/ytdl-org/youtube-dl/tree/956b8c585591b401a543e409accb163eeaaa1193) | [Unlicense text](ytdl-org/youtube-dl/956b8c585591b401a543e409accb163eeaaa1193/LICENSE) |
| `zellij-org/zellij` | [`1f3df933978e`](https://github.com/zellij-org/zellij/tree/1f3df933978e00c246553070310175c392fcfe4f) | [MIT text](zellij-org/zellij/1f3df933978e00c246553070310175c392fcfe4f/LICENSE.md) |
| `golang/go` | [`2aae1000ea1d`](https://github.com/golang/go/tree/2aae1000ea1d4b28923b96db28acf4e3b99d6aff) | [BSD-style text](golang/go/2aae1000ea1d4b28923b96db28acf4e3b99d6aff/LICENSE) |

## Disposition and replay

The owner authorized quarantine of all three held groups on November 4. The
108 exact source-capture files named in [quarantine.json](quarantine.json) are now
absent from this tree. Their original inventory, SHA-256 values and Git history
remain. The hash-verified preservation archive is held outside this repository
and all public build outputs; this is current-tree quarantine, not history erasure
or permission to redistribute historical/private copies.

The retained [disposition record](dispositions.json) keeps the original reasons:
VSCE-Sign's recovered Microsoft terms, AGPL/Warp file scope, and Vault's captured
BUSL parameters. These do not become MIT material. Composio's captured README
expressly declares Apache-2.0 and remains in place with canonical license text.

Affected frozen experiments require restoring the exact archive in a private
execution copy. Restore original relative paths only after checking the archive
SHA-256 and each recorded body hash. Never place the archive in a public bundle,
add it to Git, or silently substitute fixtures into a historical replay.

```sh
uv run python scripts/check_benchmark_licenses.py
# Before distributing a benchmark/source-evidence bundle:
uv run python scripts/check_benchmark_licenses.py --require-clearance
```

The normal check verifies retained source/notice bytes and requires quarantined
paths to remain absent. `--require-clearance` covers the inventoried current tree;
historical holds stay visible and are not legal clearance. The separate private
preservation check is:

```sh
uv run python scripts/check_benchmark_licenses.py --archive <private>/restricted-captures-preserved.tar.gz
```

It verifies the archive identity and every member without extracting files. The
archive is deliberately unavailable to public CI. Source/package releases remain
independent; this audit grants no additional rights.
