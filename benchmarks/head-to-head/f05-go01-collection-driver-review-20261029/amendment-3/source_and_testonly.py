"""Independent selected-source/fixture/current-review data checks; no native calls."""

import ast
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
binding = json.loads((HERE / "author-binding.json").read_text())
AUTHOR = Path(binding["freeze"]).parent
ROOT = AUTHOR.parents[3]
PARENT = AUTHOR.parent / "amendment-2"
sys.path.insert(0, binding["scriptCopy"])
collection = importlib.import_module("collection")
controls = importlib.import_module("controls")
listing = importlib.import_module("listing")


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def refused(operation):
    try:
        operation()
    except (ValueError, KeyError, TypeError):
        return True
    raise AssertionError("unexpected admission")


class NormalizeCollection(ast.NodeTransformer):
    def visit_Constant(self, node):
        if node.value == "go01-collection-driver-amendment-3":
            node.value = "go01-collection-driver-amendment-2"
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in {"SCRIPT_NAMES", "LOCAL_NAMES"}:
            remove = (
                {"testonly_controls.py"}
                if target.id == "SCRIPT_NAMES"
                else {
                    "test-only-source-semantics.json",
                    "actual-go-list-stdout.bin",
                    "actual-go-list-receipt.json",
                }
            )
            node.value.elts = [v for v in node.value.elts if v.value not in remove]
        return node


