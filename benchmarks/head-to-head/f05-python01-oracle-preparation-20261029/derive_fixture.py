"""Derive explicitly synthetic source slots as AST data, never native test IDs."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/maxwell/projects/agent/dotrepo")
INVENTORY = (
    ROOT
    / "benchmarks/head-to-head/f05-python01-oracle-decision-20261029/static-test-inventory.json"
)


def derive():
    inventory = json.loads(INVENTORY.read_bytes())
    cases = []
    for row in inventory["files"]:
        raw = (HERE / "sources" / row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        tree = ast.parse(raw)
        declarations = []
        if row["group"] == "root-unittest":
            for cls in tree.body:
                if isinstance(cls, ast.ClassDef) and any(
                    isinstance(base, ast.Attribute) and base.attr == "TestCase"
                    for base in cls.bases
                ):
                    declarations += [
                        (cls.name + "." + node.name, node.lineno)
                        for node in cls.body
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name.startswith("test_")
                    ]
        else:
            declarations = [
                (node.name, node.lineno)
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
            ]
        assert len(declarations) == row["staticDefinitions"]
        cardinalities = {site["function"]: site["cardinality"] for site in row["parameterSites"]}
        for name, line in declarations:
            for slot in range(1, cardinalities.get(name, 1) + 1):
                cases.append(
                    {
                        "id": "owned-synthetic::"
                        + row["path"]
                        + "::"
                        + name
                        + "::slot-"
                        + str(slot),
                        "suite": row["group"],
                        "sourcePath": row["path"],
                        "sourceSha256": row["sha256"],
                        "declaration": name,
                        "line": line,
                        "syntheticParameterSlot": slot,
                    }
                )
    assert len(cases) == 157 and sum(row["suite"] == "root-unittest" for row in cases) == 28
    return {
        "state": "owned-synthetic-source-candidate-fixture-not-native-collection",
        "repository": "github.com/666ghj/MiroFish",
        "revision": "7657031ac01184afe2cb220f5ee3545573b5e843",
        "sourceArchiveSha256": "fc70acea794785b5c6bfd06f5e0c83cb328fc5c4e05e36dab8f182fea5bd0d70",
        "scope": "root-unittest+backend-pytest-semantic-union",
        "cases": cases,
        "nativeCollectionOccurred": False,
        "nativeIdsEstablished": False,
        "diagnosticSemanticCase": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = (json.dumps(derive(), indent=2, sort_keys=True) + "\n").encode()
    with args.output.open("xb") as stream:
        stream.write(raw)
    print(
        json.dumps({"sha256": hashlib.sha256(raw).hexdigest(), "nativeCollectionOccurred": False})
    )
