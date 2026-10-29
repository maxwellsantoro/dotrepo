"""Reproduce stale driver-review acceptance reuse using only owned JSON files."""

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
controls = importlib.import_module("controls")  # Deny all subprocess/socket entrypoints.


def main():
    plan = collection.load_plan()
    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-acceptance-reuse-", dir="/tmp") as folder:
        root = Path(folder).resolve()
        previous_review = root / "previous-review.json"
        collection.write(
            previous_review,
            {
                "state": "independently-reviewed-previous-driver",
                "planSha256": "1" * 64,
                "driverPacketSha256": "2" * 64,
            },
        )
        accepted = {
            "state": "coordinator-accepted-go01-no-npm-go-projection-collection",
            "synthetic": False,
            **{key: plan[key] for key in ["sourceArchiveSha256", "imageId", "environmentSha256"]},
            "projectionSha256": plan["projection"]["archive"]["sha256"],
            "projectionSpecSha256": plan["projectionSpecSha256"],
            "initAndTestMainExecutionAccepted": True,
            "noNpmProvisioning": True,
            "nativeTaskAdmitted": False,
            "campaignAdmitted": False,
            "cacheGloballyQualified": False,
            "sourceScopeReviewFreeze": deepcopy(plan["collectionScopeReview"]),
            "projectionReviewFreeze": deepcopy(plan["collectionScopeReview"]),
            "driverReviewFreeze": {
                "path": str(previous_review),
                "sha256": collection.file_sha(previous_review),
            },
            "planSha256": "1" * 64,
            "driverPacketSha256": "2" * 64,
        }
        accept_file = root / "old-acceptance.json"
        collection.write(accept_file, accepted)
        auth = {
            "state": "coordinator-authorized-single-go01-collection-attempt",
            "synthetic": False,
            "planSha256": collection.file_sha(Path(binding["scriptCopy"]) / "plan.json"),
            "output": str(root / "output"),
            "scratch": str(root / "scratch"),
            "commands": collection.COMMANDS,
            "limits": plan["limits"],
            "maxAttempts": 1,
            "collectionAcceptance": {
                "path": str(accept_file),
                "sha256": collection.file_sha(accept_file),
            },
        }
        auth_file = root / "new-authorization.json"
        collection.write(auth_file, auth)
        try:
            collection.authorize(plan, auth_file, root / "output", root / "scratch")
            observed = True
            error = None
        except (ValueError, KeyError, FileNotFoundError) as failure:
            observed, error = False, str(failure)
        result = {
            "case": "new-current-plan-authorization-with-previous-plan-acceptance-and-review",
            "expectedAccepted": False,
            "actualAccepted": observed,
            "error": error,
            "currentPlanSha256": auth["planSha256"],
            "oldAcceptedPlanSha256": accepted["planSha256"],
            "authorization": auth,
            "acceptance": accepted,
            "priorReview": json.loads(previous_review.read_text()),
            "realDaemonProcessSocketGoNativeProviderCalls": 0,
        }
    collection.write(HERE / "acceptance-reuse.json", result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "case",
                    "expectedAccepted",
                    "actualAccepted",
                    "currentPlanSha256",
                    "oldAcceptedPlanSha256",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
