"""Scoped synthetic regressions for review subject, tmpfs and selected Go files."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile

import collection
import controls  # Denies real process/socket calls before any driver operation.
import listing

HERE = Path(__file__).resolve().parent


def accepted(operation):
    try:
        operation()
        return True
    except (ValueError, KeyError, TypeError, FileNotFoundError):
        return False


def main():
    plan = collection.load_plan()
    checks = []
    state = controls.metadata(plan)
    env = dict(value.split("=", 1) for value in state["Config"]["Env"])
    for path in [
        collection.BASE
        / "f05-go01-offline-setup-result-20261029/evidence/logs/container-inspect/stdout.bin",
        collection.BASE
        / "f05-go01-offline-setup-result-20261029/evidence/logs/offline-final-inspect/stdout.bin",
    ]:
        assert (
            collection.file_sha(path)
            == "6fcd10e50f8150a60201e10b50b3f2750674bb662af0f15d178551e9bd3582de"
        )
        historical = json.loads(path.read_bytes())[0]
        row = deepcopy(state)
        row["HostConfig"]["Tmpfs"] = historical["HostConfig"]["Tmpfs"]
        collection.inspect(row, env)
        checks.append(
            {
                "case": "positive historical tmpfs " + path.parent.name,
                "passed": True,
                "historicalOnly": True,
            }
        )
    reordered = deepcopy(state)
    for key, value in reordered["HostConfig"]["Tmpfs"].items():
        reordered["HostConfig"]["Tmpfs"][key] = ",".join(reversed(value.split(",")))
    collection.inspect(reordered, env)
    checks.append({"case": "same exact options reordered", "passed": True})
    for name, mutation in [
        ("conflicting-size", lambda t: t.update({"/workspace": t["/workspace"] + ",size=16g"})),
        ("suid-override", lambda t: t.update({"/workspace": t["/workspace"] + ",suid"})),
        ("extra-overlay", lambda t: t.update({"/workspace/extra": t["/workspace"]})),
        ("duplicate-same-size", lambda t: t.update({"/workspace": t["/workspace"] + ",size=8g"})),
        ("duplicate-nosuid", lambda t: t.update({"/tmp": t["/tmp"] + ",nosuid"})),
        ("missing-owner", lambda t: t.update({"/tmp": t["/tmp"].replace(",uid=1000", "")})),
        ("wrong-mode", lambda t: t.update({"/tmp": t["/tmp"].replace("mode=0700", "mode=0777")})),
        ("unknown-option", lambda t: t.update({"/tmp": t["/tmp"] + ",unknown"})),
        ("missing-root", lambda t: t.pop("/tmp")),
    ]:
        row = deepcopy(state)
        mutation(row["HostConfig"]["Tmpfs"])
        assert not accepted(lambda: collection.inspect(row, env)), name
        checks.append({"case": "reject-tmpfs-" + name, "passed": True})
    assert collection.flags("owned", plan["environment"]) == collection.boundary.flags(
        "owned", plan["environment"]
    )
    checks.append({"case": "reviewed safe create argv unchanged", "passed": True})

    for name, mutation in [
        ("directory-alias", lambda r: r[0].update(Dir=listing.CWD + "/wrong-directory")),
        ("dotdot-source", lambda r: r[0].update(GoFiles=[".."])),
        ("dot-source", lambda r: r[0].update(GoFiles=["."])),
        ("duplicate-source", lambda r: r[0].update(GoFiles=["owned.go", "owned.go"])),
        ("cross-field-duplicate", lambda r: r[0].update(CgoFiles=["owned.go"])),
        ("absolute-source", lambda r: r[0].update(GoFiles=["/owned.go"])),
        ("backslash-source", lambda r: r[0].update(GoFiles=["a\\owned.go"])),
        ("control-source", lambda r: r[0].update(GoFiles=["bad\n.go"])),
        ("wrong-extension", lambda r: r[0].update(GoFiles=["owned.txt"])),
        ("missing-source-in-inventory", lambda r: r[0].update(GoFiles=["missing.go"])),
    ]:
        rows = controls.package_rows()
        mutation(rows)
        assert not accepted(
            lambda: listing.packages(
                b"\n".join(json.dumps(row).encode() for row in rows), controls.FILES
            )
        ), name
        checks.append({"case": "reject-selected-package-" + name, "passed": True})
    rows = controls.package_rows()
    rows[0]["CgoFiles"], rows[0]["XTestGoFiles"] = ["cgo.go"], ["external_test.go"]
    files = dict(controls.FILES)
    relative = rows[0]["Dir"].removeprefix("/workspace/repository/")
    for name in ["cgo.go", "external_test.go"]:
        files[relative + "/" + name] = dict(files["README"])
    listing.packages(b"\n".join(json.dumps(row).encode() for row in rows), files)
    checks.append({"case": "legitimate Go Cgo Test XTest and zero-test packages", "passed": True})

    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-amendment-subject-") as temporary:
        temp = Path(temporary).resolve()
        subject = controls.synthetic_subject(plan, temp)
        fixture_freeze = collection.HERE / "FREEZE.json"
        saved_freeze = fixture_freeze.read_bytes()
        acceptance = {
            "state": "coordinator-accepted-go01-no-npm-go-projection-collection",
            "synthetic": False,
            "driverSubject": subject,
            **{key: plan[key] for key in ["sourceArchiveSha256", "imageId", "environmentSha256"]},
            "projectionSha256": plan["projection"]["archive"]["sha256"],
            "projectionSpecSha256": plan["projectionSpecSha256"],
            "initAndTestMainExecutionAccepted": True,
            "noNpmProvisioning": True,
            "nativeTaskAdmitted": False,
            "campaignAdmitted": False,
            "cacheGloballyQualified": False,
            "sourceScopeReviewFreeze": plan["collectionScopeReview"],
            "projectionReviewFreeze": plan["collectionScopeReview"],
        }
        auth = {
            "state": "coordinator-authorized-single-go01-collection-attempt",
            "synthetic": False,
            "planSha256": subject["driverPlanSha256"],
            "authorFreezeSha256": subject["authorFreezeSha256"],
            "output": str(temp / "output"),
            "scratch": str(temp / "scratch"),
            "commands": collection.COMMANDS,
            "limits": plan["limits"],
            "maxAttempts": 1,
        }
        for number, name in enumerate(
            [
                "valid-current-subject",
                "stale-acceptance-plan",
                "stale-acceptance-freeze",
                "stale-review-plan",
                "stale-review-freeze",
                "wrong-review-packet",
                "arbitrary-review",
                "before-review",
                "findings-present",
                "findings-missing",
                "review-synthetic",
                "wrong-review-scope",
                "review-authorizes",
                "auth-old-freeze",
                "freeze-missing-script",
                "freeze-old-plan",
            ]
        ):
            a, value, review = (
                deepcopy(auth),
                deepcopy(acceptance),
                controls.passed_review(deepcopy(subject)),
            )
            fixture_freeze.write_bytes(saved_freeze)
            if name == "stale-acceptance-plan":
                value["driverSubject"]["driverPlanSha256"] = "0" * 64
            if name == "stale-acceptance-freeze":
                value["driverSubject"]["authorFreezeSha256"] = "0" * 64
            if name == "stale-review-plan":
                review["subject"]["driverPlanSha256"] = "0" * 64
            if name == "stale-review-freeze":
                review["subject"]["authorFreezeSha256"] = "0" * 64
            if name == "wrong-review-packet":
                review["subject"]["packetIdentity"] = "other"
            if name == "arbitrary-review":
                review = {"unrelated": True}
            if name == "before-review":
                review = json.loads(
                    (
                        collection.BASE / "f05-go01-collection-driver-review-20261029/review.json"
                    ).read_text()
                )
            if name == "findings-present":
                review["findings"] = [{"id": "unresolved"}]
            if name == "findings-missing":
                review.pop("findings")
            if name == "review-synthetic":
                review["synthetic"] = True
            if name == "wrong-review-scope":
                review["scope"] = "task"
            if name == "review-authorizes":
                review["executionAuthorized"] = True
            if name == "auth-old-freeze":
                a["authorFreezeSha256"] = "0" * 64
            if name.startswith("freeze-"):
                frozen = json.loads(saved_freeze)
                if name == "freeze-missing-script":
                    frozen["artifactSha256"].pop("listing.py")
                if name == "freeze-old-plan":
                    frozen["driverPlanSha256"] = "0" * 64
                fixture_freeze.write_text(json.dumps(frozen))
            review_path = temp / (str(number) + "-review.json")
            collection.write(review_path, review)
            value["driverReviewFreeze"] = {
                "path": str(review_path),
                "sha256": collection.file_sha(review_path),
            }
            acceptance_path = temp / (str(number) + "-acceptance.json")
            collection.write(acceptance_path, value)
            a["collectionAcceptance"] = {
                "path": str(acceptance_path),
                "sha256": collection.file_sha(acceptance_path),
            }
            auth_path = temp / (str(number) + "-authorization.json")
            collection.write(auth_path, a)
            outcome = accepted(
                lambda: collection.authorize(
                    plan, auth_path, Path(auth["output"]), Path(auth["scratch"])
                )
            )
            assert outcome == (name == "valid-current-subject"), name
            checks.append(
                {
                    "case": "subject-" + name,
                    "passed": True,
                    "accepted": outcome,
                    "syntheticOwnedAssertionOnly": True,
                }
            )
    collection.write(
        HERE / "amendment-controls.json",
        {
            "passed": len(checks),
            "controls": checks,
            "actualCollectionOrDaemonCalls": 0,
            "syntheticAssertionFixturesNotRealReviews": True,
        },
    )
    print(json.dumps({"passed": len(checks), "actualCollectionOrDaemonCalls": 0}))


if __name__ == "__main__":
    main()
