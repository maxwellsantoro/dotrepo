"""One Go01 download-only operator attempt. No live action without external authorization."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import stat
import time
import uuid

from boundaries import (
    EXPANDED_LIMIT,
    ROOTS,
    TRANSPORT_LIMIT,
    file_sha,
    normalize_archive,
    require,
    scan_archive,
    write,
)
from process_io import DockerBackend

HERE = Path(__file__).resolve().parent
IMAGE = "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
SOURCE = "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f"
REVISION = "25f823dc198a00744b458a7bc6984359f0dd7cac"
COMMANDS = [
    "cd /workspace/repository; npm ci --ignore-scripts",
    "cd /workspace/repository/tsc; go mod download",
    "cd /workspace/repository/tools; go mod download",
]
LIMITS = {
    "workSeconds": 900,
    "cleanupSeconds": 60,
    "expandedCacheBytes": EXPANDED_LIMIT,
    "archiveBytes": TRANSPORT_LIMIT,
    "sourcePlusCacheBytes": 2 * EXPANDED_LIMIT,
    "cpus": 3,
    "memoryBytes": 4 * EXPANDED_LIMIT,
    "memorySwapBytes": 4 * EXPANDED_LIMIT,
    "pids": 256,
    "workspaceBytes": 8 * EXPANDED_LIMIT,
}


def now():
    return datetime.now(timezone.utc).isoformat()


def load_plan():
    plan = json.loads((HERE / "plan.json").read_text())
    require(
        plan["imageId"] == IMAGE
        and plan["source"]["archiveSha256"] == SOURCE
        and plan["revision"] == REVISION,
        "changed source/image identity",
    )
    require(
        plan["commands"] == COMMANDS
        and plan["exportRoots"] == list(ROOTS)
        and plan["limits"] == LIMITS,
        "changed command/roots/bounds",
    )
    require(all(type(value) is int for value in plan["limits"].values()), "noninteger plan bounds")
    require(
        plan["executionAuthorized"] is False
        and all(v is False for v in plan["draftAuditFlags"].values()),
        "plan must not mint execution/audit acceptance",
    )
    for name, digest in plan["scripts"].items():
        require(file_sha(HERE / name) == digest, "changed script closure: " + name)
    for name, digest in plan["bindings"].items():
        require(file_sha(Path(name)) == digest, "changed retained binding: " + name)
    return plan


def authorize(plan, path, output, scratch):
    value = json.loads(Path(path).read_text())
    require(
        value.get("synthetic") is False, "synthetic/missing authorization is not live authorization"
    )
    require(
        value.get("state") == "coordinator-authorized-single-download-only-attempt",
        "missing explicit external authorization",
    )
    require(
        value.get("planSha256") == file_sha(HERE / "plan.json")
        and value.get("imageId") == IMAGE
        and value.get("sourceArchiveSha256") == SOURCE,
        "authorization binding mismatch",
    )
    require(
        value.get("output") == str(Path(output).resolve())
        and value.get("scratch") == str(Path(scratch).resolve()),
        "authorization must bind unique output/scratch identities",
    )
    require(
        value.get("limits") == LIMITS
        and value.get("commands") == COMMANDS
        and value.get("maxAttempts") == 1
        and type(value.get("maxAttempts")) is int,
        "authorization conditions differ",
    )
    require(
        all(type(value) is int for value in value["limits"].values()),
        "noninteger authorization bounds",
    )
    return value


def flags(name, env):
    args = [
        "docker",
        "create",
        "--name",
        name,
        "--pull=never",
        "--platform=linux/arm64",
        "--init",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--network=bridge",
        "--ipc=private",
        "--cgroupns=private",
        "--user=1000:1000",
        "--workdir=/workspace",
        "--memory=4g",
        "--memory-swap=4g",
        "--cpus=3",
        "--pids-limit=256",
        "--ulimit",
        "nofile=4096:4096",
    ]
    for mount in [
        "/workspace:rw,exec,nosuid,nodev,size=8g,uid=1000,gid=1000,mode=0700",
        "/tmp:rw,exec,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=0700",
        "/workspace/dependency-cache:rw,exec,nosuid,nodev,size=1g,uid=1000,gid=1000,mode=0700",
    ]:
        args.extend(["--tmpfs", mount])
    for name, value in sorted(env.items()):
        args.extend(["--env", f"{name}={value}"])
    return [*args, "--entrypoint=/bin/sh", IMAGE, "-c", "while :; do sleep 3600; done"]


def inspect(row, *, offline=False, environment=None):
    host = row["HostConfig"]
    require(
        row["Image"] == IMAGE and not row["Mounts"] and not host.get("Binds"),
        "image/mount mismatch",
    )
    require(
        host["ReadonlyRootfs"]
        and not host["Privileged"]
        and host["CapDrop"] == ["ALL"]
        and "no-new-privileges" in host["SecurityOpt"],
        "isolation mismatch",
    )
    require(
        host["PidMode"] != "host" and row["Config"]["User"] == "1000:1000",
        "namespace/user mismatch",
    )
    require(
        host["Memory"] == host["MemorySwap"] == 4 * EXPANDED_LIMIT
        and host["NanoCpus"] == 3 * 10**9
        and host["PidsLimit"] == 256,
        "resource mismatch",
    )
    require(
        all("exec" in host["Tmpfs"][p].split(",") for p in ["/workspace", "/tmp"]),
        "tmpfs execution mismatch",
    )
    require(
        "size=8g" in host["Tmpfs"]["/workspace"].split(",")
        and "size=1g" in host["Tmpfs"]["/workspace/dependency-cache"].split(","),
        "tmpfs quota mismatch",
    )
    require(
        not row["NetworkSettings"]["Networks"] if offline else host["NetworkMode"] == "bridge",
        "network mismatch",
    )
    if environment is not None:
        actual = dict(entry.split("=", 1) for entry in row["Config"]["Env"])
        require(
            len(actual) == len(row["Config"]["Env"]) and actual == environment,
            "container environment differs from allowlist",
        )


def preflight(plan, check):
    check()
    archive = Path(plan["source"]["archivePath"])
    require(
        stat.S_ISREG(archive.lstat().st_mode)
        and archive.stat().st_size == plan["source"]["archiveBytes"] <= TRANSPORT_LIMIT,
        "source transport shape/size mismatch",
    )
    require(file_sha(archive) == SOURCE, "source archive hash mismatch")
    inventory = json.loads(Path(plan["source"]["inventoryPath"]).read_text())
    require(inventory["revision"] == REVISION, "inventory revision mismatch")
    deny = set(json.loads((HERE / "protected-digests.json").read_text())["digests"])
    files, expanded = scan_archive(archive, deadline=check, inventory=inventory["files"], deny=deny)
    require(expanded == plan["source"]["expandedBytes"], "source expanded bytes mismatch")
    return archive, files, expanded, deny


def watched_download(command):
    # Trusted watcher, not repository code. The 1GiB cache tmpfs bounds physical
    # capacity; quarter-second du apparent-size samples also catch logical growth.
    return (
        command
        + ' & download_pid=$!; while kill -0 "$download_pid" 2>/dev/null; do size=$(du -sb /workspace/dependency-cache); size=${size%%[!0-9]*}; if [ "$size" -gt 1073741824 ]; then kill "$download_pid" 2>/dev/null || true; echo "cache-expanded-limit" >&2; exit 73; fi; sleep 0.25; done; wait "$download_pid"'
    )


def finalize_descriptor(output, scratch, plan, result):
    preparation = {
        "revision": REVISION,
        "imageDigest": IMAGE,
        "sourceArchiveSha256": SOURCE,
        "cacheArchiveSha256": result["cacheArchiveSha256"],
        "planSha256": file_sha(HERE / "plan.json"),
        "scriptSha256": file_sha(HERE / "prepare.py"),
        "scriptClosure": plan["scripts"],
        "traceSha256": file_sha(output / "trace.json"),
        "preparationCostUsd": None,
        "costExclusions": result["costExclusions"],
        **result["draftAuditFlags"],
        "state": "draft-unqualified; independent audit and explicit acceptance required",
        "synthetic": result["synthetic"],
    }
    write(output / "preparation.json", preparation)
    for name in ["inventory.json", "provenance.json", "preparation.json", "trace.json"]:
        shutil.copyfile(output / name, scratch / name)
    for name in plan["scripts"]:
        shutil.copyfile(HERE / name, scratch / name)
    spec = {
        "bundle": {
            "revision": REVISION,
            **{
                role: {"path": name, "sha256": file_sha(scratch / name)}
                for role, name in [
                    ("archive", "cache.tar"),
                    ("inventory", "inventory.json"),
                    ("provenance", "provenance.json"),
                ]
            },
        },
        **{
            role: {"path": name, "sha256": file_sha(scratch / name)}
            for role, name in [
                ("preparation", "preparation.json"),
                ("script", "prepare.py"),
                ("trace", "trace.json"),
            ]
        },
        "state": "draft-unqualified; not runtime admission",
    }
    write(output / "dependency-cache-spec.json", spec)
    shutil.copyfile(output / "dependency-cache-spec.json", scratch / "dependency-cache-spec.json")


def run(
    authorization,
    output,
    scratch,
    *,
    backend=None,
    plan_loader=load_plan,
    source_check=preflight,
    authorization_check=authorize,
    clock=time.monotonic,
):
    output, scratch = Path(output), Path(scratch)
    output.mkdir()
    start, deadline = clock(), clock() + 900
    result = {
        "taskId": "go-01",
        "state": "incomplete",
        "stage": "authorization",
        "synthetic": backend is not None and not isinstance(backend, DockerBackend),
        "startedAt": now(),
        "costUsd": None,
        "costExclusions": ["No metered host/container/download dollar receipt."],
        "cacheAuditQualified": False,
        "draftAuditFlags": {
            "downloadOnly": False,
            "buildOutputsExcluded": False,
            "taskSourceExcluded": False,
            "credentialsExcluded": False,
        },
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
        "modelCalls": 0,
        "daemonCalls": 0,
        "cleanupAttempted": False,
        "containerAbsent": None,
    }
    write(output / "attempt.json", result)
    backend, created, name = (
        backend or DockerBackend(),
        False,
        "dotrepo-go01-download-" + uuid.uuid4().hex[:12],
    )
    result["ownedContainer"] = name
    result["containerCreateAttempted"] = False
    preflight_start = None

    def check():
        require(clock() < deadline, "900-second work deadline exhausted")

    def call(label, argv, **kwargs):
        check()
        result["stage"] = label
        result["daemonCalls"] += 1
        receipt = backend.command(output, label, argv, deadline=deadline, **kwargs)
        require(
            receipt["exitCode"] == 0 and receipt["error"] is None,
            f"{label} failed: {receipt.get('error')}",
        )
        return receipt

    def shell(label, text):
        return call(label, ["docker", "exec", name, "/bin/sh", "-eu", "-c", text])

    try:
        result["stage"] = "plan-verification"
        plan = plan_loader()
        result["stage"] = "authorization"
        authorization_check(plan, authorization, output, scratch)
        result["authorizationSha256"] = file_sha(authorization)
        result["planSha256"], result["imageId"], result["sourceArchiveSha256"] = (
            file_sha(HERE / "plan.json"),
            IMAGE,
            SOURCE,
        )
        scratch.mkdir()
        result["stage"] = "source-preflight"
        preflight_start = clock()
        archive, source_files, source_bytes, deny = source_check(plan, check)
        result["preflightSeconds"] = clock() - start
        manifest = scratch / "source.sha256"
        manifest.write_text(
            "".join(
                f"{entry['sha256']}  ./{path}\n" for path, entry in sorted(source_files.items())
            )
        )
        image = json.loads(call("image-inspect", ["docker", "image", "inspect", IMAGE])["stdout"])[
            0
        ]
        require(
            image["Id"] == IMAGE
            and image["Os"] == "linux"
            and image["Architecture"] == "arm64"
            and not image["Config"].get("Volumes")
            and not image["Config"].get("OnBuild"),
            "image admission failed",
        )
        require(
            set(v.split("=", 1)[0] for v in image["Config"]["Env"])
            == {"PATH", "RUSTUP_HOME", "CARGO_HOME", "GOTOOLCHAIN", "GOENV"},
            "unexpected image environment",
        )
        environment = {
            **dict(entry.split("=", 1) for entry in image["Config"]["Env"]),
            **plan["environment"],
        }
        created = True
        result["containerCreateAttempted"] = True
        call("create", flags(name, plan["environment"]))
        call("start", ["docker", "start", name])
        inspect(
            json.loads(call("container-inspect", ["docker", "inspect", name])["stdout"])[0],
            environment=environment,
        )
        shell(
            "initialize",
            "mkdir -p /workspace/repository /workspace/home /workspace/tmp /workspace/dependency-cache",
        )
        sent = call(
            "source-provision",
            [
                "docker",
                "exec",
                "-i",
                name,
                "tar",
                "--extract",
                "--no-same-owner",
                "--no-same-permissions",
                "-C",
                "/workspace/repository",
            ],
            stdin_path=archive,
        )
        require(sent["stdinSha256"] == SOURCE, "actual provisioned source bytes differ")
        for stage in ["initial-source-check"]:
            call(
                stage,
                [
                    "docker",
                    "exec",
                    "-i",
                    name,
                    "/bin/sh",
                    "-eu",
                    "-c",
                    "cd /workspace/repository; sha256sum --check --status -",
                ],
                stdin_path=manifest,
            )
        probes = plan["toolProbe"]
        tools = shell("tools-before", probes)["stdout"]
        for exact in plan["expectedToolLines"]:
            require(exact in tools.splitlines(), "tool version mismatch: " + exact)
        before = shell(
            "network-before",
            "cat /sys/class/net/eth0/statistics/rx_bytes /sys/class/net/eth0/statistics/tx_bytes",
        )["stdout"]
        setup = clock()
        for number, command in enumerate(COMMANDS):
            shell(f"download-{number}", watched_download(command))
            size = shell(f"cache-size-{number}", "du -sb /workspace/dependency-cache")["stdout"]
            require(int(size.split()[0]) <= EXPANDED_LIMIT, "expanded cache limit")
        result["downloadSeconds"] = clock() - setup
        require(shell("tools-after", probes)["stdout"] == tools, "tools changed during downloads")
        after = shell(
            "network-after",
            "cat /sys/class/net/eth0/statistics/rx_bytes /sys/class/net/eth0/statistics/tx_bytes",
        )["stdout"]
        a, b = list(map(int, before.split())), list(map(int, after.split()))
        require(
            len(a) == len(b) == 2 and all(y >= x for x, y in zip(a, b, strict=True)),
            "invalid network counters",
        )
        result["networkBytes"] = {
            "received": b[0] - a[0],
            "sent": b[1] - a[1],
            "basis": "container interface counters; includes protocol/incidental traffic",
        }
        call("disconnect", ["docker", "network", "disconnect", "bridge", name])
        inspect(
            json.loads(call("offline-inspect", ["docker", "inspect", name])["stdout"])[0],
            offline=True,
            environment=environment,
        )
        call(
            "tracked-source-check",
            [
                "docker",
                "exec",
                "-i",
                name,
                "/bin/sh",
                "-eu",
                "-c",
                "cd /workspace/repository; sha256sum --check --status -",
            ],
            stdin_path=manifest,
        )
        raw, normalized = scratch / "download-roots.tar", scratch / "cache.tar"
        call(
            "cache-export",
            [
                "docker",
                "exec",
                name,
                "tar",
                "-C",
                "/workspace/dependency-cache",
                "-cf",
                "-",
                *ROOTS,
            ],
            binary_path=raw,
        )
        result["stage"] = "archive-validation"
        files, expanded = normalize_archive(
            raw, normalized, deadline=check, source_bytes=source_bytes, deny=deny
        )
        write(
            output / "inventory.json",
            {
                "revision": REVISION,
                "files": {name: entry["sha256"] for name, entry in files.items()},
                "members": files,
                "expandedBytes": expanded,
            },
        )
        provenance = {
            "revision": REVISION,
            "imageId": IMAGE,
            "sourceArchiveSha256": SOURCE,
            "planSha256": file_sha(HERE / "plan.json"),
            "archiveSha256": file_sha(normalized),
            "archiveBytes": normalized.stat().st_size,
            "exportRoots": list(ROOTS),
            "normalization": "Regular bytes preserved; uid/gid/mtime zero; mode644/755. No nonregular source silently dropped.",
            "protectedAliasChecks": "exact raw/canonical known artifacts; semantic/substring or compressed-package classification remains independent audit",
            "independentAuditPending": True,
        }
        write(output / "provenance.json", provenance)
        result.update(
            state="download-cache-retained-unqualified",
            cacheArchivePath=str(normalized),
            cacheArchiveSha256=file_sha(normalized),
            cacheExpandedBytes=expanded,
            cacheFiles=len(files),
        )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        result["workElapsedSeconds"] = clock() - start
        if preflight_start is not None and "preflightSeconds" not in result:
            result["preflightSeconds"] = clock() - preflight_start
        result["workBudgetExceeded"] = result["workElapsedSeconds"] > 900
        if created:
            result["cleanupAttempted"] = True
            cleanup_start = clock()
            cleanup_deadline = cleanup_start + 60
            try:
                result["daemonCalls"] += 1
                cleanup = backend.command(
                    output, "cleanup", ["docker", "rm", "-f", name], deadline=cleanup_deadline
                )
                result["cleanupExitCode"] = cleanup["exitCode"]
                result["daemonCalls"] += 1
                missing = backend.command(
                    output,
                    "post-cleanup-inspect",
                    ["docker", "inspect", name],
                    deadline=cleanup_deadline,
                )
                result["daemonCalls"] += 1
                listing = backend.command(
                    output,
                    "post-cleanup-list",
                    ["docker", "ps", "-a", "--filter", "name=" + name, "--format", "{{.Names}}"],
                    deadline=cleanup_deadline,
                )
                result["containerAbsent"] = (
                    cleanup["exitCode"] == 0
                    and cleanup["error"] is None
                    and missing["exitCode"] != 0
                    and missing["error"] is None
                    and listing["exitCode"] == 0
                    and listing["error"] is None
                    and listing["stdout"].strip() == ""
                )
                if not result["containerAbsent"]:
                    result["state"] = "incomplete-cleanup-or-absence-unresolved"
            except Exception as error:
                result["cleanupError"] = f"{type(error).__name__}: {error}"
                result["state"] = "incomplete-cleanup-or-absence-unresolved"
            result["cleanupSeconds"] = clock() - cleanup_start
            result["cleanupBudgetExceeded"] = result["cleanupSeconds"] > 60
            if result["cleanupBudgetExceeded"]:
                result["state"] = "incomplete-cleanup-budget-exceeded"
        if result["workBudgetExceeded"]:
            result["state"] = "incomplete-work-budget-exceeded"
        result["elapsedSeconds"] = clock() - start
        finalize_start = clock()
        try:
            trace = {
                "receipts": {
                    str(path.relative_to(output)): json.loads(path.read_text())
                    for path in sorted((output / "logs").glob("*/receipt.json"))
                },
                "synthetic": result["synthetic"],
            }
            write(output / "trace.json", trace)
            if result["state"] == "download-cache-retained-unqualified":
                finalize_descriptor(output, scratch, plan, result)
        except Exception as error:
            result["state"] = "incomplete-evidence-finalization"
            result["finalizationError"] = f"{type(error).__name__}: {error}"
        result["finalizationSeconds"] = clock() - finalize_start
        result["workElapsedSeconds"] += result["finalizationSeconds"]
        result["workBudgetExceeded"] = result["workElapsedSeconds"] > 900
        if result["workBudgetExceeded"]:
            result["state"] = "incomplete-work-budget-exceeded"
        result["elapsedSeconds"] = clock() - start
        write(output / "result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["verify", "run"])
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args()
    if args.mode == "verify":
        load_plan()
    else:
        parser.error("run requires --authorization, --output and --scratch") if not all(
            [args.authorization, args.output, args.scratch]
        ) else None
        outcome = run(args.authorization, args.output, args.scratch)
        raise SystemExit(0 if outcome["state"] == "download-cache-retained-unqualified" else 1)
