"""Owned plan data/AST controls only; never execute the prospective probe."""

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def check(plan):
    assert plan["executionAuthorized"] is False and plan["actualAdmission"] is False
    assert plan["probeExecuted"] is False and plan["dependencySetupExecuted"] is False
    assert plan["nativeCollectionOccurred"] is False and plan["oracleQualified"] is False
    assert plan["campaignAdmitted"] is False
    assert (
        plan["image"]["id"]
        == "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
    )
    assert plan["image"]["pythonPath"] == "/usr/bin/python3.11"
    command = plan["dependencyPreparation"]["commandArgv"]
    for flag in ["--locked", "--no-build", "--no-install-project", "--no-python-downloads"]:
        assert flag in command
    assert "--extra" not in command and "--all-extras" not in command
    assert plan["dependencyPreparation"]["inputMembers"] == [
        "backend/pyproject.toml -> pyproject.toml",
        "backend/uv.lock -> uv.lock",
    ]
    assert plan["probe"]["network"] == "none"
    assert plan["limits"]["memoryBytes"] == 4294967296 and plan["limits"]["cpus"] == 3
    assert plan["limits"]["workSeconds"] == 900
    assert plan["cacheAndReceipts"]["globalCacheAdmission"] is False
    assert (
        hashlib.sha256((HERE / "probe.py").read_bytes()).hexdigest()
        == plan["probe"]["sourceSha256"]
    )


def main():
    plan = json.loads((HERE / "plan.json").read_bytes())
    check(plan)
    cases = [{"case": "unchanged-prospective-plan", "acceptedAsPlanOnly": True}]
    mutations = [
        ("build-hooks", lambda p: p["dependencyPreparation"]["commandArgv"].remove("--no-build")),
        (
            "project-build",
            lambda p: p["dependencyPreparation"]["commandArgv"].remove("--no-install-project"),
        ),
        ("unlocked", lambda p: p["dependencyPreparation"]["commandArgv"].remove("--locked")),
        (
            "implicit-interpreter-download",
            lambda p: p["dependencyPreparation"]["commandArgv"].remove("--no-python-downloads"),
        ),
        (
            "task-source-provision",
            lambda p: p["dependencyPreparation"]["inputMembers"].append("backend/app/"),
        ),
        ("probe-network", lambda p: p["probe"].__setitem__("network", "bridge")),
        ("actual-admission", lambda p: p.__setitem__("actualAdmission", True)),
        (
            "global-cache-admission",
            lambda p: p["cacheAndReceipts"].__setitem__("globalCacheAdmission", True),
        ),
    ]
    for name, mutate in mutations:
        changed = deepcopy(plan)
        mutate(changed)
        try:
            check(changed)
        except AssertionError:
            cases.append({"case": name, "rejectedAsPlan": True})
        else:
            raise AssertionError(name + " not rejected")
    tree = ast.parse((HERE / "probe.py").read_bytes())
    imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)}
    imports |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"hashlib", "json", "os", "pathlib", "ssl", "sys", "sysconfig"}
    result = {
        "state": "plan-data-and-owned-probe-ast-controls-pass",
        "count": len(cases),
        "cases": cases,
        "probeImports": sorted(imports),
        "probeExecuted": False,
        "sourceOrDependencyCodeExecuted": False,
        "daemonNetworkProviderActions": 0,
        "actualAdmission": False,
        "oracleQualified": False,
    }
    (HERE / "controls.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"state": result["state"], "count": len(cases)}))


if __name__ == "__main__":
    main()
