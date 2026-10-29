"""Read-only verification of retained Go01 preflight failure; never runs a driver."""

import argparse
import hashlib
import json
from pathlib import Path
import stat
import tarfile

HERE = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    require(stat.S_ISREG(path.lstat().st_mode), f"not a regular file: {path}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(root, name):
    return json.loads((root / name).read_text())


def closure(root):
    ledger = read(root, "origin-ledger.json")["files"]
    names = set()
    for row in ledger:
        name = row["retained"]
        require(name not in names, "duplicate retained path")
        names.add(name)
        path = root / name
        require(path.resolve().is_relative_to(root.resolve()), "retained path escapes")
        require(path.stat().st_size == row["bytes"], f"retained size changed: {name}")
        require(digest(path) == row["sha256"], f"retained bytes changed: {name}")
    author = read(root, "bindings/author-freeze.json")
    plan = read(root, "bindings/plan.json")
    subject = {
        "driverPlanSha256": digest(root / "bindings/plan.json"),
        "authorFreezeSha256": digest(root / "bindings/author-freeze.json"),
        "packetIdentity": plan["identity"],
    }
    require(author["driverPlanSha256"] == subject["driverPlanSha256"], "author/plan")
    require(author["identity"] == subject["packetIdentity"], "author identity")
    require(author["artifactSha256"]["plan.json"] == subject["driverPlanSha256"], "plan closure")
    for name, sha in {**plan["scripts"], **plan["localFiles"]}.items():
        require(digest(root / "bindings/driver" / name) == sha, f"driver binding: {name}")
        require(author["artifactSha256"][name] == sha, f"author closure: {name}")
    review = read(root, "bindings/passed-review.json")
    require(review["subject"] == subject, "review subject")
    require(
        review["state"] == "independent-go01-collection-driver-review-passed"
        and review["scope"] == "go01-collection-only"
        and review["findings"] == []
        and review["synthetic"] is False,
        "review did not pass current subject",
    )
    require(digest(root / "bindings/review.json") == review["report"]["sha256"], "review report")
    rf = read(root, "bindings/review-freeze.json")["artifacts"]
    for original, retained in [
        ("passed-review.json", "passed-review.json"),
        ("review.json", "review.json"),
    ]:
        require(digest(root / "bindings" / retained) == rf[original]["sha256"], "review freeze")
    acceptance = read(root, "authorization/acceptance.json")
    require(acceptance["driverSubject"] == subject, "acceptance subject")
    for key in ["sourceArchiveSha256", "imageId", "environmentSha256", "projectionSpecSha256"]:
        require(acceptance[key] == plan[key], f"acceptance {key}")
    require(acceptance["projectionSha256"] == plan["projection"]["archive"]["sha256"], "projection")
    require(
        acceptance["driverReviewFreeze"]["sha256"] == digest(root / "bindings/passed-review.json"),
        "accepted review object",
    )
    for key in ["sourceScopeReviewFreeze", "projectionReviewFreeze"]:
        require(
            acceptance[key]["sha256"]
            == digest(root / "bindings/source-projection-review-freeze.json"),
            "accepted source/projection review",
        )
    require(
        acceptance["synthetic"] is False and acceptance["initAndTestMainExecutionAccepted"] is True,
        "scoped acceptance",
    )
    require(acceptance["noNpmProvisioning"] is True, "npm acceptance scope")
    for key in ["nativeTaskAdmitted", "campaignAdmitted", "cacheGloballyQualified"]:
        require(acceptance[key] is False, "broader acceptance")
    for directory in ["authorization", "authorization/path-amendment-1"]:
        frozen = read(root, f"{directory}/FREEZE.json")
        for name, sha in frozen["artifactSha256"].items():
            require(digest(root / directory / name) == sha, "authorization freeze")
    require(
        read(root, "authorization/path-amendment-1/FREEZE.json")["priorAuthorizationFreezeSha256"]
        == digest(root / "authorization/FREEZE.json"),
        "prior authorization freeze",
    )
    require(
        read(root, "authorization/FREEZE.json")["driverReviewFreezeSha256"]
        == digest(root / "bindings/review-freeze.json"),
        "authorized review freeze",
    )
    auth1 = read(root, "authorization/authorization.json")
    auth2 = read(root, "authorization/path-amendment-1/authorization.json")
    require(
        {k: v for k, v in auth2.items() if k not in {"output", "scratch", "priorAdmissionAttempt"}}
        == {k: v for k, v in auth1.items() if k not in {"output", "scratch"}},
        "authorization changed beyond explicit path amendment",
    )
    for auth in [auth1, auth2]:
        require(
            auth["planSha256"] == subject["driverPlanSha256"]
            and auth["authorFreezeSha256"] == subject["authorFreezeSha256"],
            "auth subject",
        )
        require(
            auth["commands"] == plan["commands"] and auth["limits"] == plan["limits"],
            "auth commands/limits",
        )
        require(auth["maxAttempts"] == 1 and auth["synthetic"] is False, "auth attempt bound")
        require(
            auth["collectionAcceptance"]["sha256"]
            == digest(root / "authorization/acceptance.json"),
            "auth acceptance",
        )
    require(
        auth1["output"] == "/tmp/dotrepo-go01-native-collection-result-20261029-1", "first output"
    )
    require(
        auth2["output"] == "/private/tmp/dotrepo-go01-native-collection-result-20261029-2",
        "second output",
    )
    require(
        auth2["priorAdmissionAttempt"]["sha256"] == digest(root / "attempt-1/result.json"),
        "prior refusal",
    )
    return plan, auth2


def isolation(row, image, plan):
    host = row["HostConfig"]
    require(row["Image"] == image["Id"] == plan["imageId"], "image identity")
    require(image["Os"] == "linux" and image["Architecture"] == "arm64", "image platform")
    require(not row["Mounts"] and not host["Binds"], "mounts")
    require(host["ReadonlyRootfs"] is True and host["Privileged"] is False, "root isolation")
    for key, expected in {
        "PidMode": "",
        "IpcMode": "private",
        "CgroupnsMode": "private",
        "UsernsMode": "",
        "UTSMode": "",
        "Init": True,
        "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges"],
        "Memory": 4294967296,
        "MemorySwap": 4294967296,
        "NanoCpus": 3000000000,
        "PidsLimit": 256,
        "Devices": [],
        "DeviceRequests": None,
        "VolumesFrom": None,
        "Links": None,
        "PortBindings": {},
        "PublishAllPorts": False,
        "NetworkMode": "none",
    }.items():
        require(host[key] == expected, f"isolation {key}")
    require(host["CapAdd"] in (None, []), "added capabilities")
    require(row["Config"]["User"] == "1000:1000", "user")
    expected = {**dict(v.split("=", 1) for v in image["Config"]["Env"]), **plan["environment"]}
    env = row["Config"]["Env"]
    require(
        len(env) == len(expected) and dict(v.split("=", 1) for v in env) == expected,
        "effective environment",
    )
    require(not set(plan["explicitlyAbsentEnvironment"]) & set(expected), "excluded environment")
    wanted = {"/workspace": "8g", "/workspace/dependency-cache": "1g", "/tmp": "512m"}
    require(set(host["Tmpfs"]) == set(wanted), "tmpfs mount set")
    for path, size in wanted.items():
        opts = host["Tmpfs"][path].split(",")
        require(
            len(opts) == len(set(opts))
            and set(opts)
            == {
                "rw",
                "exec",
                "nosuid",
                "nodev",
                f"size={size}",
                "uid=1000",
                "gid=1000",
                "mode=0700",
            },
            "tmpfs options",
        )
    require(set(row["NetworkSettings"]["Networks"]) <= {"none"}, "network membership")
    for network in row["NetworkSettings"]["Networks"].values():
        require(
            not any(
                network.get(k) for k in ["IPAddress", "GlobalIPv6Address", "Gateway", "IPv6Gateway"]
            ),
            "network address",
        )


