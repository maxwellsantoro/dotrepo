"""Inspect retained tar/config bytes as data; never import target modules."""

import ast
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tomllib

HERE = Path(__file__).resolve().parent
REPO = Path("/Users/maxwell/projects/agent/dotrepo")
ARCHIVE = Path("/tmp/dotrepo-f05-qualification-next8-20261029/python-01/source.tar")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    acquisition_path = (
        REPO / "benchmarks/head-to-head/f05-qualification-next8-20261029/python-01/acquisition.json"
    )
    acquisition = json.loads(acquisition_path.read_bytes())
    inventory = json.loads((acquisition_path.parent / "inventory.json").read_bytes())["files"]
    assert sha(ARCHIVE.read_bytes()) == acquisition["archiveSha256"]
    facts, failures, python_bindings, selected = [], [], [], {}
    retained = {
        "README.md",
        "Dockerfile",
        "package.json",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "backend/requirements.txt",
        "backend/app/config.py",
        "backend/app/__init__.py",
        "backend/app/services/__init__.py",
        "backend/tests/test_zep_cloud_validation_script.py",
    }
    with tarfile.open(ARCHIVE) as archive:
        members = archive.getmembers()
        assert len(members) == 128 and all(m.isfile() for m in members)
        assert {m.name for m in members} == set(inventory)
        for m in members:
            raw = archive.extractfile(m).read()
            assert sha(raw) == inventory[m.name]
            if m.name in retained:
                selected[m.name] = {"sha256": sha(raw), "bytes": len(raw)}
                if m.name != "backend/uv.lock":
                    facts.append(
                        {
                            "path": m.name,
                            "sha256": sha(raw),
                            "lines": [
                                {"line": i, "text": s}
                                for i, s in enumerate(raw.decode().splitlines(), 1)
                                if any(
                                    w in s
                                    for w in [
                                        "3.11",
                                        "3.12",
                                        "3.13",
                                        "uv sync",
                                        "setup:backend",
                                        "requires-python",
                                        "pytest",
                                        "hatchling",
                                        "packages =",
                                        "load_dotenv",
                                        "project_root_env",
                                        "PYTHONPATH",
                                        "sys.executable",
                                        "from .",
                                    ]
                                )
                            ],
                        }
                    )
            if m.name.endswith(".py"):
                python_bindings.append({"path": m.name, "sha256": sha(raw), "bytes": len(raw)})
                try:
                    ast.parse(raw, filename=m.name, feature_version=(3, 11))
                except SyntaxError as e:
                    failures.append({"path": m.name, "line": e.lineno, "message": e.msg})
        lock = tomllib.loads(archive.extractfile("backend/uv.lock").read().decode())
        project = tomllib.loads(archive.extractfile("backend/pyproject.toml").read().decode())
        packages = []
        for p in lock["package"]:
            if p["name"] in {
                "torch",
                "numpy",
                "scipy",
                "scikit-learn",
                "pytest",
                "pytest-asyncio",
                "camel-ai",
                "camel-oasis",
                "zep-cloud",
            }:
                packages.append(
                    {
                        "name": p["name"],
                        "version": p["version"],
                        "source": p["source"],
                        "candidateCp311LinuxAarch64OrUniversalWheels": [
                            w
                            for w in p.get("wheels", [])
                            if (
                                "aarch64" in w["url"]
                                and ("cp311" in w["url"] or "abi3" in w["url"])
                            )
                            or "py3-none-any" in w["url"]
                        ],
                        "conditionalDependencies": [
                            d for d in p.get("dependencies", []) if "marker" in d
                        ],
                    }
                )
    result = {
        "state": "static-retained-data-inspection-only",
        "archiveSha256": acquisition["archiveSha256"],
        "membersVerified": 128,
        "sourceBytes": acquisition["sourceBytes"],
        "pythonGrammarAnalysis": {
            "hostVersion": sys.version,
            "featureVersion": [3, 11],
            "files": len(python_bindings),
            "failures": failures,
            "isNative311Compile": False,
            "targetCodeExecuted": False,
        },
        "requiresPython": project["project"]["requires-python"],
        "lockRequiresPython": lock["requires-python"],
        "lockResolutionMarkers": lock["resolution-markers"],
        "lockPackageCount": len(lock["package"]),
        "sourceKinds": sorted({json.dumps(p["source"], sort_keys=True) for p in lock["package"]}),
        "devDependencyGroup": project["dependency-groups"]["dev"],
        "optionalDevExtraNotSelected": project["project"]["optional-dependencies"]["dev"],
        "buildSystem": project["build-system"],
        "selectedSourceBindings": selected,
        "pythonSourceBindings": python_bindings,
        "candidateWheelEvidence": packages,
        "wheelCompatibilityOrDependencySuccessEstablished": False,
        "actualAdmission": False,
    }
    (HERE / "source-facts.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (HERE / "source-spans.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "membersVerified": 128,
                "pythonFiles": len(python_bindings),
                "grammar311Failures": len(failures),
                "lockPackages": len(lock["package"]),
            }
        )
    )


if __name__ == "__main__":
    main()
