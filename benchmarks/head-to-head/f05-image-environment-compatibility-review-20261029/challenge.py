"""Independent image metadata/mock admission controls; no daemon execution."""

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUTHOR = HERE.parent / "f05-image-environment-compatibility-20261029"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT / "scripts/tests"))
from bench import agent_runtime as runtime  # noqa: E402
from test_agent_runtime import session  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert digest(AUTHOR / "FREEZE.json") == (
        "d1b7e310c20b1a09f2999a1203fe7653a54981a62493ffc62d194121d0fbd408"
    )
    assert digest(Path(runtime.__file__)) == (
        "a0f355e2438ebac9dea36a62bd263c1451a51787da840ec64c138d29dddb8473"
    )
    image_path = HERE.parent / (
        "f05-dependency-preparation-20261029/image-attempt-3/logs/image-inspect/stdout.txt"
    )
    assert digest(image_path) == "4c6fa72b8b05b95a719110e0f7fa705758c224e253cf8c7cdf881218ea4f1913"
    image = json.loads(image_path.read_bytes())[0]
    results = []
    variants = [
        ("retained-b47", image["Config"]["Env"], True),
        ("legacy-null", None, True),
        ("legacy-empty", [], True),
        ("safe-two-defaults", ["GOENV=off", "GOTOOLCHAIN=local"], True),
        ("legacy-allowed-with-equals", ["LANG=value=literal"], True),
    ]
    for value in ("auto", "path", "go1.27.3", "local\n", "LOCAL", "", "local=extra"):
        variants.append(("wrong-toolchain-" + repr(value), ["GOTOOLCHAIN=" + value], False))
    for value in ("OFF", "", "/workspace/go-env", "off\x00", "off ", "off=extra"):
        variants.append(("wrong-goenv-" + repr(value), ["GOENV=" + value], False))
    for name, entries in [
        ("duplicate-allowed", ["PATH=/bin", "PATH=/bin"]),
        ("duplicate-safe", ["GOENV=off", "GOENV=off"]),
        ("conflict-safe-first", ["GOENV=off", "GOENV=/tmp/config"]),
        ("conflict-safe-last", ["GOENV=/tmp/config", "GOENV=off"]),
        ("missing-equals", ["GOENV"]),
        ("empty-name", ["=off"]),
        ("numeric-name", ["1NAME=a"]),
        ("space-name", ["GOENV =off"]),
        ("non-ascii-name", ["GÖENV=off"]),
        ("control-allowed-value", ["PATH=/bin\t/tmp"]),
        ("del-allowed-value", ["HOME=/workspace/\x7f"]),
        ("null-entry", [None]),
        ("boolean-entry", [False]),
        ("integer-entry", [0]),
        ("list-entry", [[]]),
        ("nonlist-null-object", {}),
        ("nonlist-false", False),
        ("nonlist-zero", 0),
        ("nonlist-string", "GOENV=off"),
        ("unknown-selector", ["GOARCH=arm64"]),
        ("unknown-preload", ["NODE_OPTIONS=--require=/tmp/preload"]),
        ("unknown-arbitrary", ["UNKNOWN=anything"]),
    ]:
        variants.append((name, entries, False))
    for name, entries, expected in variants:
        with tempfile.TemporaryDirectory(
            prefix="dotrepo-image-env-independent-", dir="/tmp"
        ) as tmp:
            request, config, _ = session.__wrapped__(Path(tmp))
            config["qualifications"] = dict.fromkeys(runtime.QUALIFICATIONS, True)
            request["environment"]["imageDigest"] = image["Id"]
            snapshot = deepcopy(config["environment"])
            metadata = deepcopy(image)
            metadata["Config"]["Env"] = entries
            calls = []

            def invoke(argv, **kwargs):
                calls.append(argv)
                return {
                    "stdout": json.dumps([metadata])
                    if argv[1:3] == ["image", "inspect"]
                    else "mock-id",
                    "stderr": "",
                    "exitCode": 0,
                    "error": None,
                }

            backend = runtime.DockerBackend(invoke)
            error = None
            try:
                backend.provision(request, config, 10)
            except ValueError as exc:
                error = str(exc)
            assert (error is None) is expected, (name, error)
            assert config["environment"] == snapshot
            if expected:
                assert [argv[1] for argv in calls] == ["image", "create", "start"]
                create = calls[1]
                assert {
                    "--network=none",
                    "--read-only",
                    "--cap-drop=ALL",
                    "--pull=never",
                    "--security-opt=no-new-privileges",
                    "--ipc=private",
                    "--cgroupns=private",
                } <= set(create)
                assert not any(arg.startswith(("GOENV=", "GOTOOLCHAIN=")) for arg in create)
                assert not any(
                    arg.startswith(("--privileged", "--cap-add", "--mount", "--volume", "--pid="))
                    for arg in create
                )
            else:
                assert len(calls) == 1 and calls[0][1:3] == ["image", "inspect"]
                assert backend.created is False
            backend.cleanup()
            results.append(
                {
                    "name": name,
                    "expectedProgression": expected,
                    "error": error,
                    "mockStages": [argv[1] for argv in calls],
                }
            )
    with tempfile.TemporaryDirectory(prefix="dotrepo-image-env-overrides-", dir="/tmp") as tmp:
        request, config, _ = session.__wrapped__(Path(tmp))
        for key, value in (("GOENV", "off"), ("GOTOOLCHAIN", "local")):
            bad = deepcopy(config)
            bad["environment"][key] = value
            try:
                runtime.validate_runtime(bad, request)
            except ValueError as exc:
                assert str(exc) == "container environment is not allowlisted"
            else:
                raise AssertionError("caller override admitted")
            results.append({"name": "caller-override-" + key, "refused": True})
    before = ast.parse((AUTHOR / "before/agent_runtime.py").read_text())
    after = ast.parse(Path(runtime.__file__).read_text())

    def assignment(tree, name):
        return next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
        )

    assert assignment(before, "ENV_KEYS") == assignment(after, "ENV_KEYS")
    assert not {"GOENV", "GOTOOLCHAIN"} & runtime.ENV_KEYS
    report = {
        "state": "independent-image-env-mock-controls-passed",
        "count": len(results),
        "cases": results,
        "callerENVKEYSUnchanged": True,
        "actualDaemonCalls": 0,
        "executionAuthorized": False,
        "taskOutcomeObserved": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
    }
    with (HERE / "challenge.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"count": len(results), "allPassed": True}))


if __name__ == "__main__":
    main()
