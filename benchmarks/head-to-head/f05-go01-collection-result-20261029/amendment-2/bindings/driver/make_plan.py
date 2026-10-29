"""Build source-only driver metadata; never calls a daemon or upstream command."""

import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
BASE = Path("/Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head")
NEXT = BASE / "f05-go01-next-qualification-20261029"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    decision_source = Path("/tmp/dotrepo-go01-collection-compiler-context-decision-20261029.json")
    assert (
        sha(decision_source) == "4a69508169da7432b0cac04cb1717d91d388ff755f47bf8f8f925e3516242e91"
    )
    decision = HERE / "compiler-context-decision.json"
    decision.write_bytes(decision_source.read_bytes())
    retrospective = HERE / "tmpfs-retrospective.json"
    retrospective.write_bytes(
        Path("/tmp/dotrepo-go01-setup-tmpfs-retrospective-check-20261029.json").read_bytes()
    )
    parent = json.loads((NEXT / "plan.json").read_text())
    projection = NEXT / "go-only-projection-1"
    spec = json.loads((projection / "projection-spec.json").read_text())
    environment = {**parent["environment"], "CC": "/usr/bin/gcc", "CXX": "/usr/bin/g++"}
    canonical_environment = (
        json.dumps(environment, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    inventory_path = BASE / "f05-common-image-audit-20261029/inventory.json"
    inventory = json.loads(inventory_path.read_text())["files"]
    tools = [
        "usr/local/go/bin/go",
        "usr/local/bin/node",
        "usr/bin/aarch64-linux-gnu-gcc-12",
        "usr/bin/aarch64-linux-gnu-g++-12",
    ]
    assert all(inventory[path]["type"] == "0" for path in tools)
    paths = [
        HERE.parent / "FREEZE.json",
        HERE.parent / "amendment-1/FREEZE.json",
        HERE.parent / "amendment-2/FREEZE.json",
        BASE / "f05-go01-collection-driver-review-20261029/amendment-2/FREEZE.json",
        BASE / "f05-go01-collection-driver-review-20261029/amendment-1/FREEZE.json",
        *sorted((HERE / "sources").rglob("*.go")),
        BASE / "f05-go01-collection-driver-review-20261029/FREEZE.json",
        BASE / "f05-go01-offline-setup-result-20261029/evidence/logs/container-inspect/stdout.bin",
        BASE
        / "f05-go01-offline-setup-result-20261029/evidence/logs/offline-final-inspect/stdout.bin",
        NEXT / "freeze.json",
        NEXT / "plan.json",
        NEXT / "input-bindings.json",
        projection / "freeze.json",
        projection / "projection-spec.json",
        projection / "inventory.json",
        projection / "provenance.json",
        inventory_path,
        BASE / "f05-go01-next-qualification-review-20261029/FREEZE.json",
        BASE / "f05-go01-offline-setup-plan-20261029/amendment-1/setup.py",
        BASE / "f05-go01-offline-setup-plan-20261029/amendment-1/freeze.json",
        BASE / "f05-go01-offline-setup-review-20261029/amendment-1/FREEZE.json",
    ]
    bindings = {str(path): sha(path) for path in paths}
    bindings.update(json.loads((NEXT / "input-bindings.json").read_text()))
    plan = {
        "identity": "go01-collection-driver-amendment-3",
        "amendsAuthorFreezeSha256": "a922cea56e81f471b1a6cd69ec576abcde7b9dd67aed246cb745e3432531196e",
        "beforeReviewFreezeSha256": "cf79a5349dae67b0862322a7632c1c8735c1f87612a68ab7cfda889a3eff10fb",
        "state": "source-only-driver-proposal-not-admitted",
        "parentPlanSha256": sha(NEXT / "plan.json"),
        "parentFreezeSha256": sha(NEXT / "freeze.json"),
        "repository": parent["repository"],
        "revision": parent["revision"],
        "imageId": parent["imageId"],
        "sourceArchiveSha256": parent["sourceArchiveSha256"],
        "commands": [row["command"] for row in parent["commandsInOrder"]],
        "cwd": parent["collectionCwd"],
        "limits": parent["limits"],
        "environment": environment,
        "environmentSha256": hashlib.sha256(canonical_environment).hexdigest(),
        "environmentCanonicalEncoding": "UTF8 JSON sorted keys compact separators plus newline",
        "expectedGoEnv": {
            "GOOS": "linux",
            "GOARCH": "arm64",
            "GOVERSION": "go1.27.3",
            "GOTOOLCHAIN": "local",
            "GOENV": "",
            "GOWORK": "/workspace/repository/go.work",
            "GOFLAGS": "-p=1 -count=1",
            "CGO_ENABLED": "1",
            "CC": "/usr/bin/gcc",
            "CXX": "/usr/bin/g++",
        },
        "explicitlyAbsentEnvironment": parent["explicitlyAbsentEnvironment"],
        "compilerContextDecisionSha256": sha(decision),
        "contextAmendment": "Prospective explicit CC/CXX selected from audited image; no observation of Go defaults; any later target qualification requires matching context/epoch",
        "projection": spec,
        "projectionSpecSha256": sha(projection / "projection-spec.json"),
        "collectionScopeReview": {
            "path": str(BASE / "f05-go01-next-qualification-review-20261029/FREEZE.json"),
            "sha256": "46211cce106432c48f87f5d47882810d39e32d81742aee8ed7f66038ca88915c",
        },
        "projectionFreezeSha256": sha(projection / "freeze.json"),
        "projectionAdmission": "UNRESOLVED separate independent review and collection-only coordinator acceptance required",
        "toolProbe": "sha256sum " + " ".join("/" + path for path in tools),
        "expectedToolOutput": "".join(
            inventory[path]["sha256"] + "  /" + path + "\n" for path in tools
        ),
        "treeObservation": "node -e " + shlex.quote((HERE / "tree-observer.js").read_text()),
        "sourceTreeRule": "Complete path/type/file-byte before and after digest/counts must match validated source archive; all outputs/build cache/tmp outside repository. Snapshot observations, not a proof of immutability between observations.",
        "listingRule": "Exact module prefix, mandatory known packages, unique full inventory incl no-test packages; full top-level listing terminals for every package; no task/body/subtest/fuzz-seed success inferred",
        "executionAuthorized": False,
        "cacheAdmissionSatisfied": False,
        "nativeTaskAdmitted": False,
        "taskOutcomeObserved": False,
        "campaignAdmitted": False,
        "cacheGloballyQualified": False,
        "requiredBeforeAuthorization": [
            "Independent driver/scope/projection reviews",
            "Explicit collection-only source/init/TestMain/no-npm acceptance",
            "Fresh one-attempt authorization matching this successor plan/output/scratch",
            "No retries/task/filter/cache/network/resource substitution",
        ],
        "scripts": {
            name: sha(HERE / name)
            for name in [
                "collection.py",
                "listing.py",
                "process_io.py",
                "tree-observer.js",
                "controls.py",
                "make_plan.py",
                "transport_controls.py",
                "observer_controls.py",
                "amendment_controls.py",
                "goenv_controls.py",
                "testonly_controls.py",
            ]
        },
        "localFiles": {
            "compiler-context-decision.json": sha(decision),
            "tmpfs-retrospective.json": sha(retrospective),
            "goenv-source-semantics.json": sha(HERE / "goenv-source-semantics.json"),
            "actual-go-env-stdout.bin": sha(HERE / "actual-go-env-stdout.bin"),
            "actual-go-env-receipt.json": sha(HERE / "actual-go-env-receipt.json"),
            "test-only-source-semantics.json": sha(HERE / "test-only-source-semantics.json"),
            "actual-go-list-stdout.bin": sha(HERE / "actual-go-list-stdout.bin"),
            "actual-go-list-receipt.json": sha(HERE / "actual-go-list-receipt.json"),
        },
        "bindings": bindings,
    }
    (HERE / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (HERE / "authorization-template.json").write_text(
        json.dumps(
            {
                "state": "NOT_AUTHORIZED",
                "synthetic": True,
                "planSha256": sha(HERE / "plan.json"),
                "authorFreezeSha256": "UNRESOLVED_FUTURE_AUTHOR_FREEZE",
                "output": "/ABSOLUTE/FRESH/OUTPUT",
                "scratch": "/ABSOLUTE/FRESH/SCRATCH",
                "commands": plan["commands"],
                "limits": plan["limits"],
                "maxAttempts": 1,
                "collectionAcceptance": {
                    "path": "/MISSING/INDEPENDENT/ACCEPTANCE",
                    "sha256": "UNRESOLVED",
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "planSha256": sha(HERE / "plan.json"),
                "environmentSha256": plan["environmentSha256"],
                "projectionBoundButUnadmitted": True,
            }
        )
    )


if __name__ == "__main__":
    main()
