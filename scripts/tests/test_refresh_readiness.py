from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_refresh_readiness import inspect  # noqa: E402


@pytest.mark.parametrize("enabled,allowed", [(True, True), (True, False), (False, True)])
def test_readiness_observes_coupled_switch_and_preserves_default_permissions(enabled, allowed):
    paths = []

    def fetch(path):
        paths.append(path)
        if path.endswith("/workflow"):
            return {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": allowed,
            }
        return {"enabled": enabled}

    report = inspect("lazy-collective/dotrepo", fetch)
    assert report["ready"] is (enabled and allowed)
    assert report["proposedWorkflowPermissions"] == {
        "default_workflow_permissions": "read",
        "can_approve_pull_request_reviews": True,
    }
    assert paths == [
        "repos/lazy-collective/dotrepo/actions/permissions",
        "repos/lazy-collective/dotrepo/actions/permissions/workflow",
    ]


def test_unreadable_or_malformed_settings_never_claim_readiness():
    def inaccessible(path):
        raise PermissionError("administration read unavailable")

    with pytest.raises(PermissionError):
        inspect("lazy-collective/dotrepo", inaccessible)
    with pytest.raises(ValueError):
        inspect("lazy-collective/dotrepo", lambda path: {})
    with pytest.raises(ValueError):
        inspect("../dotrepo")