def observations(root, plan, auth2):
    results = [read(root, f"attempt-{n}/result.json") for n in [1, 2]]
    for n, result in enumerate(results, 1):
        require(read(root, f"outer/driver-{n}.log") == result, "outer result differs")
        require(result["state"] == "incomplete" and result["synthetic"] is False, "outcome")
        for key in [
            "nativeCollectionOccurred",
            "nativeCollectionAttempted",
            "collectionObserved",
            "taskOutcomeObserved",
            "nativeTaskAdmitted",
            "campaignAdmitted",
            "cacheGloballyQualified",
        ]:
            require(result[key] is False, f"unsupported success: {key}")
        require(result["modelCalls"] == 0 and result["costUsd"] is None, "cost/provider accounting")
    first, second = results
    require(
        first["stage"] == "authorization"
        and first["daemonCalls"] == 0
        and first["containerCreateAttempted"] is False,
        "first admission",
    )
    require(first["error"] == "ValueError: authorization identity mismatch", "first reason")
    require(read(root, "attempt-1/trace.json")["receipts"] == {}, "first daemon evidence")
    require(
        second["stage"] == "go-env" and second["error"] == "ValueError: Go environment mismatch",
        "second reason",
    )
    require(
        second["authorizationSha256"]
        == digest(root / "authorization/path-amendment-1/authorization.json"),
        "actual auth hash",
    )
    require(second["collectionAcceptance"]["authorization"] == auth2, "actual auth")
    trace = read(root, "attempt-2/trace.json")["receipts"]
    expected_labels = {
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
        "source-tree-before",
        "go-env",
        "cleanup",
        "post-cleanup-inspect",
        "post-cleanup-list",
    }
    require(
        set(trace) == {f"logs/{label}/receipt.json" for label in expected_labels},
        "unexpected/missing executed command",
    )
    require(second["daemonCalls"] == len(trace) == 15, "daemon count")
    stdin_bytes = stream_bytes = 0
    for name, receipt in trace.items():
        leaf = root / "attempt-2" / name
        require(json.loads(leaf.read_text()) == receipt, "trace/receipt mismatch")
        size = 0
        for stream in ["stdout", "stderr"]:
            p = leaf.parent / f"{stream}.bin"
            require(digest(p) == receipt[f"{stream}Sha256"], "raw stream mismatch")
            size += p.stat().st_size
        require(size <= plan["limits"]["combinedStdoutStderrPerCommandBytes"], "raw cap")
        require(receipt["error"] is None and receipt["cancelled"] is False, "transport error")
        require(
            receipt["exitCode"] == (1 if name == "logs/post-cleanup-inspect/receipt.json" else 0),
            "unexpected command exit",
        )
        require(receipt["costUsd"] is None, "invented cost")
        stdin_bytes += receipt["stdinBytes"]
        stream_bytes += size

    def raw(label, stream="stdout"):
        return (root / f"attempt-2/logs/{label}/{stream}.bin").read_bytes()

    for label, expected in [
        ("source-provision", plan["sourceArchiveSha256"]),
        ("cache-provision", plan["projection"]["archive"]["sha256"]),
    ]:
        require(
            trace[f"logs/{label}/receipt.json"]["stdinSha256"] == expected,
            "archive provision binding",
        )
    require(raw("tools-before").decode() == plan["expectedToolOutput"], "tool observation")
    isolation(json.loads(raw("container-inspect"))[0], json.loads(raw("image-inspect"))[0], plan)
    env = json.loads(raw("go-env"))
    require(env == read(root, "attempt-2/go-environment.json"), "retained env byte observation")
    mismatch = {
        k: {"expected": v, "observed": env.get(k)}
        for k, v in plan["expectedGoEnv"].items()
        if env.get(k) != v
    }
    require(
        set(env) == set(plan["expectedGoEnv"])
        and mismatch == {"GOENV": {"expected": "off", "observed": ""}},
        "different env failure",
    )
    receipt = trace["logs/go-env/receipt.json"]
    require(receipt["argv"][-1] == f"cd {plan['cwd']}; {plan['commands'][0]}", "go-env command")
    require(raw("go-env", "stderr") == b"", "go-env stderr")
    require(second["containerAbsent"] is True and second["cleanupExitCode"] == 0, "cleanup outcome")
    require(
        json.loads(raw("post-cleanup-inspect")) == []
        and b"no such object" in raw("post-cleanup-inspect", "stderr"),
        "inspect absence",
    )
    require(raw("post-cleanup-list") == b"", "responsive name-list absence")
    require(
        not any(
            (root / "attempt-2" / n).exists()
            for n in ["packages.jsonstream", "collection-events.jsonl", "source-tree-after.json"]
        ),
        "unexpected later phase",
    )
    return {
        "state": "verified-retained-incomplete-outcome",
        "attempts": 2,
        "daemonCalls": 15,
        "environmentMismatch": mismatch,
        "stdinBytes": stdin_bytes,
        "rawOutputBytes": stream_bytes,
        "elapsedSecondsBothAttempts": sum(r["elapsedSeconds"] for r in results),
        "absenceEvidence": "same-attempt driver receipts only; no independent daemon observation",
        "sourceTreeBefore": read(root, "attempt-2/source-tree-before.json"),
        "sourceAndToolsAfterObserved": False,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
        "costUsd": None,
    }


