"""Real receipt replay and hostile mutations; no upstream code execution."""

from __future__ import annotations

import copy
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures/repodigest"
sys.path.insert(0, str(ROOT / "scripts"))
import observed_recipe as reader  # noqa: E402

PACKET = FIXTURES / "digest-exchange-observed-recipe-prototype-20261029"
PARENT = PACKET.parent / "digest-exchange-r1-iniconfig-execution-20261029"
OBSERVATION = FIXTURES / "digest-exchange-observed-recipe-consumer-pilot-20261029/reader-amendment"


@pytest.fixture
def observation():
    # Decode the unchanged retained witness; do not rebuild or reanchor it to
    # make a changed verifier pass. Each mutation test receives fresh objects.
    return tuple(
        reader.decode((OBSERVATION / name).read_bytes())
        for name in ("capsule.json", "request.json")
    )


def evaluate(capsule, request, root=PARENT, *, opt_in=True, anchor=None):
    return reader.evaluate(
        capsule,
        root,
        request,
        trusted_digest=reader.value_sha(capsule) if anchor is None else anchor,
        allow_observed_recipes=opt_in,
    )


def assert_abstains(result, *, original_established=False):
    assert result["recipe"] is None
    assert result["applicable"]["state"] == "abstain"
    assert result["authorized"]["state"] == "not-granted"
    assert result["established"]["state"] == (
        "established" if original_established else "unestablished"
    )


