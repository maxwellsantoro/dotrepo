"""Exercise the existing full campaign path with owned simulated tools and oracle.

No provider, Docker daemon, upstream task or empirical campaign runs here.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from test_agent_experiment import packet as campaign_fixture
from test_agent_experiment import save, write
from test_agent_runtime import FakeDocker, FakeProvider, bundle_spec, experiment, response, runtime


class OwnedTaskBackend(FakeDocker):
    def shell(self, command, timeout, output_limit):
        self.commands.append(command)
        passed = command == "owned-complete-scope"
        return {
            "stdout": json.dumps({"ownedCase": "complete-scope", "passed": passed}),
            "stderr": "" if passed else "owned wrong-scope action",
            "exitCode": 0 if passed else 7,
            "error": None,
        }


def fixture_score(trace, access):
    """Post-run owned oracle; it never screens the runtime's shell choices."""
    pending, results = {}, []
    for event in trace["events"]:
        if event["kind"] == "tool-request":
            assert event["id"] not in pending
            pending[event["id"]] = event["name"]
        elif event["kind"] == "tool-response":
            results.append((pending.pop(event["id"]), event["result"]))
    assert not pending
    native = [json.loads(r["stdout"]) for name, r in results if name == "shell"]
    complete = any(r == {"ownedCase": "complete-scope", "passed": True} for r in native)
    wrong = any(r.get("passed") is False for r in native)
    lookup = next((r for name, r in results if name == "lookup"), None)
    return {
        "correctCompletion": complete,
        "incorrectAction": wrong,
        "incorrectInstructionAccepted": wrong,
        "directApplicableInstruction": bool(
            access and lookup and lookup["status"] == 200 and not wrong
        ),
        "correctAbstentionFallback": bool(
            access and lookup and lookup["status"] == 404 and complete
        ),
        "policySelectionError": bool(access and lookup and wrong),
    }


