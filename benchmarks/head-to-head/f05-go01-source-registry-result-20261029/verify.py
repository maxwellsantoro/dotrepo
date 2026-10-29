"""Audit retained owned-helper receipts/output using only frozen pure functions."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RUNTIME = BASE / "f05-go01-source-registry-runtime-20261029"
RUNTIME_SHA = "3cc19c30e914b29aef5032204b60deb1c44112e0a6a380449a7dfa24fb6f1177"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if sha(RUNTIME / "runtime.py") != RUNTIME_SHA:
    raise ValueError("changed frozen runtime before pure-function import")
spec = importlib.util.spec_from_file_location(
    "retained_owned_registry_runtime", RUNTIME / "runtime.py"
)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
require = r.require


def load(root, name):
    return json.loads((root / name).read_text())


def closure(root):
    for row in load(root, "origin-ledger.json")["files"]:
        path = root / row["retained"]
        require(path.resolve().is_relative_to(root.resolve()), "copy path escapes")
        require(
            path.stat().st_size == row["bytes"] and r.bound(path, row["sha256"]),
            "retained copy changed",
        )
    original = load(root, "evidence/FREEZE.json")
    require(
        sha(root / "evidence/FREEZE.json")
        == "1ea59ba97218067be4bef04852d2063a25063531b6ceca0de88c83a6d07f5770",
        "actual result freeze",
    )
    require(len(original["artifacts"]) == 63, "original artifact count")
    for name, value in original["artifacts"].items():
        path = root / "evidence" / name
        require(
            sha(path) == value["sha256"] and path.stat().st_size == value["bytes"],
            "actual artifact changed",
        )
    require(len(load(root, "origin-ledger.json")["files"]) == 84, "copied origin count")
    plan = r.load_plan()
    auth = load(root, "authorization/authorization.json")
    for name, value in load(root, "authorization/FREEZE.json")["artifacts"].items():
        require(sha(root / "authorization" / name) == value["sha256"], "authorization freeze")
    require(
        sha(root / "authorization/authorization.json")
        == "e719ff5e43b4ab30209a6ae5735ea6ae59def07e449a4e0250c786eb3393d4c3",
        "actual authorization",
    )
    r.authorize(
        plan, root / "authorization/authorization.json", Path(auth["output"]), Path(auth["scratch"])
    )
    for value in auth["fullClosuresVerified"].values():
        path = r.bound(Path(value["path"]), value["sha256"])
        frozen = json.loads(path.read_text())
        entries = frozen.get("artifactSha256", frozen.get("artifacts"))
        require(len(entries) == value["verifiedArtifacts"], "bound source/review artifact count")
        for name, descriptor in entries.items():
            expected = descriptor if isinstance(descriptor, str) else descriptor["sha256"]
            r.bound(path.parent / name, expected)
    return plan, auth


def observations(root, plan, auth):
    result = load(root, "evidence/result.json")
    require(load(root, "outer/driver.log") == result, "outer result differs")
    require(
        result["authorization"] == auth and result["planSha256"] == sha(RUNTIME / "plan.json"),
        "actual plan/authorization",
    )
    require(
        result["state"] == "owned-helper-observed-uncompiled-source-registry"
        and result["synthetic"] is False,
        "owned observation state",
    )
    require(
        result["ownedRegistryOutputObserved"] is True
        and result["ownedCLIAttempted"] is True
        and result["ownedTestsPassed"] is True,
        "owned observation flags",
    )
    for key in [
        "nativeCollectionOccurred",
        "taskOutcomeObserved",
        "campaignAdmitted",
        "oracleQualified",
        "cacheGloballyQualified",
    ]:
        require(result[key] is False, "target admission overclaim")
    require(
        result["costUsd"] is None
        and result["modelCalls"] == 0
        and result["workBudgetExceeded"] is False,
        "cost/model/budget",
    )
    trace = load(root, "evidence/trace.json")["receipts"]
    labels = {
        "image-inspect",
        "create",
        "start",
        "inspect-before",
        "initialize",
        "module-provision",
        "tools-before",
        "module-before",
        "owned-tests",
        "owned-build",
        "owned-binary-sha",
        "owned-cli",
        "tools-after",
        "module-after",
        "inspect-after",
        "cleanup",
        "post-cleanup-inspect",
        "post-cleanup-list",
    }
    require(
        set(trace) == {f"logs/{name}/receipt.json" for name in labels}
        and result["daemonCalls"] == len(trace) == 18,
        "actual call set",
    )
    stdin_bytes = output_bytes = 0
    raw = {}
    for name, receipt in trace.items():
        label = name.split("/")[1]
        require(load(root, "evidence/" + name) == receipt, "trace/receipt mismatch")
        binary = (
            root
            / "evidence"
            / (
                {
                    "module-before": "module-before.tar",
                    "module-after": "module-after.tar",
                    "owned-cli": "registry.gz",
                }[label]
            )
            if label in {"module-before", "module-after", "owned-cli"}
            else None
        )
        streams = r.captured(root / "evidence", label, receipt, binary)
        raw[label] = streams
        require(
            receipt["exitCode"] == (1 if label == "post-cleanup-inspect" else 0)
            and receipt["error"] is None
            and receipt["cancelled"] is False,
            "actual command failure",
        )
        require(receipt["costUsd"] is None, "invented command cost")
        if binary:
            expected_name = {
                "module-before": "module-before.tar",
                "module-after": "module-after.tar",
                "owned-cli": "registry.gz",
            }[label]
            require(
                receipt["binaryPath"] == auth["output"] + "/" + expected_name,
                "binary path identity",
            )
        stdin_bytes += receipt["stdinBytes"]
        output_bytes += sum(map(len, streams.values())) + (binary.stat().st_size if binary else 0)
    namespace, receiver, _ = r.dependencies(plan)
    name = result["ownedContainer"]
    container_id = raw["create"]["stdout"].decode().strip()
    require(
        trace["logs/create/receipt.json"]["argv"] == namespace["flags"](name, plan["environment"]),
        "actual create arguments",
    )
    image = json.loads(raw["image-inspect"]["stdout"])[0]
    require(
        image["Id"] == plan["imageId"]
        and image["Os"] == "linux"
        and image["Architecture"] == "arm64",
        "image platform",
    )
    environment = {**dict(v.split("=", 1) for v in image["Config"]["Env"]), **plan["environment"]}
    for phase in ["before", "after"]:
        inspected = json.loads(raw["inspect-" + phase]["stdout"])[0]
        require(
            inspected["Id"] == container_id and inspected["Name"] == "/" + name, "inspect identity"
        )
        namespace["inspect"](inspected, environment)
        require(
            raw["tools-" + phase]["stdout"].decode() == r.GO_SHA + "  /usr/local/go/bin/go\n",
            "Go tool bytes",
        )
        module = r.check_module_archive((root / f"evidence/module-{phase}.tar").read_bytes(), plan)
        require(
            module == load(root, f"evidence/module-{phase}.json"), "module observation mismatch"
        )
    for label, command in zip(["owned-tests", "owned-build"], r.COMMANDS[:2], strict=True):
        require(
            trace[f"logs/{label}/receipt.json"]["argv"]
            == ["docker", "exec", name, "/bin/sh", "-eu", "-c", f"cd {r.MODULE}; " + command],
            "owned Go command changed",
        )
    require(
        trace["logs/owned-cli/receipt.json"]["argv"]
        == ["docker", "exec", "-i", name, r.COMMANDS[2]],
        "owned CLI command changed",
    )
    units = r.unit_outcome(raw["owned-tests"]["stdout"], plan["expectedTestIds"])
    require(
        units["ownedTestIds"] == result["ownedTestIds"] and len(units["ownedTestIds"]) == 29,
        "owned unit case identity",
    )
    module_raw = r.owned_archive(plan)
    module_receipt = trace["logs/module-provision/receipt.json"]
    require(
        module_receipt["stdinSha256"]
        == hashlib.sha256(module_raw).hexdigest()
        == result["moduleTarSha256"]
        and module_receipt["stdinBytes"] == len(module_raw) == result["moduleTarBytes"],
        "owned-only module provisioning",
    )
    cli = trace["logs/owned-cli/receipt.json"]
    require(
        cli["stdinBytes"] == plan["input"]["bytes"] == 21446036
        and cli["stdinSha256"] == plan["input"]["sha256"],
        "exact data-only stdin",
    )
    require(
        raw["owned-cli"]["stderr"] == b"" and raw["owned-build"]["stderr"] == b"",
        "unexpected owned stderr",
    )
    wire = (root / "evidence/registry.gz").read_bytes()
    expanded = receiver.inflate(wire)
    registry = receiver.builder.load(expanded)
    provenance = receiver.builder.load((root / "bindings/input-provenance.json").read_bytes())
    packages = receiver.builder.load((root / "bindings/native/package-inventory.json").read_bytes())
    require(
        sha(root / "bindings/native/package-inventory.json")
        == "764fa272f1c461f4ecc2d6e2b58d641cc65c8e64da23f55981fa12b70c75bc21",
        "native inventory source binding",
    )
    received = receiver.validate(registry, provenance, packages)
    received.update(
        wireSha256=sha(root / "evidence/registry.gz"),
        wireBytes=len(wire),
        expandedBytes=len(expanded),
        jsonSha256=hashlib.sha256(expanded).hexdigest(),
    )
    require(
        received == load(root, "evidence/received.json")
        and received["packages"] == 104
        and received["declarations"] == 6031
        and received["hasSourceDiagnostics"] is False,
        "receiver observation differs",
    )
    require(
        registry["state"] == result["registryState"] == "source-derived-uncompiled"
        and result["targetCompileValidityUnestablished"] is True,
        "source registry validity",
    )
    require(
        raw["owned-binary-sha"]["stdout"].decode("ascii") == result["ownedBinaryShaObservation"],
        "owned binary hash observation",
    )
    require(
        result["containerAbsent"] is True and result["sourceToolsBeforeAfterMatched"] is True,
        "integrity/cleanup result",
    )
    require(
        json.loads(raw["post-cleanup-inspect"]["stdout"]) == []
        and b"no such object" in raw["post-cleanup-inspect"]["stderr"]
        and raw["post-cleanup-list"]["stdout"] == b"",
        "same-attempt absence",
    )
    require(result["elapsedSeconds"] < 960 and result["cleanupSeconds"] < 60, "time bounds")
    comparator_path = r.HELPER_AMENDMENT / "crosscheck_registry.py"
    r.bound(
        comparator_path,
        load(root, "bindings/helper-plan.json")["receiverAmendment"]["crosscheckSha256"],
    )
    sys.modules["read_registry"] = receiver
    comparator = r.module(comparator_path, "retained_registry_comparator")
    observations = receiver.builder.load(
        (root / "bindings/partial-listing-observations.json").read_bytes()
    )
    require(
        sha(root / "bindings/native/FREEZE.json") == observations["resultFreezeSha256"],
        "native result freeze binding",
    )
    native_freeze = load(root, "bindings/native/FREEZE.json")
    for retained, original in [
        ("package-inventory.json", "evidence/package-inventory.json"),
        ("listing-stdout.bin", "evidence/logs/go-test-list/stdout.bin"),
    ]:
        require(
            sha(root / "bindings/native" / retained) == native_freeze["artifactSha256"][original],
            "native original artifact binding",
        )
    native_raw = (root / "bindings/native/listing-stdout.bin").read_bytes()
    require(
        hashlib.sha256(native_raw).hexdigest() == observations["rawEventsSha256"],
        "raw native events binding",
    )
    outputs, terminals = {name: "" for name in packages}, {}
    for line in native_raw.splitlines():
        event = receiver.builder.load(line)
        require(not event.get("Test"), "unexpected native test-body event")
        if event["Action"] == "output":
            outputs[event["Package"]] += event.get("Output", "")
        if event["Action"] in ["pass", "fail", "skip"]:
            require(event["Package"] not in terminals, "duplicate native terminal")
            terminals[event["Package"]] = event["Action"]
    require(
        len(native_raw.splitlines()) == 732 and set(terminals) == set(packages),
        "native package/event coverage",
    )
    rebuilt = {}
    for name, status in sorted(terminals.items()):
        rebuilt[name] = {
            "nativeListingTerminal": status,
            "observedNameLines": [
                line
                for line in outputs[name].splitlines()
                if line.startswith(("Test", "Benchmark", "Fuzz", "Example"))
            ],
            "noTestFilesDiagnostic": "[no test files]" in outputs[name],
            "selectedTestSourceFiles": len(packages[name].get("TestGoFiles", []))
            + len(packages[name].get("XTestGoFiles", [])),
            "comparisonRole": "positive-partial-listing"
            if status == "pass"
            else "empty-no-test-diagnostic"
            if status == "skip"
            else "source-only-not-validated-live",
        }
    require(
        rebuilt == observations["packages"],
        "partial observations differ from full raw native events",
    )
    compared = comparator.compare(registry, observations)
    compared.update(
        registryJsonSha256=hashlib.sha256(expanded).hexdigest(),
        partialObservationsSha256=sha(root / "bindings/partial-listing-observations.json"),
    )
    require(compared == load(root, "partial-crosscheck.json"), "partial comparison differs")
    require(
        len(compared["matchedPassPackages"]) == 25
        and len(compared["matchedNoTestPackages"]) == 18
        and len(compared["unvalidatedFailedPackages"]) == 61
        and compared["differences"] == [],
        "partial comparison scope",
    )
    diagnostics = load(root, "full-diagnostics.json")
    require(
        diagnostics["packages"]
        == [
            {
                "importPath": row["importPath"],
                "state": row["state"],
                "compileValidityUnestablished": row["compileValidityUnestablished"],
                "declarationCounts": {field: len(row[field]) for field in receiver.FIELDS},
                "diagnostics": row["diagnostics"],
            }
            for row in registry["packages"]
        ],
        "full diagnostics changed",
    )
    require(
        diagnostics["globalDiagnostics"] == [] and diagnostics["diagnosticCount"] == 0,
        "global diagnostics changed",
    )
    report = load(root, "report.json")
    for key in [
        "targetCompileValidityEstablished",
        "nativeCollectionOccurred",
        "nativeTaskExecuted",
        "taskOutcomeObserved",
        "oracleQualified",
        "collectionGateChanged",
        "campaignAdmitted",
        "cacheGloballyQualified",
    ]:
        require(report[key] is False, "derived report admission overclaim")
    require(
        report["partialCrosscheck"]["unvalidatedFailedPackages"] == 61
        and report["partialCrosscheck"]["differences"] == 0,
        "derived partial report overclaim",
    )
    require(
        report["effort"]["costUsd"] is None
        and report["cleanup"]["independentAbsenceObservation"] is False,
        "derived evidence overclaim",
    )
    counts = Counter(
        declaration["kind"]
        for row in registry["packages"]
        for field in receiver.FIELDS
        for declaration in row[field]
    )
    return (
        {
            "state": "verified-owned-helper-observation-uncompiled-unqualified",
            "ownedTestIds": len(units["ownedTestIds"]),
            "packages": 104,
            "declarations": 6031,
            "declarationCounts": dict(counts),
            "sourceDiagnostics": [],
            "partialMatchedPassPackages": 25,
            "partialMatchedNoTestPackages": 18,
            "unvalidatedFailedPackages": 61,
            "partialDifferences": [],
            "wireSha256": received["wireSha256"],
            "wireBytes": len(wire),
            "expandedSha256": received["jsonSha256"],
            "expandedBytes": len(expanded),
            "daemonCalls": 18,
            "stdinBytes": stdin_bytes,
            "outputBytesIncludingBinary": output_bytes,
            "elapsedSeconds": result["elapsedSeconds"],
            "costUsd": None,
            "nativeCollectionOccurred": False,
            "targetCompileValidityEstablished": False,
            "taskOutcomeObserved": False,
            "oracleQualified": False,
            "campaignAdmitted": False,
            "independentAbsenceObservation": False,
        },
        expanded,
        registry,
    )


def verify(root):
    plan, auth = closure(root)
    report, _, _ = observations(root, plan, auth)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(verify(HERE), indent=2, allow_nan=False))
