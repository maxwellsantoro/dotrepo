"""Experimental, read-only observed-recipe reader. Never executes a recipe.

Caller-supplied trusted capsule digests are trust inputs, not signatures or
self-issued review. This bounded adapter replays retained container receipts;
it does not make arbitrary observations authentic or independently rerun tests.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import re
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

FORMAT = "digest-exchange-observed-recipe/experimental-1"
POLICY = {
    "id": "observed-recipe-local-experiment-1",
    "knowledgeClass": "observed-recipe",
    "adapter": "retained-iniconfig-container-receipt-1",
    "applicability": "exact-source-recipe-environment-and-dependency-bindings-only",
    "optInRequired": True,
    "executionAuthorization": "never-granted-by-this-reader",
    "qualification": "demand-driven; not an obligatory indexing stage",
    "minimumAcceptedRuns": 2,
    "requiredLimitations": [
        "unlocked-isolated-build-dependencies",
        "boundary-network-observations",
        "single-development-task",
        "no-portability-evidence",
        "no-maintainer-endorsement",
        "no-economic-evidence",
    ],
}
LIMITS = {
    "Memory": 805306368,
    "MemorySwap": 805306368,
    "NanoCpus": 1000000000,
    "PidsLimit": 64,
    "ReadonlyRootfs": True,
    "Tmpfs": {
        "/work": "rw,exec,nosuid,size=384m,uid=1000,gid=1000,mode=0700",
        "/tmp": "rw,nosuid,noexec,size=64m,uid=1000,gid=1000,mode=0700",
    },
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def value_sha(value):
    return sha(canonical(value))


def exact(left, right):
    return canonical(left) == canonical(right)


def verifier_sha():
    return sha(Path(__file__).read_bytes())


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate-json-key")
        result[key] = value
    return result


def decode(raw):
    def reject_constant(_):
        raise ValueError("non-finite-json")

    def finite_float(value):
        result = float(value)
        require(math.isfinite(result), "non-finite-json")
        return result

    return json.loads(
        raw,
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
        parse_float=finite_float,
    )


def relative_path(name):
    require(isinstance(name, str) and name and "\\" not in name, "invalid-evidence-path")
    path = PurePosixPath(name)
    require(
        not path.is_absolute()
        and str(path) == name
        and all(part not in (".", "..") and ":" not in part for part in path.parts)
        and not any(ord(char) < 32 or ord(char) == 127 for char in name),
        "invalid-evidence-path",
    )
    return path


class Evidence:
    """Bounded local reads only, with byte receipts and no symlink traversal."""

    def __init__(self, root, inventory):
        self.root = Path(root)
        require(not self.root.is_symlink(), "symlink-evidence-root")
        require(isinstance(inventory, dict) and 0 < len(inventory) <= 500, "invalid-inventory")
        self.raw = {}
        total = 0
        for name, digest in inventory.items():
            path = self.root
            for part in relative_path(name).parts:
                path /= part
                require(not path.is_symlink(), "symlink-evidence")
            require(
                path.is_file() and path.stat().st_size <= 8 * 1024 * 1024,
                "missing-or-oversize-evidence:" + name,
            )
            raw = path.read_bytes()
            total += len(raw)
            require(total <= 16 * 1024 * 1024, "aggregate-evidence-budget")
            require(sha(raw) == digest, "evidence-hash-mismatch:" + name)
            self.raw[name] = raw

    def get(self, name):
        require(name in self.raw, "unbound-evidence:" + name)
        return self.raw[name]

    def json(self, name):
        return decode(self.get(name))


def network_isolated(observation):
    require(observation["dockerNetworks"] == {}, "attached-network")
    links = observation["links"]
    require(isinstance(links, list) and links, "missing-network-links")
    names = []
    for link in links:
        name, flags = link["ifname"], link["flags"]
        require(
            isinstance(name, str)
            and isinstance(flags, list)
            and all(isinstance(flag, str) for flag in flags),
            "malformed-network-links",
        )
        names.append(name)
        require(name == "lo" or "UP" not in flags, "up-nonloopback-interface")
    require("lo" in names and len(set(names)) == len(names), "incomplete-network-links")
    for family in ("routes4", "routes6"):
        routes = observation[family]
        require(isinstance(routes, list), "malformed-network-routes")
        require(all(route["dev"] == "lo" for route in routes), "nonloopback-route")


def container_limits(info, environment):
    host = info["HostConfig"]
    require(all(host[key] == value for key, value in LIMITS.items()), "isolation-limit-mismatch")
    require(
        not info["Mounts"]
        and not host.get("Binds")
        and not host.get("PortBindings")
        and not host.get("Privileged")
        and not host.get("CapAdd")
        and "ALL" in host["CapDrop"]
        and "no-new-privileges" in host["SecurityOpt"]
        and info["Config"]["User"] == "1000:1000",
        "isolation-contract-mismatch",
    )
    require(
        info["Image"] == environment["imageId"]
        and info["Config"]["Image"] == environment["imageReference"],
        "container-image-mismatch",
    )


def terminal(teardown, identity):
    state = teardown["terminalState"]
    require(
        teardown["containerId"] == identity
        and teardown["removed"] is True
        and state["Running"] is False
        and state["Restarting"] is False
        and state["Pid"] == 0,
        "teardown-unestablished",
    )


def replay(capsule, root, trusted_digest):
    """Establish only the recorded experiment; no applicability or permission."""
    require(
        re.fullmatch(r"[0-9a-f]{64}", trusted_digest or "") is not None,
        "missing-trusted-capsule-digest",
    )
    require(value_sha(capsule) == trusted_digest, "untrusted-or-changed-capsule")
    require(
        capsule["format"] == FORMAT and capsule["knowledgeClass"] == "observed-recipe",
        "unsupported-evidence-class",
    )
    require(
        capsule["origin"]["kind"] == "investigator-synthesis"
        and capsule["origin"]["publisherEndorsement"] is False,
        "invalid-origin-authority",
    )
    invalidation = capsule["invalidation"]
    require(invalidation["policySha256"] == value_sha(POLICY), "qualification-policy-changed")
    require(invalidation["verifierSha256"] == verifier_sha(), "evidence-verifier-changed")
    require(invalidation["strategy"] == "exact-bindings-only", "unsupported-invalidation")
    assessment = capsule["assessment"]
    require(
        assessment["limitations"] == POLICY["requiredLimitations"], "limitations-omitted-or-changed"
    )
    require(assessment["unresolvedConflicts"] == [], "conflicting-observation")
    require(
        all(value == "unestablished" for value in assessment["additionalClaims"].values())
        and set(assessment["additionalClaims"])
        == {
            "portability",
            "isolatedDependencyReproducibility",
            "maintainerEndorsement",
            "economicAdvantage",
        },
        "unsupported-additional-claim",
    )
    evidence = Evidence(root, capsule["evidence"]["artifacts"])
    manifest = {}
    for line in evidence.get("ARTIFACTS.sha256").decode().splitlines():
        digest, name = line.split("  ", 1)
        relative_path(name)
        require(name not in manifest, "duplicate-evidence-manifest-entry")
        manifest[name] = digest
    manifest["ARTIFACTS.sha256"] = sha(evidence.get("ARTIFACTS.sha256"))
    require(manifest == capsule["evidence"]["artifacts"], "incomplete-evidence-inventory")
    require(capsule["evidence"]["adapter"] == POLICY["adapter"], "unsupported-evidence-adapter")
    inputs = evidence.json("INPUTS.json")
    spec = evidence.json("SPEC.json")
    require(
        sha(evidence.get("SPEC.json")) == evidence.get("SPEC.sha256").decode().split()[0],
        "specification-receipt-mismatch",
    )
    amendment = evidence.get(inputs["activeAmendment"])
    require(sha(amendment) == inputs["amendmentSha256"], "amendment-mismatch")
    for name, digest in inputs["codeSha256"].items():
        require(sha(evidence.get(name)) == digest, "recorded-harness-changed")
    archive = evidence.get("source-checkout.tar.gz")
    require(sha(archive) == inputs["sourceArchiveSha256"], "source-archive-mismatch")
    source, recipe, environment = (capsule[key] for key in ("source", "recipe", "environment"))
    expected = inputs["expected"]
    require(
        source
        == {
            "repository": spec["task"]["repository"],
            "revision": expected["revision"],
            "tree": expected["tree"],
            "files": expected["files"],
            "dependencies": {
                "sourceArchiveSha256": inputs["sourceArchiveSha256"],
                "gitDescribe": expected["gitDescribe"],
            },
        },
        "source-or-dependency-binding-mismatch",
    )
    # Read specific regular source members; never extract files or load .git hooks.
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        require(len(tar.getmembers()) <= 1000, "archive-member-budget")
        for name, digest in source["files"].items():
            member = tar.getmember("checkout/" + str(relative_path(name)))
            require(member.isfile() and member.size <= 2 * 1024 * 1024, "invalid-source-member")
            require(sha(tar.extractfile(member).read()) == digest, "archived-source-mismatch")
    require(
        recipe
        == {
            "purpose": spec["task"]["purpose"],
            "scope": spec["task"]["scope"],
            "component": spec["task"]["component"],
            "workingDirectory": spec["task"]["workingDirectory"],
            "containerWorkingDirectory": spec["recipe"]["workingDirectory"],
            "steps": [{"id": stage, "argv": spec["recipe"][stage]} for stage in ("setup", "test")],
            "prerequisites": [
                "Complete frozen checkout with Git history and tags",
                "Pinned container image and recorded isolation limits",
            ],
            "transition": "Disconnect setup network and validate isolation before first upstream import",
        },
        "recipe-or-step-binding-mismatch",
    )
    require(
        environment["imageId"] == inputs["imageId"]
        and environment["imageReference"] == inputs["imageReference"]
        and environment["architecture"] == expected["architecture"]
        and environment["system"] == "Linux"
        and environment["limits"] == LIMITS,
        "environment-binding-mismatch",
    )
    require(
        environment["unresolvedDependencies"]
        == ["isolated setuptools/setuptools-scm versions", "generated _version.py bytes"],
        "unresolved-dependencies-invented-or-omitted",
    )
    for key in ("pythonVersion", "pythonBinarySha256", "packageVersion", "gitDescribe"):
        require(environment[key] == expected[key], "environment-version-mismatch")
    oracle = capsule["testOracle"]
    require(
        oracle["caseNames"] == expected["testCases"]
        and oracle["sourceSha256"] == expected["files"]["testing/test_iniconfig.py"]
        and oracle["className"] == "testing.test_iniconfig",
        "test-oracle-mismatch",
    )
    protocol = capsule["evidence"]["acceptedProtocol"]
    require(relative_path(protocol).parts == (protocol,), "invalid-protocol-path")
    report = evidence.json(protocol + "/report.json")
    require(
        report["outcome"] == "go-for-this-recipe-only"
        and report["assignedRuns"] == report["completedRuns"] == report["passedRuns"] == 2
        and len(report["runs"]) == 2
        and 0 < report["wallSeconds"] <= 600,
        "assigned-runs-not-established",
    )
    require(evidence.json(protocol + "/input-receipt.json") == inputs, "execution-receipt-mismatch")
    control = evidence.json(protocol + "/timeout-control.json")
    require(
        control["pass"] is True
        and control["expectedTimeout"] is True
        and control["childObserved"] is True
        and "sleep 300" in control["processesBeforeTermination"],
        "timeout-control-missing",
    )
    terminal(control["teardown"], control["teardown"]["containerId"])
    for repeat, row in enumerate(report["runs"]):
        stem = f"{protocol}/run-{repeat + 1:03}/"
        require(
            row == evidence.json(stem + "result.json")
            and row["repeat"] == repeat
            and row["pass"] is True
            and row["failure"] is None
            and row["reasons"] == [],
            "run-result-mismatch",
        )
        require(row["testCases"] == len(oracle["caseNames"]), "run-test-count-mismatch")
        terminal(row["teardown"], row["containerId"])
        for stage in ("setup", "test"):
            metrics = evidence.json(stem + stage + ".json")
            require(
                metrics["command"] == spec["recipe"][stage]
                and metrics["exitCode"] == 0
                and metrics["stopReason"] is None,
                "skipped-or-failed-step:" + stage,
            )
            require(
                0 < metrics["wallSeconds"] <= (180 if stage == "setup" else 60)
                and 0 < metrics["observedOutputBytes"] <= 1048576
                and 0 <= metrics["networkInterfaceBytes"] <= (67108864 if stage == "setup" else 0),
                "stage-budget-violation",
            )
            require(
                len(evidence.get(stem + stage + ".log")) == metrics["observedOutputBytes"],
                "missing-or-incomplete-stage-log",
            )
            require(
                evidence.json(stem + stage + "-controller.stdout") == metrics,
                "stage-controller-receipt-mismatch",
            )
        for boundary in ("before-import", "after-test"):
            network = evidence.json(stem + "network-" + boundary + ".json")
            network_isolated(network)
            info = evidence.json(stem + "container-" + boundary + ".json")
            container_limits(info, environment)
            require(
                info["Id"] == row["containerId"]
                and info["NetworkSettings"]["Networks"] == network["dockerNetworks"],
                "network-container-binding-mismatch",
            )
        for boundary in ("before", "after"):
            probe = evidence.json(stem + "probe-" + boundary + ".json")
            require(
                probe["gitHead"] == source["revision"]
                and probe["gitTree"] == source["tree"]
                and probe["trackedSha256"] == source["files"]
                and probe["trackedBytesUnchanged"] is True
                and probe["gitTrackedStatus"] == "",
                "source-provenance-mismatch",
            )
            for key in (
                "system",
                "architecture",
                "pythonVersion",
                "pythonBinarySha256",
                "pythonExecutable",
                "prefix",
                "packagePath",
                "packageVersion",
                "gitDescribe",
                "installedPackages",
                "directUrl",
            ):
                require(probe[key] == environment[key], "provenance-environment-mismatch:" + key)
            require(
                probe["packageSha256"] == source["files"]["src/iniconfig/__init__.py"],
                "wrong-imported-package",
            )
        junit = ET.fromstring(evidence.get(stem + "results.xml"))
        cases = junit.findall(".//testcase")
        require(
            Counter(case.get("name") for case in cases) == Counter(oracle["caseNames"])
            and all(case.get("classname") == oracle["className"] for case in cases),
            "incomplete-or-duplicate-test-coverage",
        )
        require(
            not any(junit.findall(".//" + tag) for tag in ("error", "failure", "skipped"))
            and all(
                int(element.get(field, "0")) == 0
                for element in junit.iter()
                for field in ("failures", "errors", "skipped")
            ),
            "test-failure-or-skip",
        )
    review = evidence.json("review-provenance.json")
    require(
        review["acceptedInputsSha256"] == sha(evidence.get("INPUTS.json"))
        and review["acceptedReportSha256"] == sha(evidence.get(protocol + "/report.json"))
        and review["finalReportSha256"] == sha(evidence.get("independent-review.md"))
        and review["agent"] == assessment["reviewer"]
        and review["reviewIsHumanMaintainerApproval"] is False,
        "review-binding-mismatch",
    )
    history = []
    for name in capsule["evidence"]["historicalProtocols"]:
        old = evidence.json(str(relative_path(name)) + "/report.json")
        history.append(
            {
                "protocol": name,
                "outcome": old["outcome"],
                "assignedRuns": old["assignedRuns"],
                "passedRuns": old["passedRuns"],
            }
        )
    require(
        history == assessment["historicalObservations"]
        and len(history) == 3
        and len({row["protocol"] for row in history}) == len(history)
        and sum(row["assignedRuns"] for row in history) == 6
        and all(row["outcome"] == "no-go" and row["passedRuns"] == 0 for row in history),
        "historical-failures-omitted-or-changed",
    )
    return {
        "state": "established",
        "reasons": [],
        "acceptedRuns": 2,
        "caseCountEach": len(oracle["caseNames"]),
        "historicalObservations": history,
        "meaning": "Retained experiment receipts validated; upstream code was not rerun.",
    }


def evaluate(capsule, root, request, *, trusted_digest, allow_observed_recipes=False):
    """Return three independent decisions; execution authority is always withheld."""
    result = {
        "knowledgeClass": "observed-recipe",
        "experimental": True,
        "capsuleSha256": value_sha(capsule),
        "policySha256": value_sha(POLICY),
        "established": {"state": "unestablished", "reasons": []},
        "applicable": {"state": "abstain", "reasons": []},
        "authorized": {"state": "not-granted", "reasons": ["reader-never-grants-execution"]},
        "recipe": None,
    }
    try:
        result["established"] = replay(capsule, root, trusted_digest)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        IndexError,
        tarfile.TarError,
        ET.ParseError,
        UnicodeError,
    ) as exc:
        result["established"]["reasons"] = ["invalid-evidence:" + str(exc)]
        result["applicable"]["reasons"] = ["experiment-not-established"]
        return result
    reasons = []
    if allow_observed_recipes is not True:
        reasons.append("experimental-policy-opt-in-required")
    if not isinstance(request, dict):
        reasons.append("missing-consumer-situation")
        request = {}
    try:
        canonical(request)
    except (ValueError, TypeError, OverflowError, RecursionError):
        reasons.append("malformed-consumer-situation")
        request = {}
    allowed = {
        "task",
        "files",
        "dependencies",
        "environment",
        "recipeSha256",
        "acceptedLimitations",
        "requirements",
    }
    if set(request) != allowed:
        reasons.append("incomplete-or-unsupported-request")
    expected_task = {key: capsule["source"][key] for key in ("repository", "revision", "tree")}
    expected_task.update(
        {
            key: capsule["recipe"][key]
            for key in ("purpose", "scope", "component", "workingDirectory")
        }
    )
    for field, expected in (
        ("task", expected_task),
        ("files", capsule["source"]["files"]),
        ("dependencies", capsule["source"]["dependencies"]),
        ("environment", capsule["environment"]),
        ("recipeSha256", value_sha(capsule["recipe"])),
    ):
        if not exact(request.get(field), expected):
            reasons.append(field + "-mismatch-or-missing")
    if not exact(request.get("acceptedLimitations"), capsule["assessment"]["limitations"]):
        reasons.append("limitations-not-explicitly-accepted")
    if not exact(
        request.get("requirements"),
        {"portable": False, "fullyReproducibleDependencies": False, "maintainerEndorsed": False},
    ):
        reasons.append("unsupported-or-unassessed-consumer-requirement")
    result["applicable"] = {
        "state": "abstain" if reasons else "suggestible",
        "reasons": reasons,
        "meaning": "Exact declared target only; actual target and permission need separate checks.",
    }
    result["limitations"] = capsule["assessment"]["limitations"]
    result["additionalClaims"] = capsule["assessment"]["additionalClaims"]
    result["source"] = capsule["source"]
    result["environment"] = capsule["environment"]
    result["assessment"] = capsule["assessment"]
    protocol = capsule["evidence"]["acceptedProtocol"]
    inventory = capsule["evidence"]["artifacts"]
    result["evidence"] = {
        "acceptedProtocol": protocol,
        "inputReceiptSha256": inventory[protocol + "/input-receipt.json"],
        "executionReportSha256": inventory[protocol + "/report.json"],
        "independentReviewSha256": inventory["independent-review.md"],
        "packetManifestSha256": inventory["ARTIFACTS.sha256"],
        "interpretation": "Bound retained evidence; no new upstream execution or reviewer authentication.",
    }
    if not reasons:
        result["recipe"] = capsule["recipe"]
    return copy.deepcopy(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsule", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--trusted-capsule-sha256", required=True)
    parser.add_argument("--allow-observed-recipes", action="store_true")
    args = parser.parse_args()
    try:
        require(
            args.capsule.stat().st_size <= 1048576 and args.request.stat().st_size <= 1048576,
            "input-size-budget",
        )
        result = evaluate(
            decode(args.capsule.read_bytes()),
            args.evidence_root,
            decode(args.request.read_bytes()),
            trusted_digest=args.trusted_capsule_sha256,
            allow_observed_recipes=args.allow_observed_recipes,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(
            json.dumps({"error": str(exc), "recipe": None, "authorized": {"state": "not-granted"}})
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["established"]["state"] == "established" else 1


if __name__ == "__main__":
    raise SystemExit(main())