def archives(root, plan):
    source = read(root, "bindings/dependency-plan.json")["source"]
    rows = []
    directories = {"."}
    p = Path(source["archivePath"])
    require(digest(p) == source["archiveSha256"] == plan["sourceArchiveSha256"], "source archive")
    with tarfile.open(p, "r:") as archive:
        for member in archive:
            if member.isdir():
                directories.add(member.name.rstrip("/"))
            else:
                require(member.isfile(), "unexpected source type")
                stream = archive.extractfile(member)
                rows.append(
                    [
                        member.name,
                        "file",
                        hashlib.file_digest(stream, "sha256").hexdigest(),
                        member.size,
                    ]
                )
                parent = Path(member.name).parent
                while str(parent) != ".":
                    directories.add(parent.as_posix())
                    parent = parent.parent
    source_manifest = "".join(
        f"{row[2]}  ./{row[0]}\n" for row in sorted(rows, key=lambda row: row[0])
    ).encode()
    receipt = read(root, "attempt-2/logs/initial-source-check/receipt.json")
    require(
        receipt["stdinBytes"] == len(source_manifest)
        and receipt["stdinSha256"] == hashlib.sha256(source_manifest).hexdigest(),
        "source checksum manifest binding",
    )
    rows += [[name, "directory"] for name in directories]
    rows.sort(key=lambda row: row[0].encode())
    canonical = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode()
    expected = {
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "entries": len(rows),
        "bytes": sum(row[3] for row in rows if row[1] == "file"),
    }
    require(
        expected == read(root, "attempt-2/source-tree-before.json"),
        "source before vs complete archive",
    )
    projection = plan["projection"]["archive"]
    require(digest(Path(projection["path"])) == projection["sha256"], "projection archive")
    cache_inventory = json.loads(Path(plan["projection"]["inventory"]["path"]).read_text())["files"]
    cache_manifest = "".join(
        f"{sha}  ./{name}\n" for name, sha in sorted(cache_inventory.items())
    ).encode()
    receipt = read(root, "attempt-2/logs/initial-cache-check/receipt.json")
    require(
        receipt["stdinBytes"] == len(cache_manifest)
        and receipt["stdinSha256"] == hashlib.sha256(cache_manifest).hexdigest(),
        "cache checksum manifest binding",
    )
    return {
        "sourceArchiveSha256": source["archiveSha256"],
        "projectionArchiveSha256": projection["sha256"],
        "sourceTreeBeforeMatchesArchive": True,
    }


def verify(root, input_archives=False):
    plan, auth2 = closure(root)
    report = observations(root, plan, auth2)
    report["inputArchives"] = (
        archives(root, plan) if input_archives else "not reread; provision hashes retained"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-archives",
        action="store_true",
        help="also hash local fixed archives and compare full source tree",
    )
    args = parser.parse_args()
    print(json.dumps(verify(HERE, args.input_archives), indent=2, allow_nan=False))
