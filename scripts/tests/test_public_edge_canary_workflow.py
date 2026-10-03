import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "canary_report", ROOT / "scripts/report_public_edge_canary.py"
)
reporter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reporter)


class FakeGitHub:
    def __init__(self, issues=None, comments=None):
        self.issues = issues or []
        self.comments = comments or {}
        self.calls = []

    @property
    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]

    def request(self, method, endpoint, payload=None, *, paginate=False):
        self.calls.append((method, endpoint, payload, paginate))
        if method == "GET":
            assert paginate
            if "/comments?" in endpoint:
                number = int(endpoint.split("/issues/")[1].split("/")[0])
                return self.comments.get(number, [])
            return self.issues
        if method == "POST" and endpoint.endswith("/issues"):
            issue = dict(payload, number=100, state="open")
            self.issues.append(issue)
            return issue
        if method == "POST" and endpoint.endswith("/comments"):
            number = int(endpoint.split("/issues/")[1].split("/")[0])
            comments = self.comments.setdefault(number, [])
            comment = dict(payload, id=len(comments) + 1, user={"login": reporter.BOT_LOGIN})
            comments.append(comment)
            return comment
        if method == "PATCH" and "/issues/comments/" in endpoint:
            comment_id = int(endpoint.rsplit("/", 1)[1])
            for comments in self.comments.values():
                for comment in comments:
                    if comment["id"] == comment_id:
                        comment.update(payload)
                        return comment
        if method == "PATCH" and "/issues/" in endpoint:
            number = int(endpoint.rsplit("/", 1)[1])
            issue = next(issue for issue in self.issues if issue["number"] == number)
            issue.update(payload)
            return issue
        raise AssertionError((method, endpoint))


def legacy_issue(state="open"):
    return {"number": 97, "state": state, "title": reporter.TITLE, "body": "Original failure"}


def publish(client, status="failure", run_number=10, run_attempt=1, reason="bad metadata"):
    return reporter.publish_report(
        client,
        repository="owner/repo",
        status=status,
        run_id=str(1000 + run_number),
        run_number=run_number,
        run_attempt=run_attempt,
        log="public edge canary failed: " + reason,
    )


