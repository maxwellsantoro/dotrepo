"""Retain a source-only prerequisite/resource proposal; execute no upstream code.

Run once with uv. This is a proposal, not an execution freeze or authority to run
the displayed source commands. Full archives remain in the declared /tmp root.
"""

import hashlib
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
SCRATCH = Path("/tmp/dotrepo-f05-qualification-next8-20261029")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def retain(task, paths):
    provenance = json.loads((HERE / task / "provenance.json").read_text())
    details = json.loads((HERE / task / "file-details.json").read_text())["files"]
    result = []
    with tarfile.open(SCRATCH / task / "source.tar") as archive:
        for name in paths:
            member = archive.getmember(name)
            assert member.isfile()
            raw = archive.extractfile(member).read()
            assert sha(raw) == details[name]["sha256"]
            output = HERE / "prerequisite-sources" / task / name
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as stream:
                stream.write(raw)
            result.append(
                {
                    "path": name,
                    "sha256": sha(raw),
                    "bytes": len(raw),
                    "lines": len(raw.splitlines()),
                    "retained": str(output.relative_to(HERE)),
                    "url": f"https://{json.loads((HERE / task / 'acquisition.json').read_text())['task']['repository']}/blob/{provenance['revision']}/{name}",
                }
            )
    return result


def main():
    paths = {
        "rust-03": ["Cargo.toml", ".github/workflows/test.yml", "CONTRIBUTING.md"],
        "typescript-01": [
            "package.json",
            "docs/development.md",
            "vitest.config.ts",
            "scripts/parallelism.ts",
            "scripts/install-lefthook.mjs",
            "native/system/scripts/build.ts",
            "pnpm-workspace.yaml",
        ],
        "typescript-03": [
            "package.json",
            ".node-version",
            "vitest.config.ts",
            "scripts/build.js",
            "pnpm-workspace.yaml",
        ],
        "go-02": [
            "go.mod",
            ".github/workflows/test.yml",
            "client/cache/read_through_test.go",
            "client/cache/memcache/memcache_test.go",
            "client/cache/redis/redis_test.go",
            "client/cache/ssdb/ssdb_test.go",
        ],
    }
    sources = {task: retain(task, names) for task, names in paths.items()}
    summary = json.loads((HERE / "source-acquisition-summary.json").read_text())
    default = {
        "cpu": 3,
        "memoryBytes": 4 * 1024**3,
        "pids": 256,
        "workspaceBytes": 8 * 1024**3,
        "tmpBytes": 512 * 1024**2,
        "environment": {"TMPDIR": "/workspace/tmp"},
        "preparationSeconds": 900,
        "executionSeconds": 1800,
        "concurrentTasks": 1,
    }
    tasks = {
        "rust-01": {
            "scopeState": "aggregate Rust coverage requires coordinator adjudication",
            "preparation": "Full Rust workspace and JS CLI lanes must be mapped before choosing an aggregate union; root recursive JS test alone is insufficient for enrolled Rust scope.",
            "bounds": default,
            "gate": "Source-derived lane union, native coverage oracle and prerequisite/toolchain closure not frozen. Curator follow-up is not an independent review.",
        },
        "rust-03": {
            "scopeState": "repository CI Rust test target identified; no execution qualification",
            "sourceCommands": [
                "cargo test --verbose --workspace",
                "cargo test --verbose --workspace -- --ignored",
                "cargo test --verbose --workspace --all-features",
            ],
            "preparation": "Candidate official Rust1.99 ARM64 image already retained satisfies source minimum1.93, but does not reproduce the entire OS/toolchain CI matrix. Add pinned libxkbcommon-dev/libgtk-3-dev in source-free image; qualify display/headless needs. Download exact locked Cargo registry and pinned Git dependencies before offline test stages.",
            "environment": {
                "RUSTFLAGS": "--deny warnings",
                "ICED_TEST_BACKEND": "tiny-skia",
                "CARGO_BUILD_JOBS": "2",
            },
            "bounds": {**default, "preparationSeconds": 1200, "executionSeconds": 3600},
            "oracle": "Freeze native discovered test identities for each of three stages. Default-only/all-features-only is incomplete. The explicit ignored stage must not be rejected merely because the preceding default stage reports those same source-declared ignored cases; preserve per-stage exclusions and union. Listing, missing stages, unexpected skips, zero cases or compile/setup failure do not provide a complete suite outcome. Full terminal assertion failures can provide an outcome without a passing suite.",
            "gate": "Exact image plus apt/toolchain/cache descriptors and multi-stage oracle remain unqualified.",
        },
        "python-01": {
            "scopeState": "full root/backend union is a proposed alternative; original default remains unresolved",
            "preparation": "Backend source requires Python>=3.11,<3.13. Candidate exact Python3.12 plus uv image must be selected/pinned and root unittest/backend pytest dependency closure established. No credentials or model APIs may be required; preserve any unavailable setup as a blocker.",
            "bounds": default,
            "gate": "Coordinator must adjudicate full union coverage and manual source-only limitation separately from lack of an aggregate default; no new task or narrower replacement.",
        },
        "python-02": {
            "scopeState": "full root product suite proposed as primary-package superset, independent challenge pending",
            "preparation": "Source .python-version3.14.10 and minimum>=3.14.2 require an exact source-free Python/uv image. Freeze local pytest-home-assistant plugin plus full lock/dependency closure and collected test/skips. Full-suite dependency/service demands cannot be inferred from package location.",
            "bounds": {
                **default,
                "memoryBytes": 6 * 1024**3,
                "workspaceBytes": 12 * 1024**3,
                "preparationSeconds": 1800,
                "executionSeconds": 3600,
            },
            "gate": "Three retained links need faithful bounded SourceBundle support; exact dependencies, expected collection/exclusions and resource feasibility remain unknown.",
        },
        "python-03": {
            "scopeState": "full core plus download product suite proposed as primary-package superset",
            "preparation": "Select exact compatible Python and test runner from source constraints rather than assuming current Python3.14. Predeclare source-defined not-working/skipped test cases and SOCKS stand-in coverage exclusions. No credentials, public website crawling or unrestricted egress is authorized by this source-only packet.",
            "bounds": default,
            "gate": "Freeze expected exclusions before execution. Unexpected skip/early-return, exhausted network with green summary, core-only or one-download subset is noncompletion. Hardcoded SOCKS stand-ins are excluded coverage, not proof of actual proxy behavior. Full terminal assertion failure can still supply the requested outcome.",
        },
        "typescript-01": {
            "scopeState": "root default test identified; no execution qualification",
            "sourceCommands": ["pnpm install", "pnpm run typecheck", "pnpm test"],
            "preparation": "Node>=24.9 with type stripping, pnpm11.28.5, Git>=2.26, C compiler/Node headers; pin exact image/tools. Default test builds Linux ARM64 glibc host addon before complete Vitest suite. Root hook wrapper returns when archive lacks Git metadata (install-lefthook.mjs626-627); do not invent .git. Install scripts/native build still require isolated qualification. Include real PowerShell or freeze explicit source-defined omitted coverage; no API key for default unit tests may be invented.",
            "bounds": {
                **default,
                "memoryBytes": 12 * 1024**3,
                "workspaceBytes": 16 * 1024**3,
                "preparationSeconds": 1800,
                "executionSeconds": 1800,
            },
            "resourceRationale": "Source documents an 8GiB old-space upper ceiling per compiler, not a measured minimum RSS. Proposed12GiB is an unqualified conservative bound, exceeding current8GiB Docker VM; no VM/resource change is authorized. A later approved4/6GiB full-scope attempt could record actual feasibility/failure after source/interface/cache freeze. Serialize typecheck/build steps and use explicit2 Vitest workers without changing test inclusion.",
            "oracle": "Preserve all four default Vitest include groups. No filtered subset, CI coverage partition or snapshot refresh. Native-addon setup failure is noncompletion. Freeze skip IDs/conditions before run; retain expected environmental exclusions separately from tests actually exercised.",
            "gate": "Fourteen tracked links include actual fixtures. Faithful bounded link provisioning, exact dependency/native closure, PowerShell policy and larger memory allocation remain unresolved.",
        },
        "typescript-03": {
            "scopeState": "root default five-project Vitest target identified; no execution qualification",
            "sourceCommands": [
                "pnpm install",
                "node scripts/build.js vue -f global -d",
                "pnpm test run",
            ],
            "preparation": "Pin pnpm12.11.2 and an exact Node release consistent with source .node-version lts/* and engines>=20; mutable lts alias is insufficient. Freeze Playwright Chromium plus Puppeteer browser versions/system dependency closure; source-authorized Vue global development build supplies E2E artifacts before all default projects run. Qualify Chromium sandbox feasibility under no-new-privileges/dropcaps without silently using privileged/host flags.",
            "bounds": {
                **default,
                "memoryBytes": 6 * 1024**3,
                "workspaceBytes": 12 * 1024**3,
                "preparationSeconds": 1200,
            },
            "oracle": "Require unit, unit-gc, unit-jsdom, e2e and e2e-browser with native case accounting; preserve forked --expose-gc configuration and browser execution. test-unit, test-e2e alone, zero browser tests or missing built files is not complete default coverage.",
            "gate": "Exact Node alias resolution, native/browser image/cache closure and source-generated artifact prerequisites remain unqualified.",
        },
        "go-02": {
            "scopeState": "cache component includes root plus memcache/redis/ssdb packages; command not maintainer-declared complete tuple",
            "proposedDerivedCommand": "go test -json -count=1 ./client/cache/...",
            "preparation": "Pin Go1.24.2 (source go.mod and CI), locked module download and exact Redis/Memcached/SSDB versions. All three services must be reachable on container loopback6379/11211/8888 because root tests hardcode these ports. Root CI ORM MySQL/Postgres/etcd are not assumed necessary for this component. ARM64 SSDB availability and fixed service startup/health checks need actual qualification.",
            "bounds": default,
            "oracle": "Freeze go list/test discovery for all four cache packages; JSON terminal states must cover every native expected test. Reject skips at any depth using append-only oracle-revision/oracle.py. Memory-only subset, unavailable service, listing or setup error is noncompletion; complete native assertion failures can still supply an outcome.",
            "gate": "Source-free pinned service toolchains and fixed loopback startup without socket/mount/hostnetwork access remain unresolved. Derived scope command must not be promoted to established maintainer instruction.",
        },
    }
    for row in summary["tasks"]:
        task = row["task"]["id"]
        tasks[task]["task"] = row["task"]
        tasks[task]["archiveSha256"] = row["archiveSha256"]
        tasks[task]["sourceBundleReady"] = row["sourceBundleReady"]
        tasks[task]["sourceBindings"] = sources.get(task, [])
    write(
        HERE / "execution-proposal.json",
        {
            "identity": "f05-next8-source-only-execution-proposal-v1",
            "state": "proposal only; no upstream execution authorized or performed",
            "sourceFreezeSha256": "fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41",
            "tasks": tasks,
            "isolation": "Fresh ephemeral nonroot containers; no host mounts/socket/credentials; read-only root, cap-drop ALL, no-new-privileges, default private PID namespace, explicit exec,nosuid,nodev tmpfs. Workspace/tmpfs sizes are capacity ceilings, not available RAM promises: all resident tmpfs/page-cache/process memory remains charged to the same container/VM limits. TMPDIR moves scratch out of the512MiB partition without raising the memory cap. Source injected by bounded bytes; no fake Git checkout metadata. No oracle/gold/profile files in agent context. Public dependency download only during separately recorded preparation, network none during default execution; any task-specific egress requires a new reviewed policy.",
            "cachePolicy": "No cache built in this packet. Both arms must receive identical independently qualified immutable dependency archive/image conditions. No node_modules/build targets/task-source preinstallation disguised as cold cache. Every preparation receipt, source/tool/image/cache hash, time/bytes and exclusions frozen before sessions; mutable cross-session caches prohibited.",
            "accounting": {
                "modelCalls": 0,
                "upstreamProjectCodeExecuted": False,
                "indexConsulted": False,
                "costUsd": None,
                "costExclusions": [
                    "No host/container/download charge meter; numeric resource bounds are proposed caps, not measured cost or usage."
                ],
            },
            "oracleBoundary": "Complete intended task outcome can be pass or native assertion failure. Setup/collection failure, interruption, listing, missing scope or unadjudicated skipped coverage is noncompletion. Scope/default uncertainty is not instruction establishment and is not transformed into a correct abstention. Original gold and first-four results remain unchanged.",
            "launchRequirements": [
                "Coordinator scope/adjudication decisions plus fresh independent challenge",
                "Exact toolchain/source-free image digests and dependency/browser/service closure",
                "Faithful bounded source links where present",
                "Native collection/outcome oracle with positive/negative controls, explicit expected exclusions and no gold exposure",
                "Numeric resource approval and actual isolated per-task qualification",
                "Campaign model/settings/budgets/cache policy frozen independently; randomized72sessions remain unrun",
            ],
        },
    )


if __name__ == "__main__":
    main()
