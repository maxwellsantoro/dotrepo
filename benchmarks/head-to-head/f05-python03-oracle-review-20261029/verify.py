"""Independent static source review. No imports or execution of upstream code."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUTHOR = HERE.with_name("f05-python03-oracle-preparation-20261029")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def load(path):
    return json.loads(path.read_bytes())


def main(output):
    freeze = load(AUTHOR / "freeze.json")
    require(
        sha((AUTHOR / "freeze.json").read_bytes())
        == "df2b640f4c3ac6fbf778751d77a2241aef74b036c247a6521c9ab7e1e6ef0c88",
        "author freeze",
    )
    for name, item in freeze["artifacts"].items():
        raw = (AUTHOR / name).read_bytes()
        require(sha(raw) == item["sha256"] and len(raw) == item["bytes"], name)
    for name, item in load(AUTHOR / "input-bindings.json").items():
        raw = (ROOT / name).read_bytes()
        require(sha(raw) == item["sha256"] and len(raw) == item["bytes"], name)
    scan = load(AUTHOR / "source-scan.json")
    source = Path(scan["sourceArchivePath"])
    require(sha(source.read_bytes()) == scan["sourceArchiveSha256"], "archive SHA")
    inventory_raw = Path(scan["sourceInventoryPath"]).read_bytes()
    require(sha(inventory_raw) == scan["sourceInventorySha256"], "inventory SHA")
    inventory = json.loads(inventory_raw)
    files = {}
    with tarfile.open(source, "r:") as archive:
        for member in archive:
            name = member.name
            require(
                name not in files
                and not name.startswith("/")
                and all(p not in ("", ".", "..") for p in name.split("/")),
                "safe unique source path",
            )
            require(member.isfile() and not member.sparse and member.size <= 2097152, name)
            require(sum(map(len, files.values())) + member.size <= 16777216, "total bound")
            raw = archive.extractfile(member).read()
            require(sha(raw) == inventory["files"][name], name)
            files[name] = raw
    require(set(files) == set(inventory["files"]), "complete path set")
    require(len(files) == 981 and sum(map(len, files.values())) == 6945071, "archive totals")
    for name, item in load(AUTHOR / "selected-source-members.json").items():
        require(
            item["text"].encode() == files[name]
            and item["sha256"] == sha(files[name])
            and item["bytes"] == len(files[name]),
            f"exact source text {name}",
        )
    spans = load(AUTHOR / "source-spans.json")
    skip_sites = load(AUTHOR / "source-skip-candidates.json")
    for span in spans + skip_sites:
        raw = files[span["path"]]
        actual = "".join(
            raw.decode().splitlines(keepends=True)[span["startLine"] - 1 : span["endLine"]]
        )
        require(actual == span["excerpt"] and sha(raw) == span["sha256"], "exact source span")
    trees = {
        name: ast.parse(raw.decode(), filename=name)
        for name, raw in files.items()
        if name.startswith("test/") and name.endswith(".py")
    }
    require(len(trees) == 32, "AST extent")
    socks = {
        node.name: node
        for node in trees["test/test_socks.py"].body
        if isinstance(node, ast.ClassDef)
    }
    expected = {
        "TestSocks": {"test_socks4", "test_socks4a", "test_socks5"},
        "TestMultipleSocks": {
            "test_proxy_http",
            "test_proxy_https",
            "test_secondary_proxy_http",
            "test_secondary_proxy_https",
        },
    }
    for cls, names in expected.items():
        actual = {
            n.name
            for n in socks[cls].body
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
        }
        require(actual == names, f"exact source method set {cls}")
    defaults = [node for node in socks["TestSocks"].body if isinstance(node, ast.Assign)]
    require(
        any(
            any(isinstance(t, ast.Name) and t.id == "_SKIP_SOCKS_TEST" for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
            for node in defaults
        ),
        "literal stand-in default",
    )
    params = json.loads(files["test/parameters.json"])
    absent = {"primary_proxy", "primary_server_ip", "secondary_proxy", "secondary_server_ip"}
    require(
        not (absent & set(params)) and "test/local_parameters.json" not in files,
        "default proxy configuration",
    )
    proposal = load(AUTHOR / "exclusion-proposal.json")
    actual_ids = {name for group in proposal["groups"] for name in group["sourceIdentities"]}
    expected_ids = {
        f"test.test_socks.{cls}.{name}" for cls, names in expected.items() for name in names
    }
    require(actual_ids == expected_ids and len(actual_ids) == 7, "exact proposed identities")
    require(
        all(
            not g["accepted"] and not g["observed"] and not g["behaviorExercised"]
            for g in proposal["groups"]
        ),
        "no accepted behavior",
    )
    requirement = load(AUTHOR / "oracle-requirements.json")
    scope = load(AUTHOR / "scope-disposition.json")
    require(not any(scope["admissions"].values()), "no admission")
    require(
        requirement["nativeManifest"] is requirement["nativeCaseCount"] is None,
        "no native manifest/count",
    )
    network = [
        n
        for n in ast.walk(trees["test/test_download.py"])
        if isinstance(n, ast.If) and n.lineno == 180
    ]
    require(
        len(network) == 1 and any(isinstance(n, ast.Return) for n in network[0].body),
        "network exhausted return site",
    )
    result = {
        "state": "passed-independent-static-source-integrity",
        "authorArtifactCount": len(freeze["artifacts"]),
        "historicalInputBindings": len(load(AUTHOR / "input-bindings.json")),
        "sourceArchiveSha256": scan["sourceArchiveSha256"],
        "regularFiles": len(files),
        "expandedBytes": sum(map(len, files.values())),
        "exactSelectedTexts": len(load(AUTHOR / "selected-source-members.json")),
        "exactSourceSpans": len(spans),
        "syntacticSkipSiteBindings": len(skip_sites),
        "testPythonAstParses": len(trees),
        "proposedExclusionSourceIdentities": sorted(actual_ids),
        "nativeCaseCount": None,
        "upstreamImportsOrExecution": False,
        "scopeOracleEnvironmentOrCampaignAdmission": False,
    }
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    main(parser.parse_args().output)
