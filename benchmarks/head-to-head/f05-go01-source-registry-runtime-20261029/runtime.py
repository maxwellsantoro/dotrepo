"""One explicitly authorized owned stdlib helper run; target source is stdin data."""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tarfile
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
HELPER = BASE / "f05-go01-source-registry-20261029"
HELPER_AMENDMENT = HELPER / "amendment-1"
BASE_HELPER_FREEZE = "b2fd2550fd9ca1b5dc20774badfb77863e28236cc0535f11c6012a5aa6a0ab8d"
HELPER_FREEZE = "e569edd4888a092aa46745d950614964ca86fc755637827fd9723fad0413da4d"
HELPER_PLAN = "74258ec831c551ad1b39a497ed09320c3824aa0be9a836fb3d076684f5703482"
IMAGE = "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
GO_SHA = "d487fddb6939f3e78f7293fcbdeae610ba8ceae966d3faa4b2094a5688559230"
MODULE = "/workspace/owned-module"
COMMANDS = [
    "go test -json -count=1 -timeout=60s .",
    "go build -o /workspace/owned-bin/registry .",
    "/workspace/owned-bin/registry",
]
MODULE_FILES = {"go.mod", "registry.go", "registry_test.go"}
TOP_TESTS = [
    "TestDiscoveryNamesAndSignatures",
    "TestExamplesUseOutputAndSourceOrder",
    "TestDuplicatesRetainDistinctStableDeclarations",
    "TestExternalPackageClauseAndEmptyRegistry",
    "TestPhysicalLocationIgnoresLineDirective",
    "TestBodylessExampleAndMethodAreNotRegistered",
    "TestJSONStructureRefusesAmbiguity",
    "TestDeterministicBoundedGzipEncoding",
]
SUB_TESTS = [
    "bare-prefix",
    "uppercase",
    "dot-import-shape",
    "underscore",
    "unicode-title",
    "unicode-lower",
    "lower-prefix",
    "receiver",
    "string-and-comment",
    "result",
    "nonpointer",
    "wrongtype",
    "two-params",
    "generics",
    "benchmark",
    "fuzz",
    "main-as-test",
    "main-as-test-discovery-quirk",
    "main-wrapper",
    "bad-main",
    "parse-error",
]
EXPECTED_TESTS = TOP_TESTS + [TOP_TESTS[0] + "/" + name for name in SUB_TESTS]
TEXT_LIMIT = 2 << 20
BOUND = {
    BASE
    / "f05-go01-offline-setup-plan-20261029/amendment-1/setup.py": "06e3eb82f695812f96816c820f61fef1cceb242c636de5980284824948604de0",
    BASE
    / "f05-go01-dependency-preparation-20261029/boundaries.py": "7b03c7ab687043ab23061efde9d6328a21bb6ca94176085c87a50df8265de9e6",
    BASE
    / "f05-go01-collection-driver-20261029/amendment-3/collection.py": "6db7f294c3158129fc75fee991ec436c1838ab0119bd7f7df9026df3d297b3d8",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def bound(path, expected):
    path = Path(path)
    require(
        stat.S_ISREG(path.lstat().st_mode) and file_sha(path) == expected,
        f"changed binding: {path}",
    )
    return path


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def dependencies(plan):
    for path, expected in BOUND.items():
        bound(path, expected)
    setup = module(next(iter(BOUND)), "registry_owned_isolation")
    setup.load_helpers()
    # Extract only the two pure wrappers from the immutable reviewed source.
    source = ast.parse(list(BOUND)[2].read_text())
    nodes = [
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name in {"flags", "inspect"}
    ]
    require(len(nodes) == 2, "missing reviewed isolation wrappers")
    namespace = {"boundary": setup, "require": require}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "reviewed-isolation-functions", "exec"),
        namespace,
    )
    for name, expected in plan["receiverClosure"].items():
        bound(HELPER_AMENDMENT / name, expected)
    sys.modules["build_input"] = module(
        HELPER_AMENDMENT / "build_input.py", "registry_owned_builder"
    )
    receiver = module(HELPER_AMENDMENT / "read_registry.py", "registry_owned_receiver")
    for name, expected in plan["receiverInputs"].items():
        bound(HELPER / name, expected)
    provenance = receiver.builder.load((HELPER / "input-provenance.json").read_bytes())
    require(
        provenance["inputSha256"] == plan["input"]["sha256"]
        and provenance["sourceContext"] == plan["sourceContext"],
        "receiver provenance context",
    )
    bound(
        Path(provenance["packageInventoryPath"]),
        provenance["sourceContext"]["packageInventorySha256"],
    )
    transport = module(HERE / "process_io.py", "registry_owned_transport")
    return namespace, receiver, transport


