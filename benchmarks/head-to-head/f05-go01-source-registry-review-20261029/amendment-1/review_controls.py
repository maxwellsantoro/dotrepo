"""Independent Python-only amendment review; no Go or upstream execution."""

from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent.parent / "f05-go01-source-registry-20261029"
AUTHOR = BASE / "amendment-1"
BEFORE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    with (HERE / name).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def binding():
    counts = {}
    for path, expected in [
        (BASE, "b2fd2550fd9ca1b5dc20774badfb77863e28236cc0535f11c6012a5aa6a0ab8d"),
        (BEFORE, "df6d752afd787928917416664c879a5422edf632750ba3e2d52cb37f2edce074"),
        (AUTHOR, "e569edd4888a092aa46745d950614964ca86fc755637827fd9723fad0413da4d"),
    ]:
        assert sha(path / "FREEZE.json") == expected
        freeze = json.loads((path / "FREEZE.json").read_bytes())
        artifacts = freeze.get("artifactSha256", freeze.get("artifacts"))
        for name, item in artifacts.items():
            digest = item if isinstance(item, str) else item["sha256"]
            assert sha(path / name) == digest, name
            if isinstance(item, dict):
                assert (path / name).stat().st_size == item["bytes"], name
        counts[str(path)] = len(artifacts)
    assert sha(BASE / "local-input.json") == (
        "0acd95252e7acfc23ce616d59125ebc98c0a7e4b079a789057e44a4479c88015"
    )
    assert (BASE / "local-input.json").stat().st_size == 21446036
    plan = json.loads((AUTHOR / "plan.json").read_bytes())
    original = json.loads((BASE / "plan.json").read_bytes())
    for key in [
        "helperBuildContextProspective",
        "sourceContext",
        "input",
        "inputBounds",
        "sourceRegistrySemantics",
        "futurePartialCrosscheck",
    ]:
        assert plan[key] == original[key], key
    for entry in plan["helperSourceBindings"].values():
        assert sha(BASE.parents[2] / entry["path"]) == entry["sha256"]
    return {"artifactCounts": counts, "inputUnchanged": True, "inheritedContextUnchanged": True}


def run(script, scratch):
    command = ["uv", "run", "--offline", "--no-sync", "python", str(script)]
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(AUTHOR),
        "TMPDIR": str(scratch),
    }
    proc = subprocess.run(command, cwd=scratch, env=env, capture_output=True, check=False)
    assert proc.returncode == 0, (command, proc.stdout.decode(), proc.stderr.decode())
    return {
        "argv": command,
        "exitCode": proc.returncode,
        "stdoutSha256": hashlib.sha256(proc.stdout).hexdigest(),
        "stderr": proc.stderr.decode(),
    }


def independent_cases(scratch):
    sys.path.insert(0, str(AUTHOR))
    builder = importlib.import_module("build_input")
    receiver = importlib.import_module("read_registry")
    # Capture the exact before-review fixture before any challenge mutates its copy.
    fixture = {}
    import runpy

    before = runpy.run_path(str(scratch / "receiver_challenge.py"))
    original_validate = receiver.validate

    def capture(value, provenance, packages):
        if not fixture:
            fixture.update(
                value=deepcopy(value), provenance=deepcopy(provenance), packages=deepcopy(packages)
            )
        return original_validate(value, provenance, packages)

    receiver.validate = capture
    try:
        before["main"]()
    finally:
        receiver.validate = original_validate
    results = []

    def check(name, expected, operation):
        try:
            operation()
            accepted = True
        except (ValueError, KeyError, TypeError):
            accepted = False
        results.append({"case": name, "expectedAccepted": expected, "actualAccepted": accepted})
        assert accepted is expected, name

    def candidate(diagnostic=None, optional=None):
        value = deepcopy(fixture["value"])
        if diagnostic is not None:
            value["state"] = value["packages"][0]["state"] = "unresolved-source-discovery"
            value["packages"][0]["diagnostics"] = [diagnostic]
        if optional:
            value["packages"][0]["tests"][0].update(optional)
        return lambda: original_validate(value, fixture["provenance"], fixture["packages"])

    for label, path in [
        ("selected wrong package", "tsc/other/owned_test.go"),
        ("empty source", ""),
        ("traversal", "tsc/owned/../owned_test.go"),
    ]:
        check(label, False, candidate({"code": "owned", "message": "owned", "sourcePath": path}))
    # A globally selected source from another package must still be refused here.
    other = "tsc/other/owned_test.go"
    fixture["provenance"]["selectedFiles"][other] = {"sha256": "f" * 64, "bytes": 12}
    check(
        "globally selected but different package",
        False,
        candidate({"code": "owned", "message": "owned", "sourcePath": other}),
    )
    for diagnostic in [
        {"code": "unknown-but-retained", "message": "not interpreted"},
        {"code": "multiple-testmain-unresolved", "message": "retained wrappers"},
    ]:
        check("path-omitted diagnostic " + diagnostic["code"], True, candidate(diagnostic))
    for key in ["code", "message"]:
        for bad in [None, 0, False, [], {}]:
            check(
                "diagnostic " + key + " " + repr(bad),
                False,
                candidate({"code": "owned", "message": "owned", key: bad}),
            )
    for key in ["emptyOutput", "unordered"]:
        for bad in [0, 1, "false", None]:
            check(
                "literal boolean required " + key + " " + repr(bad),
                False,
                candidate(optional={key: bad}),
            )
        for good in [False, True]:
            check(
                "literal boolean accepted " + key + " " + repr(good),
                True,
                candidate(optional={key: good}),
            )
    for raw in [
        b'{"v":NaN}',
        b'{"v":Infinity}',
        b'{"v":-Infinity}',
        b'{"v":1e999}',
        b'{"v":-1e999}',
        b'{"v":0,"v":1}',
    ]:
        check("strict JSON " + raw.decode(), False, lambda raw=raw: builder.load(raw))
    for raw in [b'{"v":0}', b'{"v":false}', b'{"v":1.5}']:
        check("finite JSON " + raw.decode(), True, lambda raw=raw: builder.load(raw))
    return results


