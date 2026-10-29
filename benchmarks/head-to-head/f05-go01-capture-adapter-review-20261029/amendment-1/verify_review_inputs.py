"""Verify the two retained manifest shapes and bounded adapter source delta."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AUTHOR = (
    ROOT / "benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-3/amendment-1"
)


def normalized(path):
    tree = ast.parse(path.read_text())
    tree.body = [
        node
        for node in tree.body
        if not (isinstance(node, ast.FunctionDef) and node.name == "isolation_options")
        and not (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id in {"ROOT", "AM2"} for t in node.targets)
        )
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "association":
            for child in ast.walk(node):
                if hasattr(child, "body") and isinstance(child.body, list):
                    child.body = [
                        item
                        for item in child.body
                        if not (
                            isinstance(item, ast.Expr)
                            and isinstance(item.value, ast.Call)
                            and isinstance(item.value.func, ast.Name)
                            and item.value.func.id == "isolation_options"
                        )
                    ]
    return ast.dump(tree, include_attributes=False)


def main():
    verified = []
    for path in (AUTHOR.parent, AUTHOR, HERE.parent, AUTHOR.parents[1] / "amendment-2"):
        freeze = path / "FREEZE.json"
        data = json.loads(freeze.read_bytes())
        artifacts = data.get("artifacts", data.get("artifactSha256"))
        assert isinstance(artifacts, dict)
        for relative, record in artifacts.items():
            raw = (path / relative).read_bytes()
            if isinstance(record, dict):
                assert len(raw) == record["bytes"], (path, relative)
                expected = record["sha256"]
            else:
                expected = record
            assert hashlib.sha256(raw).hexdigest() == expected, (path, relative)
        verified.append(
            {
                "path": str(freeze.relative_to(ROOT)),
                "sha256": hashlib.sha256(freeze.read_bytes()).hexdigest(),
                "artifacts": len(artifacts),
            }
        )
    bindings = json.loads((AUTHOR / "source-bindings.json").read_bytes())["files"]
    for row in bindings:
        raw = (ROOT / row["path"]).read_bytes()
        assert len(raw) == row["bytes"]
        assert hashlib.sha256(raw).hexdigest() == row["sha256"], row["path"]
    assert normalized(AUTHOR.parent / "adapter.py") == normalized(AUTHOR / "adapter.py")
    report = {
        "state": "independent-source-and-frozen-artifact-verification-passed",
        "verified": verified,
        "boundInputs": len(bindings),
        "adapterASTUnchangedExceptPathRelocationAndIsolationHelperCall": True,
        "parentScorerControlsReused": 44,
        "reuseReason": "Exact scorer/map/policy and original retained success bytes unchanged; isolation-only successor.",
        "executionAuthorized": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
        "newRuntimeActions": 0,
    }
    with (HERE / "integrity-and-source.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"allPassed": True, "artifacts": sum(r["artifacts"] for r in verified)}))


if __name__ == "__main__":
    main()