def load_plan():
    plan = json.loads((HERE / "plan.json").read_text())
    bound(HELPER / "FREEZE.json", BASE_HELPER_FREEZE)
    bound(HELPER_AMENDMENT / "FREEZE.json", HELPER_FREEZE)
    bound(HELPER_AMENDMENT / "plan.json", HELPER_PLAN)
    original = json.loads((HELPER_AMENDMENT / "plan.json").read_text())
    helper_hashes = json.loads((HELPER / "FREEZE.json").read_text())["artifactSha256"]
    receiver_hashes = json.loads((HELPER_AMENDMENT / "FREEZE.json").read_text())["artifactSha256"]
    require(
        plan["identity"] == "go01-owned-source-registry-runtime-v1"
        and plan["commands"] == COMMANDS,
        "runtime identity/commands",
    )
    require(plan["imageId"] == IMAGE and plan["moduleCwd"] == MODULE, "image/module")
    require(
        plan["helperSubject"]
        == {
            "planSha256": HELPER_PLAN,
            "authorFreezeSha256": HELPER_FREEZE,
            "packetIdentity": original["identity"],
        },
        "helper subject",
    )
    require(
        set(plan["moduleFiles"]) == MODULE_FILES and plan["input"] == original["input"],
        "owned module/input boundary",
    )
    require(
        plan["expectedTestIds"] == EXPECTED_TESTS
        and plan["environment"] == original["helperBuildContextProspective"]["environment"],
        "helper tests/context",
    )
    require(plan["sourceContext"] == original["sourceContext"], "target data context changed")
    require(
        set(plan["scripts"])
        == {"runtime.py", "process_io.py", "make_plan.py", "controls.py", "transport_controls.py"},
        "runtime script closure",
    )
    for name, expected in plan["scripts"].items():
        bound(HERE / name, expected)
    for name, descriptor in plan["moduleFiles"].items():
        require(
            descriptor["sha256"]
            == helper_hashes[name]
            == original["helperSourceBindings"][name]["sha256"],
            "module not bound to helper freeze",
        )
        path = bound(HELPER / name, descriptor["sha256"])
        require(path.stat().st_size == descriptor["bytes"], "module byte count")
    require(
        set(plan["receiverClosure"]) == {"read_registry.py", "build_input.py"}
        and plan["receiverInputs"]
        == {"input-provenance.json": helper_hashes["input-provenance.json"]},
        "receiver closure shape",
    )
    for name, expected in plan["receiverClosure"].items():
        require(expected == receiver_hashes[name], "receiver helper freeze binding")
    require(
        plan["limits"]
        == {
            "workSecondsIncludingPreflight": 900,
            "cleanupSeconds": 60,
            "cpus": 3,
            "memoryBytes": 4294967296,
            "memorySwapBytes": 4294967296,
            "pids": 256,
            "workspaceTmpfsBytes": 8589934592,
            "dependencyTmpfsBytes": 1073741824,
            "tmpTmpfsBytes": 536870912,
            "combinedStdoutStderrPerCommandBytes": 2097152,
            "compressedRegistryBytes": 2097152,
            "expandedRegistryBytes": 8388608,
        },
        "changed resource/output limits",
    )
    for key in [
        "executionAuthorized",
        "nativeCollectionOccurred",
        "taskOutcomeObserved",
        "campaignAdmitted",
        "oracleQualified",
        "cacheGloballyQualified",
    ]:
        require(plan[key] is False, "source plan cannot mint admission")
    return plan


