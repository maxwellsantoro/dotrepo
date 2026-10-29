"""Construct only the prospective owned-helper runtime contract."""

import json
from pathlib import Path

import runtime

HERE = Path(__file__).resolve().parent
original = json.loads((runtime.HELPER_AMENDMENT / "plan.json").read_text())
hashes = json.loads((runtime.HELPER / "FREEZE.json").read_text())["artifactSha256"]
receiver_hashes = json.loads((runtime.HELPER_AMENDMENT / "FREEZE.json").read_text())[
    "artifactSha256"
]
plan = {
    "identity": "go01-owned-source-registry-runtime-v1",
    "state": "source-only-runtime-proposal-not-authorized",
    "helperSubject": {
        "planSha256": runtime.HELPER_PLAN,
        "authorFreezeSha256": runtime.HELPER_FREEZE,
        "packetIdentity": original["identity"],
    },
    "imageId": runtime.IMAGE,
    "moduleCwd": runtime.MODULE,
    "commands": runtime.COMMANDS,
    "commandPathAmendment": "Final runtime reuses helper proposal paths exactly; initial root-declared /workspace/registry development alternative was superseded before freeze.",
    "moduleFiles": {
        name: {"sha256": hashes[name], "bytes": (runtime.HELPER / name).stat().st_size}
        for name in sorted(runtime.MODULE_FILES)
    },
    "input": original["input"],
    "sourceContext": original["sourceContext"],
    "environment": original["helperBuildContextProspective"]["environment"],
    "contextRule": "Helper CGO0/GOWORKoff/offline environment is distinct from retained target selection context, which is input data only; no Go env query.",
    "expectedTestIds": runtime.EXPECTED_TESTS,
    "receiverClosure": {
        name: receiver_hashes[name] for name in ["build_input.py", "read_registry.py"]
    },
    "receiverInputs": {"input-provenance.json": hashes["input-provenance.json"]},
    "limits": {
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
    "scripts": {
        name: runtime.file_sha(HERE / name)
        for name in [
            "runtime.py",
            "process_io.py",
            "make_plan.py",
            "controls.py",
            "transport_controls.py",
        ]
    },
    "reusedBindings": {str(path): expected for path, expected in runtime.BOUND.items()},
    "transportSourceSha256": "2b312dad157e536a21733ed05c54b9715b3e6d2d60e50e62249c96da13dd2b6b",
    "transportAmendment": "Binary/text combined accounting tightened and cancellation kills client before finally wait; binary bytes and stderr share2MiB combined stream ceiling. Receiver unchanged at2MiB compressed/8MiB expanded. Binary stdout never UTF8-decoded.",
    "positiveReviewBindings": "PENDING independent helper and runtime static pass objects; external to author plan/freezes, required by fresh root authorization.",
    "executionAuthorized": False,
    "nativeCollectionOccurred": False,
    "taskOutcomeObserved": False,
    "campaignAdmitted": False,
    "oracleQualified": False,
    "cacheGloballyQualified": False,
}
with (HERE / "plan.json").open("x") as stream:
    json.dump(plan, stream, indent=2, allow_nan=False)
    stream.write("\n")
print(
    json.dumps(
        {"state": "source-only-plan-written", "planSha256": runtime.file_sha(HERE / "plan.json")},
        indent=2,
    )
)
