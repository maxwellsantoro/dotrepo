"""Offline runtime controls; no Docker daemon, provider API, or upstream execution."""

from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench import agent_experiment as experiment  # noqa: E402
from bench import agent_runtime as runtime  # noqa: E402
from test_agent_experiment import packet as campaign_fixture  # noqa: E402
from test_agent_experiment import save, write  # noqa: E402


@pytest.fixture
def campaign(tmp_path):
    return campaign_fixture.__wrapped__(tmp_path)


def archive(files, *, link=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        for name, content in files.items():
            item = tarfile.TarInfo(name)
            item.size = len(content)
            stream.addfile(item, io.BytesIO(content))
        if link:
            item = tarfile.TarInfo(link[0])
            item.type, item.linkname = tarfile.SYMTYPE, link[1]
            stream.addfile(item)
    return buffer.getvalue()


def bundle_spec(root, files, revision, *, link=None):
    blob = write(root, "source.tar", archive(files, link=link))
    inventory = {
        "revision": revision,
        "files": {name: experiment.digest(raw) for name, raw in files.items()},
        "missingSubmodules": [],
        "missingLfsObjects": [],
        "limitations": ["Archive contains no synthetic Git metadata"],
    }
    return {
        "revision": revision,
        "archive": blob,
        "inventory": write(root, "source-inventory.json", inventory),
        "provenance": write(
            root,
            "source-provenance.json",
            {
                "revision": revision,
                "archiveSha256": blob["sha256"],
                "url": f"https://example.test/fixture/archive/{revision}.tar",
                "checkedAt": "2026-10-28T12:00:00Z",
            },
        ),
    }


def cache_spec(root, request, source, files):
    bundle = bundle_spec(root / "cache", files, request["task"]["revision"])
    for role in ("archive", "inventory", "provenance"):
        bundle[role]["path"] = "cache/" + bundle[role]["path"]
    script = write(root, "download-only.sh", b"# fixture download-only preparation\n")
    trace = write(root, "preparation-trace.json", {"fixture": "no provider or real download"})
    preparation = {
        "imageDigest": request["environment"]["imageDigest"],
        "revision": request["task"]["revision"],
        "sourceArchiveSha256": experiment.digest(source.archive),
        "cacheArchiveSha256": bundle["archive"]["sha256"],
        "scriptSha256": script["sha256"],
        "traceSha256": trace["sha256"],
        "downloadOnly": True,
        "buildOutputsExcluded": True,
        "taskSourceExcluded": True,
        "credentialsExcluded": True,
        "toolVersions": {"fixture": "not an empirical cache qualification"},
        "limitations": ["Synthetic cache controls only"],
        "preparationCostUsd": None,
    }
    return {
        "bundle": bundle,
        "script": script,
        "trace": trace,
        "preparation": write(root, "cache-preparation.json", preparation),
    }


@pytest.fixture
def session(tmp_path):
    request = {
        "version": 1,
        "sessionId": "task-r1-source-first",
        "arm": "source-first",
        "workspaceKey": "fixture/task-r1-source-first",
        "cacheKey": "fixture/task-r1-source-first",
        "task": {
            "id": "task",
            "repository": "example.test/fixture/repo",
            "revision": "a" * 40,
            "scope": "repository",
            "startingState": "pre-clone",
            "request": "Investigate tests",
        },
        "model": {
            "provider": "fixture",
            "id": "fixture-model",
            "version": "fixture-version",
            "inferenceSettings": {"temperature": 0},
        },
        "environment": {"id": "fixture-image", "imageDigest": "sha256:" + "b" * 64},
        "cacheState": "cold",
        "budgets": {
            "wallTimeSeconds": 60,
            "toolCalls": 5,
            "inputTokens": 100,
            "outputTokens": 100,
            "monetaryUsd": 10,
        },
        "artifacts": {"runtime": {"path": "runtime.json", "sha256": "c" * 64}},
    }
    spec = bundle_spec(
        tmp_path,
        {
            "README.md": b"Run the task-specific test command.\n",
            "src/lib.rs": b"// frozen fixture source\n",
        },
        "a" * 40,
    )
    config = {
        "backend": "docker-ephemeral-v1",
        "runnerSha256": experiment.digest(Path(runtime.__file__).read_bytes()),
        "networkPolicy": "none",
        "containerUser": "1000:1000",
        "resources": {
            "memoryBytes": 256000000,
            "cpus": 1,
            "pidsLimit": 32,
            "workspaceBytes": 1000000,
            "tmpBytes": 1000000,
        },
        "environment": {"HOME": "/workspace/.home", "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        "maxToolOutputBytes": 8192,
        "maxProviderCalls": 10,
        "qualifications": {key: False for key in runtime.QUALIFICATIONS},
        "providerRates": {
            "inputUsdPerToken": 0.001,
            "outputUsdPerToken": 0.002,
            "fixedUsdPerCall": 0,
        },
        "sourceBundles": {request["task"]["repository"]: spec},
    }
    bundle = runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)
    return request, config, bundle


@pytest.mark.parametrize(
    "binding", ["imageDigest", "revision", "sourceArchiveSha256", "traceSha256"]
)
def test_dependency_cache_rejects_different_preparation_binding(session, tmp_path, binding):
    request, _, source = session
    spec = cache_spec(tmp_path, request, source, {"cargo/registry/cache/example.crate": b"crate"})
    preparation = json.loads((tmp_path / spec["preparation"]["path"]).read_bytes())
    preparation[binding] = "different"
    spec["preparation"] = write(tmp_path, "cache-preparation.json", preparation)
    with pytest.raises(ValueError, match="binding mismatch"):
        runtime.dependency_cache(tmp_path, spec, request, source, set(), 1000000)


@pytest.mark.parametrize("path", ["repository/answer", "cargo-target/test", "node_modules/answer"])
def test_dependency_cache_rejects_non_download_paths(session, tmp_path, path):
    request, _, source = session
    spec = cache_spec(tmp_path, request, source, {path: b"unqualified data"})
    with pytest.raises(ValueError, match="outside download-cache roots"):
        runtime.dependency_cache(tmp_path, spec, request, source, set(), 1000000)


def test_dependency_cache_rejects_hidden_profile_inside_allowed_path(session, tmp_path):
    request, _, source = session
    profile = b'{"hidden":"profile"}'
    spec = cache_spec(tmp_path, request, source, {"npm-cache/_cacache/answer": profile})
    with pytest.raises(ValueError, match="hidden/protected"):
        runtime.dependency_cache(
            tmp_path, spec, request, source, runtime.content_digests(profile), 1000000
        )


def test_dependency_cache_rejects_task_archive_disguised_as_download(session, tmp_path):
    request, _, source = session
    spec = cache_spec(
        tmp_path, request, source, {"npm-cache/_cacache/source-archive": source.archive}
    )
    with pytest.raises(ValueError, match="hidden/protected"):
        runtime.dependency_cache(tmp_path, spec, request, source, set(), 1000000)


def test_failed_cache_audit_refuses_before_copy(session, tmp_path):
    request, _, source = session
    spec = cache_spec(tmp_path, request, source, {"cargo/registry/cache/example.crate": b"crate"})
    preparation = json.loads((tmp_path / spec["preparation"]["path"]).read_bytes())
    preparation["buildOutputsExcluded"] = False
    spec["preparation"] = write(tmp_path, "cache-preparation.json", preparation)
    with pytest.raises(ValueError, match="audit incomplete"):
        runtime.dependency_cache(tmp_path, spec, request, source, set(), 1000000)


def test_dependency_cache_and_source_share_workspace_bound(session, tmp_path):
    request, _, _ = session
    source_spec = bundle_spec(tmp_path, {"source.bin": b"s" * 50001}, request["task"]["revision"])
    source = runtime.source_bundle(tmp_path, source_spec, request["task"]["revision"], set(), 70000)
    spec = cache_spec(tmp_path, request, source, {"go/pkg/mod/example/data": b"x" * 20000})
    with pytest.raises(ValueError, match="source and dependency cache exceed"):
        runtime.dependency_cache(tmp_path, spec, request, source, set(), 70000)


def test_cache_conditions_require_explicit_per_task_bindings(session):
    request, config, _ = session
    config["dependencyCaches"] = {request["task"]["repository"]: {}}
    with pytest.raises(ValueError, match="cold sessions"):
        runtime.validate_runtime(config, request)
    request["cacheState"] = "frozen-warm"
    config["dependencyCaches"] = {}
    with pytest.raises(ValueError, match="per-task"):
        runtime.validate_runtime(config, request)


def test_frozen_warm_seed_precedes_first_paid_request_and_stays_separate(session, tmp_path):
    request, config, source = session
    request["cacheState"] = "frozen-warm"
    spec = cache_spec(tmp_path, request, source, {"cargo/registry/cache/example.crate": b"crate"})
    config["dependencyCaches"] = {request["task"]["repository"]: spec}
    source.dependency_cache = runtime.dependency_cache(
        tmp_path, spec, request, source, set(), 1000000
    )
    order = []

    class WarmDocker(FakeDocker):
        def seed_dependencies(self, bundle, timeout):
            order.append("seed")
            assert set(bundle.files) == {"cargo/registry/cache/example.crate"}
            return {"exitCode": 0, "error": None}

    class OrderedProvider(FakeProvider):
        def complete(self, messages, tools, timeout):
            order.append("provider")
            return super().complete(messages, tools, timeout)

    result = run(session, tmp_path, OrderedProvider(response(text="done")), WarmDocker())
    assert order == ["seed", "provider"]
    assert result["status"] == "agent-finished"
    events = [json.loads(line) for line in (tmp_path / "run/events.jsonl").read_text().splitlines()]
    cache_event = next(event for event in events if event["kind"] == "dependency-cache")
    assert cache_event["preparationSha256"] == spec["preparation"]["sha256"]
    assert result["effort"]["preparationCostUsd"] is None


@pytest.mark.parametrize("hidden_cache", [False, True])
def test_full_freeze_loads_warm_cache_and_rejects_profile_alias_before_launch(
    campaign, session, tmp_path, hidden_cache
):
    path, manifest = campaign
    task = manifest["tasks"][0]
    request = deepcopy(session[0])
    request.update(task=task, environment=manifest["environment"])
    source_spec = bundle_spec(tmp_path, {"README.md": b"Only upstream source"}, task["revision"])
    source = runtime.source_bundle(tmp_path, source_spec, task["revision"], set(), 1000000)
    profile = '{"execution":{"test":"PRIVATE PROFILE ANSWER"}}'
    contents = b'{ "execution": {"test": "PRIVATE PROFILE ANSWER"} }' if hidden_cache else b"crate"
    spec = cache_spec(tmp_path, request, source, {"cargo/registry/cache/example.crate": contents})
    config = deepcopy(session[1])
    config["sourceBundles"] = {task["repository"]: source_spec}
    config["dependencyCaches"] = {task["repository"]: spec}
    manifest["cacheState"] = "frozen-warm"
    manifest["artifacts"]["runtime"] = write(tmp_path, "runtime.json", config)
    manifest["artifacts"]["responses"] = write(
        tmp_path,
        "responses.json",
        {
            "snapshotSha256": manifest["artifacts"]["snapshot"]["sha256"],
            "profiles": {task["repository"]: {"status": 200, "body": profile}},
        },
    )
    save(campaign)
    out = tmp_path / "prepared"
    experiment.prepare(path, out)
    session_id = f"{task['id']}-r1-source-first"
    if hidden_cache:
        with pytest.raises(ValueError, match="aliases hidden/protected"):
            runtime.load_session(path, out / "assignment.json", session_id)
    else:
        loaded = runtime.load_session(path, out / "assignment.json", session_id)
        assert len(loaded) == 6 and loaded[5] is None
        assert loaded[2].dependency_cache.files == {"cargo/registry/cache/example.crate": b"crate"}


def test_failed_dependency_seed_stops_before_provider_and_cleans(session, tmp_path):
    request, config, source = session
    request["cacheState"] = "frozen-warm"
    spec = cache_spec(tmp_path, request, source, {"cargo/registry/cache/example.crate": b"crate"})
    config["dependencyCaches"] = {request["task"]["repository"]: spec}
    source.dependency_cache = runtime.dependency_cache(
        tmp_path, spec, request, source, set(), 1000000
    )

    class FailingWarmDocker(FakeDocker):
        def seed_dependencies(self, bundle, timeout):
            return {"exitCode": 1, "error": "fixture-copy-failure"}

    provider, backend = FakeProvider(response(text="never")), FailingWarmDocker()
    result = run(session, tmp_path, provider, backend)
    assert not provider.requests and backend.cleanups == 1
    assert result["status"] == "infrastructure-failure"
    assert "fixture-copy-failure" in (tmp_path / "run/events.jsonl").read_text()


def response(
    *calls, text=None, cost=0.1, incoming=1, outgoing=2, model="fixture-version", status=200
):
    message = {
        "role": "assistant",
        "content": text,
        "tool_calls": [
            {
                "id": f"call-{i}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            for i, (name, arguments) in enumerate(calls)
        ],
    }
    return {
        "status": status,
        "body": {
            "model": model,
            "choices": [{"finish_reason": "tool_calls" if calls else "stop", "message": message}],
            "usage": {
                "prompt_tokens": incoming,
                "completion_tokens": outgoing,
                "cost": cost,
                "prompt_tokens_details": {"cached_tokens": 0},
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        },
        "error": None,
        "httpRequests": 0,
        "decodedBytes": 0,
    }


class FakeProvider:
    simulation = True

    def __init__(self, *responses, quote=None):
        self.responses, self.requests = list(responses), []
        self.admission = quote or {"inputTokens": 2, "outputTokens": 3, "providerCostUsd": 0.2}

    def quote(self, messages, tools):
        return self.admission

    def complete(self, messages, tools, timeout):
        self.requests.append(deepcopy({"messages": messages, "tools": tools, "timeout": timeout}))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeDocker:
    simulation = True

    def __init__(self, *, failure=None):
        self.failure, self.checkouts, self.commands, self.cleanups = failure, [], [], 0

    def provision(self, request, config, timeout):
        if self.failure == "provision":
            raise RuntimeError("fixture provision failure")
        return {"containerName": "fixture-disposable", "mounts": [], "network": "none"}

    def checkout(self, bundle, timeout):
        self.checkouts.append(deepcopy(bundle.files))
        return {
            "stdout": "",
            "stderr": "",
            "exitCode": 1 if self.failure == "checkout" else 0,
            "error": None,
        }

    def shell(self, command, timeout, output_limit):
        self.commands.append(command)
        return {"stdout": "fixture output", "stderr": "", "exitCode": 7, "error": None}

    def cleanup(self):
        self.cleanups += 1
        return {"exitCode": 1 if self.failure == "cleanup" else 0, "error": None}


def run(session, tmp_path, provider, backend=None, *, clock=None, lookup=None):
    request, config, bundle = session
    return runtime.run_session(
        request,
        config,
        bundle,
        "Frozen common instructions",
        "Frozen task",
        lookup,
        provider,
        backend or FakeDocker(),
        tmp_path / "run",
        **({"clock": clock} if clock else {}),
    )


def test_preclone_acquires_source_on_agent_decision_and_shell_is_not_gold_gated(session, tmp_path):
    backend = FakeDocker()
    provider = FakeProvider(
        response(("read_upstream", {"path": "README.md"})),
        response(("checkout_source", {})),
        response(("shell", {"command": "wrong-task-command"})),
        response(text="Proposed completion despite failed action"),
    )
    result = run(session, tmp_path, provider, backend)
    assert result["status"] == "agent-finished"
    assert result["correctCompletion"] is None and not result["scoringPerformed"]
    assert backend.commands == ["wrong-task-command"]  # No hidden expected-command screen.
    assert len(backend.checkouts) == backend.cleanups == 1
    assert result["effort"]["providerCostUsd"] == pytest.approx(0.4)
    assert result["effort"]["inputTokens"] == 4
    assert result["effort"]["httpRequests"] == 0
    assert result["effort"]["preparationCostUsd"] is None
    trace = experiment.read_json(tmp_path / "run/trace.json")
    assert any(
        e["kind"] == "tool-response" and e["result"].get("exitCode") == 7 for e in trace["events"]
    )
    # Earlier raw provider requests remain snapshots, not later-mutated message references.
    requests = [e for e in trace["events"] if e["kind"] == "provider-request"]
    assert len(requests[0]["messages"]) == 2
    usage = experiment.read_json(tmp_path / "run/usage.json")
    assert usage["effort"] == result["effort"]
    assert set(usage) == {
        "sessionId",
        "requestSha256",
        "model",
        "environment",
        "runtimeSha256",
        "effort",
    }


def test_local_starts_provisioned_and_both_arms_share_the_same_upstream_tools(session, tmp_path):
    session[0]["task"]["startingState"] = "local-checkout"
    backend = FakeDocker()
    provider = FakeProvider(
        response(("shell", {"command": "arbitrary-chosen-command"})), response(text="done")
    )
    result = run(session, tmp_path, provider, backend)
    assert result["status"] == "agent-finished"
    assert backend.checkouts[0] == session[2].files
    assert backend.commands == ["arbitrary-chosen-command"]
    names = {t["function"]["name"] for t in provider.requests[0]["tools"]}
    assert names == {"shell", "read_upstream", "checkout_source"}


def test_source_first_cannot_reach_profile_even_via_forged_tool_call(session, tmp_path):
    provider = FakeProvider(
        response(("lookup", {})),
        response(("read_upstream", {"path": "../gold.json"})),
        response(text="fallback"),
    )
    result = run(session, tmp_path, provider, lookup={"status": 200, "body": "secret-profile"})
    trace = (tmp_path / "run/trace.json").read_text()
    assert "secret-profile" not in trace
    assert "arm denies lookup" in trace and "source path escapes bundle" in trace
    assert result["effort"]["toolCalls"] == 2


def test_access_arm_receives_only_frozen_response_and_cannot_request_url(session, tmp_path):
    session[0]["arm"] = "dotrepo-access"
    provider = FakeProvider(
        response(("lookup", {})),
        response(("lookup", {"url": "http://host/gold"})),
        response(text="done"),
    )
    result = run(session, tmp_path, provider, lookup={"status": 404, "body": "frozen absence"})
    trace = (tmp_path / "run/trace.json").read_text()
    assert result["status"] == "agent-finished"
    assert "frozen absence" in trace and "invalid frozen lookup request" in trace


@pytest.mark.parametrize(
    "name,args",
    [
        ("read_file", {"path": "/host/gold"}),
        ("exec", {"command": "host-command"}),
        ("shell", {"command": "x", "cwd": "/host"}),
    ],
)
def test_no_host_filesystem_or_extra_shell_arguments(session, tmp_path, name, args):
    backend = FakeDocker()
    provider = FakeProvider(response((name, args)), response(text="done"))
    run(session, tmp_path, provider, backend)
    assert not backend.commands


def test_preclone_shell_before_checkout_fails_and_remains_visible(session, tmp_path):
    backend = FakeDocker()
    result = run(
        session,
        tmp_path,
        FakeProvider(response(("shell", {"command": "test"})), response(text="done")),
        backend,
    )
    assert not backend.commands
    assert result["effort"]["toolCalls"] == 1
    assert "checkout_source is required" in (tmp_path / "run/trace.json").read_text()


@pytest.mark.parametrize(
    "metric,limit", [("inputTokens", 1), ("outputTokens", 2), ("monetaryUsd", 0.1)]
)
def test_admission_stops_before_provider_call(session, tmp_path, metric, limit):
    session[0]["budgets"][metric] = limit
    provider, backend = FakeProvider(response(text="never")), FakeDocker()
    result = run(session, tmp_path, provider, backend)
    assert result["status"] == "budget-exhausted" and not provider.requests
    assert backend.cleanups == 1


def test_tool_budget_exhaustion_retains_first_failed_action_and_usage(session, tmp_path):
    session[0]["budgets"]["toolCalls"] = 1
    provider = FakeProvider(response(("unsupported", {}), ("read_upstream", {"path": "README.md"})))
    result = run(session, tmp_path, provider)
    assert result["status"] == "budget-exhausted" and result["effort"]["toolCalls"] == 1
    assert result["effort"]["providerCostUsd"] == pytest.approx(0.1)


def test_missing_native_usage_or_cost_stops_additional_calls_without_zero_filling(
    session, tmp_path
):
    provider = FakeProvider(response(text="unscored", cost=None), response(text="never"))
    result = run(session, tmp_path, provider)
    assert result["status"] == "usage-unresolved" and len(provider.requests) == 1
    assert result["effort"]["providerCostUsd"] is None
    assert "providerCostUsd unavailable" in result["measurementExclusions"]


def test_failed_provider_call_retains_native_charges_and_cleanup(session, tmp_path):
    failed = response(text="error", status=503, cost=0.75, incoming=15, outgoing=3)
    failed["body"]["error"] = {"message": "native provider failure"}
    backend = FakeDocker()
    result = run(session, tmp_path, FakeProvider(failed), backend)
    assert result["status"] == "provider-failure"
    assert result["effort"]["providerCostUsd"] == 0.75 and result["effort"]["inputTokens"] == 15
    assert "native provider failure" in (tmp_path / "run/trace.json").read_text()
    assert backend.cleanups == 1


def test_transport_exception_never_leaks_credentials_or_invents_zero_charge(session, tmp_path):
    result = run(session, tmp_path, FakeProvider(RuntimeError("Bearer PRIVATE-API-KEY")))
    assert result["status"] == "provider-failure" and result["effort"]["providerCostUsd"] is None
    assert result["providerCalls"] == 1
    assert "PRIVATE-API-KEY" not in (tmp_path / "run/trace.json").read_text()


def test_model_version_change_stops_before_tool_actions_with_receipts(session, tmp_path):
    backend = FakeDocker()
    result = run(
        session,
        tmp_path,
        FakeProvider(response(("checkout_source", {}), model="changed-version")),
        backend,
    )
    assert result["observedModelVersions"] == ["changed-version"]
    assert result["status"] == "infrastructure-failure" and not backend.checkouts
    assert result["effort"]["providerCostUsd"] == 0.1
    receipt = experiment.read_json(tmp_path / "run/usage.json")
    assert receipt["model"]["version"] == "changed-version"
    assert receipt["model"]["version"] != session[0]["model"]["version"]
    assert result["observedModel"]["version"] == "changed-version"
    assert result["requestedModel"] == session[0]["model"]
    assert "Observed model version differs from frozen request" in result["protocolDeviations"]


@pytest.mark.parametrize("failure", ["provision", "checkout", "cleanup"])
def test_failure_cleanup_and_partial_receipts_retained(session, tmp_path, failure):
    session[0]["task"]["startingState"] = "local-checkout"
    backend = FakeDocker(failure=failure)
    result = run(session, tmp_path, FakeProvider(response(text="done")), backend)
    assert backend.cleanups == 1
    assert (tmp_path / "run/events.jsonl").is_file()
    assert (tmp_path / "run/usage.json").is_file()
    if failure == "cleanup":
        assert result["protocolDeviations"]


def test_wall_time_exhaustion_stops_and_cleans(session, tmp_path):
    readings = iter([0, 61, 62])
    backend, provider = FakeDocker(), FakeProvider(response(text="never"))
    result = run(session, tmp_path, provider, backend, clock=lambda: next(readings))
    assert result["status"] == "budget-exhausted" and not provider.requests
    assert backend.cleanups == 1


@pytest.mark.parametrize("path", ["../gold", "/host/gold", "src/../gold"])
def test_unsafe_archive_path_rejected(tmp_path, path):
    spec = bundle_spec(tmp_path, {path: b"untrusted"}, "a" * 40)
    with pytest.raises(ValueError, match="escapes"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


def test_archive_symlinks_extra_files_and_hidden_aliases_rejected(tmp_path):
    spec = bundle_spec(tmp_path, {"README.md": b"upstream"}, "a" * 40, link=("gold", "/host/gold"))
    with pytest.raises(ValueError, match="links/devices"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)
    spec = bundle_spec(tmp_path, {"README.md": b"hidden-gold"}, "a" * 40)
    with pytest.raises(ValueError, match="aliases hidden"):
        runtime.source_bundle(
            tmp_path, spec, "a" * 40, {experiment.digest(b"hidden-gold")}, 1000000
        )


def test_source_revision_and_recursively_bound_inventory_cannot_drift(tmp_path):
    spec = bundle_spec(tmp_path, {"src/a.rs": b"frozen"}, "a" * 40)
    with pytest.raises(ValueError, match="revision differs"):
        runtime.source_bundle(tmp_path, spec, "b" * 40, set(), 1000000)
    inventory = experiment.read_json(tmp_path / spec["inventory"]["path"])
    inventory["files"]["src/a.rs"] = "0" * 64
    spec["inventory"] = write(tmp_path, spec["inventory"]["path"], inventory)
    with pytest.raises(ValueError, match="inventory hash"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


def test_docker_flags_are_exact_digest_mount_free_and_bounded(session):
    request, config, _ = session
    config["qualifications"] = dict.fromkeys(runtime.QUALIFICATIONS, True)
    invoked = []

    def invoke(argv, **kwargs):
        invoked.append((argv, kwargs))
        image = [{"Id": request["environment"]["imageDigest"], "Config": {"Env": ["PATH=/bin"]}}]
        return {
            "stdout": json.dumps(image) if argv[1:3] == ["image", "inspect"] else "fixture-id",
            "stderr": "",
            "exitCode": 0,
            "error": None,
        }

    backend = runtime.DockerBackend(invoke)
    backend.provision(request, config, 10)
    created = next(argv for argv, _ in invoked if "create" in argv)
    assert "--network=none" in created and "--read-only" in created and "--cap-drop=ALL" in created
    assert "--security-opt=no-new-privileges" in created and "--pull=never" in created
    assert request["environment"]["imageDigest"] in created and "--entrypoint=/bin/sh" in created
    assert "--memory-swap" in created and "--pids-limit" in created and "--cpus" in created
    assert not any(arg == "--pid" or arg.startswith("--pid=") for arg in created)
    tmpfs = [created[index + 1] for index, arg in enumerate(created) if arg == "--tmpfs"]
    assert len(tmpfs) == 2
    for mount in tmpfs:
        options = mount.split(":", 1)[1].split(",")
        assert {"exec", "nosuid", "nodev"} <= set(options)
        assert "noexec" not in options
    assert not any(
        arg in {"-v", "--volume", "--mount", "--privileged", "--env-file"} for arg in created
    )
    backend.cleanup()
    assert invoked[-1][0][1:4] == ["rm", "--force", "--volumes"]


@pytest.mark.parametrize(
    "image_config", [{"Env": ["OPENROUTER_API_KEY=secret"]}, {"Volumes": {"/host": {}}}]
)
def test_unqualified_image_environment_or_volumes_rejected(session, image_config):
    request, config, _ = session
    config["qualifications"] = dict.fromkeys(runtime.QUALIFICATIONS, True)

    def invoke(argv, **kwargs):
        return {
            "stdout": json.dumps(
                [{"Id": request["environment"]["imageDigest"], "Config": image_config}]
            ),
            "stderr": "",
            "exitCode": 0,
            "error": None,
        }

    with pytest.raises(ValueError):
        runtime.DockerBackend(invoke).provision(request, config, 10)


def test_unqualified_live_launch_has_no_docker_or_provider_side_effects(session, tmp_path):
    provider, backend = FakeProvider(response(text="never")), FakeDocker()
    provider.simulation = backend.simulation = False
    with pytest.raises(ValueError, match="launch blocked"):
        run(session, tmp_path, provider, backend)
    assert not (tmp_path / "run").exists() and not provider.requests and backend.cleanups == 0


def test_frozen_provider_adapter_has_no_crawler_defaults_or_byte_token_estimates(session):
    request, config, _ = session
    model = {
        "provider": "openrouter",
        "id": "explicit/model",
        "version": "explicit/model-version",
        "inferenceSettings": {
            "max_tokens": 10,
            "temperature": 0.25,
            "provider": {"require_parameters": True},
        },
    }
    counted, sent = [], []

    def count(body):
        counted.append(deepcopy(body))
        return 17

    def transport(body, timeout):
        sent.append(deepcopy(body))
        return response(text="native", model=model["version"])

    adapter = runtime.OpenRouterAdapter(model, config["providerRates"], count, transport)
    messages, tools = (
        [{"role": "user", "content": "Do the frozen task"}],
        runtime.tool_schemas("source-first"),
    )
    quote = adapter.quote(messages, tools)
    assert quote["inputTokens"] == 17 and quote["outputTokens"] == 10
    assert quote["providerCostUsd"] == pytest.approx(0.037)
    adapter.complete(messages, tools, 5)
    assert counted[0] == sent[0]
    assert sent[0]["model"] == "explicit/model" and sent[0]["temperature"] == 0.25
    assert "reasoning" not in sent[0] and "response_format" not in sent[0]


def test_full_existing_freeze_validation_precedes_runtime_loading(campaign, tmp_path):
    path, manifest = campaign
    task = manifest["tasks"][0]
    spec = bundle_spec(tmp_path, {"README.md": b"Only upstream fixture bytes"}, task["revision"])
    request_id = f"{task['id']}-r1-source-first"
    # Reuse only the existing complete preparation fixture; runtime data remains unqualified.
    runtime_config = {
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
        "maxProviderCalls": 5,
        "qualifications": dict.fromkeys(runtime.QUALIFICATIONS, False),
        "providerRates": {
            "inputUsdPerToken": 0.001,
            "outputUsdPerToken": 0.001,
            "fixedUsdPerCall": 0,
        },
        "sourceBundles": {task["repository"]: spec},
    }
    manifest["artifacts"]["runtime"] = write(tmp_path, "runtime.json", runtime_config)
    manifest["artifacts"]["responses"] = write(
        tmp_path,
        "responses.json",
        {
            "snapshotSha256": manifest["artifacts"]["snapshot"]["sha256"],
            "profiles": {task["repository"]: {"status": 404, "body": ""}},
        },
    )
    save(campaign)
    out = tmp_path / "prepared"
    experiment.prepare(path, out)
    loaded = runtime.load_session(path, out / "assignment.json", request_id)
    assert loaded[0]["sessionId"] == request_id and loaded[2].files["README.md"].startswith(
        b"Only upstream"
    )
    (tmp_path / spec["archive"]["path"]).write_bytes(b"changed after freeze")
    with pytest.raises(ValueError, match="hash mismatch"):
        runtime.load_session(path, out / "assignment.json", request_id)


def test_limited_host_capture_stops_flooding_without_retaining_unbounded_output():
    # This runs our fixed benign control subprocess; no third-party task is executed.
    result = runtime.limited_process(
        ["uv", "run", "python", "-c", "print('x' * 10000)"], timeout=10, output_limit=1024
    )
    assert result["error"] == "output-limit"
    assert len(result["stdout"]) + len(result["stderr"]) <= 1024


def test_cli_cannot_launch_live_campaign_without_qualified_transport(campaign, tmp_path):
    # An incomplete runtime artifact is rejected before Docker/provider setup.
    path, _ = campaign
    out = tmp_path / "prepared"
    experiment.prepare(path, out)
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "bench.agent_runtime",
            "--manifest",
            str(path),
            "--assignment",
            str(out / "assignment.json"),
            "--session-id",
            "task-00-r1-source-first",
            "--live",
        ],
        cwd=BENCH,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "error:" in result.stderr


def test_native_usage_exceeding_admission_bound_stops_before_agent_tools(session, tmp_path):
    backend = FakeDocker()
    provider = FakeProvider(response(("checkout_source", {}), incoming=15), response(text="never"))
    result = run(session, tmp_path, provider, backend)
    assert result["status"] == "budget-exhausted" and len(provider.requests) == 1
    assert result["effort"]["inputTokens"] == 15
    assert result["protocolDeviations"] == [
        "Native usage exceeded qualified per-call admission bound"
    ]
    assert not backend.checkouts


def test_image_digest_mismatch_refuses_before_create_and_never_pulls(session):
    request, config, _ = session
    config["qualifications"] = dict.fromkeys(runtime.QUALIFICATIONS, True)
    commands = []

    def invoke(argv, **kwargs):
        commands.append(argv)
        return {
            "stdout": json.dumps([{"Id": "sha256:" + "0" * 64, "Config": {}}]),
            "stderr": "",
            "exitCode": 0,
            "error": None,
        }

    with pytest.raises(ValueError, match="digest mismatch"):
        runtime.DockerBackend(invoke).provision(request, config, 10)
    assert len(commands) == 1 and commands[0][1:3] == ["image", "inspect"]


def test_partial_docker_create_failure_still_removes_named_container_and_retains_raw_error(session):
    request, config, _ = session
    config["qualifications"] = dict.fromkeys(runtime.QUALIFICATIONS, True)

    def invoke(argv, **kwargs):
        if "inspect" in argv:
            return {
                "stdout": json.dumps([{"Id": request["environment"]["imageDigest"], "Config": {}}]),
                "stderr": "",
                "exitCode": 0,
                "error": None,
            }
        return {
            "stdout": "",
            "stderr": "fixture Docker create failure",
            "exitCode": 3 if "create" in argv else 0,
            "error": None,
        }

    backend = runtime.DockerBackend(invoke)
    with pytest.raises(ValueError, match="create failed"):
        backend.provision(request, config, 10)
    backend.cleanup()
    assert backend.operations[-1]["argv"][1:4] == ["rm", "--force", "--volumes"]
    assert backend.operations[-2]["result"]["stderr"] == "fixture Docker create failure"


def test_host_provider_credentials_are_absent_from_docker_cli_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-private-value")
    result = runtime.limited_process(
        ["uv", "run", "python", "-c", "import os; print('OPENROUTER_API_KEY' in os.environ)"],
        timeout=10,
        output_limit=1024,
    )
    assert result["exitCode"] == 0 and result["stdout"].strip() == "False"
    assert "fixture-private-value" not in json.dumps(result)


def test_source_omissions_survive_without_synthetic_git_metadata(session, tmp_path):
    session[2].inventory["missingSubmodules"] = ["vendor/optional-submodule"]
    session[2].inventory["missingLfsObjects"] = ["fixtures/large-input"]
    result = run(session, tmp_path, FakeProvider(response(text="could not complete setup")))
    assert result["sourceOmissions"]["missingSubmodules"] == ["vendor/optional-submodule"]
    assert result["sourceOmissions"]["missingLfsObjects"] == ["fixtures/large-input"]
    assert not any(name.startswith(".git") for name in session[2].files)


def test_invalid_native_token_type_keeps_valid_charges_and_stops_new_calls(session, tmp_path):
    invalid = response(text="not trusted", cost=0.1, incoming=False)
    provider = FakeProvider(invalid, response(text="never"))
    result = run(session, tmp_path, provider)
    assert result["status"] == "usage-unresolved" and len(provider.requests) == 1
    assert result["effort"]["inputTokens"] is None
    assert result["effort"]["providerCostUsd"] == 0.1
    assert '"prompt_tokens": false' in (tmp_path / "run/trace.json").read_text()


def test_live_adapter_cannot_substitute_model_settings_or_rate_bounds(session, tmp_path):
    session[1]["qualifications"] = dict.fromkeys(runtime.QUALIFICATIONS, True)
    provider, backend = FakeProvider(response(text="never")), FakeDocker()
    provider.simulation = backend.simulation = False
    provider.model = deepcopy(session[0]["model"])
    provider.model["inferenceSettings"]["temperature"] = False  # Does not equal numeric zero.
    provider.rates = deepcopy(session[1]["providerRates"])
    with pytest.raises(ValueError, match="model/settings differ"):
        run(session, tmp_path, provider, backend)
    provider.model = deepcopy(session[0]["model"])
    provider.rates["outputUsdPerToken"] = 0
    with pytest.raises(ValueError, match="rate bounds differ"):
        run(session, tmp_path, provider, backend)
    assert not provider.requests and not (tmp_path / "run").exists()


@pytest.mark.parametrize(
    "alias",
    [
        "snapshot",
        "responses",
        "profile-body",
        "profile-json-reencoded",
        "other-profile-body",
        "accessInstructions",
    ],
)
def test_source_first_cannot_read_access_artifact_or_profile_body_from_source_bundle(
    campaign, session, tmp_path, alias
):
    path, manifest = campaign
    task = manifest["tasks"][0]
    profile_body = '{"execution": {"test": "FROZEN DOTREPO PROFILE COMMAND"}}'
    other_body = "ANOTHER FROZEN PROFILE THAT MUST NOT ENTER THE SOURCE ARM"
    responses = {
        "snapshotSha256": manifest["artifacts"]["snapshot"]["sha256"],
        "profiles": {
            task["repository"]: {"status": 200, "body": profile_body},
            "example.test/other/repo": {"status": 200, "body": other_body},
        },
    }
    manifest["artifacts"]["responses"] = write(tmp_path, "responses.json", responses)
    if alias in {"snapshot", "responses", "accessInstructions"}:
        source_bytes = (tmp_path / manifest["artifacts"][alias]["path"]).read_bytes()
    elif alias == "profile-json-reencoded":
        source_bytes = b'{\n"execution":{"test":"FROZEN DOTREPO PROFILE COMMAND"}\n}'
        assert source_bytes != profile_body.encode()
    elif alias == "other-profile-body":
        source_bytes = other_body.encode()
    else:
        source_bytes = profile_body.encode()
    spec = bundle_spec(tmp_path, {"README.md": source_bytes}, task["revision"])
    config = deepcopy(session[1])
    config["sourceBundles"] = {task["repository"]: spec}
    manifest["artifacts"]["runtime"] = write(tmp_path, "runtime.json", config)
    save(campaign)
    out = tmp_path / "prepared"
    experiment.prepare(path, out)
    with pytest.raises(ValueError, match="aliases hidden/protected"):
        runtime.load_session(path, out / "assignment.json", f"{task['id']}-r1-source-first")


@pytest.mark.parametrize("role", ["gold", "oracle"])
@pytest.mark.parametrize("task_index", [0, 1])
def test_reserialized_hidden_answer_is_rejected_before_session_load(
    campaign, session, tmp_path, role, task_index
):
    path, manifest = campaign
    task, protected_task = manifest["tasks"][0], manifest["tasks"][task_index]
    # The artifact's original serialization need not be the runner's canonical
    # encoding. Protect every task's answers, including another task's artifact.
    protected = b'{ "answer": "PRIVATE EVALUATOR DATA", "role": "' + role.encode() + b'" }'
    protected_task[role] = write(tmp_path, f"protected-{role}.json", protected)
    source_bytes = json.dumps(json.loads(protected), separators=(",", ":")).encode()
    assert not runtime.content_digests(source_bytes) & {experiment.digest(protected)}
    spec = bundle_spec(tmp_path, {"README.md": source_bytes}, task["revision"])
    config = deepcopy(session[1])
    config["sourceBundles"] = {task["repository"]: spec}
    manifest["artifacts"]["runtime"] = write(tmp_path, "runtime.json", config)
    manifest["artifacts"]["responses"] = write(
        tmp_path,
        "responses.json",
        {
            "snapshotSha256": manifest["artifacts"]["snapshot"]["sha256"],
            "profiles": {task["repository"]: {"status": 404, "body": ""}},
        },
    )
    save(campaign)
    out = tmp_path / "prepared"
    experiment.prepare(path, out)
    with pytest.raises(ValueError, match="aliases hidden/protected"):
        runtime.load_session(path, out / "assignment.json", f"{task['id']}-r1-source-first")


@pytest.mark.parametrize("body", [[], None, "not-a-json-object", 17])
def test_nonobject_provider_response_preserves_attempt_and_unknown_charges(session, tmp_path, body):
    envelope = response(text="will be replaced")
    envelope.update(body=body, httpRequests=1, decodedBytes=len(json.dumps(body).encode()))
    provider, backend = FakeProvider(envelope, response(text="never")), FakeDocker()
    result = run(session, tmp_path, provider, backend)
    assert result["providerCalls"] == len(provider.requests) == 1
    assert result["status"] == "provider-failure"
    assert result["effort"]["httpRequests"] == 1
    assert result["effort"]["decodedBytes"] == envelope["decodedBytes"]
    for key in runtime.USAGE_KEYS:
        assert result["effort"][key] is None
        assert key + " unavailable" in result["measurementExclusions"]
    assert result["observedModel"] is None
    assert "observedModel unavailable" in result["measurementExclusions"]
    assert backend.cleanups == 1 and result["protocolDeviations"]
    receipt = experiment.read_json(tmp_path / "run/usage.json")
    assert receipt["model"] is None and receipt["effort"]["providerCostUsd"] is None
    trace = experiment.read_json(tmp_path / "run/trace.json")
    native = next(
        event["native"] for event in trace["events"] if event["kind"] == "provider-response"
    )
    assert native["body"] == body


def test_mocked_native_http_array_response_is_accounted_without_retaining_authorization(
    session, tmp_path, monkeypatch
):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size):
            return b"[]"

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
            return Response()

    monkeypatch.setattr(runtime, "build_opener", lambda *args: Opener())
    envelope = runtime.openrouter_transport("fixture-private-provider-key")({"messages": []}, 5)
    result = run(session, tmp_path, FakeProvider(envelope))
    assert result["effort"]["httpRequests"] == 1
    assert result["effort"]["inputTokens"] is None and result["effort"]["providerCostUsd"] is None
    assert "fixture-private-provider-key" not in (tmp_path / "run/trace.json").read_text()


def symlink_spec(root, files, links, *, members=None, revision="a" * 40):
    """Build a bound fixture without creating any host filesystem link."""
    import hashlib

    spec = bundle_spec(root, files, revision)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        for name in members if members is not None else [*files, *links]:
            item = tarfile.TarInfo(name)
            if name in links:
                item.type, item.linkname = tarfile.SYMTYPE, links[name]
                item.mode = 0o777
                stream.addfile(item)
            else:
                item.size = len(files[name])
                item.mode = 0o755 if name.endswith(".sh") else 0o644
                stream.addfile(item, io.BytesIO(files[name]))
    spec["archive"] = write(root, "source.tar", buffer.getvalue())
    inventory = experiment.read_json(root / spec["inventory"]["path"])
    inventory["symlinks"] = {}
    for name, target in links.items():
        raw = target.encode()
        inventory["symlinks"][name] = {
            "target": target,
            "sha256": experiment.digest(raw),
            "gitBlobSha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
            "mode": "120000",
        }
    spec["inventory"] = write(root, "source-inventory.json", inventory)
    provenance = experiment.read_json(root / spec["provenance"]["path"])
    provenance["archiveSha256"] = spec["archive"]["sha256"]
    spec["provenance"] = write(root, "source-provenance.json", provenance)
    return spec


def test_source_links_chains_dotdot_and_typed_reads_without_host_links(tmp_path):
    spec = symlink_spec(
        tmp_path,
        {"data/readme": b"source", "data/run.sh": b"#!/bin/sh\n"},
        {"links/data": "../data/", "README": "links/data/../data/readme"},
    )
    bundle = runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)
    assert bundle.resolved_links["README"] == {"path": "data/readme", "type": "regular"}
    assert (
        json.loads(runtime.source_read(bundle, "README"))["target"] == "links/data/../data/readme"
    )
    assert {r["type"] for r in json.loads(runtime.source_read(bundle, ""))} == {
        "regular",
        "symlink",
    }
    assert runtime.source_read(bundle, "data/readme") == b"source"
    assert not (tmp_path / "README").exists()


@pytest.mark.parametrize(
    "files,links",
    [
        ({"safe/file": b"ok"}, {"alias": "safe", "bad": "alias/../../escape"}),
        # Lexically x/y/../../file is contained, but y resolves one level
        # shallower before '..' is applied, so actual resolution escapes.
        ({"safe/file": b"ok", "file": b"ok"}, {"x/y": "../safe", "bad": "x/y/../../file"}),
        ({"file": b"ok"}, {"a": "b", "b": "a"}),
        ({"file": b"ok"}, {"a": "missing"}),
        ({"file": b"ok"}, {"a/up": ".."}),
        ({"a/file": b"ok", "b/file": b"ok"}, {"a/to-b": "../b", "b/to-a": "../a"}),
        ({"file": b"ok"}, {"a": "file/../file"}),
    ],
)
def test_source_links_reject_logical_escape_cycles_dangling_and_nondirectory(
    tmp_path, files, links
):
    spec = symlink_spec(tmp_path, files, links)
    with pytest.raises(ValueError, match="escapes|cycle|dangling|regular file"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


@pytest.mark.parametrize(
    "target", ["/etc/passwd", "C:/host", "C:host", "a\\b", "a\x00b", "a\nb", "a\x85b"]
)
def test_source_links_reject_unsafe_targets(tmp_path, target):
    spec = symlink_spec(tmp_path, {"file": b"ok"}, {"link": target})
    with pytest.raises(ValueError, match="unsafe source link target"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


@pytest.mark.parametrize("link_first", [False, True])
def test_source_links_refuse_members_beneath_link_in_both_archive_orders(tmp_path, link_first):
    files, links = {"target/file": b"safe", "alias/injected": b"injected"}, {"alias": "target"}
    order = [*links, *files] if link_first else [*files, *links]
    spec = symlink_spec(tmp_path, files, links, members=order)
    with pytest.raises(ValueError, match="under non-directory"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


@pytest.mark.parametrize("field", ["target", "sha256", "gitBlobSha", "mode"])
def test_source_links_bind_exact_target_bytes_git_blob_and_mode(tmp_path, field):
    spec = symlink_spec(tmp_path, {"file": b"ok"}, {"link": "file"})
    inventory = experiment.read_json(tmp_path / spec["inventory"]["path"])
    inventory["symlinks"]["link"][field] = "different"
    spec["inventory"] = write(tmp_path, "source-inventory.json", inventory)
    with pytest.raises(ValueError, match="identity mismatch"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


def test_source_links_refuse_duplicates_and_protected_target_content(tmp_path):
    spec = symlink_spec(tmp_path, {"file": b"hidden"}, {"link": "file"})
    with pytest.raises(ValueError, match="aliases hidden/protected"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, runtime.content_digests(b"hidden"), 1000000)
    spec = symlink_spec(
        tmp_path, {"file": b"ok"}, {"link": "file"}, members=["file", "link", "link"]
    )
    with pytest.raises(ValueError, match="duplicate source member"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


@pytest.mark.parametrize("kind", [tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE])
def test_source_links_do_not_admit_hardlinks_devices_or_fifos(tmp_path, kind):
    spec = symlink_spec(tmp_path, {"file": b"ok"}, {"link": "file"})
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        item = tarfile.TarInfo("link")
        item.type, item.linkname = kind, "file"
        stream.addfile(item)
    spec["archive"] = write(tmp_path, "source.tar", buffer.getvalue())
    provenance = experiment.read_json(tmp_path / spec["provenance"]["path"])
    provenance["archiveSha256"] = spec["archive"]["sha256"]
    spec["provenance"] = write(tmp_path, "source-provenance.json", provenance)
    with pytest.raises(ValueError, match="links/devices"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)


def test_dependency_cache_remains_regular_only_with_valid_source_links(session, tmp_path):
    request, _, source = session
    spec = cache_spec(tmp_path, request, source, {"cargo/registry/cache/item": b"ok"})
    linked = symlink_spec(
        tmp_path / "cache",
        {"cargo/registry/cache/item": b"ok"},
        {"cargo/registry/cache/link": "item"},
    )
    for role in ("archive", "inventory", "provenance"):
        linked[role]["path"] = "cache/" + linked[role]["path"]
    spec["bundle"] = linked
    preparation = experiment.read_json(tmp_path / spec["preparation"]["path"])
    preparation["cacheArchiveSha256"] = linked["archive"]["sha256"]
    spec["preparation"] = write(tmp_path, "cache-preparation.json", preparation)
    with pytest.raises(ValueError, match="cache links are forbidden"):
        runtime.dependency_cache(tmp_path, spec, request, source, set(), 1000000)


def test_link_checkout_transports_regular_members_then_links_and_retains_copy_cost(tmp_path):
    spec = symlink_spec(tmp_path, {"data/run.sh": b"#!/bin/sh\n"}, {"link": "data/"})
    bundle = runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)
    invoked = []

    def invoke(argv, **kwargs):
        invoked.append((argv, kwargs))
        return {"exitCode": 0, "error": None, "stdout": "", "stderr": ""}

    result = runtime.DockerBackend(invoke).checkout(bundle, 10)
    assert invoked[0][0][-2:] == ["/bin/mkdir", "/workspace/repository"]
    streams = [kwargs["data"] for _, kwargs in invoked if kwargs.get("data")]
    assert result["sourceCopy"]["stdinBytes"] == sum(map(len, streams)) > len(bundle.archive)
    for number, raw in enumerate(streams):
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive_stream:
            members = list(archive_stream)
            assert all(member.issym() == (number == 1) for member in members)
            if number == 0:
                assert members[0].mode == 0o755
            else:
                assert members[0].linkname == "data/"


ACTUAL_LINKS = json.loads(
    (
        BENCH / "f05-qualification-next8-20261029/source-links-qualification/actual-links.json"
    ).read_text()
)["links"]


@pytest.mark.parametrize("actual", ACTUAL_LINKS, ids=lambda a: a["task"] + ":" + a["path"])
def test_actual_seventeen_link_targets_admit_without_projection(tmp_path, actual):
    target = actual["lexicallyResolvedTarget"]
    files = {target + "/fixture.txt" if actual["targetKind"] == "directory" else target: b"fixture"}
    spec = symlink_spec(tmp_path, files, {actual["path"]: actual["target"]})
    bundle = runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)
    link = bundle.symlinks[actual["path"]]
    assert link["sha256"] == actual["sha256"] and link["gitBlobSha"] == actual["gitBlobSha"]
    assert bundle.resolved_links[actual["path"]] == {"path": target, "type": actual["targetKind"]}


def test_source_link_loader_keeps_six_tuple_and_validates_before_backend(
    campaign, session, tmp_path
):
    path, manifest = campaign
    task = manifest["tasks"][0]
    spec = symlink_spec(
        tmp_path, {"README.md": b"source"}, {"CLAUDE.md": "README.md"}, revision=task["revision"]
    )
    config = deepcopy(session[1])
    config["sourceBundles"] = {task["repository"]: spec}
    manifest["artifacts"]["runtime"] = write(tmp_path, "runtime.json", config)
    manifest["artifacts"]["responses"] = write(
        tmp_path,
        "responses.json",
        {
            "snapshotSha256": manifest["artifacts"]["snapshot"]["sha256"],
            "profiles": {task["repository"]: {"status": 404, "body": ""}},
        },
    )
    save(campaign)
    out = tmp_path / "prepared"
    experiment.prepare(path, out)
    loaded = runtime.load_session(path, out / "assignment.json", f"{task['id']}-r1-source-first")
    assert len(loaded) == 6 and loaded[2].symlinks["CLAUDE.md"]["target"] == "README.md"
    # Both validation calls are loader-only: no Docker/provider API is involved.
    hidden = (tmp_path / task["gold"]["path"]).read_bytes()
    bad = symlink_spec(
        tmp_path, {"README.md": hidden}, {"CLAUDE.md": "README.md"}, revision=task["revision"]
    )
    config["sourceBundles"] = {task["repository"]: bad}
    manifest["artifacts"]["runtime"] = write(tmp_path, "runtime.json", config)
    save(campaign)
    out = tmp_path / "prepared-negative"
    experiment.prepare(path, out)
    with pytest.raises(ValueError, match="hidden/protected"):
        runtime.load_session(path, out / "assignment.json", f"{task['id']}-r1-source-first")


def test_link_metadata_output_is_bounded_and_copy_padding_is_accounted(session, tmp_path):
    request, config, _ = session
    spec = symlink_spec(tmp_path, {"file": b"ok"}, {"link": "file"})
    bundle = runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)
    config["maxToolOutputBytes"] = 32

    class CopyDocker(FakeDocker):
        def checkout(self, bundle, timeout):
            result = super().checkout(bundle, timeout)
            return {**result, "sourceCopy": {"stdinBytes": len(bundle.archive) + 10240}}

    provider = FakeProvider(
        response(("read_upstream", {"path": "link"})),
        response(("checkout_source", {})),
        response(text="done"),
    )
    result = run((request, config, bundle), tmp_path, provider, CopyDocker())
    events = [json.loads(line) for line in (tmp_path / "run/events.jsonl").read_text().splitlines()]
    metadata = next(e["result"] for e in events if e["kind"] == "tool-response")
    assert metadata["truncated"] and len(metadata["content"].encode()) <= 32
    assert result["effort"]["decodedBytes"] == 32 + len(bundle.archive) + 10240


@pytest.mark.parametrize("mutation", ["conflict", "missing-link", "tar-target"])
def test_source_link_inventory_cannot_reinterpret_or_omit_archive_members(tmp_path, mutation):
    spec = symlink_spec(tmp_path, {"file": b"ok"}, {"link": "file"})
    inventory = experiment.read_json(tmp_path / spec["inventory"]["path"])
    if mutation == "conflict":
        inventory["files"]["link"] = experiment.digest(b"file")
    elif mutation == "missing-link":
        del inventory["symlinks"]["link"]
    else:
        import hashlib

        target = b"file/"
        inventory["symlinks"]["link"].update(
            target=target.decode(),
            sha256=experiment.digest(target),
            gitBlobSha=hashlib.sha1(b"blob 5\0" + target).hexdigest(),
        )
    spec["inventory"] = write(tmp_path, "source-inventory.json", inventory)
    with pytest.raises(ValueError, match="conflicting|links/devices|archive mismatch"):
        runtime.source_bundle(tmp_path, spec, "a" * 40, set(), 1000000)