def subject(plan):
    require(
        plan == json.loads((HERE / "plan.json").read_text()),
        "provided plan differs from current bytes",
    )
    require(stat.S_ISREG((HERE / "FREEZE.json").lstat().st_mode), "runtime freeze not regular")
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    require(
        frozen["identity"] == plan["identity"]
        and frozen["planSha256"] == file_sha(HERE / "plan.json"),
        "runtime freeze subject",
    )
    for name, expected in {"plan.json": file_sha(HERE / "plan.json"), **plan["scripts"]}.items():
        require(
            frozen["artifactSha256"][name] == expected and file_sha(HERE / name) == expected,
            "runtime closure",
        )
    return {
        "planSha256": file_sha(HERE / "plan.json"),
        "authorFreezeSha256": file_sha(HERE / "FREEZE.json"),
        "packetIdentity": plan["identity"],
    }


def review(descriptor, expected, role):
    path = bound(Path(descriptor["path"]), descriptor["sha256"])
    value = json.loads(path.read_text())
    require(
        value["subject"] == expected
        and value["state"] == f"independent-owned-registry-{role}-review-passed"
        and value["scope"] == "owned-source-registry-only",
        "review subject/state",
    )
    require(
        value["findings"] == [] and value["synthetic"] is False and value["staticOnly"] is True,
        "review did not pass statically",
    )
    for key in [
        "executionAuthorized",
        "nativeTaskAdmitted",
        "campaignAdmitted",
        "oracleQualified",
        "ownedGoTestsExecuted",
        "helperCLIExecuted",
    ]:
        require(value[key] is False, "review scope exceeded")


def authorize(plan, path, output, scratch):
    auth = json.loads(Path(path).read_text())
    current = subject(plan)
    require(
        auth["state"] == "coordinator-authorized-single-owned-registry-attempt"
        and auth["synthetic"] is False,
        "authorization state",
    )
    require(
        auth["runtimeSubject"] == current and auth["helperSubject"] == plan["helperSubject"],
        "authorization subject",
    )
    require(
        auth["output"] == str(output)
        and auth["scratch"] == str(scratch)
        and auth["maxAttempts"] == 1,
        "authorization paths/attempt count",
    )
    require(
        auth["commands"] == plan["commands"]
        and auth["limits"] == plan["limits"]
        and auth["inputSha256"] == plan["input"]["sha256"],
        "authorization commands/limits/input",
    )
    review(auth["runtimeReview"], current, "runtime")
    review(auth["helperReview"], plan["helperSubject"], "helper")
    return auth


def owned_archive(plan):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(MODULE_FILES):
            raw = (HELPER / name).read_bytes()
            require(
                hashlib.sha256(raw).hexdigest() == plan["moduleFiles"][name]["sha256"],
                "module changed before archive",
            )
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.uid, item.gid, item.mtime = len(raw), 0o644, 0, 0, 0
            archive.addfile(item, io.BytesIO(raw))
    return buffer.getvalue()