def main():
    initial = binding()
    scratch = Path(tempfile.mkdtemp(prefix="dotrepo-go01-registry-amendment-review-", dir="/tmp"))
    receipts = []
    for name in ["constructor_controls.py", "receiver_controls.py", "amendment_controls.py"]:
        data = (AUTHOR / name).read_text()
        if name == "amendment_controls.py":
            data = data.replace("AUTHOR = HERE\n", "AUTHOR = Path(" + repr(str(AUTHOR)) + ")\n")
        (scratch / name).write_text(data)
        receipts.append(run(scratch / name, scratch))
    for source_name, target_name in [
        ("constructor-controls.json", "replay-constructor-controls.json"),
        ("receiver-controls.json", "replay-receiver-controls.json"),
        ("receiver-challenge.json", "replay-author-amendment-controls.json"),
    ]:
        shutil.copyfile(scratch / source_name, HERE / target_name)
    # Keep the seven operations identical, but include strict-loader refusal in the
    # operation's exception boundary; the old harness decoded NaN before its catch.
    old = (BEFORE / "receiver_challenge.py").read_text()
    old = old.replace(
        '    parsed = builder.load(raw)\n    check("non-JSON NaN accepted through loader and optional field", False, parsed)',
        '    cases.append({"case": "non-JSON NaN accepted through loader and optional field", '
        '"expectedAccepted": False, "actualAccepted": accepts(lambda: receiver.validate('
        "builder.load(raw), provenance, packages))})",
    )
    before_scratch = scratch / "before"
    before_scratch.mkdir()
    (before_scratch / "receiver_challenge.py").write_text(old)
    (before_scratch / "author-binding.json").write_text(json.dumps({"packet": str(AUTHOR)}))
    (scratch / "author-binding.json").write_text(json.dumps({"packet": str(AUTHOR)}))
    own = independent_cases(before_scratch)
    prior = json.loads((before_scratch / "receiver-challenge.json").read_bytes())
    assert prior["unexpectedAcceptances"] == []
    shutil.copyfile(before_scratch / "receiver-challenge.json", HERE / "replay-before-cases.json")
    # Comparator algorithm unchanged; use the original, explicitly bound Go source
    # for its static producer-exit assertion, and amended Python imports.
    state = (
        (BEFORE / "state_compatibility.py")
        .read_text()
        .replace(
            '(AUTHOR / "registry.go").read_text()', '(AUTHOR.parent / "registry.go").read_text()'
        )
    )
    (scratch / "state_compatibility.py").write_text(state)
    receipts.append(run(scratch / "state_compatibility.py", scratch))
    shutil.copyfile(scratch / "state-compatibility.json", HERE / "replay-state-compatibility.json")
    receipts.append(run(AUTHOR / "verify.py", scratch))
    final = binding()
    assert initial == final
    write(
        "independent-controls.json",
        {
            "cases": own,
            "passed": len(own),
            "fixtureDisclosure": "Owned Python shapes; no Go-produced observations",
        },
    )
    write(
        "binding-and-replays.json",
        {
            "before": initial,
            "after": final,
            "scratch": str(scratch),
            "receipts": receipts,
            "beforeHarnessAdaptations": [
                "NaN load moved inside exception boundary only",
                "static Go source reference uses unchanged parent",
            ],
            "GoCompiledOrRun": False,
            "executionAuthorized": False,
        },
    )
    print(
        json.dumps(
            {
                "independentCases": len(own),
                "beforeCases": len(prior["cases"]),
                "artifactIntegrity": final,
                "scratch": str(scratch),
            }
        )
    )


if __name__ == "__main__":
    main()
