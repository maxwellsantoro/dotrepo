"""Three-scope offline operator requalification; coordinator acceptance required.

No model/agent campaign or general execution service. Verification and synthetic
controls never start Docker or read upstream source bytes. Live execution is a
separate authorized operation, gated by immutable plan and cache-audit receipts.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import time
import uuid

from control import HERE, checked, command, sha, write
from oracle import go_outcome, vitest_outcome
from oracle_v5 import rust_default_outcome


def file_sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            value.update(raw)
    return value.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def safe_name(name):
    path = PurePosixPath(name)
    require(
        isinstance(name, str) and name and not path.is_absolute() and ".." not in path.parts,
        "unsafe archive path",
    )
    require(
        str(path) == name and all(ord(c) >= 32 and ord(c) != 127 for c in name),
        "unsafe archive path",
    )


def verify_plan():
    plan = json.loads((HERE / "plan.v5.json").read_text())
    for name, digest in plan["code"].items():
        require(file_sha(HERE / name) == digest, "changed driver/oracle/control")
    for row in plan["frozenMetadata"]:
        require(
            file_sha(Path(row["path"])) == row["sha256"], "changed source/cache/tool/scope metadata"
        )
    require(
        plan["imageId"]
        == "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092",
        "unexpected image",
    )
    require(set(plan["tasks"]) == {"rust-02", "typescript-02", "go-03"}, "changed cohort")
    return plan


def audit_binding(plan, task_id):
    task = plan["tasks"][task_id]
    return {
        "imageDigest": plan["imageId"],
        "revision": task["revision"],
        "sourceArchiveSha256": task["source"]["archive"]["sha256"],
        "cacheArchiveSha256": task["cache"]["archive"]["sha256"],
        "draftPreparationSha256": task["cache"]["draftPreparation"]["sha256"],
    }


def authorize(plan, acceptance, audit_receipts, plan_sha):
    """Validate supplied coordinator/audit assertions; do not claim authenticity.

    Acceptance is an external operator disposition after the human/coordinator
    authorizes the run. A local JSON file alone does not authenticate its author.
    """
    require(
        acceptance.get("state") == "accepted-for-three-scope-offline-requalification",
        "coordinator acceptance missing",
    )
    require(acceptance.get("planSha256") == plan_sha, "acceptance binds another plan")
    require(acceptance.get("imageId") == plan["imageId"], "acceptance binds another image")
    require(
        set(acceptance.get("cacheAudits", {})) == set(plan["tasks"]),
        "all three cache audits required",
    )
    for task_id in plan["tasks"]:
        artifact = acceptance["cacheAudits"][task_id]
        require(set(artifact) == {"path", "sha256"}, "invalid audit artifact binding")
        raw = audit_receipts[task_id]
        require(sha(raw) == artifact["sha256"], "changed audit receipt")
        receipt = json.loads(raw)
        require(receipt.get("state") == "qualified-download-cache", "cache audit unqualified")
        for key, expected in audit_binding(plan, task_id).items():
            require(receipt.get(key) == expected, "cache audit binding mismatch")
        for key in [
            "downloadOnly",
            "buildOutputsExcluded",
            "taskSourceExcluded",
            "credentialsExcluded",
            "protectedEvaluationAliasesExcluded",
        ]:
            require(receipt.get(key) is True, "cache audit remains unresolved")


def archive_input(spec, limit, prefixes=None, deadline=None):
    """Only called after coordinator acceptance; never execute host source bytes."""
    path = Path(spec["archive"]["path"])
    require(path.stat().st_size <= limit, f"archive exceeds byte limit: {path}")
    observed = file_sha(path)
    require(
        observed == spec["archive"]["sha256"],
        f"archive hash mismatch: {path}; expected={spec['archive']['sha256']}; observed={observed}",
    )
    inventory_path = Path(spec["inventory"]["path"])
    require(file_sha(inventory_path) == spec["inventory"]["sha256"], "inventory changed")
    inventory = json.loads(inventory_path.read_text())["files"]
    seen, total = set(), 0
    with tarfile.open(path, mode="r:") as archive:
        for member in archive:
            require(
                deadline is None or time.monotonic() < deadline,
                "task deadline exhausted during validation",
            )
            name = member.name.rstrip("/")
            safe_name(name)
            if member.isdir():
                continue
            require(
                member.isfile() and name not in seen, "source/cache nonregular or duplicate member"
            )
            require(member.size <= 128 * 1024**2 and len(seen) < 200000, "member boundary exceeded")
            require(member.mode & ~0o777 == 0, "unsafe member permissions")
            require(
                prefixes is None or any(name.startswith(prefix + "/") for prefix in prefixes),
                "cache outside frozen roots",
            )
            total += member.size
            require(total <= limit, "expanded byte limit exceeded")
            raw = archive.extractfile(member).read()
            require(inventory.get(name) == sha(raw), "member inventory mismatch")
            seen.add(name)
    require(seen == set(inventory), "archive inventory incomplete")
    return path, inventory, total


def container_flags(name, plan, env):
    argv = [
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
        "--network=none",
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
        "--tmpfs",
        "/workspace:rw,exec,nosuid,nodev,size=8g,uid=1000,gid=1000,mode=0700",
        "--tmpfs",
        "/tmp:rw,exec,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=0700",
    ]
    for key, value in sorted(env.items()):
        argv.extend(["--env", key + "=" + value])
    return argv + ["--entrypoint=/bin/sh", plan["imageId"], "-c", "while :; do sleep 3600; done"]


def score(task, native, listing, report):
    if task["kind"] == "go":
        result = go_outcome(listing, native["stdout"], task["packagePrefix"])
        result["qualified"] = (
            result["qualified"]
            and result.get("packages") == task["expectedPackages"]
            and result.get("expectedTopLevelTests") == task["expectedTopLevelTests"]
        )
        return result
    if task["kind"] == "rust":
        return rust_default_outcome(native, task["expectedTests"], task["rustDefaultPolicy"])
    return vitest_outcome(report, task["expectedTests"], task["suite"])


def run(plan, task_id, acceptance_path, output, metadata_verification=None):
    started = time.monotonic()
    deadline = started + 1800
    try:
        relative_output = output.resolve().relative_to(Path("/tmp").resolve())
    except ValueError as error:
        raise ValueError("output outside owned scratch prefix") from error
    require(
        relative_output.parts
        and relative_output.parts[0].startswith("dotrepo-f05-offline-requalification-"),
        "output outside owned scratch prefix",
    )
    require(not output.exists(), "output already exists")
    acceptance_raw = acceptance_path.read_bytes()
    acceptance = json.loads(acceptance_raw)
    receipts = {
        task_id: Path(row["path"]).read_bytes()
        for task_id, row in acceptance.get("cacheAudits", {}).items()
    }
    authorize(plan, acceptance, receipts, file_sha(HERE / "plan.v5.json"))
    task = plan["tasks"][task_id]
    output.mkdir(parents=True)
    acceptance_binding = {
        "acceptanceSha256": sha(acceptance_raw),
        "planSha256": file_sha(HERE / "plan.v5.json"),
        "auditHashes": {key: sha(raw) for key, raw in receipts.items()},
    }
    write(output / "acceptance-binding.json", acceptance_binding)
    name = "dotrepo-f05-offline-" + task_id + "-" + uuid.uuid4().hex[:10]
    result = {
        "taskId": task_id,
        "stage": "accepted-preflight",
        "state": "accepted-preflight",
        "preflightSeconds": None,
        "metadataVerification": metadata_verification
        or {
            "state": "direct API; separate metadata verification timing not supplied",
            "elapsedSeconds": None,
        },
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "imageId": plan["imageId"],
        "sourceRevision": task["revision"],
        "sourceArchiveSha256": task["source"]["archive"]["sha256"],
        "cacheArchiveSha256": task["cache"]["archive"]["sha256"],
        "containerCreateAttempted": False,
        "dockerCalls": 0,
        "taskOutcomeObserved": False,
        "testsPassed": None,
        "costUsd": None,
        "costExclusions": [
            "No metered host/container charge source; dependency preparation retained separately."
        ],
        "modelCalls": 0,
        "indexConsulted": False,
        "campaignExecuted": False,
    }
    write(output / "attempt.json", {**result, "acceptance": acceptance_binding})

    def execute(label, argv, *, data=b"", allow_failure=False):
        remaining = deadline - time.monotonic()
        require(remaining > 0, "1800-second task budget exhausted")
        result["stage"] = label
        result["dockerCalls"] += 1
        row = command(
            output,
            label,
            ["docker", "exec", *(["-i"] if data else []), name, *argv],
            data=data,
            timeout=remaining,
        )
        if not allow_failure:
            require(row["exitCode"] == 0 and row["error"] is None, label + " failed")
        return row

    def shell(label, text, **kwargs):
        return execute(
            label, ["/bin/sh", "-eu", "-c", "cd /workspace/repository; " + text], **kwargs
        )

    def check_files(label, inventory, prefix, allow_failure=False):
        for name in inventory:
            safe_name(name)
        data = "".join(
            digest + "  " + prefix + "/" + name + "\n" for name, digest in inventory.items()
        ).encode()
        return execute(
            label,
            ["sha256sum", "--check", "--quiet", "--strict", "-"],
            data=data,
            allow_failure=allow_failure,
        )

    def host_call(label, argv):
        remaining = deadline - time.monotonic()
        require(remaining > 0, "1800-second task budget exhausted")
        result["stage"] = label
        result["dockerCalls"] += 1
        if label == "create":
            result["containerCreateAttempted"] = True
        return checked(output, label, argv, timeout=remaining)

    try:
        result["stage"] = "accepted-source-preflight"
        source, source_inventory, source_bytes = archive_input(
            task["source"], 1024**3, deadline=deadline
        )
        result["stage"] = "accepted-cache-preflight"
        cache, cache_inventory, cache_bytes = archive_input(
            task["cache"], 512 * 1024**2, task["cacheRoots"], deadline=deadline
        )
        require(source_bytes + cache_bytes <= 2 * 1024**3, "source plus cache exceeds bound")
        result["preflightSeconds"] = time.monotonic() - started
        image_raw = host_call("image-inspect", ["docker", "image", "inspect", plan["imageId"]])
        image = json.loads(image_raw["stdout"])[0]
        require(
            image["Id"] == plan["imageId"]
            and image["Os"] == "linux"
            and image["Architecture"] == "arm64",
            "changed image/platform",
        )
        require(
            not image["Config"].get("Volumes") and not image["Config"].get("OnBuild"),
            "unsafe image configuration",
        )
        host_call("create", container_flags(name, plan, plan["environment"]))
        host_call("start", ["docker", "start", name])
        observed = host_call("container-inspect", ["docker", "inspect", name])
        row = json.loads(observed["stdout"])[0]
        host = row["HostConfig"]
        require(
            not row["Mounts"]
            and row["Image"] == plan["imageId"]
            and row["Config"]["User"] == "1000:1000",
            "container provisioning mismatch",
        )
        require(
            not row["NetworkSettings"]["Networks"]
            or set(row["NetworkSettings"]["Networks"]) == {"none"},
            "network unexpectedly available",
        )
        require(
            host["NetworkMode"] == "none"
            and not host["Privileged"]
            and host["ReadonlyRootfs"]
            and host["CapDrop"] == ["ALL"]
            and "no-new-privileges" in host["SecurityOpt"],
            "container isolation mismatch",
        )
        require(
            host["PidMode"] != "host"
            and host["Memory"] == host["MemorySwap"] == 4 * 1024**3
            and host["PidsLimit"] == 256
            and host["NanoCpus"] == 3 * 10**9,
            "container resource mismatch",
        )
        expected_env = dict(item.split("=", 1) for item in image["Config"]["Env"])
        expected_env.update(plan["environment"])
        require(
            dict(item.split("=", 1) for item in row["Config"]["Env"]) == expected_env,
            "unexpected container environment",
        )
        execute(
            "initialize",
            [
                "mkdir",
                "-p",
                "/workspace/repository",
                "/workspace/dependency-cache",
                "/workspace/home",
                "/workspace/tmp",
            ],
        )
        for label, archive, destination in [
            ("source-provision", source, "/workspace/repository"),
            ("cache-provision", cache, "/workspace/dependency-cache"),
        ]:
            execute(
                label,
                ["tar", "--extract", "--no-same-owner", "--no-same-permissions", "-C", destination],
                data=archive.read_bytes(),
            )
        check_files("initial-source-byte-check", source_inventory, "/workspace/repository")
        check_files("initial-cache-byte-check", cache_inventory, "/workspace/dependency-cache")
        shell("source-free-tool-byte-hashes", plan["toolHashCommand"])
        shell("tools-before-setup", task["toolProbe"])
        setup_start = time.monotonic()
        for number, text in enumerate(task["offlineSetup"]):
            shell("offline-setup-" + str(number), text)
        result["offlineSetupSeconds"] = time.monotonic() - setup_start
        shell("tools-after-setup", task["afterSetupProbe"])
        listing = (
            shell("native-list", task["listCommand"])["stdout"] if task.get("listCommand") else ""
        )
        native = shell("native-tests", task["testCommand"], allow_failure=True)
        result["testExitCode"], result["executionError"] = native["exitCode"], native["error"]
        report = {}
        if task["kind"] == "vitest":
            report = json.loads(
                execute("vitest-native-report", ["cat", "/workspace/vitest.json"])["stdout"]
            )
        result["oracle"] = score(task, native, listing, report)
        tracked = check_files(
            "tracked-source-after-tests",
            source_inventory,
            "/workspace/repository",
            allow_failure=True,
        )
        result["trackedSourceIntact"] = tracked["exitCode"] == 0 and tracked["error"] is None
        result["taskOutcomeObserved"] = result["oracle"]["qualified"] and native["error"] is None
        result["testsPassed"] = native["exitCode"] == 0 if result["taskOutcomeObserved"] else None
        result["state"] = (
            "offline-outcome-observed-pending-independent-review"
            if result["taskOutcomeObserved"] and result["trackedSourceIntact"]
            else "incomplete-or-protocol-deviation"
        )
    except Exception as error:
        result["failureStage"] = result["stage"]
        result["errorType"] = type(error).__name__
        result["error"] = str(error)
        result["state"] = (
            "failed-before-native-outcome"
            if not result["taskOutcomeObserved"]
            else "outcome-with-protocol-deviation"
        )
        raise
    finally:
        result["preflightSeconds"] = (
            result["preflightSeconds"]
            if result["preflightSeconds"] is not None
            else time.monotonic() - started
        )
        result["workElapsedSeconds"] = time.monotonic() - started
        result["cleanupAttempted"] = result["containerCreateAttempted"]
        result["cleanupExitCode"] = None
        cleanup_start = time.monotonic()
        if result["containerCreateAttempted"]:
            result["dockerCalls"] += 1
            try:
                cleanup = command(output, "cleanup", ["docker", "rm", "-f", name])
                result["cleanupExitCode"] = cleanup["exitCode"]
            except Exception as error:
                result["cleanupError"] = f"{type(error).__name__}: {error}"
            if result["cleanupExitCode"] != 0:
                result["state"] = "cleanup-unresolved"
        else:
            result["cleanupReason"] = "no container creation attempted; no daemon cleanup needed"
        result["cleanupSeconds"] = (
            time.monotonic() - cleanup_start if result["cleanupAttempted"] else 0.0
        )
        result["elapsedSeconds"] = time.monotonic() - started
        metadata_seconds = result["metadataVerification"].get("elapsedSeconds")
        result["totalMeasuredOperatorSeconds"] = (
            result["elapsedSeconds"] + metadata_seconds
            if type(metadata_seconds) in (int, float)
            else None
        )
        write(output / "result.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["verify", "run"])
    parser.add_argument("--task", choices=["rust-02", "typescript-02", "go-03"])
    parser.add_argument("--acceptance", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    metadata_started = time.monotonic()
    plan = verify_plan()
    metadata_verification = {
        "state": "passed",
        "elapsedSeconds": time.monotonic() - metadata_started,
        "outsideTaskDeadline": True,
        "planSha256": file_sha(HERE / "plan.v5.json"),
    }
    if args.mode == "verify":
        require(
            not any([args.task, args.acceptance, args.output]),
            "verify does not accept live arguments",
        )
        print(
            json.dumps(
                {
                    "state": "frozen-metadata-valid; live authorization and cache audits pending",
                    "tasks": sorted(plan["tasks"]),
                    "dockerCalls": 0,
                    "upstreamSourceArchiveBytesRead": False,
                    "metadataVerification": metadata_verification,
                }
            )
        )
    else:
        require(
            all([args.task, args.acceptance, args.output]),
            "live execution requires task, acceptance and unique output",
        )
        run(plan, args.task, args.acceptance, args.output, metadata_verification)


if __name__ == "__main__":
    main()
