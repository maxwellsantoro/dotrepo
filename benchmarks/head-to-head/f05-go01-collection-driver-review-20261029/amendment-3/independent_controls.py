"""Current-subject/closure and full fake-path controls; no subprocess/network."""

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
binding = json.loads((HERE / "author-binding.json").read_text())
sys.path.insert(0, binding["scriptCopy"])
collection = importlib.import_module("collection")
controls = importlib.import_module("controls")
listing = importlib.import_module("listing")


def verdict(operation):
    try:
        return True, operation()
    except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
        return False, type(error).__name__ + ": " + str(error)


def main():
    plan = collection.load_plan()
    subject = collection.current_subject(plan)
    actual_freeze = Path(binding["freeze"])
    assert subject["authorFreezeSha256"] == collection.file_sha(actual_freeze)
    checks = []

    def record(case, expected, operation):
        accepted, detail = verdict(operation)
        assert accepted == expected, (case, accepted, detail)
        checks.append(
            {
                "case": case,
                "passed": True,
                "accepted": accepted,
                "reason": detail if isinstance(detail, str) else None,
            }
        )

    record("actual-complete-author-subject", True, lambda: collection.current_subject(plan))
    copy = Path(binding["scriptCopy"])
    frozen_bytes = (copy / "FREEZE.json").read_bytes()
    for name, mutate in [
        ("missing-plan-artifact", lambda f: f["artifactSha256"].pop("plan.json")),
        ("missing-current-script", lambda f: f["artifactSha256"].pop("listing.py")),
        (
            "wrong-current-script-hash",
            lambda f: f["artifactSha256"].update({"listing.py": "0" * 64}),
        ),
        ("missing-local-decision", lambda f: f["artifactSha256"].pop("tmpfs-retrospective.json")),
        ("old-plan-top-level", lambda f: f.update(driverPlanSha256="0" * 64)),
        ("wrong-packet-identity", lambda f: f.update(identity="old-packet")),
    ]:
        value = json.loads(frozen_bytes)
        mutate(value)
        (copy / "FREEZE.json").write_text(json.dumps(value))
        record("closure-" + name, False, lambda: collection.current_subject(plan))
        (copy / "FREEZE.json").write_bytes(frozen_bytes)
    for name in ["listing.py", "compiler-context-decision.json"]:
        path = copy / name
        data = path.read_bytes()
        path.write_bytes(data + b"\n")
        record("changed-byte-" + name, False, lambda: collection.current_subject(plan))
        path.write_bytes(data)
    changed = deepcopy(plan)
    changed["scripts"].pop("listing.py")
    record("incomplete-provided-plan", False, lambda: collection.current_subject(changed))

    with tempfile.TemporaryDirectory(
        prefix="dotrepo-go01-amendment-independent-", dir="/tmp"
    ) as folder:
        root = Path(folder).resolve()
        acceptance = {
            "state": "coordinator-accepted-go01-no-npm-go-projection-collection",
            "synthetic": False,
            "driverSubject": deepcopy(subject),
            **{k: plan[k] for k in ["sourceArchiveSha256", "imageId", "environmentSha256"]},
            "projectionSha256": plan["projection"]["archive"]["sha256"],
            "projectionSpecSha256": plan["projectionSpecSha256"],
            "initAndTestMainExecutionAccepted": True,
            "noNpmProvisioning": True,
            "nativeTaskAdmitted": False,
            "campaignAdmitted": False,
            "cacheGloballyQualified": False,
            "sourceScopeReviewFreeze": deepcopy(plan["collectionScopeReview"]),
            "projectionReviewFreeze": deepcopy(plan["collectionScopeReview"]),
        }
        base_auth = {
            "state": "coordinator-authorized-single-go01-collection-attempt",
            "synthetic": False,
            "planSha256": subject["driverPlanSha256"],
            "authorFreezeSha256": subject["authorFreezeSha256"],
            "commands": collection.COMMANDS,
            "limits": plan["limits"],
            "maxAttempts": 1,
        }

        def materialize(label, review, accept=None, auth=None):
            r = root / (label + "-review.json")
            collection.write(r, review)
            a = deepcopy(acceptance if accept is None else accept)
            a["driverReviewFreeze"] = {"path": str(r), "sha256": collection.file_sha(r)}
            a_path = root / (label + "-acceptance.json")
            collection.write(a_path, a)
            v = deepcopy(base_auth if auth is None else auth)
            v.update(
                output=str(root / (label + "-output")),
                scratch=str(root / (label + "-scratch")),
                collectionAcceptance={"path": str(a_path), "sha256": collection.file_sha(a_path)},
            )
            path = root / (label + "-auth.json")
            collection.write(path, v)
            return path, Path(v["output"]), Path(v["scratch"])

        passed = controls.passed_review(deepcopy(subject))
        for label, mutate in [
            ("current", lambda r: None),
            ("old-review-plan", lambda r: r["subject"].update(driverPlanSha256="0" * 64)),
            ("old-review-freeze", lambda r: r["subject"].update(authorFreezeSha256="0" * 64)),
            ("old-review-packet", lambda r: r["subject"].update(packetIdentity="old")),
            ("wrong-state", lambda r: r.update(state="findings-pending")),
            ("wrong-scope", lambda r: r.update(scope="native-task")),
            ("findings-present", lambda r: r.update(findings=[{"unresolved": True}])),
            ("findings-missing", lambda r: r.pop("findings")),
            ("findings-wrong-type", lambda r: r.update(findings={})),
            ("synthetic-review", lambda r: r.update(synthetic=True)),
            ("native-admission", lambda r: r.update(nativeTaskAdmitted=True)),
            ("campaign-admission", lambda r: r.update(campaignAdmitted=True)),
            ("global-cache-admission", lambda r: r.update(cacheGloballyQualified=True)),
            ("execution-admission", lambda r: r.update(executionAuthorized=True)),
            ("missing-false-flag", lambda r: r.pop("executionAuthorized")),
        ]:
            review = deepcopy(passed)
            mutate(review)
            path, out, scratch = materialize(label, review)
            record(
                "review-" + label,
                label == "current",
                lambda: collection.authorize(plan, path, out, scratch),
            )
        for label, review in [
            ("arbitrary", {"hashValidButNotReview": True}),
            ("actual-before-review", json.loads((HERE.parent / "review.json").read_text())),
        ]:
            path, out, scratch = materialize(label, review)
            record("review-" + label, False, lambda: collection.authorize(plan, path, out, scratch))
        for key in subject:
            value = deepcopy(acceptance)
            value["driverSubject"][key] = "old"
            path, out, scratch = materialize("accept-" + key, passed, value)
            record(
                "acceptance-" + key, False, lambda: collection.authorize(plan, path, out, scratch)
            )
        auth = deepcopy(base_auth)
        auth["authorFreezeSha256"] = "0" * 64
        path, out, scratch = materialize("auth-old-freeze", passed, auth=auth)
        record("auth-old-freeze", False, lambda: collection.authorize(plan, path, out, scratch))

        def inputs(*args):
            source = root / "source.bytes"
            cache = root / "cache.bytes"
            source.write_bytes(b"owned")
            cache.write_bytes(b"cache")
            return (
                source,
                cache,
                controls.FILES,
                {"go/pkg/mod/owned": controls.FILES["README"]},
                collection.tree_expected(controls.FILES),
            )

        for label, bad_review, failure in [
            ("full-current", False, None),
            ("full-unrelated", True, None),
            ("full-create-failure", False, "create"),
            ("full-cleanup-failure", False, "cleanup"),
        ]:
            path, out, scratch = materialize(label, {"unrelated": True} if bad_review else passed)
            fake = controls.Fake(plan, failure, [0])
            result = collection.run(
                path,
                out,
                scratch,
                backend=fake,
                plan_loader=lambda: deepcopy(plan),
                input_check=inputs,
                clock=lambda: 0,
            )
            expected = label == "full-current"
            assert (result["state"] == "native-top-level-collection-observed") == expected, (
                label,
                result,
            )
            assert result["synthetic"] is True and result["nativeCollectionOccurred"] is False
            assert all(
                result[k] is False
                for k in [
                    "taskOutcomeObserved",
                    "nativeTaskAdmitted",
                    "campaignAdmitted",
                    "cacheGloballyQualified",
                ]
            )
            assert result["costUsd"] is None and (out / "result.json").exists()
            if bad_review:
                assert fake.calls == []
            if result["containerCreateAttempted"]:
                assert any(row[0] == "cleanup" for row in fake.calls)
            checks.append(
                {
                    "case": label,
                    "passed": True,
                    "result": result,
                    "labels": [row[0] for row in fake.calls],
                }
            )

    rows = controls.package_rows()
    files = deepcopy(controls.FILES)

    def packages(candidate, selected=files):
        return listing.packages(b"\n".join(json.dumps(row).encode() for row in candidate), selected)

    record("source-membership-positive", True, lambda: packages(rows))
    for name, mutate in [
        ("missing-file", lambda r: r[0].update(GoFiles=["not-retained.go"])),
        ("cross-field-duplicate", lambda r: r[0].update(CgoFiles=["owned.go"])),
        ("control-character", lambda r: r[0].update(GoFiles=["x\x00.go"])),
        ("absolute-file", lambda r: r[0].update(GoFiles=["/x.go"])),
    ]:
        candidate = deepcopy(rows)
        mutate(candidate)
        record("source-membership-" + name, False, lambda: packages(candidate))
    state = controls.metadata(plan)
    env = dict(x.split("=", 1) for x in state["Config"]["Env"])
    record("strict-tmpfs-positive", True, lambda: collection.inspect(state, env))
    for name, mutate in [
        ("extra-root", lambda m: m.update({"/workspace/extra": m["/workspace"]})),
        ("duplicate-size", lambda m: m.update({"/workspace": m["/workspace"] + ",size=8g"})),
        ("conflicting-size", lambda m: m.update({"/workspace": m["/workspace"] + ",size=16g"})),
        ("security-override", lambda m: m.update({"/tmp": m["/tmp"] + ",suid"})),
    ]:
        candidate = deepcopy(state)
        mutate(candidate["HostConfig"]["Tmpfs"])
        record("strict-tmpfs-" + name, False, lambda: collection.inspect(candidate, env))
    collection.write(
        HERE / "independent-controls.json",
        {
            "passed": len(checks),
            "checks": checks,
            "subject": subject,
            "fixtureDisclosure": "Owned synthetic review/auth shapes only. They do not authorize native action.",
            "realDaemonGoCargoPackageUpstreamNativeProviderNetworkCalls": 0,
        },
    )
    print(json.dumps({"passed": len(checks), "subject": subject, "realDaemonCalls": 0}))


if __name__ == "__main__":
    main()