def test_real_receipts_replay_three_separate_decisions(observation, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("reader must not execute or contact a service")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    capsule, request = observation
    result = evaluate(capsule, request)
    assert result["established"]["state"] == "established"
    assert result["established"]["acceptedRuns"] == 2
    assert result["established"]["caseCountEach"] == 54
    assert sum(row["assignedRuns"] for row in result["established"]["historicalObservations"]) == 6
    assert result["applicable"]["state"] == "suggestible"
    assert result["authorized"]["state"] == "not-granted"
    assert result["recipe"] == capsule["recipe"]
    assert set(result["additionalClaims"].values()) == {"unestablished"}


def test_opt_in_is_not_establishment_or_permission(observation):
    capsule, request = observation
    for opt_in in (False, None, "yes", 1):
        assert_abstains(evaluate(capsule, request, opt_in=opt_in), original_established=True)


@pytest.mark.parametrize("anchor", ["", "0" * 64, "not-a-digest"])
def test_trust_anchor_cannot_be_self_issued_by_an_untrusted_capsule(observation, anchor):
    capsule, request = observation
    assert_abstains(evaluate(capsule, request, anchor=anchor))


@pytest.mark.parametrize(
    "mutation",
    [
        "repository",
        "revision",
        "tree",
        "scope",
        "directory",
        "purpose",
        "component",
        "file-missing",
        "file-added",
        "file-changed",
        "dependency-missing",
        "dependency-changed",
        "image",
        "architecture",
        "python",
        "package",
        "environment-missing",
        "recipe",
        "portability",
        "reproducibility",
        "endorsement",
        "limitations",
        "unknown-field",
        "numeric-boolean",
        "empty-request",
    ],
)
def test_changed_consumer_target_abstains_without_erasing_the_observation(observation, mutation):
    capsule, request = observation
    if mutation in ("repository", "revision", "tree", "scope", "purpose", "component"):
        request["task"][mutation] = "different"
    elif mutation == "directory":
        request["task"]["workingDirectory"] = "testing"
    elif mutation == "file-missing":
        request["files"].pop("uv.lock")
    elif mutation == "file-added":
        request["files"]["CONTRIBUTING.md"] = "a" * 64
    elif mutation == "file-changed":
        request["files"]["uv.lock"] = "a" * 64
    elif mutation == "dependency-missing":
        request["dependencies"].pop("sourceArchiveSha256")
    elif mutation == "dependency-changed":
        request["dependencies"]["gitDescribe"] = "v0.0"
    elif mutation == "environment-missing":
        del request["environment"]
    elif mutation in ("image", "architecture", "python", "package"):
        key, value = {
            "image": ("imageReference", "other@sha256:" + "0" * 64),
            "architecture": ("architecture", "x86_64"),
            "python": ("pythonVersion", [3, 13, 0]),
            "package": ("packageVersion", "0.0"),
        }[mutation]
        request["environment"][key] = value
    elif mutation == "recipe":
        request["recipeSha256"] = "0" * 64
    elif mutation in ("portability", "reproducibility", "endorsement"):
        key = {
            "portability": "portable",
            "reproducibility": "fullyReproducibleDependencies",
            "endorsement": "maintainerEndorsed",
        }[mutation]
        request["requirements"][key] = True
    elif mutation == "limitations":
        request["acceptedLimitations"] = []
    elif mutation == "unknown-field":
        request["execute"] = True
    elif mutation == "numeric-boolean":
        request["environment"]["limits"]["ReadonlyRootfs"] = 1
    else:
        request.clear()
    assert_abstains(evaluate(capsule, request), original_established=True)


@pytest.mark.parametrize(
    "mutation",
    [
        "step-removed",
        "step-order",
        "source",
        "file",
        "dependency",
        "environment",
        "policy",
        "verifier",
        "reviewer",
        "conflict",
        "limitation",
        "endorsement",
        "additional-claim",
        "old-negative-protocol",
        "history-omitted",
        "adapter",
    ],
)
def test_reanchoring_changed_capsule_does_not_bypass_semantic_evidence_checks(
    observation, mutation
):
    capsule, request = observation
    if mutation == "step-removed":
        capsule["recipe"]["steps"].pop(0)
    elif mutation == "step-order":
        capsule["recipe"]["steps"].reverse()
    elif mutation == "source":
        capsule["source"]["revision"] = "0" * 40
    elif mutation == "file":
        capsule["source"]["files"].pop("uv.lock")
    elif mutation == "dependency":
        capsule["source"]["dependencies"].clear()
    elif mutation == "environment":
        capsule["environment"]["pythonVersion"] = [3, 13, 0]
    elif mutation in ("policy", "verifier"):
        capsule["invalidation"][mutation + "Sha256"] = "0" * 64
    elif mutation == "reviewer":
        capsule["assessment"]["reviewer"] = "self-issued"
    elif mutation == "conflict":
        capsule["assessment"]["unresolvedConflicts"] = ["same tuple failed later"]
    elif mutation == "limitation":
        capsule["assessment"]["limitations"] = []
    elif mutation == "endorsement":
        capsule["origin"]["publisherEndorsement"] = True
    elif mutation == "additional-claim":
        capsule["assessment"]["additionalClaims"]["portability"] = "established"
    elif mutation == "old-negative-protocol":
        capsule["evidence"]["acceptedProtocol"] = "run-003"
    elif mutation == "history-omitted":
        capsule["evidence"]["historicalProtocols"].clear()
    else:
        capsule["evidence"]["adapter"] = "any-recipe"
    assert_abstains(evaluate(capsule, request))


def replace_artifact(root, capsule, name, value):
    raw = json.dumps(value).encode() if isinstance(value, (dict, list)) else value
    (root / name).write_bytes(raw)
    capsule["evidence"]["artifacts"][name] = reader.sha(raw)
    # Rebind both manifest and capsule, so semantic guards must reject the lie.
    inventory = capsule["evidence"]["artifacts"]
    manifest = "".join(
        digest + "  " + path + "\n"
        for path, digest in inventory.items()
        if path != "ARTIFACTS.sha256"
    ).encode()
    (root / "ARTIFACTS.sha256").write_bytes(manifest)
    inventory["ARTIFACTS.sha256"] = reader.sha(manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-artifact",
        "changed-bytes",
        "missing-dependency-archive",
        "step-skipped",
        "wrong-argv",
        "missing-log",
        "missing-parameter",
        "duplicate-parameter",
        "skip",
        "missing-provenance",
        "source-change",
        "wrong-import",
        "network-up",
        "route",
        "network-missing",
        "teardown",
        "timeout",
        "review",
        "limits",
    ],
)
def test_corrupted_or_incomplete_receipts_cannot_qualify(observation, tmp_path, mutation):
    capsule, request = observation
    root = tmp_path / "evidence"
    shutil.copytree(PARENT, root, ignore=shutil.ignore_patterns("__pycache__"))
    stem = "run-004/run-001/"
    if mutation in ("missing-artifact", "changed-bytes"):
        path = root / (stem + "setup.json")
        path.unlink() if mutation == "missing-artifact" else path.write_bytes(b"{}")
    elif mutation == "missing-dependency-archive":
        del capsule["evidence"]["artifacts"]["source-checkout.tar.gz"]
    elif mutation in ("step-skipped", "wrong-argv"):
        name = stem + "setup.json"
        value = reader.decode((root / name).read_bytes())
        value["exitCode"] = None if mutation == "step-skipped" else 0
        if mutation == "wrong-argv":
            value["command"] = ["true"]
        replace_artifact(root, capsule, name, value)
    elif mutation == "missing-log":
        replace_artifact(root, capsule, stem + "test.log", b"")
    elif mutation in ("missing-parameter", "duplicate-parameter", "skip"):
        import xml.etree.ElementTree as ET

        name = stem + "results.xml"
        xml = ET.fromstring((root / name).read_bytes())
        suite = xml.find("testsuite")
        cases = suite.findall("testcase")
        if mutation == "missing-parameter":
            suite.remove(cases[0])
        elif mutation == "duplicate-parameter":
            cases[1].set("name", cases[0].get("name"))
        else:
            ET.SubElement(cases[0], "skipped")
        replace_artifact(root, capsule, name, ET.tostring(xml))
    elif mutation in ("missing-provenance", "source-change", "wrong-import"):
        name = stem + "probe-before.json"
        value = reader.decode((root / name).read_bytes())
        if mutation == "missing-provenance":
            value.pop("pythonBinarySha256")
        elif mutation == "source-change":
            value["trackedSha256"]["uv.lock"] = "0" * 64
        else:
            value["packagePath"] = "/installed/other/iniconfig.py"
        replace_artifact(root, capsule, name, value)
    elif mutation in ("network-up", "route", "network-missing"):
        name = stem + "network-before-import.json"
        value = reader.decode((root / name).read_bytes())
        if mutation == "network-up":
            value["links"][-1]["flags"].append("UP")
        elif mutation == "route":
            value["routes6"].append({"dev": "eth0"})
        else:
            value.pop("routes6")
        replace_artifact(root, capsule, name, value)
    elif mutation == "teardown":
        for name in (stem + "result.json", "run-004/report.json"):
            value = reader.decode((root / name).read_bytes())
            row = value["runs"][0] if "runs" in value else value
            row["teardown"]["removed"] = False
            replace_artifact(root, capsule, name, value)
    elif mutation == "timeout":
        name = "run-004/timeout-control.json"
        value = reader.decode((root / name).read_bytes())
        value["childObserved"] = False
        replace_artifact(root, capsule, name, value)
    elif mutation == "review":
        name = "review-provenance.json"
        value = reader.decode((root / name).read_bytes())
        value["acceptedInputsSha256"] = "0" * 64
        replace_artifact(root, capsule, name, value)
    else:
        name = stem + "container-before-import.json"
        value = reader.decode((root / name).read_bytes())
        value["HostConfig"]["MemorySwap"] = -1
        replace_artifact(root, capsule, name, value)
    assert_abstains(evaluate(capsule, request, root))


