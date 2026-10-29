"""Local data/hash replay only. Never launches a process or scores actual tasks."""

import ast
import difflib
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import derive  # noqa: E402
import oracle  # noqa: E402

HERE = Path(__file__).resolve().parent


def verify():
    metadata, names, bindings = derive.derive()
    for row in json.loads((HERE / "capture-dependency.json").read_bytes())["files"]:
        derive.require(
            hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() == row["sha256"],
            "changed capture assessment",
        )
    derive.require(
        (HERE / "expected-map.json").read_bytes() == derive.canonical(names),
        "derived full map changed",
    )
    derive.require(
        json.loads((HERE / "expectation.json").read_bytes()) == metadata, "derived metadata changed"
    )
    loaded, loaded_names = oracle.load_expectation()
    derive.require(loaded == metadata and loaded_names == names, "oracle source adapter differs")
    original = (HERE.parent / "amendment-1/oracle.py").read_text()
    successor = (HERE / "oracle.py").read_text()
    old_lifecycle = original[
        original.index("        started, ended, ran, terminal") : original.index(
            "        failed = {key"
        )
    ]
    new_lifecycle = successor[
        successor.index("        started, ended, ran, terminal") : successor.index(
            "        failed = {key"
        )
    ]

    # Only this source-based refusal narrows the old zero-name-package branch.
    class NarrowingOnly(ast.NodeTransformer):
        removed = 0

        def visit_BoolOp(self, node):
            self.generic_visit(node)
            marker = ast.dump(
                ast.parse('package in metadata["noSelectedTestSourcePackages"]', mode="eval").body
            )
            kept = [value for value in node.values if ast.dump(value) != marker]
            self.removed += len(node.values) - len(kept)
            node.values = kept
            return node

    transformer = NarrowingOnly()
    normalized = transformer.visit(ast.parse("def lifecycle():\n" + new_lifecycle))
    derive.require(
        transformer.removed == 1
        and ast.dump(ast.parse("def lifecycle():\n" + old_lifecycle)) == ast.dump(normalized),
        "unexpected hierarchy/lifecycle delta",
    )
    old_end = original[
        original.index("        failed = {key") : original.index("        result.update(")
    ]
    new_end = successor[
        successor.index("        failed = {key") : successor.index("        result.update(")
    ]
    derive.require(old_end == new_end, "unexpected assertion/process delta")
    # Source exclusion authorization/identity logic is copied unchanged except its origin noun.
    old_policy = original[
        original.index("        exclusions = {}") : original.index("        started, ended")
    ]
    new_policy = successor[
        successor.index("        exclusions = {}") : successor.index("        started, ended")
    ]
    derive.require(
        old_policy.replace(
            "exclusion absent from native collection", "exclusion absent from source expectation"
        )
        == new_policy,
        "skip policy widened",
    )
    expected_diff = "".join(
        difflib.unified_diff(
            original.splitlines(True),
            successor.splitlines(True),
            fromfile="amendment-1/oracle.py",
            tofile="amendment-2/oracle.py",
        )
    )
    derive.require((HERE / "oracle.diff").read_text() == expected_diff, "source diff differs")
    return {
        "state": "verified-source-adapter-synthetic-scorer-preparation",
        "boundSourceFiles": len(bindings["files"]),
        "fullMapSha256": hashlib.sha256(derive.canonical(names)).hexdigest(),
        "fullMapBytes": len(derive.canonical(names)),
        "packages": 104,
        "topLevelNames": 5972,
        "emptyNamePackages": 40,
        "sourcePackagesWithoutSelectedTestFiles": len(metadata["noSelectedTestSourcePackages"]),
        "nativeNoTestDiagnosticsObservedPreviously": 18,
        "lifecycleDelta": "unchanged except refusing no-test-files skip for a source-selected test-file package",
        "skipPolicyWidened": False,
        "actualCaptureJoin": "OPEN",
        "actualOracleQualified": False,
        "campaignAdmitted": False,
        "newNativeActions": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
