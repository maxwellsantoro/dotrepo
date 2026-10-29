"""One separately authorized direct-Go collection attempt; no task completion."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tarfile
import time
import uuid

import listing

HERE = Path(__file__).resolve().parent
BASE = Path("/Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head")
BOUNDARY = BASE / "f05-go01-offline-setup-plan-20261029/amendment-1/setup.py"
BOUNDARY_SHA = "06e3eb82f695812f96816c820f61fef1cceb242c636de5980284824948604de0"
NEXT = BASE / "f05-go01-next-qualification-20261029"
NEXT_PLAN_SHA = "5eff74e73198becf50a55d3145f704a9eff29e4f6107d95826a54aa58d486f69"
IMAGE = "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
SOURCE = "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f"
TEXT_LIMIT = 2 * 1024**2
SCRIPT_NAMES = {
    "collection.py",
    "listing.py",
    "process_io.py",
    "tree-observer.js",
    "controls.py",
    "make_plan.py",
    "transport_controls.py",
    "observer_controls.py",
    "amendment_controls.py",
}
LOCAL_NAMES = {"compiler-context-decision.json", "tmpfs-retrospective.json"}
COMMANDS = [
    "go env -json GOOS GOARCH GOVERSION GOTOOLCHAIN GOENV GOWORK GOFLAGS CGO_ENABLED CC CXX",
    "go list -json ./...",
    "go test -json -list . ./...",
]


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


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def dependencies():
    global boundary, DockerBackend
    require(
        stat.S_ISREG(BOUNDARY.lstat().st_mode) and file_sha(BOUNDARY) == BOUNDARY_SHA,
        "changed reviewed isolation boundary",
    )
    boundary = module(BOUNDARY, "collection_reviewed_boundary")
    boundary.load_helpers()
    DockerBackend = module(HERE / "process_io.py", "collection_transport").DockerBackend


def load_plan():
    plan = json.loads((HERE / "plan.json").read_text())
    require(file_sha(NEXT / "plan.json") == NEXT_PLAN_SHA, "changed parent collection plan")
    parent = json.loads((NEXT / "plan.json").read_text())
    require(
        plan.get("identity") == "go01-collection-driver-amendment-1",
        "changed driver packet identity",
    )
    require(
        [row["command"] for row in parent["commandsInOrder"]] == COMMANDS == plan["commands"],
        "changed collection commands",
    )
    require(
        plan["imageId"] == IMAGE and plan["sourceArchiveSha256"] == SOURCE,
        "changed source/image identity",
    )
    require(
        plan["executionAuthorized"] is False and plan["cacheAdmissionSatisfied"] is False,
        "plan cannot mint admission",
    )
    require(
        plan["limits"] == parent["limits"] and all(type(v) is int for v in plan["limits"].values()),
        "changed limits",
    )
    expected_environment = {**parent["environment"], "CC": "/usr/bin/gcc", "CXX": "/usr/bin/g++"}
    require(plan["environment"] == expected_environment, "changed collection environment")
    raw = (json.dumps(expected_environment, sort_keys=True, separators=(",", ":")) + "\n").encode()
    require(
        hashlib.sha256(raw).hexdigest() == plan["environmentSha256"], "environment hash mismatch"
    )
    require(
        plan["expectedGoEnv"]
        == {
            "GOOS": "linux",
            "GOARCH": "arm64",
            "GOVERSION": "go1.27.3",
            "GOTOOLCHAIN": "local",
            "GOENV": "off",
            "GOWORK": "/workspace/repository/go.work",
            "GOFLAGS": "-p=1 -count=1",
            "CGO_ENABLED": "1",
            "CC": "/usr/bin/gcc",
            "CXX": "/usr/bin/g++",
        },
        "changed exact Go context",
    )
    for name, digest in plan["scripts"].items():
        require(file_sha(HERE / name) == digest, "changed driver closure: " + name)
    for name, digest in plan["localFiles"].items():
        require(file_sha(HERE / name) == digest, "changed local decision: " + name)
    for path, digest in plan["bindings"].items():
        require(file_sha(Path(path)) == digest, "changed retained input: " + path)
    require(plan["projection"] is not None, "Go-only projection unresolved")
    dependencies()
    return plan


def bound_artifact(value):
    path = Path(value["path"])
    require(
        path.is_absolute()
        and stat.S_ISREG(path.lstat().st_mode)
        and file_sha(path) == value["sha256"],
        "external acceptance artifact mismatch",
    )
    value = json.loads(path.read_text())
    require(isinstance(value, dict), "external acceptance/review artifact must be a JSON object")
    return value


def current_subject(plan):
    require(
        plan == json.loads((HERE / "plan.json").read_text()),
        "provided plan differs from current plan bytes",
    )
    require(
        set(plan["scripts"]) == SCRIPT_NAMES and set(plan["localFiles"]) == LOCAL_NAMES,
        "incomplete declared script/local closure",
    )
    freeze_path = HERE / "FREEZE.json"
    require(stat.S_ISREG(freeze_path.lstat().st_mode), "author freeze missing/not regular")
    frozen = json.loads(freeze_path.read_text())
    require(isinstance(frozen, dict), "author freeze must be a JSON object")
    plan_sha = file_sha(HERE / "plan.json")
    required = {"plan.json": plan_sha, **plan["scripts"], **plan["localFiles"]}
    require(
        frozen.get("identity") == plan["identity"] and frozen.get("driverPlanSha256") == plan_sha,
        "author freeze subject mismatch",
    )
    hashes = frozen.get("artifactSha256", {})
    require(isinstance(hashes, dict), "author freeze hash map is invalid")
    require(
        all(
            hashes.get(name) == digest and file_sha(HERE / name) == digest
            for name, digest in required.items()
        ),
        "author freeze does not bind complete current script/local closure",
    )
    return {
        "driverPlanSha256": plan_sha,
        "authorFreezeSha256": file_sha(freeze_path),
        "packetIdentity": plan["identity"],
    }


def authorize(plan, path, output, scratch):
    subject = current_subject(plan)
    auth = json.loads(Path(path).read_text())
    require(
        auth.get("synthetic") is False
        and auth.get("state") == "coordinator-authorized-single-go01-collection-attempt",
        "missing collection authorization",
    )
    require(
        auth.get("planSha256") == file_sha(HERE / "plan.json")
        and auth.get("output") == str(output.resolve())
        and auth.get("scratch") == str(scratch.resolve()),
        "authorization identity mismatch",
    )
    require(
        auth.get("authorFreezeSha256") == subject["authorFreezeSha256"],
        "authorization author-freeze mismatch",
    )
    require(
        auth.get("commands") == COMMANDS
        and auth.get("limits") == plan["limits"]
        and type(auth.get("maxAttempts")) is int
        and auth["maxAttempts"] == 1
        and all(type(v) is int for v in auth["limits"].values()),
        "authorization command/bounds mismatch",
    )
    accepted = bound_artifact(auth["collectionAcceptance"])
    require(
        accepted.get("synthetic") is False
        and accepted.get("state") == "coordinator-accepted-go01-no-npm-go-projection-collection",
        "collection scope not accepted",
    )
    require(
        accepted.get("driverSubject") == subject,
        "acceptance subject is not current driver plan/author freeze",
    )
    for key in ["sourceArchiveSha256", "imageId", "environmentSha256"]:
        require(accepted.get(key) == plan[key], "scope acceptance identity mismatch")
    require(
        accepted.get("projectionSha256") == plan["projection"]["archive"]["sha256"]
        and accepted.get("projectionSpecSha256") == plan["projectionSpecSha256"],
        "projection acceptance mismatch",
    )
    require(
        accepted.get("initAndTestMainExecutionAccepted") is True
        and accepted.get("noNpmProvisioning") is True
        and all(
            accepted.get(key) is False
            for key in ["nativeTaskAdmitted", "campaignAdmitted", "cacheGloballyQualified"]
        ),
        "acceptance exceeds collection-only scope",
    )
    for key in ["sourceScopeReviewFreeze", "projectionReviewFreeze", "driverReviewFreeze"]:
        if key != "driverReviewFreeze":
            require(
                accepted[key] == plan["collectionScopeReview"],
                "source/projection scope review binding differs",
            )
        bound_artifact(accepted[key])
    review = bound_artifact(accepted["driverReviewFreeze"])
    require(
        review.get("state") == "independent-go01-collection-driver-review-passed"
        and review.get("synthetic") is False
        and review.get("scope") == "go01-collection-only"
        and review.get("subject") == subject
        and isinstance(review.get("findings"), list)
        and review["findings"] == []
        and all(
            review.get(key) is False
            for key in [
                "executionAuthorized",
                "nativeTaskAdmitted",
                "campaignAdmitted",
                "cacheGloballyQualified",
            ]
        ),
        "driver review is not a passed current-subject collection-only review",
    )
    return {
        "authorization": auth,
        "collectionAcceptanceSha256": file_sha(auth["collectionAcceptance"]["path"]),
        "driverSubject": subject,
        "scope": "collection only; init/TestMain allowed, no test-body/task outcome admission",
    }


def inputs(plan, check):
    source, source_files, source_bytes, deny = boundary.prior.preflight(
        boundary.prior.load_plan(), check
    )
    projection = plan["projection"]
    cache = Path(projection["archive"]["path"])
    require(
        stat.S_ISREG(cache.lstat().st_mode)
        and cache.stat().st_size == projection["archive"]["bytes"] <= 536870912
        and file_sha(cache) == projection["archive"]["sha256"],
        "projection archive mismatch",
    )
    inventory = bound_artifact(projection["inventory"])
    cache_files, cache_bytes = boundary.scan_archive(
        cache, deadline=check, inventory=inventory["files"], roots=("go/pkg/mod",), deny=deny
    )
    require(
        len(cache_files) == projection["files"] == 14922
        and cache_bytes == projection["expandedBytes"] == 278162103
        and source_bytes + cache_bytes <= 2147483648,
        "projection/source limits mismatch",
    )
    with tarfile.open(source, mode="r:") as archive:
        directories = {member.name.rstrip("/") for member in archive if member.isdir()}
    return source, cache, source_files, cache_files, tree_expected(source_files, directories)


def flags(name, environment):
    return boundary.flags(name, environment)


def inspect(row, environment):
    boundary.inspect(row, environment)
    owner = {"uid=1000", "gid=1000", "mode=0700"}
    expected = {
        "/workspace": {"rw", "exec", "nosuid", "nodev", "size=8g"} | owner,
        "/workspace/dependency-cache": {"rw", "exec", "nosuid", "nodev", "size=1g"} | owner,
        "/tmp": {"rw", "exec", "nosuid", "nodev", "size=512m"} | owner,
    }
    tmpfs = row["HostConfig"]["Tmpfs"]
    require(isinstance(tmpfs, dict) and set(tmpfs) == set(expected), "unexpected tmpfs mount set")
    for path, wanted in expected.items():
        require(isinstance(tmpfs[path], str), "invalid tmpfs option representation")
        options = tmpfs[path].split(",")
        require(
            len(options) == len(set(options)) and set(options) == wanted,
            "duplicate/conflicting/unknown tmpfs options",
        )


def tree_expected(files, explicit_directories=()):
    directories = {".", *explicit_directories}
    for name in explicit_directories:
        parent = Path(name).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    rows = []
    for name, value in files.items():
        rows.append([name, "file", value["sha256"], value["bytes"]])
        parent = Path(name).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    rows.extend([name, "directory"] for name in directories)
    rows.sort(key=lambda row: row[0].encode())
    raw = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode()
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "entries": len(rows),
        "bytes": sum(row["bytes"] for row in files.values()),
    }


def raw_streams(output, label, receipt):
    values = {}
    for role in ["stdout", "stderr"]:
        path = output / "logs" / label / (role + ".bin")
        require(
            stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= TEXT_LIMIT,
            "missing/oversize raw trace",
        )
        raw = path.read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == receipt[role + "Sha256"], "raw trace hash mismatch"
        )
        values[role] = raw
    require(sum(len(raw) for raw in values.values()) <= TEXT_LIMIT, "combined raw trace bound")
    return values


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
        "collectionObserved": False,
        "nativeCollectionAttempted": False,
        "nativeTaskAdmitted": False,
        "campaignAdmitted": False,
        "cacheGloballyQualified": False,
    }
    write(output / "attempt.json", result)
    name = "dotrepo-go01-collection-" + uuid.uuid4().hex[:12]
    result["ownedContainer"] = name
    preflight_start = None
    collection_start = None

    def check():
        require(clock() < deadline, "900-second work deadline exhausted")

    def call(label, argv, **kwargs):
        check()
        result["stage"] = label
        result["daemonCalls"] += 1
        receipt = backend.command(output, label, argv, deadline=deadline, **kwargs)
        if receipt.get("cancelled"):
            raise KeyboardInterrupt(receipt.get("error", "client cancellation"))
        require(
            receipt["exitCode"] == 0 and receipt["error"] is None,
            label + " failed: " + str(receipt.get("error")),
        )
        raw = raw_streams(output, label, receipt)
        require(
            receipt.get("stdinBytes", 0)
            == (Path(kwargs["stdin_path"]).stat().st_size if kwargs.get("stdin_path") else 0),
            "stdin byte count mismatch",
        )
        return {
            **receipt,
            "stdout": raw["stdout"].decode("utf-8", errors="strict"),
            "stderr": raw["stderr"].decode("utf-8", errors="strict"),
            "rawStdout": raw["stdout"],
        }

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
            collectionAcceptance=accepted,
            imageId=IMAGE,
            sourceArchiveSha256=SOURCE,
            cacheArchiveSha256=plan["projection"]["archive"]["sha256"],
            environmentSha256=plan["environmentSha256"],
        )
        scratch.mkdir()
        result["stage"] = "input-preflight"
        preflight_start = clock()
        source, cache, source_files, cache_files, expected_tree = input_check(plan, check)
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
            len(image["Config"]["Env"]) == 5
            and set(v.split("=", 1)[0] for v in image["Config"]["Env"])
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
            (
                "cache-provision",
                cache,
                "/workspace/dependency-cache",
                plan["projection"]["archive"]["sha256"],
            ),
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
        require(tools == plan["expectedToolOutput"], "audited tool bytes mismatch")
        before_tree = listing.objects(
            shell("source-tree-before", plan["treeObservation"])["rawStdout"]
        )
        require(before_tree == [expected_tree], "initial full source tree mismatch")
        write(output / "source-tree-before.json", before_tree[0])
        collection_start = clock()
        inventory = None
        for label, command, filename in zip(
            ["go-env", "go-list", "go-test-list"],
            COMMANDS,
            ["go-environment.json", "packages.jsonstream", "collection-events.jsonl"],
            strict=True,
        ):
            if label == "go-test-list":
                result["nativeCollectionAttempted"] = True
            observed = shell(label, "cd /workspace/repository/tsc; " + command)
            with (output / filename).open("xb") as stream:
                stream.write(observed["rawStdout"])
            if label == "go-env":
                listing.environment(observed["rawStdout"], plan["expectedGoEnv"])
            elif label == "go-list":
                inventory = listing.packages(observed["rawStdout"], source_files)
                write(output / "package-inventory.json", inventory)
            else:
                manifest = listing.collection(observed["rawStdout"], inventory)
                manifest.update(
                    sourceArchiveSha256=SOURCE,
                    imageId=IMAGE,
                    environmentSha256=plan["environmentSha256"],
                    packageInventorySha256=file_sha(output / "packages.jsonstream"),
                    rawEventsSha256=file_sha(output / filename),
                    collectionCompletedAt=datetime.now(timezone.utc).isoformat(),
                    taskOutcomeObserved=False,
                    campaignAdmitted=False,
                )
                write(output / "collection-manifest.json", manifest)
        result["collectionSeconds"] = clock() - collection_start
        after_tree = listing.objects(
            shell("source-tree-after", plan["treeObservation"])["rawStdout"]
        )
        write(
            output / "source-tree-after.json", after_tree[0] if len(after_tree) == 1 else after_tree
        )
        require(after_tree == before_tree, "source additions/deletions/type/content change")
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
        result.update(
            state="native-top-level-collection-observed",
            collectionObserved=True,
            nativeCollectionOccurred=not result["synthetic"],
        )
    except BaseException as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        result["cancelled"] = isinstance(error, (KeyboardInterrupt, SystemExit))
    finally:
        result["workElapsedSeconds"] = clock() - start
        if collection_start is not None and "collectionSeconds" not in result:
            result["collectionSeconds"] = clock() - collection_start
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
            except BaseException as error:
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
        except BaseException as error:
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
        verified = load_plan()
        print(
            json.dumps(
                {
                    "state": "metadata-verified-not-authorized",
                    "environmentSha256": verified["environmentSha256"],
                    "projectionArchiveSha256": verified["projection"]["archive"]["sha256"],
                }
            )
        )
    else:
        result = run(args.authorization, args.output, args.scratch)
        print(json.dumps(result))
        raise SystemExit(0 if result["state"] == "native-top-level-collection-observed" else 1)
