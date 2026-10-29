"""Trusted local source/hash/AST checks; no Go or process execution."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTHOR = Path(json.loads((HERE / "author-binding.json").read_text())["freeze"]).parent
PARENT = AUTHOR.parent / "amendment-1"
ROOT = AUTHOR.parents[3]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Normalize(ast.NodeTransformer):
    def visit_Constant(self, node):
        if node.value == "go01-collection-driver-amendment-2":
            node.value = "go01-collection-driver-amendment-1"
        return node

    def visit_Dict(self, node):
        self.generic_visit(node)
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == "GOENV"
                and isinstance(value, ast.Constant)
                and value.value == ""
            ):
                value.value = "off"
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in {"SCRIPT_NAMES", "LOCAL_NAMES"}:
            removed = (
                {"goenv_controls.py"}
                if target.id == "SCRIPT_NAMES"
                else {
                    "goenv-source-semantics.json",
                    "actual-go-env-stdout.bin",
                    "actual-go-env-receipt.json",
                }
            )
            node.value.elts = [v for v in node.value.elts if v.value not in removed]
        return node


def main():
    semantics = json.loads((AUTHOR / "goenv-source-semantics.json").read_text())
    inventory = ROOT / semantics["frozenImageInventory"]["path"]
    assert sha(inventory) == semantics["frozenImageInventory"]["sha256"]
    image = json.loads(inventory.read_text())
    observations = []
    for item in semantics["sourceObservations"]:
        path = AUTHOR / "sources" / item["path"]
        data = path.read_bytes()
        assert sha(path) == item["sha256"] == image["files"][item["path"]]["sha256"]
        assert len(data) == image["files"][item["path"]]["size"]
        excerpt = "".join(
            data.decode().splitlines(keepends=True)[item["startLine"] - 1 : item["endLine"]]
        )
        assert excerpt == item["excerpt"]
        observations.append(
            {"path": item["path"], "sha256": sha(path), "spanBound": True, "imageBound": True}
        )
    cfg = (AUTHOR / "sources/usr/local/go/src/cmd/go/internal/cfg/cfg.go").read_text()
    env = (AUTHOR / "sources/usr/local/go/src/cmd/go/internal/envcmd/env.go").read_text()
    assert 'if file == "off" {\n\t\t\treturn "", false, fmt.Errorf("GOENV=off")' in cfg
    assert 'if file, _, _ := EnvFile(); file != "" {' in cfg
    assert 'readEnvFile(filepath.Join(goroot, "go.env"), "GOROOT")' in cfg
    assert "envFile, envFileChanged, _ := cfg.EnvFile()" in env
    assert '{Name: "GOENV", Value: envFile, Changed: envFileChanged}' in env
    old = json.loads((PARENT / "plan.json").read_text())
    new = json.loads((AUTHOR / "plan.json").read_text())
    same = [
        "commands",
        "cwd",
        "limits",
        "environment",
        "environmentSha256",
        "imageId",
        "sourceArchiveSha256",
        "projection",
        "treeObservation",
        "toolProbe",
        "expectedToolOutput",
    ]
    assert all(old[k] == new[k] for k in same)
    expected = dict(old["expectedGoEnv"])
    assert expected["GOENV"] == "off"
    expected["GOENV"] = ""
    assert new["expectedGoEnv"] == expected and new["environment"]["GOENV"] == "off"
    normalized = Normalize().visit(ast.parse((AUTHOR / "collection.py").read_text()))
    assert ast.dump(normalized, include_attributes=False) == ast.dump(
        ast.parse((PARENT / "collection.py").read_text()), include_attributes=False
    )
    unchanged = [
        "listing.py",
        "process_io.py",
        "tree-observer.js",
        "controls.py",
        "amendment_controls.py",
        "observer_controls.py",
        "transport_controls.py",
    ]
    assert all(sha(AUTHOR / n) == sha(PARENT / n) for n in unchanged)
    raw = (AUTHOR / "actual-go-env-stdout.bin").read_bytes()
    receipt = json.loads((AUTHOR / "actual-go-env-receipt.json").read_text())
    assert (
        hashlib.sha256(raw).hexdigest()
        == receipt["stdoutSha256"]
        == semantics["actualFailedAttempt"]["stdoutSha256"]
    )
    assert (
        sha(AUTHOR / "actual-go-env-receipt.json")
        == semantics["actualFailedAttempt"]["receiptSha256"]
    )
    assert receipt["exitCode"] == 0 and receipt["error"] is None
    assert json.loads(raw) == new["expectedGoEnv"]
    result = {
        "state": "source/query correction independently verified; no result reclassification",
        "sources": observations,
        "sameContextFields": same,
        "inputGOENV": "off",
        "queriedGOENV": "",
        "configurationLimit": "User env file disabled; image GOROOT/go.env defaults remain.",
        "normalizedRuntimeAstEqualsParent": True,
        "unchangedCodeFiles": unchanged,
        "historicalQueryReceiptBound": True,
        "newGoDaemonNetworkNativeCalls": 0,
    }
    with (HERE / "source-and-delta.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(
        json.dumps(
            {
                "sources": len(observations),
                "minimalRuntimeDelta": True,
                "historicalQueryBound": True,
            }
        )
    )


if __name__ == "__main__":
    main()
