# Go-01 single offline npm setup observation

The one separately authorized attempt completed as `offline-npm-setup-observed`.
The exact amended plan f1dc272c and driver06e3eb82 ran normal hook-enabled
`npm ci --offline --foreground-scripts` with no retry. All three frozen
postinstall hooks were observed and npm exited zero after adding168packages.
This is setup evidence only; taskOutcomeObserved, nativeCollectionOccurred,
cacheGloballyQualified and campaignAdmitted remain false.

The retained command output identifies:

- @vscode/vsce-sign2.1.0: node ./src/postinstall.js;
- dprint0.57.4: node ./install.cjs;
- esbuild0.28.2: node install.js.

The authorized setup included the known esbuild native --version hook and libc
probe behavior. The fixed observer read eight selected package versions and six
contained executable file/bin-link metadata/hash records; it did not invoke those
binaries. The vsce own-bin copy matches its optional binary hash; dprint and
esbuild .bin entries resolve to executable package binaries matching their platform
binary hashes. These observations resolve the bounded question of whether this
normal offline setup can run from the retained inputs. They do not establish
full task module loading, CLI semantics, source-compiled task outcome or correctness.

The exact source archive c583f283, unchanged cache archive583fad50 and common
LinuxARM64 imageb47cd4 were admitted. Source and cache stdin byte counts were
280,422,400 and366,622,720 respectively. Normal setup retained the lock-declared
published typescript7.0.2 alias and @typescript/typescript-linux-arm64@7.0.2;
both versions were observed as package metadata. They were explicitly accepted
only for this setup observation. No cache pruning/replacement occurred and original
unqualified download/cache falseflags remain unchanged. Native/campaign policy and
source-compiled evidence remain separate gates.

Preflight took3.885seconds, setup5.745seconds, total work19.505seconds and
cleanup0.538seconds (elapsed20.044seconds). Frozen bounds stayed900seconds plus
60cleanup, 3CPU/4GiB equal-swap/256PID/8GiBworkspace. Costs are unknown/null;
no measured network-byte zero, peak RSS, HTTP count or token savings is asserted.
No TypeScript compiler task, Go helper build/install, Hereby task, collection/tests,
provider or model action was invoked by the driver.

The container had network=none from creation, a readonly root, UID/GID1000,
private/default namespaces, no added capabilities, exact no-new-privileges,
no host mounts/socket/credentials and executable bounded tmpfs. Initial and final
inspect passed the amended policy. Source bytes and tool versions rechecked
unchanged. Driver cleanup removed the container; post-removal inspect and a
responsive exact-owned-name listing confirmed absence. No additional daemon action
occurred after the attempt. This was LinuxARM64 container execution on macOS,
not native Linux-host or x86 qualification.

The packet retains actual authorization and scoped cache disposition, 19 bounded
raw command receipts/stdout/stderr, inspect/config/tool observations, package
metadata and the result. checks.json records read-only verification of all raw
receipt hashes, input streams, plan/auth/disposition bindings and retained checks.
No archives are copied to Git; originals stay at their frozen /tmp paths.
Independent static result review remains separate. Earlier frozen inputs, helper
source, plans, reviews, caches and global admission flags were not modified.

The actual command was:

```
uv run --offline --no-sync python benchmarks/head-to-head/f05-go01-offline-setup-plan-20261029/amendment-1/setup.py run --authorization /tmp/dotrepo-go01-offline-setup-authorization-20261029-1.json --output /private/tmp/dotrepo-go01-offline-setup-evidence-20261029-1 --scratch /private/tmp/dotrepo-go01-offline-setup-scratch-20261029-1
```

This receipt records a completed attempt and does not authorize another run.