def test_full_synthetic_assignment_runtime_oracle_and_analysis_path(tmp_path, monkeypatch):
    path, manifest = campaign_fixture.__wrapped__(tmp_path)
    specs, profiles, entries = {}, {}, []
    for index, task in enumerate(manifest["tasks"]):
        task["repository"] = f"example.test/owned/repo-{index:02}"
        prefix = f"sources/{task['id']}"
        spec = bundle_spec(
            tmp_path / prefix,
            {"README.md": f"Owned upstream fixture {index}; use owned-complete-scope.\n".encode()},
            task["revision"],
        )
        for role in ("archive", "inventory", "provenance"):
            spec[role]["path"] = prefix + "/" + spec[role]["path"]
        specs[task["repository"]] = spec
        profiles[task["repository"]] = {
            "status": 404 if index % 4 == 1 else 200,
            "body": json.dumps(
                {
                    "fixture": f"Owned frozen profile {index}",
                    "command": "owned-wrong-scope" if index % 4 == 2 else "owned-complete-scope",
                }
            ),
        }
        entries.append(
            {
                "set": "f05",
                "repository": task["repository"],
                "taskIds": [task["id"]],
                "relatedRepositories": [],
            }
        )
    manifest["artifacts"]["splitLedger"] = write(
        tmp_path, "artifacts/splitLedger.json", {"entries": entries}
    )
    config = {
        "backend": "docker-ephemeral-v1",
        "runnerSha256": experiment.digest(Path(runtime.__file__).read_bytes()),
        "networkPolicy": "none",
        "containerUser": "1000:1000",
        "resources": {
            "memoryBytes": 100000000,
            "cpus": 1,
            "pidsLimit": 32,
            "workspaceBytes": 1000000,
            "tmpBytes": 1000000,
        },
        "environment": {"HOME": "/workspace/.home"},
        "maxToolOutputBytes": 8192,
        "maxProviderCalls": 10,
        "qualifications": dict.fromkeys(runtime.QUALIFICATIONS, False),
        "providerRates": {
            "inputUsdPerToken": 0.001,
            "outputUsdPerToken": 0.001,
            "fixedUsdPerCall": 0,
        },
        "sourceBundles": specs,
    }
    manifest["artifacts"]["runtime"] = write(tmp_path, "runtime.json", config)
    manifest["artifacts"]["responses"] = write(
        tmp_path,
        "responses.json",
        {"snapshotSha256": manifest["artifacts"]["snapshot"]["sha256"], "profiles": profiles},
    )
    # Bind this owned post-run oracle's source, rather than claiming a task oracle ran.
    manifest["artifacts"]["scorer"] = write(
        tmp_path, "owned-scorer.py", Path(__file__).read_bytes()
    )
    save((path, manifest))
    assignment = tmp_path / "prepared"
    plan = experiment.prepare(path, assignment)

    def no_live_adapter(*args, **kwargs):
        pytest.fail("synthetic campaign attempted a live adapter")

    monkeypatch.setattr(runtime, "DockerBackend", no_live_adapter)
    monkeypatch.setattr(runtime, "OpenRouterAdapter", no_live_adapter)
    rows, seen_backends, seen_providers = [], [], []
    start = datetime(2026, 10, 29, 11, tzinfo=timezone.utc)
    for session in plan["sessions"]:
        request, cfg, source, common, prompt, lookup = runtime.load_session(
            path, assignment / "assignment.json", session["sessionId"]
        )
        index = int(request["task"]["id"].split("-")[-1])
        access = request["arm"] == "dotrepo-access"
        calls = []
        if index % 4 != 3:
            if access:
                calls.append(("lookup", {}))
            if not access or index % 4 in (1, 2):
                calls.append(("read_upstream", {"path": "README.md"}))
            if request["task"]["startingState"] == "pre-clone":
                calls.append(("checkout_source", {}))
            if index % 4 == 2:
                calls.append(("shell", {"command": "owned-wrong-scope"}))
            calls.append(("shell", {"command": "owned-complete-scope"}))
        provider = FakeProvider(
            *[response(call, model=manifest["model"]["version"]) for call in calls],
            response(text="owned final claim", model=manifest["model"]["version"]),
        )
        backend = OwnedTaskBackend()
        seen_backends.append(backend)
        seen_providers.append(provider)
        prefix = "runs/" + request["sessionId"]
        result = runtime.run_session(
            request,
            cfg,
            source,
            common,
            prompt,
            lookup,
            provider,
            backend,
            tmp_path / prefix,
            clock=lambda: 0,
        )
        assert result["simulation"] and result["status"] == "agent-finished"
        assert result["correctCompletion"] is None and not result["scoringPerformed"]
        assert backend.cleanups == 1
        if index % 4 == 2:
            assert backend.commands == ["owned-wrong-scope", "owned-complete-scope"]
        trace = experiment.read_json(tmp_path / prefix / "trace.json")
        if not access:
            assert "Owned frozen profile" not in json.dumps(trace)
        metrics = fixture_score(trace, access)
        host_task = next(t for t in manifest["tasks"] if t["id"] == request["task"]["id"])
        assert "gold" not in request["task"] and "oracle" not in request["task"]
        bindings = {
            role: {
                "path": f"{prefix}/{role}.json",
                "sha256": experiment.digest((tmp_path / prefix / f"{role}.json").read_bytes()),
            }
            for role in ("trace", "usage")
        }
        score = {
            "sessionId": request["sessionId"],
            "traceSha256": bindings["trace"]["sha256"],
            "scorerSha256": manifest["artifacts"]["scorer"]["sha256"],
            "oracleSha256": host_task["oracle"]["sha256"],
            "goldSha256": host_task["gold"]["sha256"],
            "errorRubricSha256": manifest["artifacts"]["errorRubric"]["sha256"],
            "rationale": "Owned simulated output, scored after runtime; no empirical task evidence",
            **metrics,
        }
        bindings["score"] = write(tmp_path, f"{prefix}/score.json", score)
        rows.append(
            {
                "sessionId": request["sessionId"],
                **{
                    k: deepcopy(request[k])
                    for k in (
                        "model",
                        "environment",
                        "budgets",
                        "cacheState",
                        "workspaceKey",
                        "cacheKey",
                    )
                },
                "requestSha256": result["requestSha256"],
                "startedAt": start.isoformat(),
                "endedAt": start.isoformat(),
                "status": "completed" if metrics["correctCompletion"] else "noncompletion",
                "protocolDeviations": result["protocolDeviations"],
                "measurementExclusions": result["measurementExclusions"],
                "controls": dict.fromkeys(
                    (
                        "freshSession",
                        "goldInaccessible",
                        "otherSessionsInaccessible",
                        "cacheConditionEnforced",
                        "armAccessEnforced",
                        "budgetsEnforced",
                    ),
                    True,
                ),
                **bindings,
                "effort": result["effort"],
            }
        )
        start += timedelta(seconds=1)
    observations = write(
        tmp_path,
        "observations.json",
        {
            "version": 1,
            "assignmentSha256": experiment.digest((assignment / "assignment.json").read_bytes()),
            "runs": rows,
        },
    )
    report = experiment.summarize(
        path, assignment / "assignment.json", tmp_path / observations["path"]
    )
    assert report["assignedSessions"] == len(seen_backends) == len(seen_providers) == 72
    assert len({id(x) for x in seen_backends}) == len({id(x) for x in seen_providers}) == 72
    for arm in experiment.ARMS:
        assert report["summary"][arm]["correctCompletion"] == pytest.approx(0.75)
        assert report["summary"][arm]["incorrectAction"] == pytest.approx(0.25)
        assert report["summary"][arm]["incorrectInstructionAccepted"] == pytest.approx(0.25)
    assert report["summary"]["dotrepo-access"]["directApplicableInstruction"] == pytest.approx(0.25)
    assert report["summary"]["dotrepo-access"]["correctAbstentionFallback"] == pytest.approx(0.25)
    assert report["summary"]["source-first"]["directApplicableInstruction"] == 0
    assert not report["independentlyVerified"] and not report["externalAdoption"]