@pytest.mark.parametrize(
    "path", ["../outside", "/absolute", "a/../b", "a//b", "./file", "C:/x", "a\\b"]
)
def test_evidence_paths_cannot_escape_root(observation, path):
    capsule, request = observation
    capsule["evidence"]["artifacts"] = {path: "0" * 64}
    assert_abstains(evaluate(capsule, request))


def test_symlink_evidence_and_duplicate_json_keys_fail_closed(observation, tmp_path):
    capsule, request = observation
    root = tmp_path / "link"
    root.symlink_to(PARENT, target_is_directory=True)
    assert_abstains(evaluate(capsule, request, root))
    with pytest.raises(ValueError, match="duplicate-json-key"):
        reader.decode(b'{"exitCode": 1, "exitCode": 0}')


def test_request_alias_cannot_modify_the_established_capsule(observation):
    capsule, request = observation
    before = copy.deepcopy(capsule)
    request["environment"]["installedPackages"].clear()
    assert capsule == before


def test_cli_opt_in_returns_a_plan_but_has_no_execute_option(observation, tmp_path):
    capsule, request = observation
    for name, value in (("capsule", capsule), ("request", request)):
        (tmp_path / (name + ".json")).write_text(json.dumps(value))
    command = [
        "uv",
        "run",
        "--offline",
        "python",
        str(ROOT / "scripts/observed_recipe.py"),
        "--capsule",
        str(tmp_path / "capsule.json"),
        "--request",
        str(tmp_path / "request.json"),
        "--evidence-root",
        str(PARENT),
        "--trusted-capsule-sha256",
        reader.value_sha(capsule),
    ]
    for opted_in in (False, True):
        result = subprocess.run(
            command + (["--allow-observed-recipes"] if opted_in else []),
            cwd=ROOT,
            capture_output=True,
            timeout=15,
            check=True,
        )
        result = json.loads(result.stdout)
        assert result["established"]["state"] == "established"
        assert result["applicable"]["state"] == ("suggestible" if opted_in else "abstain")
        assert result["authorized"]["state"] == "not-granted"
    rejected = subprocess.run(command + ["--execute"], cwd=ROOT, capture_output=True, timeout=15)
    assert rejected.returncode == 2
    assert b"unrecognized arguments: --execute" in rejected.stderr