def main():
    semantics = json.loads((AUTHOR / "test-only-source-semantics.json").read_text())
    image = ROOT / semantics["imageInventory"]["path"]
    assert sha(image) == semantics["imageInventory"]["sha256"]
    image_files = json.loads(image.read_text())["files"]
    spans = []
    for span in semantics["toolSourceSpans"]:
        path = AUTHOR / "sources" / span["path"]
        data = path.read_bytes()
        assert sha(path) == span["sha256"] == image_files[span["path"]]["sha256"]
        assert len(data) == image_files[span["path"]]["size"]
        assert (
            "".join(
                data.decode().splitlines(keepends=True)[span["startLine"] - 1 : span["endLine"]]
            )
            == span["excerpt"]
        )
        spans.append(
            {
                "path": span["path"],
                "startLine": span["startLine"],
                "endLine": span["endLine"],
                "bound": True,
            }
        )
    build = (AUTHOR / "sources/usr/local/go/src/go/build/build.go").read_text()
    assert (
        "if len(p.GoFiles)+len(p.CgoFiles)+len(p.TestGoFiles)+len(p.XTestGoFiles) == 0 {" in build
    )
    old_listing = ast.parse((PARENT / "listing.py").read_text())
    new_listing = ast.parse((AUTHOR / "listing.py").read_text())

    def guard(tree):
        return next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "require"
            and len(n.args) == 2
            and isinstance(n.args[1], ast.Constant)
            and n.args[1].value == "package has no selected Go source"
        )

    assert ast.dump(guard(new_listing).args[0], include_attributes=False) == ast.dump(
        ast.parse("bool(selected)", mode="eval").body, include_attributes=False
    )
    guard(new_listing).args[0] = deepcopy(guard(old_listing).args[0])
    assert ast.dump(new_listing, include_attributes=False) == ast.dump(
        old_listing, include_attributes=False
    )
    assert ast.dump(
        NormalizeCollection().visit(ast.parse((AUTHOR / "collection.py").read_text())),
        include_attributes=False,
    ) == ast.dump(ast.parse((PARENT / "collection.py").read_text()), include_attributes=False)
    plan = collection.load_plan()
    old_plan = json.loads((PARENT / "plan.json").read_text())
    same = [
        "commands",
        "cwd",
        "limits",
        "environment",
        "environmentSha256",
        "expectedGoEnv",
        "imageId",
        "sourceArchiveSha256",
        "projection",
        "treeObservation",
        "toolProbe",
        "expectedToolOutput",
    ]
    assert all(plan[k] == old_plan[k] for k in same)
    source_inventory = ROOT / semantics["sourceInventory"]["path"]
    assert sha(source_inventory) == semantics["sourceInventory"]["sha256"]
    files = json.loads(source_inventory.read_text())["files"]
    raw = (AUTHOR / "actual-go-list-stdout.bin").read_bytes()
    receipt = json.loads((AUTHOR / "actual-go-list-receipt.json").read_text())
    assert (
        hashlib.sha256(raw).hexdigest()
        == receipt["stdoutSha256"]
        == semantics["actualFailedAttempt"]["queryStdoutSha256"]
    )
    assert (
        sha(AUTHOR / "actual-go-list-receipt.json")
        == semantics["actualFailedAttempt"]["queryReceiptSha256"]
    )
    assert receipt["exitCode"] == 0 and receipt["error"] is None
    accepted = listing.packages(raw, files)
    assert len(accepted) == 104
    target = listing.PREFIX + "/internal/fourslash/tests"
    row = accepted[target]
    counts = {
        field: len(row.get(field, []))
        for field in ["GoFiles", "CgoFiles", "TestGoFiles", "XTestGoFiles"]
    }
    assert counts == {"GoFiles": 0, "CgoFiles": 0, "TestGoFiles": 3, "XTestGoFiles": 4368}
    selected = {n for field in counts for n in row.get(field, [])}
    assert len(selected) == 4371
    assert all("tsc/internal/fourslash/tests/" + n in files for n in selected)
    source_plan = json.loads(
        (
            ROOT / "benchmarks/head-to-head/f05-go01-dependency-preparation-20261029/plan.json"
        ).read_text()
    )
    wanted = {v["path"]: v for v in semantics["actualFailedAttempt"]["sourceDeclarations"]}
    found = {}
    with tarfile.open(source_plan["source"]["archivePath"], "r:") as archive:
        for member in archive:
            if member.name in wanted:
                data = archive.extractfile(member).read()
                v = wanted[member.name]
                assert hashlib.sha256(data).hexdigest() == v["sha256"] == files[member.name]
                assert data.decode().splitlines(keepends=True)[v["line"] - 1] == v["excerpt"]
                found[member.name] = True
    assert set(found) == set(wanted)
    synthetic = controls.package_rows()
    index = next(i for i, r in enumerate(synthetic) if r["ImportPath"] == target)
    checks = []
    for field in ["TestGoFiles", "XTestGoFiles"]:
        rows = deepcopy(synthetic)
        rows[index].update(GoFiles=[], CgoFiles=[], TestGoFiles=[], XTestGoFiles=[])
        rows[index][field] = ["owned_test.go"]
        assert listing.packages(b"\n".join(json.dumps(r).encode() for r in rows), controls.FILES)[
            target
        ][field]
        checks.append("positive-" + field)
    for label, mutate in [
        ("empty", lambda r: r.update(GoFiles=[], CgoFiles=[], TestGoFiles=[], XTestGoFiles=[])),
        (
            "ignored-only",
            lambda r: r.update(
                GoFiles=[],
                CgoFiles=[],
                TestGoFiles=[],
                XTestGoFiles=[],
                IgnoredGoFiles=["owned.go"],
            ),
        ),
        ("unsafe-test", lambda r: r.update(GoFiles=[], TestGoFiles=["../owned_test.go"])),
        ("missing-test", lambda r: r.update(GoFiles=[], TestGoFiles=["missing_test.go"])),
        (
            "cross-field-duplicate",
            lambda r: r.update(
                GoFiles=[], TestGoFiles=["owned_test.go"], XTestGoFiles=["owned_test.go"]
            ),
        ),
    ]:
        rows = deepcopy(synthetic)
        mutate(rows[index])
        assert refused(
            lambda: listing.packages(
                b"\n".join(json.dumps(r).encode() for r in rows), controls.FILES
            )
        )
        checks.append("reject-" + label)
    subject = collection.current_subject(plan)
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-go01-oldreview-testonly-", dir="/tmp"
    ) as folder:
        p = Path(folder).resolve()
        old_review = HERE.parent / "amendment-2/passed-review.json"
        acceptance = {
            "state": "coordinator-accepted-go01-no-npm-go-projection-collection",
            "synthetic": False,
            "driverSubject": subject,
            **{k: plan[k] for k in ["sourceArchiveSha256", "imageId", "environmentSha256"]},
            "projectionSha256": plan["projection"]["archive"]["sha256"],
            "projectionSpecSha256": plan["projectionSpecSha256"],
            "initAndTestMainExecutionAccepted": True,
            "noNpmProvisioning": True,
            "nativeTaskAdmitted": False,
            "campaignAdmitted": False,
            "cacheGloballyQualified": False,
            "sourceScopeReviewFreeze": plan["collectionScopeReview"],
            "projectionReviewFreeze": plan["collectionScopeReview"],
            "driverReviewFreeze": {"path": str(old_review), "sha256": sha(old_review)},
        }
        collection.write(p / "acceptance.json", acceptance)
        auth = {
            "state": "coordinator-authorized-single-go01-collection-attempt",
            "synthetic": False,
            "planSha256": subject["driverPlanSha256"],
            "authorFreezeSha256": subject["authorFreezeSha256"],
            "output": str(p / "output"),
            "scratch": str(p / "scratch"),
            "commands": collection.COMMANDS,
            "limits": plan["limits"],
            "maxAttempts": 1,
            "collectionAcceptance": {
                "path": str(p / "acceptance.json"),
                "sha256": sha(p / "acceptance.json"),
            },
        }
        collection.write(p / "auth.json", auth)
        assert refused(
            lambda: collection.authorize(plan, p / "auth.json", p / "output", p / "scratch")
        )
        checks.append("actual-old-amendment2-review-rejected")
    result = {
        "state": "independent-source-and-testonly-controls-passed",
        "toolSpans": spans,
        "minimalListingAstDelta": True,
        "minimalCollectionAstDelta": True,
        "sameContextFields": same,
        "rawFixturePackageObjects": len(accepted),
        "rawTestOnlySelectedFileCounts": counts,
        "all4371SelectedFilesBound": True,
        "sourceDeclarationsBound": len(found),
        "controls": checks,
        "rawFixtureOnlyNotNativeCollection": True,
        "newGoDaemonNodePackageNetworkNativeCalls": 0,
    }
    with (HERE / "source-and-testonly.json").open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(
        json.dumps(
            {
                "sourceSpans": len(spans),
                "rawObjects": len(accepted),
                "independentControls": len(checks),
                "minimalDelta": True,
            }
        )
    )


if __name__ == "__main__":
    main()
