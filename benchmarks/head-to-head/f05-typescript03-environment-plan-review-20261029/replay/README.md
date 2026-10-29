# Vue TypeScript03 source-only preparation plan

The task remains repository-default testing at vuejs/core revision
05db7e807be841e6f343d0237669669b18c89d4d. All five Vitest projects remain required:
unit, unit-gc, unit-jsdom, e2e and e2e-browser. Source declares a global development
Vue build before browser tests; the prospective full route retains that prerequisite
then unfiltered `pnpm test run`. No test-unit/e2e-only replacement or new skip is allowed.

The existing b47 LinuxARM64 image's Node24.22.2 is supported as a source-constraint
candidate: its exact executable hash is retained, and root constraints plus all91
observed lock engine-range forms permit it. This does not resolve mutable `lts/*`,
prove ABI/dependency/browser readiness, or show which Node a future pnpm launch uses.
The image inventory has npm/npx but no installed pnpm/corepack at the inspected
locations or pnpm package manifest. pnpm12.11.2 must be prepared explicitly.

The lock has TWO YAML documents. The first pins pnpm12.11.2 plus platform executable
packages with SRI; the second pins the workspace graph. tool-pins.json preserves15
specific tool/runner/browser package rows, engines, SRI and source line ranges.
The smallest next ready gate is exact archive-only pnpm/platform acquisition and
source/bin/option audit against those pins. No download or install occurred here.

preparation-contract.json separates candidate download-only tool/fetch commands from
normal offline installation and hooks. `--ignore-scripts` is only for download/tool
preparation, not claimed equivalent to normal setup. Root preinstall is
`npx only-allow pnpm`, with no retained lock/dependency pin for only-allow. Its actual
resolution remains unresolved: no latest fetch, guessed pin or silent bypass is
approved. Root postinstall simple-git-hooks and allowed native/Puppeteer hooks require
source/effect receipts; absent .git in the source archive is not silently repaired.

The workflow's e2e lane explicitly prepares Puppeteer and Playwright Chromium. Exact
browser build revisions, LinuxARM64 support, native libraries, cached executable
provenance and containment feasibility remain open. Unit-only skip-download settings
cannot supply full setup. Puppeteer's CI-dependent sandbox flags are source-bound;
the initial CI/launch policy must be frozen before any native attempt, not selected
after failure. Existing pnpm-store/browser cache roots are not admitted by the current
warm-cache policy, and no renamed/disguised cache projection is proposed.

The contract retains3CPU/4GiB/256PIDs,900seconds preparation,1GiB expanded downloads,
512MiB archive and current workspace/trace bounds. Receipts must account accepted
attempts, preflight/download/hooks/build/export/cleanup and unknown costs; failure or
cap overflow remains visible. No resource/version/platform change to obtain a pass.
Trusted native five-project collection/error/skip/phase reporting and post-run
source/tool/context capture remain separate oracle gates. No green baseline required.

All703 source members were hash-checked;18 selected config/lock/runner/build sources
are retained byte-exactly. Owned data-only parsing/range/reference checks and Ruff
pass. The initial owned Ruff diagnostic is retained. No upstream code was imported
or executed, and no Go/Node/daemon/install/network/provider action ran. Original
packets are unchanged. This is a plan for independent review, not a runnable or
qualified environment, cache, oracle or campaign; every actual admission flag is false.