@pytest.mark.parametrize("knowledge", ["publisher-instruction", "extracted-instruction"])
def test_observed_reader_does_not_inherit_other_knowledge_authority(observation, knowledge):
    capsule, request = observation
    capsule["knowledgeClass"] = knowledge
    assert_abstains(evaluate(capsule, request))


def test_original_preflight_capsule_is_invalidated_by_changed_verifier(observation):
    _, request = observation
    fixture = PACKET / "development-fixture"
    old = reader.decode((fixture / "capsule.json").read_bytes())
    result = reader.evaluate(
        old,
        PARENT,
        request,
        trusted_digest=(fixture / "capsule.sha256").read_text().strip(),
        allow_observed_recipes=True,
    )
    assert_abstains(result)
    assert "evidence-verifier-changed" in result["established"]["reasons"][0] or (
        "qualification-policy-changed" in result["established"]["reasons"][0]
    )


def test_duplicate_historical_protocols_cannot_replace_distinct_rejected_runs(observation):
    capsule, request = observation
    capsule["evidence"]["historicalProtocols"] = ["run-001"] * 3
    capsule["assessment"]["historicalObservations"] = [
        capsule["assessment"]["historicalObservations"][0]
    ] * 3
    result = evaluate(capsule, request)
    assert_abstains(result)
    assert "historical-failures-omitted-or-changed" in result["established"]["reasons"][0]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_request_abstains_while_preserving_original_establishment(observation, value):
    capsule, request = observation
    request["environment"]["pythonVersion"] = value
    result = evaluate(capsule, request)
    assert_abstains(result, original_established=True)
    assert "malformed-consumer-situation" in result["applicable"]["reasons"]


@pytest.mark.parametrize("value", [b"1e999", b"-1e999"])
def test_json_exponent_overflow_is_rejected_as_nonfinite(value):
    with pytest.raises(ValueError, match="non-finite-json"):
        reader.decode(b'{"value":' + value + b"}")
