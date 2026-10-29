"""Local source-data controls. No upstream imports, subprocesses or native tests."""

import ast
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def excerpt_matches(files, span):
    data = files[span["path"]]
    require(sha(data) == span["sha256"], "source hash mismatch")
    actual = "".join(
        data.decode().splitlines(keepends=True)[span["startLine"] - 1 : span["endLine"]]
    )
    require(actual == span["excerpt"], "line excerpt mismatch")


def refused(operation):
    try:
        operation()
    except ValueError:
        return True
    raise AssertionError("counterexample was accepted")


def main():
    scan = json.loads((HERE / "source-scan.json").read_text())
    archive = Path(scan["sourceArchivePath"])
    require(archive.stat().st_size <= 16 * 1024 * 1024, "archive bound")
    require(sha(archive.read_bytes()) == scan["sourceArchiveSha256"], "archive hash")
    inventory_path = Path(scan["sourceInventoryPath"])
    require(sha(inventory_path.read_bytes()) == scan["sourceInventorySha256"], "inventory hash")
    inventory = json.loads(inventory_path.read_text())
    files = {}
    with tarfile.open(archive, "r:") as tar:
        total = 0
        for member in tar:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and ".." not in path.parts, "unsafe archive path")
            if member.isdir():
                continue
            require(member.isfile() and member.name not in files, "nonregular or duplicate")
            require(member.size <= 128 * 1024 * 1024, "member bound")
            total += member.size
            require(total <= 16 * 1024 * 1024 and len(files) < 2000, "expanded bound")
            data = tar.extractfile(member).read(member.size + 1)
            require(len(data) == member.size, "member size")
            require(sha(data) == inventory["files"][member.name], "member hash")
            files[member.name] = data
    require(set(files) == set(inventory["files"]), "exact inventory path set")
    require(len(files) == 981 and total == 6945071, "frozen totals")
    for path, record in json.loads((HERE / "selected-source-members.json").read_text()).items():
        require(record["text"].encode() == files[path], "selected text bytes")
        require(
            record["sha256"] == sha(files[path]) and record["bytes"] == len(files[path]),
            "selected binding",
        )
    spans = json.loads((HERE / "source-spans.json").read_text())
    candidates = json.loads((HERE / "source-skip-candidates.json").read_text())
    for span in spans + candidates:
        excerpt_matches(files, span)
    for path, record in json.loads((HERE / "input-bindings.json").read_text()).items():
        data = (ROOT / path).read_bytes()
        require(
            sha(data) == record["sha256"] and len(data) == record["bytes"],
            "historical input changed",
        )
    test_files = {
        p: ast.parse(d.decode(), filename=p)
        for p, d in files.items()
        if p.startswith("test/") and p.endswith(".py")
    }
    require(len(test_files) == 32, "AST scan extent")
    socks = test_files["test/test_socks.py"]
    methods = {
        n.name: {m.name for m in n.body if isinstance(m, ast.FunctionDef)}
        for n in socks.body
        if isinstance(n, ast.ClassDef)
    }
    proposals = json.loads((HERE / "exclusion-proposal.json").read_text())
    for group in proposals["groups"]:
        require(group["accepted"] is False and group["observed"] is False, "no minted exclusions")
        for identity in group["sourceIdentities"]:
            prefix, class_name, method = identity.rsplit(".", 2)
            require(
                prefix == "test.test_socks" and method in methods[class_name],
                "exact source identity",
            )
    params = json.loads(files["test/parameters.json"])
    keys = {"primary_proxy", "primary_server_ip", "secondary_proxy", "secondary_server_ip"}
    require(not keys.intersection(params), "default proxy keys")
    require("test/local_parameters.json" not in files, "optional local config absent")
    require(
        "    _SKIP_SOCKS_TEST = True\n" in files["test/test_socks.py"].decode(),
        "source stand-in default",
    )
    oracle = json.loads((HERE / "oracle-requirements.json").read_text())
    scope = json.loads((HERE / "scope-disposition.json").read_text())
    require(
        oracle["nativeManifest"] is None and oracle["nativeCaseCount"] is None,
        "no invented collection",
    )
    require(
        not any(scope["admissions"].values()) and oracle["taskOutcomeObserved"] is False,
        "no native admission",
    )
    altered_files = dict(files)
    altered_files[spans[0]["path"]] += b"\n"
    checks = {
        "changed_source_rejected": refused(lambda: excerpt_matches(altered_files, spans[0])),
        "changed_excerpt_rejected": refused(
            lambda: excerpt_matches(files, dict(spans[0], excerpt="wrong"))
        ),
        "shifted_span_rejected": refused(
            lambda: excerpt_matches(files, dict(spans[0], startLine=112))
        ),
        "invented_proxy_identity_rejected": refused(
            lambda: require("test_socks40" in methods["TestSocks"], "identity")
        ),
        "configuration_assumption_rejected": refused(
            lambda: require("primary_proxy" in params, "missing proxy")
        ),
        "empty_collection_rejected_as_readiness": refused(
            lambda: require(bool(oracle["nativeManifest"]), "manifest missing")
        ),
    }
    if (HERE / "freeze.json").exists():
        for path, record in json.loads((HERE / "freeze.json").read_text())["artifacts"].items():
            data = (HERE / path).read_bytes()
            require(sha(data) == record["sha256"] and len(data) == record["bytes"], "packet freeze")
    print(
        json.dumps(
            {
                "state": "source-data controls passed",
                "regularFiles": len(files),
                "expandedBytes": total,
                "selectedTexts": 20,
                "sourceSpans": len(spans),
                "syntacticSkipCandidates": len(candidates),
                "testPythonFilesAstParsed": len(test_files),
                "counterexamples": checks,
                "nativeCollectionOccurred": False,
                "executionOccurred": False,
                "indexConsulted": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