def check_module_archive(raw, plan):
    require(len(raw) <= TEXT_LIMIT, "module observation cap")
    observed = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            name = member.name.removeprefix("./").rstrip("/")
            if member.isdir():
                require(name in {"", "."}, "unexpected module directory")
                continue
            require(
                member.isfile()
                and not member.sparse
                and name in MODULE_FILES
                and name not in observed,
                "unowned/special module member",
            )
            data = archive.extractfile(member).read(TEXT_LIMIT + 1)
            require(len(data) == member.size and member.mode == 0o644, "module size/mode")
            observed[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    require(observed == plan["moduleFiles"], "owned module tree changed")
    return {"files": len(observed), "manifest": observed}


def unit_outcome(raw, expected):
    events = [
        json.loads(line)
        for line in raw.decode("utf-8", errors="strict").splitlines()
        if line.strip()
    ]
    package = "dotrepo.invalid/go01-source-registry-experiment"
    started, passed = set(), set()
    package_starts = package_passes = 0
    for event in events:
        require(package_passes == 0, "event after package terminal")
        require(
            event.get("Package") == package
            and event["Action"] in {"start", "run", "output", "pass"},
            "owned unit failure/skip/scope",
        )
        name = event.get("Test")
        if name:
            require(name in expected, "unexpected owned test")
            if event["Action"] == "run":
                require(package_starts == 1, "test before package start")
                if "/" in name:
                    require(
                        name.split("/", 1)[0] in started - passed, "child without active parent"
                    )
                require(name not in started, "duplicate test start")
                started.add(name)
            elif event["Action"] == "pass":
                require(name in started and name not in passed, "test terminal mismatch")
                require(
                    all(child in passed for child in expected if child.startswith(name + "/")),
                    "parent before child terminal",
                )
                passed.add(name)
        elif event["Action"] == "start":
            package_starts += 1
        elif event["Action"] == "pass":
            require(started == passed == set(expected), "package before tests complete")
            package_passes += 1
    require(
        started == passed == set(expected) and package_starts == package_passes == 1,
        "incomplete owned unit coverage",
    )
    return {"ownedTestIds": sorted(passed), "ownedTestsPassed": True}


def captured(output, label, receipt, binary_path=None):
    leaf = output / "logs" / label
    values = {}
    for role in ["stdout", "stderr"]:
        path = leaf / f"{role}.bin"
        require(
            path.stat().st_size <= TEXT_LIMIT and file_sha(path) == receipt[role + "Sha256"],
            "raw receipt mismatch",
        )
        values[role] = path.read_bytes()
    size = sum(map(len, values.values()))
    if binary_path is not None:
        require(
            binary_path.stat().st_size == receipt["binaryBytes"]
            and file_sha(binary_path) == receipt["binarySha256"],
            "binary raw receipt mismatch",
        )
        size += binary_path.stat().st_size
        require(values["stdout"] == b"", "binary stdout decoded/duplicated")
    require(size <= TEXT_LIMIT, "combined binary/text output cap")
    return values


def run(
    authorization,
    output,
    scratch,
    *,
    backend=None,
    plan_loader=load_plan,
    authorization_check=authorize,
    clock=time.monotonic,
):
    output, scratch = Path(output).resolve(), Path(scratch).resolve()
    output.mkdir()
    start = clock()
    deadline = start + 900
    result = {
        "state": "incomplete",
        "stage": "preflight",
        "synthetic": backend is not None,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "ownedRegistryOutputObserved": False,
        "ownedCLIAttempted": False,
        "ownedTestsPassed": False,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
        "campaignAdmitted": False,
        "oracleQualified": False,
        "cacheGloballyQualified": False,
        "daemonCalls": 0,
        "containerCreateAttempted": False,
        "containerAbsent": None,
        "costUsd": None,
        "modelCalls": 0,
    }
    write(output / "attempt.json", result)
    name = "dotrepo-owned-registry-" + uuid.uuid4().hex[:12]
    result["ownedContainer"] = name
    created = False
    namespace = receiver = transport = None

    def call(label, argv, *, stdin_path=None, binary_path=None, exits=(0,)):
        require(clock() < deadline, "work deadline exhausted")
        result["stage"] = label
        result["daemonCalls"] += 1
        receipt = backend.command(
            output, label, argv, deadline=deadline, stdin_path=stdin_path, binary_path=binary_path
        )
        if receipt.get("cancelled"):
            raise KeyboardInterrupt(receipt.get("error"))
        require(
            receipt["error"] is None and receipt["exitCode"] in exits,
            label + " failed: " + str(receipt["error"]),
        )
        require(
            receipt["stdinBytes"] == (stdin_path.stat().st_size if stdin_path else 0),
            "stdin count mismatch",
        )
        if stdin_path:
            require(receipt["stdinSha256"] == file_sha(stdin_path), "stdin hash mismatch")
        return receipt, captured(output, label, receipt, binary_path)

    def shell(label, command, **kwargs):
        return call(label, ["docker", "exec", name, "/bin/sh", "-eu", "-c", command], **kwargs)

    try:
        plan = plan_loader()
        result["stage"] = "authorization"
        accepted = authorization_check(plan, authorization, output, scratch)
        result["authorization"] = accepted
        require(
            not scratch.exists()
            and not output.is_relative_to(scratch)
            and not scratch.is_relative_to(output)
            and not output.is_relative_to(BASE)
            and not scratch.is_relative_to(BASE),
            "scratch exists/aliases protected inputs/output",
        )
        scratch.mkdir()
        input_path = bound(Path(plan["input"]["path"]), plan["input"]["sha256"])
        require(input_path.stat().st_size == plan["input"]["bytes"] == 21446036, "input byte bound")
        namespace, receiver, transport = dependencies(plan)
        backend = backend or transport.DockerBackend()
        module_tar = scratch / "owned-module.tar"
        module_tar.write_bytes(owned_archive(plan))
        result.update(
            planSha256=file_sha(HERE / "plan.json"),
            inputSha256=plan["input"]["sha256"],
            moduleTarSha256=file_sha(module_tar),
            moduleTarBytes=module_tar.stat().st_size,
        )
        _, observed = call("image-inspect", ["docker", "image", "inspect", IMAGE])
        image = json.loads(observed["stdout"])[0]
        require(
            image["Id"] == IMAGE
            and image["Os"] == "linux"
            and image["Architecture"] == "arm64"
            and not image["Config"].get("Volumes")
            and not image["Config"].get("OnBuild"),
            "image mismatch",
        )
        require(
            len(image["Config"]["Env"]) == 5
            and set(v.split("=", 1)[0] for v in image["Config"]["Env"])
            == {"PATH", "RUSTUP_HOME", "CARGO_HOME", "GOTOOLCHAIN", "GOENV"},
            "unqualified image environment",
        )
        environment = {
            **dict(v.split("=", 1) for v in image["Config"]["Env"]),
            **plan["environment"],
        }
        result["containerCreateAttempted"] = created = True
        _, created_raw = call("create", namespace["flags"](name, plan["environment"]))
        container_id = created_raw["stdout"].decode("ascii", errors="strict").strip()
        require(
            len(container_id) == 64 and all(c in "0123456789abcdef" for c in container_id),
            "create container identity",
        )
        call("start", ["docker", "start", name])
        _, inspected = call("inspect-before", ["docker", "inspect", name])
        inspected_row = json.loads(inspected["stdout"])[0]
        require(
            inspected_row["Id"] == container_id and inspected_row["Name"] == "/" + name,
            "inspected container identity",
        )
        namespace["inspect"](inspected_row, environment)
        shell(
            "initialize",
            f"test ! -e {MODULE}; mkdir {MODULE}; mkdir /workspace/home /workspace/tmp /workspace/owned-bin; test ! -e /workspace/owned-go-build; test ! -e /workspace/owned-go-mod; test ! -e /workspace/owned-go-path",
        )
        call(
            "module-provision",
            ["docker", "exec", "-i", name, "tar", "--extract", "--no-same-owner", "-C", MODULE],
            stdin_path=module_tar,
        )
        for phase in ["before", "after"]:
            _, tools = shell("tools-" + phase, "sha256sum /usr/local/go/bin/go")
            require(
                tools["stdout"].decode() == GO_SHA + "  /usr/local/go/bin/go\n",
                "Go binary mismatch",
            )
            module_observation = output / f"module-{phase}.tar"
            shell(
                "module-" + phase,
                f"tar --create --format=ustar -C {MODULE} .",
                binary_path=module_observation,
            )
            write(
                output / f"module-{phase}.json",
                check_module_archive(module_observation.read_bytes(), plan),
            )
            if phase == "after":
                break
            _, tests = shell("owned-tests", f"cd {MODULE}; " + COMMANDS[0])
            result.update(unit_outcome(tests["stdout"], plan["expectedTestIds"]))
            shell("owned-build", f"cd {MODULE}; " + COMMANDS[1])
            _, binary = shell("owned-binary-sha", "sha256sum /workspace/owned-bin/registry")
            result["ownedBinaryShaObservation"] = binary["stdout"].decode("ascii", errors="strict")
            wire_path = output / "registry.gz"
            result["ownedCLIAttempted"] = True
            cli, raw = call(
                "owned-cli",
                ["docker", "exec", "-i", name, COMMANDS[2]],
                stdin_path=input_path,
                binary_path=wire_path,
                exits=(0, 1),
            )
            require(raw["stderr"] == b"", "helper stderr")
            expanded = receiver.inflate(wire_path.read_bytes())
            value = receiver.builder.load(expanded)
            provenance = receiver.builder.load(
                bound(
                    HELPER / "input-provenance.json",
                    plan["receiverInputs"]["input-provenance.json"],
                ).read_bytes()
            )
            packages_path = bound(
                Path(provenance["packageInventoryPath"]),
                provenance["sourceContext"]["packageInventorySha256"],
            )
            received = receiver.validate(
                value, provenance, receiver.builder.load(packages_path.read_bytes())
            )
            require(
                cli["exitCode"] == (1 if received["hasSourceDiagnostics"] else 0),
                "helper exit disagrees with source diagnostics",
            )
            write(
                output / "received.json",
                {
                    **received,
                    "wireSha256": file_sha(wire_path),
                    "wireBytes": wire_path.stat().st_size,
                    "expandedBytes": len(expanded),
                    "jsonSha256": hashlib.sha256(expanded).hexdigest(),
                },
            )
            result["ownedRegistryOutputObserved"] = True
            result.update(
                registryState=value["state"],
                hasSourceDiagnostics=received["hasSourceDiagnostics"],
                ownedCLIExitCode=cli["exitCode"],
                targetCompileValidityUnestablished=True,
            )
        _, inspected = call("inspect-after", ["docker", "inspect", name])
        inspected_row = json.loads(inspected["stdout"])[0]
        require(
            inspected_row["Id"] == container_id and inspected_row["Name"] == "/" + name,
            "inspected container identity",
        )
        namespace["inspect"](inspected_row, environment)
        bound(input_path, plan["input"]["sha256"])
        require(clock() < deadline, "work deadline exhausted after observations")
        result.update(
            state="owned-helper-observed-uncompiled-source-registry",
            stage="observed",
            sourceToolsBeforeAfterMatched=True,
        )
    except BaseException as exc:
        result.update(
            error=f"{type(exc).__name__}: {exc}",
            cancelled=isinstance(exc, (KeyboardInterrupt, SystemExit)),
        )
    finally:
        if created:
            cleanup_start = clock()
            cleanup_deadline = cleanup_start + 60
            cleanup = {}
            for label, argv in [
                ("cleanup", ["docker", "rm", "-f", name]),
                ("post-cleanup-inspect", ["docker", "inspect", name]),
                (
                    "post-cleanup-list",
                    ["docker", "ps", "-a", "--filter", "name=" + name, "--format", "{{.Names}}"],
                ),
            ]:
                try:
                    result["daemonCalls"] += 1
                    receipt = backend.command(output, label, argv, deadline=cleanup_deadline)
                    cleanup[label] = {"receipt": receipt, "raw": captured(output, label, receipt)}
                except BaseException as exc:
                    cleanup[label] = {"error": f"{type(exc).__name__}: {exc}"}
            remove, inspect, names = [
                cleanup.get(k, {}) for k in ["cleanup", "post-cleanup-inspect", "post-cleanup-list"]
            ]
            result["containerAbsent"] = bool(
                remove.get("receipt", {}).get("exitCode") == 0
                and not remove.get("receipt", {}).get("error")
                and inspect.get("receipt", {}).get("exitCode") == 1
                and inspect.get("receipt", {}).get("error") is None
                and inspect.get("raw", {}).get("stdout", b"x").strip() == b"[]"
                and b"no such object" in inspect.get("raw", {}).get("stderr", b"").lower()
                and names.get("receipt", {}).get("exitCode") == 0
                and not names.get("receipt", {}).get("error")
                and not names.get("raw", {}).get("stdout", b"x").strip()
            )
            result["cleanupSeconds"] = clock() - cleanup_start
            if not result["containerAbsent"]:
                result.update(state="incomplete", cleanupUnresolved=True)
        result["elapsedSeconds"] = clock() - start
        result["workBudgetExceeded"] = (
            result["elapsedSeconds"] - result.get("cleanupSeconds", 0) > 900
        )
        receipts = (
            {
                str(path.relative_to(output)): json.loads(path.read_text())
                for path in sorted((output / "logs").glob("*/receipt.json"))
            }
            if (output / "logs").exists()
            else {}
        )
        write(output / "trace.json", {"receipts": receipts, "synthetic": result["synthetic"]})
        write(output / "result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args()
    if not args.authorization:
        print(json.dumps({"state": "source-only-not-authorized", "plan": load_plan()}, indent=2))
    else:
        require(args.output is not None and args.scratch is not None, "output/scratch required")
        result = run(args.authorization, args.output, args.scratch)
        print(json.dumps(result, indent=2))
        raise SystemExit(
            0 if result["state"] == "owned-helper-observed-uncompiled-source-registry" else 1
        )
