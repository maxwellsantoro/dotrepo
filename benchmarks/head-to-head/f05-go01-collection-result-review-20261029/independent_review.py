"""Independent local bytes/receipt/report checks; never invokes retained code."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKET = Path(json.loads((HERE / "author-binding.json").read_text())["packet"])


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, reason):
    if not value:
        raise ValueError(reason)


def main():
    frozen = read(PACKET / "FREEZE.json")
    for name, digest in frozen["artifactSha256"].items():
        require(sha(PACKET / name) == digest, name)
    ledger = read(PACKET / "origin-ledger.json")["files"]
    origins = 0
    for row in ledger:
        retained = PACKET / row["retained"]
        original = Path(row["source"])
        require(
            retained.stat().st_size == row["bytes"] and sha(retained) == row["sha256"],
            "retained copy",
        )
        require(
            original.stat().st_size == row["bytes"] and sha(original) == row["sha256"],
            "original changed",
        )
        origins += 1
    plan = read(PACKET / "bindings/plan.json")
    report = read(PACKET / "report.json")
    results = [read(PACKET / f"attempt-{n}/result.json") for n in [1, 2]]
    first, second = results
    name = second["ownedContainer"]
    image = plan["imageId"]
    require(
        first["daemonCalls"] == 0 and first["containerCreateAttempted"] is False, "first admission"
    )
    require(first["error"] == "ValueError: authorization identity mismatch", "first refusal")
    require(
        second["stage"] == "go-env" and second["error"] == "ValueError: Go environment mismatch",
        "second refusal",
    )
    trace = read(PACKET / "attempt-2/trace.json")["receipts"]

    def shell(text):
        return ["docker", "exec", name, "/bin/sh", "-eu", "-c", text]

    expected = {
        "image-inspect": ["docker", "image", "inspect", image],
        "start": ["docker", "start", name],
        "container-inspect": ["docker", "inspect", name],
        "initialize": shell(
            "mkdir -p /workspace/repository /workspace/dependency-cache /workspace/home /workspace/tmp"
        ),
        "source-provision": [
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
        "cache-provision": [
            "docker",
            "exec",
            "-i",
            name,
            "tar",
            "--extract",
            "--no-same-owner",
            "--no-same-permissions",
            "-C",
            "/workspace/dependency-cache",
        ],
        "initial-source-check": [
            "docker",
            "exec",
            "-i",
            name,
            "/bin/sh",
            "-eu",
            "-c",
            "cd /workspace/repository; sha256sum --check --status -",
        ],
        "initial-cache-check": [
            "docker",
            "exec",
            "-i",
            name,
            "/bin/sh",
            "-eu",
            "-c",
            "cd /workspace/dependency-cache; sha256sum --check --status -",
        ],
        "tools-before": shell(plan["toolProbe"]),
        "source-tree-before": shell(plan["treeObservation"]),
        "go-env": shell("cd " + plan["cwd"] + "; " + plan["commands"][0]),
        "cleanup": ["docker", "rm", "-f", name],
        "post-cleanup-inspect": ["docker", "inspect", name],
        "post-cleanup-list": [
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=" + name,
            "--format",
            "{{.Names}}",
        ],
    }
    create = [
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
    ]
    for root, size in [
        ("/workspace", "8g"),
        ("/tmp", "512m"),
        ("/workspace/dependency-cache", "1g"),
    ]:
        create += [
            "--tmpfs",
            root + ":rw,exec,nosuid,nodev,size=" + size + ",uid=1000,gid=1000,mode=0700",
        ]
    for key, value in sorted(plan["environment"].items()):
        create += ["--env", key + "=" + value]
    create += ["--entrypoint=/bin/sh", image, "-c", "while :; do sleep 3600; done"]
    expected["create"] = create
    require(set(trace) == {"logs/" + key + "/receipt.json" for key in expected}, "command closure")
    input_bytes = output_bytes = 0
    for label, argv in expected.items():
        relative = "logs/" + label + "/receipt.json"
        receipt = trace[relative]
        require(receipt == read(PACKET / "attempt-2" / relative), "trace receipt")
        require(receipt["argv"] == argv, "unexpected actual argv: " + label)
        require(receipt["exitCode"] == (1 if label == "post-cleanup-inspect" else 0), "exit code")
        require(receipt["error"] is None and receipt["cancelled"] is False, "transport status")
        require(receipt["costUsd"] is None, "unknown cost")
        for stream in ["stdout", "stderr"]:
            raw = PACKET / "attempt-2/logs" / label / (stream + ".bin")
            require(sha(raw) == receipt[stream + "Sha256"], "raw hash")
            output_bytes += raw.stat().st_size
        input_bytes += receipt["stdinBytes"]
    env = read(PACKET / "attempt-2/logs/go-env/stdout.bin")
    expected_env = dict(plan["expectedGoEnv"])
    require(expected_env.pop("GOENV") == "off", "old expectation")
    observed_env = dict(env)
    require(observed_env.pop("GOENV") == "", "query mismatch")
    require(observed_env == expected_env, "other query fields")
    inspect = read(PACKET / "attempt-2/logs/container-inspect/stdout.bin")[0]
    require("GOENV=off" in inspect["Config"]["Env"], "actual input")
    require(
        inspect["Image"] == image
        and inspect["Mounts"] == []
        and inspect["HostConfig"]["NetworkMode"] == "none",
        "basic actual isolation",
    )
    require(second["containerAbsent"] is True and second["cleanupExitCode"] == 0, "cleanup status")
    require(
        read(PACKET / "attempt-2/logs/post-cleanup-inspect/stdout.bin") == [], "inspect absence"
    )
    require(
        (PACKET / "attempt-2/logs/post-cleanup-list/stdout.bin").read_bytes() == b"", "list absence"
    )
    require(
        b"no such object"
        in (PACKET / "attempt-2/logs/post-cleanup-inspect/stderr.bin").read_bytes(),
        "absence diagnostic",
    )
    require(
        not any(
            (PACKET / "attempt-2" / v).exists()
            for v in [
                "packages.jsonstream",
                "collection-events.jsonl",
                "collection-manifest.json",
                "source-tree-after.json",
            ]
        ),
        "later outputs",
    )
    for result in results:
        require(
            result["state"] == "incomplete" and result["synthetic"] is False, "actual incomplete"
        )
        require(
            all(
                result[k] is False
                for k in [
                    "nativeCollectionAttempted",
                    "nativeCollectionOccurred",
                    "taskOutcomeObserved",
                    "nativeTaskAdmitted",
                    "campaignAdmitted",
                    "cacheGloballyQualified",
                ]
            ),
            "no result admission",
        )
    require(report["state"] == "incomplete-at-go-environment-preflight", "reported state")
    require(
        all(
            report[k] is False
            for k in [
                "nativeCollectionOccurred",
                "taskOutcomeObserved",
                "nativeTaskAdmitted",
                "campaignAdmitted",
                "cacheGloballyQualified",
                "packageInventoryObserved",
                "testListObserved",
            ]
        ),
        "reported no admission",
    )
    effort = report["effort"]
    require(
        effort["stdinBytes"] == input_bytes
        and effort["rawOutputBytes"] == output_bytes
        and effort["daemonCalls"] == len(trace),
        "report byte accounting",
    )
    require(
        math.isclose(
            effort["sumDriverElapsedSeconds"],
            sum(v["elapsedSeconds"] for v in results),
            rel_tol=1e-14,
        ),
        "report timing",
    )
    require(
        effort["costUsd"] is None and bool(effort["excludedUnknownCosts"]), "report unknown cost"
    )
    require(report["cleanup"]["independentAbsenceObservation"] is False, "absence limit")
    require(
        report["integrityAndIsolation"]["sourceAndToolAfterChecksObserved"] is False, "after limit"
    )
    require(
        report["preservation"]["originalOuterArgvReceiptAvailable"] is False, "outer receipt limit"
    )
    require(
        read(PACKET / "coordinator-handoff.json")["kind"]
        == "coordinator-message-transcription-not-original-process-receipt",
        "coordinator metadata",
    )
    replay = read(HERE / "replay-verification.json")
    require(
        replay["inputArchives"]["sourceTreeBeforeMatchesArchive"] is True, "full archive verifier"
    )
    output = {
        "state": "independently-verified-incomplete-result",
        "originalCopiesVerified": origins,
        "allPacketArtifactsVerified": len(frozen["artifactSha256"]),
        "actualArgvClosuresVerified": len(expected),
        "stdinBytes": input_bytes,
        "rawOutputBytes": output_bytes,
        "elapsedSecondsBothAttempts": sum(v["elapsedSeconds"] for v in results),
        "queryInputGOENV": "off",
        "queryOutputGOENV": "",
        "resultRemainsIncomplete": True,
        "noInventoryOrListing": True,
        "cleanupEvidence": "same-attempt only",
        "afterIntegrity": "not established",
        "outerExitReceipt": "coordinator transcription only",
        "costUsd": None,
        "newDaemonGoPackageNativeProviderNetworkCalls": 0,
    }
    with (HERE / "independent-checks.json").open("x") as f:
        json.dump(output, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
