"""One separately authorized offline npm setup observation; no task/test admission."""

import argparse
from datetime import datetime, timezone
import importlib
import hashlib
import json
from pathlib import Path
import stat
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
BASE = Path("/Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head")
PREP = BASE / "f05-go01-dependency-preparation-20261029"
HELPERS = {
    "prepare.py": "132cc30c00be4f8a7de80646ee8f87b3fff5d945c99a8f63df7a80780144538b",
    "process_io.py": "54fafcbeefb9c7516f65e4a1eae2959dd2934c9359b316ef2e0cf79fe0207ede",
    "boundaries.py": "7b03c7ab687043ab23061efde9d6328a21bb6ca94176085c87a50df8265de9e6",
}
IMAGE = "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
SOURCE = "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f"
REVISION = "25f823dc198a00744b458a7bc6984359f0dd7cac"
CACHE = "583fad501fa7b1a1a6d85ab8fe4b890786e39c1e016f785d6d3fb9d060383284"
COMMAND = "cd /workspace/repository; npm ci --offline --foreground-scripts"
LIMITS = {
    "workSeconds": 900,
    "cleanupSeconds": 60,
    "expandedCacheBytes": 1073741824,
    "archiveBytes": 536870912,
    "sourcePlusCacheBytes": 2147483648,
    "cpus": 3,
    "memoryBytes": 4294967296,
    "memorySwapBytes": 4294967296,
    "pids": 256,
    "workspaceBytes": 8589934592,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def load_helpers():
    global prior, scan_archive, DockerBackend
    for helper, digest in HELPERS.items():
        path = PREP / helper
        require(
            stat.S_ISREG(path.lstat().st_mode) and file_sha(path) == digest,
            "changed frozen helper before import: " + helper,
        )
    sys.path.insert(0, str(PREP))
    prior = importlib.import_module("prepare")
    scan_archive = importlib.import_module("boundaries").scan_archive
    DockerBackend = importlib.import_module("process_io").DockerBackend


def load_plan():
    load_helpers()
    plan = json.loads((HERE / "plan.json").read_text())
    prior.load_plan()
    require(
        plan["imageId"] == IMAGE
        and plan["sourceArchiveSha256"] == SOURCE
        and plan["cache"]["sha256"] == CACHE,
        "changed frozen identities",
    )
    require(plan["command"] == COMMAND and plan["limits"] == LIMITS, "changed command/bounds")
    require(all(type(v) is int for v in plan["limits"].values()), "bounds must be integers")
    require(
        plan["executionAuthorized"] is False and plan["cacheAdmissionSatisfied"] is False,
        "plan cannot mint acceptance",
    )
    for name, digest in plan["scripts"].items():
        require(file_sha(HERE / name) == digest, "changed script: " + name)
    for name, digest in plan["bindings"].items():
        require(file_sha(Path(name)) == digest, "changed retained binding: " + name)
    return plan


def authorize(plan, path, output, scratch):
    auth = json.loads(Path(path).read_text())
    require(
        auth.get("synthetic") is False
        and auth.get("state") == "coordinator-authorized-single-offline-npm-setup",
        "missing live authorization",
    )
    require(
        auth.get("planSha256") == file_sha(HERE / "plan.json")
        and auth.get("output") == str(output.resolve())
        and auth.get("scratch") == str(scratch.resolve()),
        "authorization binding mismatch",
    )
    require(
        auth.get("command") == COMMAND
        and auth.get("limits") == LIMITS
        and type(auth.get("maxAttempts")) is int
        and auth["maxAttempts"] == 1,
        "authorization bounds/command differ",
    )
    require(
        all(type(v) is int for v in auth["limits"].values()),
        "authorization bounds must be integers",
    )
    artifact = auth["cacheAcceptance"]
    acceptance_path = Path(artifact["path"])
    require(
        acceptance_path.is_absolute()
        and stat.S_ISREG(acceptance_path.lstat().st_mode)
        and file_sha(acceptance_path) == artifact["sha256"],
        "cache acceptance artifact mismatch",
    )
    acceptance = json.loads(acceptance_path.read_text())
    require(
        acceptance.get("synthetic") is False
        and acceptance.get("state") == "coordinator-accepted-go01-cache-for-offline-npm-setup",
        "cache not accepted",
    )
    require(
        acceptance.get("sourceArchiveSha256") == SOURCE
        and acceptance.get("imageId") == IMAGE
        and acceptance.get("cacheArchiveSha256") == CACHE
        and acceptance.get("cacheSpecSha256") == plan["cacheSpecSha256"],
        "cache acceptance identity mismatch",
    )
    disposition = acceptance.get("publishedTaskPayloadDisposition", {})
    require(
        disposition.get("state") == "allowed-only-for-offline-npm-setup-observation"
        and disposition.get("payloadsSha256") == plan["publishedTaskPayloadsSha256"]
        and disposition.get("nativeTaskAdmitted") is False
        and disposition.get("campaignAdmitted") is False,
        "missing explicit published task payload setup-only disposition",
    )
    audit = acceptance["auditFreeze"]
    audit_path = Path(audit["path"])
    require(
        audit_path.is_absolute()
        and stat.S_ISREG(audit_path.lstat().st_mode)
        and file_sha(audit_path) == audit["sha256"],
        "independent audit freeze mismatch",
    )
    return {
        "authorization": auth,
        "cacheAcceptanceSha256": artifact["sha256"],
        "auditFreeze": audit,
    }


def inputs(plan, check):
    source, source_files, source_bytes, deny = prior.preflight(prior.load_plan(), check)
    cache = Path(plan["cache"]["path"])
    require(
        stat.S_ISREG(cache.lstat().st_mode)
        and cache.stat().st_size == plan["cache"]["bytes"] <= 512 * 1048576,
        "cache transport shape/limit",
    )
    require(file_sha(cache) == CACHE, "cache hash mismatch")
    inventory = json.loads(Path(plan["cacheInventoryPath"]).read_text())
    cache_files, cache_bytes = scan_archive(
        cache, deadline=check, inventory=inventory["files"], roots=prior.ROOTS, deny=deny
    )
    require(
        cache_bytes == plan["cache"]["expandedBytes"] <= 1073741824
        and source_bytes + cache_bytes <= 2147483648,
        "cache/source expanded bounds",
    )
    return source, cache, source_files, cache_files


def flags(name, environment):
    result = prior.flags(name, environment)
    result[result.index("--network=bridge")] = "--network=none"
    return result


def inspect(row, environment):
    host = row["HostConfig"]
    require(
        row["Image"] == IMAGE
        and not row["Mounts"]
        and not host.get("Binds")
        and host["ReadonlyRootfs"] is True
        and host["Privileged"] is False,
        "image/mount/root isolation mismatch",
    )
    require(
        "CapAdd" in host
        and host["CapAdd"] in (None, [])
        and host["CapDrop"] == ["ALL"]
        and host["SecurityOpt"] == ["no-new-privileges"],
        "added capabilities or security override",
    )
    require(
        host["PidMode"] == ""
        and host["IpcMode"] == "private"
        and host["CgroupnsMode"] == "private"
        and host["UsernsMode"] == ""
        and host["UTSMode"] == ""
        and row["Config"]["User"] == "1000:1000"
        and host["Init"] is True,
        "namespace/user/init mismatch",
    )
    require(
        host["Devices"] == []
        and host["DeviceRequests"] is None
        and host["VolumesFrom"] is None
        and host["Links"] is None
        and host["PortBindings"] == {}
        and host["PublishAllPorts"] is False,
        "unexpected device/container attachment or port publication",
    )
    require(
        host["Memory"] == host["MemorySwap"] == 4294967296
        and host["NanoCpus"] == 3000000000
        and host["PidsLimit"] == 256,
        "resource mismatch",
    )
    require(
        host["NetworkMode"] == "none" and set(row["NetworkSettings"]["Networks"]) <= {"none"},
        "offline network mismatch",
    )
    for network in row["NetworkSettings"]["Networks"].values():
        require(
            not any(
                network.get(key)
                for key in ["IPAddress", "GlobalIPv6Address", "Gateway", "IPv6Gateway"]
            ),
            "unexpected network address",
        )
    for path, size in [
        ("/workspace", "size=8g"),
        ("/workspace/dependency-cache", "size=1g"),
        ("/tmp", "size=512m"),
    ]:
        options = host["Tmpfs"][path].split(",")
        require(
            all(value in options for value in ["exec", "nosuid", "nodev", size]),
            "tmpfs bounds/execution mismatch",
        )
    values = row["Config"]["Env"]
    require(
        len(values) == len(environment) and dict(v.split("=", 1) for v in values) == environment,
        "effective environment mismatch",
    )


def run(
    authorization,
    output,
    scratch,
    *,
    backend=None,
    plan_loader=load_plan,
    authorization_check=authorize,
    input_check=inputs,
    clock=time.monotonic,
):
    output, scratch = Path(output), Path(scratch)
    output.mkdir()
    start = clock()
    deadline = start + 900
    result = {
        "state": "incomplete",
        "stage": "plan-verification",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "synthetic": backend is not None,
        "taskId": "go-01",
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
        "modelCalls": 0,
        "costUsd": None,
        "costExclusions": ["No metered host/container setup dollar receipt."],
        "daemonCalls": 0,
        "containerCreateAttempted": False,
        "containerAbsent": None,
        "setupObserved": False,
        "campaignAdmitted": False,
        "cacheGloballyQualified": False,
    }
    write(output / "attempt.json", result)
    name = "dotrepo-go01-offline-setup-" + uuid.uuid4().hex[:12]
    result["ownedContainer"] = name
    preflight_start = None
    setup_start = None

    def check():
        require(clock() < deadline, "900-second work deadline exhausted")

    def call(label, argv, **kwargs):
        check()
        result["stage"] = label
        result["daemonCalls"] += 1
        receipt = backend.command(output, label, argv, deadline=deadline, **kwargs)
        require(
            receipt["exitCode"] == 0 and receipt["error"] is None,
            label + " failed: " + str(receipt.get("error")),
        )
        return receipt

    def shell(label, text):
        return call(label, ["docker", "exec", name, "/bin/sh", "-eu", "-c", text])

    try:
        plan = plan_loader()
        result["stage"] = "authorization"
        accepted = authorization_check(plan, authorization, output, scratch)
        backend = backend or DockerBackend()
        result.update(
            planSha256=file_sha(HERE / "plan.json"),
            authorizationSha256=file_sha(authorization),
            cacheAcceptance=accepted,
            imageId=IMAGE,
            sourceArchiveSha256=SOURCE,
            cacheArchiveSha256=CACHE,
        )
        scratch.mkdir()
        result["stage"] = "input-preflight"
        preflight_start = clock()
        source, cache, source_files, cache_files = input_check(plan, check)
        result["preflightSeconds"] = clock() - preflight_start
        source_manifest = scratch / "source.sha256"
        source_manifest.write_text(
            "".join(f"{v['sha256']}  ./{k}\n" for k, v in sorted(source_files.items()))
        )
        cache_manifest = scratch / "cache.sha256"
        cache_manifest.write_text(
            "".join(f"{v['sha256']}  ./{k}\n" for k, v in sorted(cache_files.items()))
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
            "image admission mismatch",
        )
        require(
            set(v.split("=", 1)[0] for v in image["Config"]["Env"])
            == {"PATH", "RUSTUP_HOME", "CARGO_HOME", "GOTOOLCHAIN", "GOENV"},
            "image environment mismatch",
        )
        environment = {
            **dict(v.split("=", 1) for v in image["Config"]["Env"]),
            **plan["environment"],
        }
        result["containerCreateAttempted"] = True
        call("create", flags(name, plan["environment"]))
        call("start", ["docker", "start", name])
        inspect(
            json.loads(call("container-inspect", ["docker", "inspect", name])["stdout"])[0],
            environment,
        )
        shell(
            "initialize",
            "mkdir -p /workspace/repository /workspace/dependency-cache /workspace/home /workspace/tmp",
        )
        for label, archive, target, digest in [
            ("source-provision", source, "/workspace/repository", SOURCE),
            ("cache-provision", cache, "/workspace/dependency-cache", CACHE),
        ]:
            sent = call(
                label,
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
                    target,
                ],
                stdin_path=archive,
            )
            require(sent["stdinSha256"] == digest, "provisioned archive hash mismatch")
        for label, manifest, target in [
            ("initial-source-check", source_manifest, "/workspace/repository"),
            ("initial-cache-check", cache_manifest, "/workspace/dependency-cache"),
        ]:
            call(
                label,
                [
                    "docker",
                    "exec",
                    "-i",
                    name,
                    "/bin/sh",
                    "-eu",
                    "-c",
                    "cd " + target + "; sha256sum --check --status -",
                ],
                stdin_path=manifest,
            )
        tools = shell("tools-before", plan["toolProbe"])["stdout"]
        require(tools.splitlines() == plan["expectedToolLines"], "tool versions mismatch")
        effective = json.loads(shell("npm-config", plan["npmConfigProbe"])["stdout"])
        require(
            effective["offline"] is True
            and effective["ignore-scripts"] is False
            and effective["cache"] == "/workspace/dependency-cache/npm-cache"
            and effective["registry"] == "https://registry.npmjs.org"
            and effective["userconfig"] == "/dev/null",
            "npm effective config mismatch",
        )
        setup_start = clock()
        npm_receipt = shell("npm-ci", COMMAND)
        log = npm_receipt["stdout"] + "\n" + npm_receipt.get("stderr", "")
        result["lifecycleLogMarkers"] = {
            marker: marker in log for marker in plan["expectedHookMarkers"]
        }
        require(all(result["lifecycleLogMarkers"].values()), "missing foreground hook observations")
        result["setupSeconds"] = clock() - setup_start
        metadata = shell("package-observations", plan["packageObservation"])["stdout"]
        observation = json.loads(metadata)
        require(
            observation["versions"] == plan["expectedPackageVersions"],
            "installed package version mismatch",
        )
        require(
            all(observation["files"][key] is not None for key in plan["requiredObservedFiles"]),
            "missing setup binary/bin-link observation",
        )
        for key in plan["requiredObservedFiles"]:
            row = observation["files"][key]
            require(
                row["contained"] is True
                and row["isFile"] is True
                and type(row["mode"]) is int
                and row["mode"] & 0o111,
                "invalid/nonexecutable/outside package binary observation",
            )
        write(output / "package-observations.json", observation)
        require(shell("tools-after", plan["toolProbe"])["stdout"] == tools, "tools changed")
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
            stdin_path=source_manifest,
        )
        inspect(
            json.loads(call("offline-final-inspect", ["docker", "inspect", name])["stdout"])[0],
            environment,
        )
        result.update(state="offline-npm-setup-observed", setupObserved=True)
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["workElapsedSeconds"] = clock() - start
        if setup_start is not None and "setupSeconds" not in result:
            result["setupSeconds"] = clock() - setup_start
        if preflight_start is not None and "preflightSeconds" not in result:
            result["preflightSeconds"] = clock() - preflight_start
        if result["containerCreateAttempted"]:
            cleanup_start = clock()
            try:
                cleanup_deadline = cleanup_start + 60
                rows = []
                for label, argv in [
                    ("cleanup", ["docker", "rm", "-f", name]),
                    ("post-cleanup-inspect", ["docker", "inspect", name]),
                    (
                        "post-cleanup-list",
                        [
                            "docker",
                            "ps",
                            "-a",
                            "--filter",
                            "name=" + name,
                            "--format",
                            "{{.Names}}",
                        ],
                    ),
                ]:
                    result["daemonCalls"] += 1
                    rows.append(backend.command(output, label, argv, deadline=cleanup_deadline))
                result["containerAbsent"] = (
                    rows[0]["exitCode"] == 0
                    and rows[0]["error"] is None
                    and rows[1]["exitCode"] != 0
                    and rows[1]["error"] is None
                    and rows[2]["exitCode"] == 0
                    and rows[2]["error"] is None
                    and rows[2]["stdout"].strip() == ""
                )
                result["cleanupExitCode"] = rows[0]["exitCode"]
                if not result["containerAbsent"]:
                    result["state"] = "incomplete-cleanup-or-absence-unresolved"
            except Exception as error:
                result.update(
                    state="incomplete-cleanup-or-absence-unresolved",
                    cleanupError=type(error).__name__ + ": " + str(error),
                )
            result["cleanupSeconds"] = clock() - cleanup_start
            if result["cleanupSeconds"] > 60:
                result["state"] = "incomplete-cleanup-budget-exceeded"
        try:
            write(
                output / "trace.json",
                {
                    "receipts": {
                        str(p.relative_to(output)): json.loads(p.read_text())
                        for p in sorted((output / "logs").glob("*/receipt.json"))
                    },
                    "synthetic": result["synthetic"],
                },
            )
        except Exception as error:
            result.update(
                state="incomplete-evidence-finalization",
                finalizationError=type(error).__name__ + ": " + str(error),
            )
        result["elapsedSeconds"] = clock() - start
        result["workElapsedSeconds"] = result["elapsedSeconds"] - result.get("cleanupSeconds", 0)
        result["workBudgetExceeded"] = result["workElapsedSeconds"] > 900
        if result["workBudgetExceeded"]:
            result["state"] = "incomplete-work-budget-exceeded"
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
        if not all([args.authorization, args.output, args.scratch]):
            parser.error("run needs authorization/output/scratch")
        outcome = run(args.authorization, args.output, args.scratch)
        raise SystemExit(0 if outcome["state"] == "offline-npm-setup-observed" else 1)