class CanaryReporterTests(unittest.TestCase):
    def test_first_failure_creates_one_issue_and_one_report(self):
        client = FakeGitHub()
        publish(client)
        self.assertEqual(len(client.issues), 1)
        self.assertEqual(len(client.comments[100]), 1)
        self.assertEqual([call[0] for call in client.writes], ["POST", "POST"])

    def test_healthy_run_never_creates_an_issue(self):
        client = FakeGitHub()
        publish(client, status="success")
        self.assertEqual(client.writes, [])

    def test_repeated_failures_preserve_legacy_comments_and_do_not_add_noise(self):
        history = [
            {"id": i, "body": "old failure", "user": {"login": reporter.BOT_LOGIN}}
            for i in range(2202)
        ]
        client = FakeGitHub([legacy_issue()], {97: history})
        publish(client)
        client.calls.clear()
        for run_number in range(11, 61):
            publish(client, run_number=run_number)
        self.assertEqual(len(client.comments[97]), 2203)
        self.assertEqual(client.comments[97][0]["body"], "old failure")
        self.assertEqual(client.writes, [])

    def test_changed_failure_updates_same_comment(self):
        client = FakeGitHub([legacy_issue()])
        publish(client)
        client.calls.clear()
        publish(client, run_number=11, reason="different metadata error")
        self.assertEqual(len(client.comments[97]), 1)
        self.assertEqual([call[0] for call in client.writes], ["PATCH"])
        self.assertIn("different metadata error", client.comments[97][0]["body"])

    def test_recovery_updates_report_but_does_not_close_issue(self):
        client = FakeGitHub([legacy_issue()])
        publish(client)
        client.calls.clear()
        publish(client, status="success", run_number=11)
        self.assertEqual([call[0] for call in client.writes], ["PATCH"])
        self.assertIn("Recovered", client.comments[97][0]["body"])
        self.assertEqual(client.issues[0]["state"], "open")
        client.calls.clear()
        publish(client, status="success", run_number=12)
        self.assertEqual(client.writes, [])

    def test_failure_after_recovery_reopens_existing_issue_without_new_comment(self):
        client = FakeGitHub([legacy_issue()])
        publish(client, status="success")
        client.issues[0]["state"] = "closed"
        client.calls.clear()
        publish(client, run_number=11)
        self.assertEqual(len(client.issues), 1)
        self.assertEqual(len(client.comments[97]), 1)
        self.assertEqual(client.issues[0]["state"], "open")
        self.assertEqual([call[0] for call in client.writes], ["PATCH", "PATCH"])

    def test_closing_unchanged_outage_suppresses_repeated_reopening(self):
        client = FakeGitHub([legacy_issue()])
        publish(client)
        client.issues[0]["state"] = "closed"
        client.calls.clear()
        publish(client, run_number=11)
        self.assertEqual(client.issues[0]["state"], "closed")
        self.assertEqual(client.writes, [])

    def test_closed_legacy_issue_is_reused(self):
        client = FakeGitHub([legacy_issue("closed")])
        publish(client)
        self.assertEqual(len(client.issues), 1)
        self.assertEqual(client.issues[0]["state"], "open")
        self.assertEqual([call[0] for call in client.writes], ["PATCH", "POST"])

    def test_old_rerun_cannot_overwrite_newer_transition(self):
        client = FakeGitHub([legacy_issue()])
        publish(client, status="success", run_number=20)
        client.calls.clear()
        self.assertEqual(publish(client, run_number=10, run_attempt=2), "ignored stale result")
        self.assertEqual(client.writes, [])

    def test_only_bot_owned_marked_comments_are_changed(self):
        other = {"id": 1, "body": reporter.MARKER + "\n", "user": {"login": "someone"}}
        client = FakeGitHub([legacy_issue()], {97: [other]})
        publish(client)
        self.assertEqual(other["body"], reporter.MARKER + "\n")
        self.assertEqual([call[0] for call in client.writes], ["POST"])

    def test_partial_previous_creation_is_recovered_without_another_issue(self):
        client = FakeGitHub()
        with patch.object(client, "request", wraps=client.request) as request:
            # A failed comment write leaves the created issue discoverable.
            def fail_comment(method, endpoint, payload=None, **kwargs):
                if method == "POST" and endpoint.endswith("/comments"):
                    raise RuntimeError("uncertain response")
                return FakeGitHub.request(client, method, endpoint, payload, **kwargs)

            request.side_effect = fail_comment
            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                publish(client)
            self.assertEqual(sum(call.args[0] == "POST" for call in request.call_args_list), 2)
        publish(client, run_number=11)
        self.assertEqual(len(client.issues), 1)
        self.assertEqual(len(client.comments[100]), 1)

    def test_cache_busters_do_not_change_failure_identity(self):
        one = reporter.failure_summary(
            "public edge canary failed: https://a.test/?_canary=abc returned 500"
        )
        two = reporter.failure_summary(
            "public edge canary failed: https://a.test/?_canary=def returned 500"
        )
        self.assertEqual(one, two)

    def test_api_flattens_all_pages_including_empty_last_page(self):
        result = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps([[{"id": 1}], [{"id": 2}], []])
        )
        with patch.object(reporter.subprocess, "run", return_value=result) as run:
            values = reporter.GitHub().request("GET", "repos/owner/repo/issues", paginate=True)
        self.assertEqual(values, [{"id": 1}, {"id": 2}])
        self.assertIn("--paginate", run.call_args.args[0])
        self.assertIn("--slurp", run.call_args.args[0])

    def test_workflow_preserves_failed_canary_exit_and_reports_recovery(self):
        workflow = (ROOT / ".github/workflows/public-edge-canary.yml").read_text()
        self.assertIn("id: edge_check\n        shell: bash", workflow)
        self.assertIn("steps.edge_check.outcome == 'success'", workflow)
        self.assertIn("steps.edge_check.outcome == 'failure'", workflow)
        self.assertIn("report_public_edge_canary.py", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertNotIn("gh issue comment", workflow)
        self.assertNotIn("date -u -d", workflow)
