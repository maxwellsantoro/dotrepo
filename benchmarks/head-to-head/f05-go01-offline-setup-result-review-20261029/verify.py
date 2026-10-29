"""Verify retained offline setup evidence and package payloads; never execute it."""

import base64
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import posixpath
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = ROOT / "benchmarks/head-to-head/f05-go01-offline-setup-result-20261029"
PLAN = ROOT / "benchmarks/head-to-head/f05-go01-offline-setup-plan-20261029/amendment-1"
DOWNLOAD = ROOT / "benchmarks/head-to-head/f05-go01-dependency-download-result-20261029"
CACHE_REVIEW = ROOT / "benchmarks/head-to-head/f05-go01-dependency-download-review-20261029"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def verify_freeze(path):
    frozen = load(path)
    if "artifactSha256" in frozen:
        files = frozen["artifactSha256"]
    else:
        files = {entry["path"]: entry["sha256"] for entry in frozen["files"]}
    for name, expected in files.items():
        assert digest(path.parent / name) == expected, (path, name)
    return len(files)


def main():
    assert (
        digest(PACKET / "freeze.json")
        == "de606b246aaa19ec93a8cc90123e10a8ef08bfe68c12881f6fd2f400a0891a61"
    )
    artifacts = verify_freeze(PACKET / "freeze.json")
    plan = load(PLAN / "plan.json")
    result = load(PACKET / "evidence/result.json")
    auth = load(PACKET / "authorization.json")
    acceptance = load(PACKET / "cache-disposition.json")
    observation = load(PACKET / "evidence/package-observations.json")
    parent_bindings = []
    for entry in load(PACKET / "input-bindings.json").values():
        path = Path(entry["path"])
        assert digest(path) == entry["sha256"]
        parent_bindings.append(entry)
    for name, expected in plan["bindings"].items():
        assert digest(Path(name)) == expected
    for name, expected in plan["scripts"].items():
        assert digest(PLAN / name) == expected
    assert digest(PLAN / "plan.json") == result["planSha256"] == auth["planSha256"]
    assert digest(PACKET / "authorization.json") == result["authorizationSha256"]
    assert auth["maxAttempts"] == 1 and auth["synthetic"] is False
    assert auth["state"] == "coordinator-authorized-single-offline-npm-setup"
    assert (
        auth["command"]
        == plan["command"]
        == "cd /workspace/repository; npm ci --offline --foreground-scripts"
    )
    assert auth["limits"] == plan["limits"]
    assert (
        digest(Path(auth["cacheAcceptance"]["path"]))
        == digest(PACKET / "cache-disposition.json")
        == auth["cacheAcceptance"]["sha256"]
    )
    assert acceptance["state"] == "coordinator-accepted-go01-cache-for-offline-npm-setup"
    assert acceptance["cacheSpecSha256"] == plan["cacheSpecSha256"]
    disposition = acceptance["publishedTaskPayloadDisposition"]
    assert disposition["state"] == "allowed-only-for-offline-npm-setup-observation"
    assert disposition["payloadsSha256"] == digest(PLAN / "published-task-payloads.json")
    assert disposition["nativeTaskAdmitted"] is False and disposition["campaignAdmitted"] is False
    assert (
        acceptance["cacheGloballyQualified"] is False
        and acceptance["originalAuditFlagsRemainFalse"] is True
    )
    assert result["cacheAcceptance"]["authorization"] == auth
    assert result["cacheAcceptance"]["auditFreeze"] == acceptance["auditFreeze"]
    assert result["cacheAcceptance"]["cacheAcceptanceSha256"] == digest(
        PACKET / "cache-disposition.json"
    )
    assert digest(Path(acceptance["auditFreeze"]["path"])) == acceptance["auditFreeze"]["sha256"]
    assert verify_freeze(CACHE_REVIEW / "FREEZE.json") == 28
    assert verify_freeze(DOWNLOAD / "freeze.json") == 92
    prior = load(DOWNLOAD / "evidence/result.json")
    assert all(value is False for value in prior["draftAuditFlags"].values())
    for key in ("sourceArchiveSha256", "cacheArchiveSha256", "imageId"):
        assert result[key] == acceptance[key] == prior[key]
    assert result["state"] == "offline-npm-setup-observed" and result["setupObserved"] is True
    for key in (
        "synthetic",
        "nativeCollectionOccurred",
        "taskOutcomeObserved",
        "campaignAdmitted",
        "cacheGloballyQualified",
        "workBudgetExceeded",
    ):
        assert result[key] is False
    assert result["costUsd"] is None and result["modelCalls"] == 0
    source = Path(
        load(ROOT / "benchmarks/head-to-head/f05-go01-dependency-preparation-20261029/plan.json")[
            "source"
        ]["archivePath"]
    )
    cache = Path(plan["cache"]["path"])
    assert digest(source) == result["sourceArchiveSha256"]
    assert digest(cache) == result["cacheArchiveSha256"]
    receipts = {}
    trace = load(PACKET / "evidence/trace.json")
    for path in sorted((PACKET / "evidence/logs").glob("*/receipt.json")):
        receipt = load(path)
        for stream in ("stdout", "stderr"):
            assert digest(path.parent / f"{stream}.bin") == receipt[f"{stream}Sha256"]
        assert receipt["error"] is None and receipt["costUsd"] is None
        assert receipt["exitCode"] == (1 if path.parent.name == "post-cleanup-inspect" else 0)
        assert trace["receipts"][str(path.relative_to(PACKET / "evidence"))] == receipt
        receipts[path.parent.name] = receipt
    expected_order = [
        "image-inspect",
        "create",
        "start",
        "container-inspect",
        "initialize",
        "source-provision",
        "cache-provision",
        "initial-source-check",
        "initial-cache-check",
        "tools-before",
        "npm-config",
        "npm-ci",
        "package-observations",
        "tools-after",
        "tracked-source-check",
        "offline-final-inspect",
        "cleanup",
        "post-cleanup-inspect",
        "post-cleanup-list",
    ]
    assert len(receipts) == result["daemonCalls"] == 19
    assert sorted(receipts, key=lambda name: receipts[name]["startedAt"]) == expected_order
    name = result["ownedContainer"]
    for label, command in (
        ("npm-ci", plan["command"]),
        ("npm-config", plan["npmConfigProbe"]),
        ("package-observations", plan["packageObservation"]),
        ("tools-before", plan["toolProbe"]),
        ("tools-after", plan["toolProbe"]),
    ):
        assert receipts[label]["argv"] == ["docker", "exec", name, "/bin/sh", "-eu", "-c", command]
    assert receipts["source-provision"]["stdinSha256"] == result["sourceArchiveSha256"]
    assert receipts["source-provision"]["stdinBytes"] == source.stat().st_size == 280422400
    assert receipts["cache-provision"]["stdinSha256"] == result["cacheArchiveSha256"]
    assert receipts["cache-provision"]["stdinBytes"] == cache.stat().st_size == 366622720
    assert (
        receipts["initial-source-check"]["stdinSha256"]
        == receipts["tracked-source-check"]["stdinSha256"]
        == load(DOWNLOAD / "evidence/logs/tracked-source-check/receipt.json")["stdinSha256"]
    )
    assert (
        receipts["initial-source-check"]["stdinBytes"]
        == receipts["tracked-source-check"]["stdinBytes"]
        == 10223478
    )
    inventory = load(DOWNLOAD / "evidence/inventory.json")
    cache_manifest = "".join(
        f"{value}  ./{key}\n" for key, value in sorted(inventory["files"].items())
    ).encode()
    assert sha(cache_manifest) == receipts["initial-cache-check"]["stdinSha256"]
    assert len(cache_manifest) == receipts["initial-cache-check"]["stdinBytes"]
    tool_before = (PACKET / "evidence/logs/tools-before/stdout.bin").read_bytes()
    assert tool_before == (PACKET / "evidence/logs/tools-after/stdout.bin").read_bytes()
    assert all(line in tool_before.decode().splitlines() for line in plan["expectedToolLines"])
    config = load(PACKET / "evidence/logs/npm-config/stdout.bin")
    for key, value in (
        ("offline", True),
        ("ignore-scripts", False),
        ("foreground-scripts", True),
        ("cache", "/workspace/dependency-cache/npm-cache"),
        ("registry", "https://registry.npmjs.org"),
        ("userconfig", "/dev/null"),
    ):
        assert config[key] == value
    policy = load(PLAN / "inspect-policy.json")["required"]
    image = load(PACKET / "evidence/logs/image-inspect/stdout.bin")[0]
    env = dict(item.split("=", 1) for item in image["Config"]["Env"])
    env.update(plan["environment"])
    for label in ("container-inspect", "offline-final-inspect"):
        metadata = load(PACKET / f"evidence/logs/{label}/stdout.bin")[0]
        host = metadata["HostConfig"]
        assert metadata["Image"] == result["imageId"] and metadata["Config"]["User"] == "1000:1000"
        assert metadata["Mounts"] == [] and not host["Binds"]
        assert host["ReadonlyRootfs"] is True and host["Privileged"] is False
        assert host["CapAdd"] in (None, [])
        assert all(host[key] == value for key, value in policy.items())
        assert host["Memory"] == host["MemorySwap"] == 4294967296
        assert host["NanoCpus"] == 3000000000 and host["PidsLimit"] == 256
        assert host["NetworkMode"] == "none" and set(metadata["NetworkSettings"]["Networks"]) <= {
            "none"
        }
        for network in metadata["NetworkSettings"]["Networks"].values():
            assert not any(
                network.get(key)
                for key in ("IPAddress", "GlobalIPv6Address", "Gateway", "IPv6Gateway")
            )
        assert set(host["Tmpfs"]) == {"/tmp", "/workspace", "/workspace/dependency-cache"}
        for path, size in (
            ("/tmp", "size=512m"),
            ("/workspace", "size=8g"),
            ("/workspace/dependency-cache", "size=1g"),
        ):
            assert {
                "rw",
                "exec",
                "nosuid",
                "nodev",
                "uid=1000",
                "gid=1000",
                "mode=0700",
                size,
            } == set(host["Tmpfs"][path].split(","))
        assert dict(item.split("=", 1) for item in metadata["Config"]["Env"]) == env
    assert receipts["cleanup"]["argv"] == ["docker", "rm", "-f", name]
    assert (
        b"no such object"
        in (PACKET / "evidence/logs/post-cleanup-inspect/stderr.bin").read_bytes().lower()
    )
    assert (PACKET / "evidence/logs/post-cleanup-list/stdout.bin").read_bytes() == b""
    assert result["containerAbsent"] is True and result["cleanupExitCode"] == 0
    hook_log = b"\n".join(
        (PACKET / f"evidence/logs/npm-ci/{stream}.bin").read_bytes()
        for stream in ("stdout", "stderr")
    ).decode()
    assert all(marker in hook_log for marker in plan["expectedHookMarkers"])
    assert result["lifecycleLogMarkers"] == dict.fromkeys(plan["expectedHookMarkers"], True)
    assert observation == load(PACKET / "evidence/logs/package-observations/stdout.bin")
    assert observation["versions"] == plan["expectedPackageVersions"]
    identities = load(CACHE_REVIEW / "classifications.json")["npmPackageIdentities"]
    alias = {"@typescript/bundled-typescript": "typescript"}
    selected = {}
    for installed, version in observation["versions"].items():
        hits = [
            (path, item)
            for path, item in identities.items()
            if item.get("package") == alias.get(installed, installed)
            and item.get("version") == version
        ]
        assert len(hits) == 1, installed
        selected[hits[0][0]] = (installed, hits[0][1])
    package_files = {}
    package_checks = []
    with tarfile.open(cache, mode="r:") as archive:
        for member in archive:
            if member.name not in selected:
                continue
            installed, identity = selected[member.name]
            raw = archive.extractfile(member).read()
            assert (
                "sha512-" + base64.b64encode(hashlib.sha512(raw).digest()).decode()
                == identity["integrity"]
            )
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as package:
                for item in package:
                    if item.isfile():
                        assert item.size <= 128 * 1024**2
                        payload = package.extractfile(item).read()
                        relative = item.name.split("/", 1)[1]
                        package_files[installed + "/" + relative] = {
                            "bytes": len(payload),
                            "sha256": sha(payload),
                            "mode": item.mode,
                        }
            package_checks.append({"installedName": installed, **identity})
    correspondence = {
        "@vscode/vsce-sign/bin/vsce-sign": "@vscode/vsce-sign-linux-arm64/bin/vsce-sign",
        "@vscode/vsce-sign-linux-arm64/bin/vsce-sign": "@vscode/vsce-sign-linux-arm64/bin/vsce-sign",
        "@dprint/linux-arm64-glibc/dprint": "@dprint/linux-arm64-glibc/dprint",
        "@esbuild/linux-arm64/bin/esbuild": "@esbuild/linux-arm64/bin/esbuild",
        ".bin/dprint": "@dprint/linux-arm64-glibc/dprint",
        ".bin/esbuild": "@esbuild/linux-arm64/bin/esbuild",
    }
    assert set(observation["files"]) == set(correspondence)
    payload_matches = []
    root = "/workspace/repository/node_modules/"
    for key, original in correspondence.items():
        row = observation["files"][key]
        cached = package_files[original]
        assert row["isFile"] is True and row["contained"] is True
        assert row["mode"] == 0o755
        assert row["sha256"] == cached["sha256"] and row["bytes"] == cached["bytes"]
        assert row["resolved"].startswith(root)
        if key.startswith(".bin/"):
            expected_link = (
                "../dprint/dprint" if key.endswith("dprint") else "../esbuild/bin/esbuild"
            )
            assert row["link"] == expected_link
            assert (
                posixpath.normpath(posixpath.join(root, posixpath.dirname(key), row["link"]))
                == row["resolved"]
            )
        else:
            assert row["link"] is None and row["resolved"] == root + key
        payload_matches.append({"observed": key, "sourceCachePackageMember": original, **cached})
    assert (
        abs(result["workElapsedSeconds"] + result["cleanupSeconds"] - result["elapsedSeconds"])
        < 1e-6
    )
    assert 0 < result["setupSeconds"] <= result["workElapsedSeconds"] < 900
    assert 0 < result["preflightSeconds"] < result["workElapsedSeconds"]
    assert 0 < result["cleanupSeconds"] < 60
    assert 0 <= result["setupSeconds"] - receipts["npm-ci"]["elapsedSeconds"] < 0.1
    assert datetime.fromisoformat(result["startedAt"]) < datetime.fromisoformat(
        receipts["image-inspect"]["startedAt"]
    )
    summary = {
        "state": "bounded-static-result-review-passed",
        "findings": [],
        "frozenResultArtifacts": artifacts,
        "rawDriverReceipts": len(receipts),
        "declaredParentBindings": len(parent_bindings),
        "planBindingCount": len(plan["bindings"]),
        "scriptClosureCount": len(plan["scripts"]),
        "hookMarkers": result["lifecycleLogMarkers"],
        "versions": observation["versions"],
        "packageProvenance": package_checks,
        "observedPayloadMatches": payload_matches,
        "setupStepSeconds": result["setupSeconds"],
        "preflightSeconds": result["preflightSeconds"],
        "workSeconds": result["workElapsedSeconds"],
        "cleanupSeconds": result["cleanupSeconds"],
        "elapsedSeconds": result["elapsedSeconds"],
        "costUsd": None,
        "onlyRetainedCleanupObserved": True,
        "globalCacheFlagsRemainFalse": True,
        "nativeCollectionTaskOutcomeCampaignAdmitted": False,
        "newDaemonNetworkPackageNativeProviderCargoCalls": 0,
        "limits": [
            "Marker presence and zero npm exit are observed; source hook effects are inferred only where final file hashes support them.",
            "Final vsce/dprint/esbuild files match public SRI-bound package bytes. No universal child-process trace or all-hook-branch proof.",
            "Published task-family compiler remains explicitly accepted only for this setup observation, without task/runtime/campaign/global cache admission.",
            "No independent rerun or current container absence probe; retained inspect/cleanup observations only.",
        ],
    }
    (HERE / "review.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "state",
                    "findings",
                    "frozenResultArtifacts",
                    "rawDriverReceipts",
                    "hookMarkers",
                    "setupStepSeconds",
                    "elapsedSeconds",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
