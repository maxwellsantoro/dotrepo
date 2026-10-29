# Go-01 npm hook assessment: source/data only

The three frozen install-script packages have real setup effects. Their presence
in cache supports candidate offline inputs; it does not establish equivalence
between normal npm ci and npm ci --ignore-scripts, or qualify the full task.
This packet authorizes no execution.

Before reading any hook body, identities.json declared these exact packages from
the retained lock and compressed cache bytes. Its SHA256 is
ad4aafcd5e1b8a4b6a31ebc758f4028c27154b8960bf138fff98975a5a4157bd.

| Package | Version | Compressed tarball SHA256 |
| --- | --- | --- |
| @vscode/vsce-sign | 2.1.0 | 406852a22ee49aabb8f3b9b1a6b47e25a5772207a2b64eca170ace59136c7929 |
| dprint | 0.57.4 | 557f7a8bee7e462f95b22677ca76eb2ff7f6ede8ad0043b48a063a785b24101c |
| esbuild | 0.28.2 | e045f94c235c7adc50e77ba2a579c7bec41b496b6b47c3a7845f7c1e19959a88 |

Each compressed byte sequence matches its lock SHA512 integrity. identities.json
also binds original source archive c583f283, npm lock 52b6c9bd, download cache
583fad50, preparation provenance and immutable download result freeze. No source
fetch occurred. All observations target the frozen Debian Bookworm Linux ARM64
container, Node v24.22.2 and npm 11.19.1, with the earlier environment allowlist.

## What normal setup would do

**vsce-sign** runs node ./src/postinstall.js. For Linux ARM64 and a non-Alpine
os-release, it selects @vscode/vsce-sign-linux-arm64 and copies bin/vsce-sign into
its own bin directory. If optional dependency resolution/copy fails, it attempts
a nested npm install and then direct registry download/extraction; that path
sets executable permissions. The runtime main resolves its own bin path, rather
than implementing a lazy setup fallback. Ignoring scripts omits the copy and
therefore changes available signing behavior. Other operating systems/architectures,
Alpine detection, npm_config_arch override and fallback failures are explicit
source branches, not observed behavior here.

**dprint** runs node ./install.cjs and install_api.cjs. For Linux ARM64 glibc,
it resolves @dprint/linux-arm64-glibc, links/copies its binary into dprint, adds
executable permissions and attempts to replace the .bin entry with the native
path. Copy failure can fall back to the optional-package path; .bin optimization
failure is swallowed. Missing optional binaries trigger registry download,
hash verification, write and chmod. Libc detection can read ldd, inspect a Node
process report, or execute ldd --version. With ignored installation hooks,
bin.cjs can call runInstall lazily before spawning dprint, so deferred mutations,
download attempts and failures remain possible. That source path is not an
observed equivalence result.

**esbuild** runs node install.js. Linux ARM64 little-endian selects
@esbuild/linux-arm64/bin/esbuild. It resolves the optional binary, may optimize
the CLI entry through hardlink/rename, and executes --version to require an exact
version match. Missing optional packages can cause nested npm install or direct
registry download with fallback-byte integrity checks. Manual binary override,
Windows, Yarn and WASM paths differ; no override is present in the frozen
allowlist. Ignored hooks omit eager setup/optimization/version validation. Its
retained CLI and API resolve optional binaries lazily, but those resolution,
execution and service paths were not run.

The exact platform packages for all three are present as integrity-addressed
compressed entries in the retained cache. optional-platform-cache.json records
lock platform predicates and cache inventory identities; optional-compressed-
integrity.json additionally verifies their raw SHA256 and lock SHA512. Native
binary bodies were not inspected or executed, nor was npm's optional dependency
installation/bin-link behavior observed. This is evidence of available compressed
inputs, not installed prerequisites.

## Consequence for the full default task

The previously frozen Herebyfile defines test as the test:tsc alias and executes
the gotestsum wrapper on ./... from tsc. It does not add formatter or extension
signing tasks. The retained root manifest has no install/prepare hook and declares
allowScripts entries for all three packages; neither that field nor hasInstallScript
proves execution. No direct esbuild/dprint/vsce import appears in the retained
Herebyfile import block. This bounded review did not exhaustively adjudicate all
transitively imported helpers/package loaders, so it does not prove the hooks
irrelevant to module loading or default-task prerequisites. Scope, wrapper,
resource bounds, proposed exclusions and original failures remain unchanged.

assessment.json therefore leaves equivalenceEstablished=false and
cacheAuditQualified=false. A future separately authorized qualification must
observe offline npm resolution/setup under the exact environment, account for
native esbuild --version and other hook effects if normal setup is selected,
and retain setup failures. Full module loading, native collection, dynamic skip
conditions, oracle policy acceptance and the complete wrapper task remain gates.
No new exclusion follows from this assessment.

## Inspection boundary and checks

read_members.py only reads named members into bounded text; it never extracts to
an executable tree or invokes package code. It checks declared compressed hashes,
regular/directory member types, safe unique paths, at most 10,000 members,
32 MiB compressed/expanded package data and 2 MiB per member. Fourteen requested
metadata/hook/runtime-closure files are retained with raw-text hashes; 22 exact
line spans bind the findings. Native optional package inspection was limited to
compressed integrity and existing lock/inventory metadata. No general source
expansion occurred. External built-in Node APIs and native binary behavior are
not independently established by this source review.

The read log and binding checks are in checks.json. All retained member hashes,
lengths and span excerpts checked; Ruff check/format passed with --no-cache.
Replay a specific read with uv run --offline --no-sync python read_members.py
<0|1|2> <fresh-output-name> package/<member>; output creation is exclusive.
All Python ran through uv. No network, Docker, package scripts, build, native
tests/collection, provider or model calls occurred. Unmetered local inspection
cost remains unknown/null. This is source/data assessment pending independent
review, not execution permission or setup admission.
