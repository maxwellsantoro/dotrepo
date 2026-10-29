"""Internal F-05 single-session runtime; no model/task is selected by this module.

The frozen runtime artifact uses backend=docker-ephemeral-v1 and runnerSha256;
networkPolicy=none, cacheState=cold; explicit resources, environment, containerUser,
maxToolOutputBytes and maxProviderCalls; sourceBundles maps canonical repositories
onto {revision, archive, inventory, provenance} content bindings. Inventory is
{revision, files:{relativePath:sha256}, missingSubmodules:[], missingLfsObjects:[],
limitations:[]}. Archives contain only inventoried regular files/directories,
without links/devices/traversal or generated Git metadata. Provenance is retained
upstream evidence, not inferred from a directory name. The image must contain
only qualified dependencies, never gold, profiles, credentials or task sources.

Local tasks provision a vetted archive before investigation; pre-clone tasks start
empty. Both arms can read_upstream and checkout_source. shell runs only inside
the ephemeral container; lookup returns only the task's frozen profile response,
only in the access arm. No host tool, arbitrary URL, mount, oracle or scorer is
exposed. Shell choices are not screened against gold. Scoring happens afterward.

Live execution needs all frozen qualification flags plus a provider adapter with
qualified native-token upper bounds and frozen maximum rates. The adapter must
not estimate tokens from bytes. Unknown charges/usage stop further paid calls.
HTTP receipts retain native response bodies, including failed calls. This module
checks consistency, not authenticity of supplied provider or source attestations.
The CLI currently validates contracts only; it cannot launch an unfrozen campaign.

Source bundles cannot alias hidden answers, access-only artifacts, or any retained
profile response body (including equivalent JSON encoding). These checks happen
on the host before either arm can read or provision a bundle. Provider bodies
that are not JSON objects retain transport accounting and null native usage.
Normalized receipt model.version is the actual observed version, never a copied
expected version after drift; model is null if no version was observed. Requested
routing identity/settings are retained separately in run.json and raw requests.
Drift/unknown-identity receipts require an explicit campaign abort/disposition;
they must not be rewritten to pass the preparation summarizer's equality checks.

Primary API references used for the adapter/backend:
https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion
https://docs.docker.com/reference/cli/docker/container/create/
https://docs.docker.com/engine/security/
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import subprocess
import tarfile
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid

from . import agent_experiment as experiment


ENV_KEYS = {
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TZ",
    "TMPDIR",
    "CARGO_HOME",
    "RUSTUP_HOME",
    "UV_CACHE_DIR",
    "XDG_CACHE_HOME",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
}
QUALIFICATIONS = {
    "taskEnvironmentFrozen",
    "imageAuditedWithoutGoldProfilesOrCredentials",
    "sourceProvisioningQualified",
    "providerTokenBoundsQualified",
    "budgetStopQualified",
    "armAccessQualified",
}
TOOL_NAMES = ("shell", "read_upstream", "checkout_source", "lookup")
USAGE_KEYS = ("inputTokens", "outputTokens", "cachedTokens", "reasoningTokens", "providerCostUsd")
ACCESS_ARTIFACTS = {
    "accessInstructions",
    "integration",
    "snapshot",
    "responses",
    "policy",
    "consumer",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(left, right):
    return experiment.encode(left) == experiment.encode(right)


def numeric(value, *, integer=False):
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and value >= 0
        and (not integer or type(value) is int)
    )


def relative_path(value):
    require(isinstance(value, str) and value and "\\" not in value, "invalid source path")
    path = PurePosixPath(value)
    require(
        not path.is_absolute() and all(p not in {"", ".", ".."} for p in value.split("/")),
        "source path escapes bundle",
    )
    return value


def content_digests(raw):
    """Compare exact bytes and JSON meaning without scanning arbitrary prose."""
    digests = {experiment.digest(raw)}
    try:
        digests.add(experiment.digest(experiment.encode(json.loads(raw))))
    except (ValueError, UnicodeDecodeError):
        pass
    return digests


@dataclass
class SourceBundle:
    archive: bytes
    files: dict[str, bytes]
    inventory: dict
    provenance_sha256: str


def source_bundle(root, spec, revision, hidden_hashes, max_bytes):
    require(
        set(spec) == {"revision", "archive", "inventory", "provenance"}, "invalid source bundle"
    )
    require(spec["revision"] == revision, "source bundle revision differs from task")
    blobs = {}
    for role in ("archive", "inventory", "provenance"):
        require(
            spec[role]["sha256"] not in hidden_hashes,
            "source bundle aliases hidden/protected evaluation or access artifact",
        )
        blobs[role] = experiment.artifact(root, spec[role])
        require(
            not content_digests(blobs[role]) & hidden_hashes,
            "source bundle aliases hidden/protected evaluation or access artifact",
        )
    provenance = json.loads(blobs["provenance"])
    require(
        provenance["revision"] == revision
        and provenance["archiveSha256"] == spec["archive"]["sha256"],
        "source provenance revision/archive binding mismatch",
    )
    require(
        isinstance(provenance["url"], str) and provenance["url"].startswith("https://"),
        "source provenance needs upstream locator",
    )
    experiment.timestamp(provenance["checkedAt"])
    inventory = json.loads(blobs["inventory"])
    require(
        set(inventory)
        == {"revision", "files", "missingSubmodules", "missingLfsObjects", "limitations"},
        "source inventory must declare omissions and limitations",
    )
    require(inventory["revision"] == revision, "inventory revision differs from task")
    for key in ("missingSubmodules", "missingLfsObjects", "limitations"):
        require(
            isinstance(inventory[key], list) and all(isinstance(x, str) for x in inventory[key]),
            "source omissions must remain explicit",
        )
    require(isinstance(inventory["files"], dict) and inventory["files"], "empty source inventory")
    require(len(blobs["archive"]) <= max_bytes, "archive exceeds workspace byte limit")
    files, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(blobs["archive"]), mode="r:") as archive:
        for member in archive:
            name = member.name.rstrip("/")
            relative_path(name)
            require(member.isdir() or member.isfile(), "source links/devices are forbidden")
            if member.isdir():
                continue
            require(name not in files, "duplicate source member")
            total += member.size
            require(
                total <= max_bytes and member.size <= max_bytes,
                "source exceeds workspace byte limit",
            )
            raw = archive.extractfile(member).read()
            digest = experiment.digest(raw)
            require(
                not content_digests(raw) & hidden_hashes,
                "source member aliases hidden/protected evaluation or access artifact",
            )
            require(inventory["files"].get(name) == digest, "source file inventory hash mismatch")
            files[name] = raw
    require(set(files) == set(inventory["files"]), "source inventory missing/extra files")
    return SourceBundle(blobs["archive"], files, inventory, spec["provenance"]["sha256"])


def load_session(manifest_path, assignment_path, session_id):
    """Verify full campaign first, but expose only allowlisted session data."""
    manifest, plan = experiment.verify(manifest_path, assignment_path)
    session = next((s for s in plan["sessions"] if s["sessionId"] == session_id), None)
    require(session is not None, "unknown assigned session")
    request = experiment.session_request(manifest, session)
    root = Path(manifest_path).parent.resolve()
    config = json.loads(experiment.artifact(root, request["artifacts"]["runtime"]))
    validate_runtime(config, request)
    hidden = {task[role]["sha256"] for task in manifest["tasks"] for role in ("gold", "oracle")}
    # Source-first cannot obtain profiles indirectly through its upstream tools.
    # This host-only inspection adds deny hashes; none of these bytes is exposed.
    for role in ACCESS_ARTIFACTS:
        hidden.update(content_digests(experiment.artifact(root, manifest["artifacts"][role])))
    responses = json.loads(experiment.artifact(root, manifest["artifacts"]["responses"]))
    require(
        isinstance(responses, dict) and isinstance(responses.get("profiles"), dict),
        "frozen responses must explicitly retain profile/absence objects",
    )
    require(
        responses["snapshotSha256"] == manifest["artifacts"]["snapshot"]["sha256"],
        "frozen responses bind different snapshot",
    )
    for response in responses["profiles"].values():
        require(
            isinstance(response, dict)
            and set(response) == {"status", "body"}
            and type(response["status"]) is int
            and isinstance(response["body"], str),
            "invalid frozen profile response",
        )
        if response["body"].strip():
            hidden.update(content_digests(response["body"].encode()))
    spec = config["sourceBundles"][request["task"]["repository"]]
    bundle = source_bundle(
        root, spec, request["task"]["revision"], hidden, config["resources"]["workspaceBytes"]
    )
    common = experiment.artifact(root, request["artifacts"]["commonPrompt"]).decode()
    task_prompt = experiment.artifact(root, request["task"]["prompt"]).decode()
    access = (
        experiment.artifact(root, request["artifacts"]["accessInstructions"]).decode()
        if request["arm"] == "dotrepo-access"
        else ""
    )
    lookup = None
    if request["arm"] == "dotrepo-access":
        lookup = responses["profiles"].get(request["task"]["repository"])
        require(lookup is not None, "frozen response must explicitly retain profile or absence")
        require(set(lookup) == {"status", "body"}, "invalid frozen profile response")
        require(
            type(lookup["status"]) is int and isinstance(lookup["body"], str),
            "invalid profile response",
        )
    return request, config, bundle, common + "\n" + access, task_prompt, lookup


def validate_runtime(config, request):
    experiment.resolved(config, "runtime")
    require(config["backend"] == "docker-ephemeral-v1", "unsupported backend")
    require(
        config["runnerSha256"] == experiment.digest(Path(__file__).read_bytes()),
        "runtime code changed",
    )
    require(config["networkPolicy"] == "none", "this backend requires explicit network=none")
    require(request["cacheState"] == "cold", "this backend supports fresh cold caches only")
    require(
        request["workspaceKey"] == request["cacheKey"], "workspace/cache session identity differs"
    )
    require(
        request["workspaceKey"].endswith("/" + request["sessionId"]),
        "invalid session workspace key",
    )
    require(
        re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", config["containerUser"]) is not None,
        "container must use an explicit non-root UID:GID",
    )
    resources = config["resources"]
    require(
        set(resources) == {"memoryBytes", "cpus", "pidsLimit", "workspaceBytes", "tmpBytes"},
        "incomplete container resources",
    )
    for key, value in resources.items():
        require(numeric(value, integer=key != "cpus") and value > 0, "invalid resource limit")
    for key in ("maxToolOutputBytes", "maxProviderCalls"):
        require(type(config[key]) is int and config[key] > 0, f"invalid {key}")
    env = config["environment"]
    require(
        isinstance(env, dict) and set(env) <= ENV_KEYS, "container environment is not allowlisted"
    )
    require(
        all(isinstance(v, str) and "\x00" not in v for v in env.values()), "invalid environment"
    )
    require(env.get("HOME") == "/workspace/.home", "HOME must be session-local")
    require(set(config["qualifications"]) == QUALIFICATIONS, "missing launch qualifications")
    require(
        all(type(v) is bool for v in config["qualifications"].values()),
        "invalid qualification flags",
    )
    rates = config["providerRates"]
    require(
        set(rates) == {"inputUsdPerToken", "outputUsdPerToken", "fixedUsdPerCall"}
        and all(numeric(v) for v in rates.values()),
        "missing frozen maximum rates",
    )
    require(
        request["task"]["startingState"] in {"pre-clone", "local-checkout"},
        "invalid starting state",
    )
    require(isinstance(config["sourceBundles"], dict), "source bundles must be frozen")


def live_ready(config):
    require(
        all(config["qualifications"].values()),
        "live launch blocked: frozen qualifications incomplete",
    )


def tool_schemas(arm):
    specs = {
        "shell": {"command": {"type": "string"}},
        "read_upstream": {"path": {"type": "string"}},
        "checkout_source": {},
        "lookup": {},
    }
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": {
                    "shell": "Run a shell command only inside this session's container workspace.",
                    "read_upstream": "Read a retained upstream path; an empty path lists available files.",
                    "checkout_source": "Provision the pinned upstream archive into the fresh workspace.",
                    "lookup": "Read the frozen dotrepo response; does not authorize command execution.",
                }[name],
                "parameters": {
                    "type": "object",
                    "properties": specs[name],
                    "required": list(specs[name]),
                    "additionalProperties": False,
                },
            },
        }
        for name in TOOL_NAMES
        if name != "lookup" or arm == "dotrepo-access"
    ]


def limited_process(argv, *, data=b"", timeout, output_limit):
    """Bound host capture even when an untrusted container writes indefinitely."""
    host_env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    with tempfile.TemporaryFile() as incoming:
        incoming.write(data)
        incoming.seek(0)
        process = subprocess.Popen(
            argv, stdin=incoming, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=host_env
        )
        selector = selectors.DefaultSelector()
        streams = {process.stdout: bytearray(), process.stderr: bytearray()}
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        deadline, error = time.monotonic() + timeout, None
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = "timeout"
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    available = output_limit - sum(map(len, streams.values()))
                    streams[key.fileobj].extend(chunk[:available])
                    if len(chunk) > available:
                        error = "output-limit"
                        break
                if error:
                    break
        finally:
            if error:
                process.kill()
            process.wait(timeout=max(1, deadline - time.monotonic()))
            selector.close()
            for stream in streams:
                stream.close()
        return {
            "stdout": bytes(streams[process.stdout]).decode(errors="replace"),
            "stderr": bytes(streams[process.stderr]).decode(errors="replace"),
            "exitCode": process.returncode,
            "error": error,
        }


class DockerBackend:
    """One disposable, mount-free container; the model never sees this API."""

    simulation = False

    def __init__(self, invoke=limited_process):
        self.invoke = invoke
        self.name = "dotrepo-f05-" + uuid.uuid4().hex
        self.created = False
        self.operations = []

    def _call(self, args, timeout, *, data=b"", limit=65536):
        result = self.invoke(["docker", *args], data=data, timeout=timeout, output_limit=limit)
        self.operations.append(
            {"argv": ["docker", *args], "stdinBytes": len(data), "result": result}
        )
        return result

    def provision(self, request, config, timeout):
        live_ready(config)
        deadline = time.monotonic() + timeout

        def remaining():
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("container provisioning deadline")
            return left

        image = request["environment"]["imageDigest"]
        inspected = self._call(["image", "inspect", image], remaining())
        require(inspected["exitCode"] == 0, "frozen local image missing; pulls are forbidden")
        metadata = json.loads(inspected["stdout"])[0]
        require(metadata["Id"] == image, "local image digest mismatch")
        image_config = metadata.get("Config") or {}
        require(not image_config.get("Volumes"), "image-declared volumes are forbidden")
        require(not image_config.get("OnBuild"), "image has unqualified on-build directives")
        image_env = image_config.get("Env") or []
        require(
            all(item.split("=", 1)[0] in ENV_KEYS for item in image_env),
            "image contains nonallowlisted environment",
        )
        resources = config["resources"]
        uid, gid = config["containerUser"].split(":")
        flags = [
            "create",
            "--name",
            self.name,
            "--pull=never",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--network=none",
            "--ipc=private",
            "--pid=private",
            "--cgroupns=private",
            "--user",
            config["containerUser"],
            "--workdir=/workspace",
            "--memory",
            str(resources["memoryBytes"]),
            "--memory-swap",
            str(resources["memoryBytes"]),
            "--cpus",
            str(resources["cpus"]),
            "--pids-limit",
            str(resources["pidsLimit"]),
            "--ulimit",
            "nofile=1024:1024",
            "--log-driver=none",
            "--no-healthcheck",
            "--tmpfs",
            f"/workspace:rw,nosuid,nodev,size={resources['workspaceBytes']},uid={uid},gid={gid},mode=0700",
            "--tmpfs",
            f"/tmp:rw,nosuid,nodev,size={resources['tmpBytes']},uid={uid},gid={gid},mode=0700",
            "--label",
            "dotrepo.session=" + request["workspaceKey"],
        ]
        for key, value in sorted(config["environment"].items()):
            flags += ["--env", f"{key}={value}"]
        flags += ["--entrypoint=/bin/sh", image, "-c", "while :; do sleep 3600; done"]
        # The name is fixed before create so partial creates can still be removed.
        self.created = True
        result = self._call(flags, remaining())
        require(result["exitCode"] == 0 and not result["error"], "container create failed")
        started = self._call(["start", self.name], remaining())
        require(started["exitCode"] == 0, "container start failed")
        return {
            "imageId": metadata["Id"],
            "containerName": self.name,
            "network": "none",
            "mounts": [],
            "readonlyRoot": True,
        }

    def checkout(self, bundle, timeout):
        deadline = time.monotonic() + timeout
        result = self._call(
            ["exec", self.name, "/bin/mkdir", "-p", "/workspace/repository"], timeout
        )
        if result["exitCode"] != 0:
            return result
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("source provisioning deadline")
        return self._call(
            [
                "exec",
                "-i",
                self.name,
                "/bin/tar",
                "--extract",
                "--no-same-owner",
                "--no-same-permissions",
                "--directory=/workspace/repository",
            ],
            left,
            data=bundle.archive,
        )

    def shell(self, command, timeout, output_limit):
        return self._call(
            ["exec", "--workdir=/workspace/repository", self.name, "/bin/sh", "-c", command],
            timeout,
            limit=output_limit,
        )

    def cleanup(self):
        if not self.created:
            return {"exitCode": 0, "error": None}
        return self._call(["rm", "--force", "--volumes", self.name], 15)


class OpenRouterAdapter:
    """Explicit frozen model/settings; inject a qualified tokenizer and transport.

    token_upper_bound must count the complete message/tool request in native model
    tokens with a qualified conservative bound. There is no byte-based fallback.
    """

    simulation = False

    def __init__(self, model, rates, token_upper_bound, transport):
        require(model["provider"] == "openrouter", "adapter provider mismatch")
        self.model, self.rates = model, rates
        self.token_upper_bound, self.transport = token_upper_bound, transport
        settings = model["inferenceSettings"]
        require(
            type(settings.get("max_tokens")) is int and settings["max_tokens"] > 0,
            "freeze an explicit per-call output ceiling",
        )
        require(
            not (set(settings) & {"model", "messages", "tools", "stream", "models", "plugins"}),
            "settings may not replace agent tools, model, or messages",
        )
        require(
            (settings.get("provider") or {}).get("require_parameters") is True,
            "provider must require support for frozen inference parameters",
        )

    def body(self, messages, tools):
        return {
            "model": self.model["id"],
            "messages": messages,
            "tools": tools,
            **self.model["inferenceSettings"],
            "stream": False,
        }

    def quote(self, messages, tools):
        body = self.body(messages, tools)
        incoming = self.token_upper_bound(body)
        require(numeric(incoming, integer=True), "qualified native token bound unavailable")
        outgoing = body["max_tokens"]
        return {
            "inputTokens": incoming,
            "outputTokens": outgoing,
            "providerCostUsd": incoming * self.rates["inputUsdPerToken"]
            + outgoing * self.rates["outputUsdPerToken"]
            + self.rates["fixedUsdPerCall"],
        }

    def complete(self, messages, tools, timeout):
        return self.transport(self.body(messages, tools), timeout)


def openrouter_transport(api_key):
    """Credentials stay in host headers and are never included in retained events."""
    require(isinstance(api_key, str) and api_key, "missing provider credential")

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = build_opener(ProxyHandler({}), NoRedirect())

    def send(body, timeout):
        request = Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=experiment.encode(body),
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                raw, status = response.read(2 * 1024 * 1024 + 1), response.status
        except HTTPError as exc:
            raw, status = exc.read(2 * 1024 * 1024 + 1), exc.code
        except Exception as exc:
            return {
                "status": None,
                "body": {},
                "error": type(exc).__name__,
                "httpRequests": 1,
                "decodedBytes": None,
            }
        if len(raw) > 2 * 1024 * 1024:
            return {
                "status": status,
                "body": {},
                "error": "response-size-limit",
                "httpRequests": 1,
                "decodedBytes": len(raw),
            }
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            payload = {"unparseableResponse": raw.decode(errors="replace")}
        return {
            "status": status,
            "body": payload,
            "error": None,
            "httpRequests": 1,
            "decodedBytes": len(raw),
        }

    return send


def usage(payload):
    if not isinstance(payload, dict):
        return dict.fromkeys(USAGE_KEYS)
    native = payload.get("usage") or {}
    if not isinstance(native, dict):
        return dict.fromkeys(USAGE_KEYS)
    prompt_details = native.get("prompt_tokens_details") or {}
    completion_details = native.get("completion_tokens_details") or {}
    fields = {
        "inputTokens": native.get("prompt_tokens"),
        "outputTokens": native.get("completion_tokens"),
        "cachedTokens": prompt_details.get("cached_tokens")
        if isinstance(prompt_details, dict)
        else None,
        "reasoningTokens": completion_details.get("reasoning_tokens")
        if isinstance(completion_details, dict)
        else None,
        "providerCostUsd": native.get("cost"),
    }
    for key, value in fields.items():
        if value is not None and not numeric(value, integer=key != "providerCostUsd"):
            # Retain the invalid native field in the raw trace; never turn it
            # into a numeric zero or erase valid charges from the same response.
            fields[key] = None
    return fields


def run_session(
    request,
    config,
    bundle,
    system_prompt,
    task_prompt,
    lookup,
    provider,
    backend,
    output,
    *,
    clock=time.monotonic,
):
    """Investigate without gold; retain outcomes even when tools/providers fail."""
    validate_runtime(config, request)
    simulation = bool(provider.simulation and backend.simulation)
    require(provider.simulation == backend.simulation, "cannot mix simulated and live adapters")
    if not simulation:
        live_ready(config)
        require(
            same(getattr(provider, "model", None), request["model"]),
            "live provider model/settings differ from frozen request",
        )
        require(
            same(getattr(provider, "rates", None), config["providerRates"]),
            "live provider rate bounds differ from freeze",
        )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started, events = clock(), []
    budget = request["budgets"]
    request_hash = experiment.digest(experiment.encode(request))
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request["task"]["request"] + "\n" + task_prompt},
    ]
    tools = tool_schemas(request["arm"])
    effort = {key: 0 for key in experiment.EFFORT}
    # These allocations need their frozen accounting, not an invented zero.
    effort.update(preparationCostUsd=None, maintenanceCostUsd=None)
    status, final, checked_out, calls = "infrastructure-failure", None, False, 0
    model_observations, deviations = [], []

    def remaining():
        result = budget["wallTimeSeconds"] - (clock() - started)
        if result <= 0:
            raise TimeoutError("session-wall-time")
        return result

    def emit(kind, value):
        event = json.loads(experiment.encode({"index": len(events) + 1, "kind": kind, **value}))
        events.append(event)
        # Persist incrementally before acting again, retaining partial failed runs.
        with (output / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")

    def provision_source():
        nonlocal checked_out
        result = backend.checkout(bundle, remaining())
        emit(
            "checkout",
            {
                "result": result,
                "archiveBytes": len(bundle.archive),
                "provenanceSha256": bundle.provenance_sha256,
                "inventory": bundle.inventory,
            },
        )
        if effort["decodedBytes"] is not None:
            effort["decodedBytes"] += len(bundle.archive)
        checked_out = result["exitCode"] == 0 and not result.get("error")
        return result

    try:
        emit("provision", {"result": backend.provision(request, config, remaining())})
        if request["task"]["startingState"] == "local-checkout":
            require(provision_source()["exitCode"] == 0 and checked_out, "initial checkout failed")
        for _ in range(config["maxProviderCalls"]):
            remaining()
            quote = provider.quote(messages, tools)
            require(
                set(quote) == {"inputTokens", "outputTokens", "providerCostUsd"}
                and all(
                    numeric(value, integer=key != "providerCostUsd") for key, value in quote.items()
                ),
                "invalid provider admission quote",
            )
            ceilings = {
                "inputTokens": budget["inputTokens"],
                "outputTokens": budget["outputTokens"],
                "providerCostUsd": budget["monetaryUsd"],
            }
            if any(
                effort[key] is None or effort[key] + quote[key] > limit
                for key, limit in ceilings.items()
            ):
                status = "budget-exhausted"
                emit("stop", {"reason": "provider-admission-budget", "quote": quote})
                break
            emit(
                "provider-request",
                {
                    "messages": messages,
                    "tools": tools,
                    "quote": quote,
                    "requestedModel": request["model"],
                },
            )
            calls += 1
            try:
                envelope = provider.complete(messages, tools, remaining())
            except Exception as exc:
                envelope = {
                    "status": None,
                    "body": {},
                    "error": type(exc).__name__,
                    "httpRequests": None,
                    "decodedBytes": None,
                }
            payload = envelope["body"]
            observed = usage(payload)
            exceeded_quote = any(
                observed[key] is not None and observed[key] > quote[key] for key in quote
            )
            if exceeded_quote:
                deviations.append("Native usage exceeded qualified per-call admission bound")
            for key, value in observed.items():
                effort[key] = (
                    effort[key] + value if effort[key] is not None and value is not None else None
                )
            effort["httpRequests"] = (
                effort["httpRequests"] + envelope["httpRequests"]
                if effort["httpRequests"] is not None and envelope["httpRequests"] is not None
                else None
            )
            effort["decodedBytes"] = (
                effort["decodedBytes"] + envelope["decodedBytes"]
                if effort["decodedBytes"] is not None and envelope["decodedBytes"] is not None
                else None
            )
            emit("provider-response", {"native": envelope})
            if not isinstance(payload, dict):
                status = "provider-failure"
                deviations.append(
                    "Provider response body is not a JSON object; native usage unresolved"
                )
                emit("stop", {"reason": "nonobject-provider-response"})
                break
            if payload.get("model") is not None:
                model_observations.append(payload["model"])
                if payload["model"] != request["model"]["version"]:
                    deviations.append("Observed model version differs from frozen request")
                    emit("stop", {"reason": "model-version-drift", "observed": payload["model"]})
                    break
            if any(
                effort[key] is not None and effort[key] > limit for key, limit in ceilings.items()
            ):
                deviations.append("Native usage exceeded frozen admission/session bounds")
                status = "budget-exhausted"
                break
            if envelope["status"] != 200 or envelope["error"]:
                status = "provider-failure"
                break
            if exceeded_quote:
                status = "budget-exhausted"
                break
            if payload.get("model") is None or any(observed[k] is None for k in ceilings):
                status = "usage-unresolved"
                emit("stop", {"reason": "unknown-native-usage-cost-or-model"})
                break
            remaining()
            choice = payload["choices"][0]
            require(
                choice.get("finish_reason") not in {"length", "content_filter", "error"},
                "provider stopped without a complete decision",
            )
            message = choice["message"]
            messages.append(message)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                final = message.get("content")
                status = "agent-finished"
                break
            for call in tool_calls:
                remaining()
                if effort["toolCalls"] >= budget["toolCalls"]:
                    status = "budget-exhausted"
                    break
                effort["toolCalls"] += 1
                name = call["function"]["name"]
                arguments = json.loads(call["function"]["arguments"])
                emit("tool-request", {"name": name, "arguments": arguments, "id": call["id"]})
                try:
                    require(name in TOOL_NAMES, "unsupported tool")
                    require(
                        name != "lookup" or request["arm"] == "dotrepo-access", "arm denies lookup"
                    )
                    if name == "shell":
                        require(
                            set(arguments) == {"command"} and isinstance(arguments["command"], str),
                            "invalid shell request",
                        )
                        require(checked_out, "checkout_source is required before shell")
                        result = backend.shell(
                            arguments["command"], remaining(), config["maxToolOutputBytes"]
                        )
                        if result.get("error") in {"timeout", "output-limit"}:
                            status = "budget-exhausted"
                    elif name == "checkout_source":
                        require(arguments == {}, "checkout_source takes no arguments")
                        require(
                            not checked_out,
                            "source already provisioned; caches are not reset mid-session",
                        )
                        result = provision_source()
                    elif name == "read_upstream":
                        require(set(arguments) == {"path"}, "invalid source request")
                        name_in_archive = arguments["path"]
                        raw = (
                            experiment.encode(sorted(bundle.files))
                            if name_in_archive == ""
                            else bundle.files[relative_path(name_in_archive)]
                        )
                        result = {
                            "content": raw[: config["maxToolOutputBytes"]].decode(errors="replace"),
                            "truncated": len(raw) > config["maxToolOutputBytes"],
                        }
                        if effort["decodedBytes"] is not None:
                            effort["decodedBytes"] += min(len(raw), config["maxToolOutputBytes"])
                    else:
                        require(
                            arguments == {} and lookup is not None, "invalid frozen lookup request"
                        )
                        result = lookup
                        if effort["decodedBytes"] is not None:
                            effort["decodedBytes"] += len(experiment.encode(result))
                except (ValueError, KeyError, TypeError) as exc:
                    result = {"error": str(exc)}
                emit("tool-response", {"id": call["id"], "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, allow_nan=False),
                    }
                )
                if status == "budget-exhausted":
                    break
            if status == "budget-exhausted":
                break
        else:
            status = "budget-exhausted"
            emit("stop", {"reason": "provider-call-ceiling"})
    except TimeoutError:
        status = "budget-exhausted"
        emit("stop", {"reason": "session-wall-time"})
    except Exception as exc:
        # Avoid retaining credential-bearing exception representations from a transport.
        emit("failure", {"exceptionType": type(exc).__name__})
    finally:
        try:
            cleaned = backend.cleanup()
            emit("cleanup", {"result": cleaned})
            if cleaned.get("exitCode") != 0 or cleaned.get("error"):
                deviations.append("Container cleanup failed; operator removal required")
        except Exception as exc:
            emit("cleanup", {"exceptionType": type(exc).__name__})
            deviations.append("Container cleanup failed; operator removal required")
        effort["elapsedSeconds"] = max(0, clock() - started)
        if effort["elapsedSeconds"] > budget["wallTimeSeconds"]:
            deviations.append("Session wall ceiling reached; termination/cleanup overhead retained")
        if getattr(backend, "operations", None):
            emit("docker-operations", {"operations": backend.operations})
        observed_model = (
            {**request["model"], "version": model_observations[-1]} if model_observations else None
        )
        receipt = {
            "sessionId": request["sessionId"],
            "requestSha256": request_hash,
            "model": observed_model,
            "environment": request["environment"],
            "runtimeSha256": request["artifacts"]["runtime"]["sha256"],
            "effort": effort,
        }
        (output / "usage.json").write_bytes(experiment.encode(receipt))
        trace = {"sessionId": request["sessionId"], "requestSha256": request_hash, "events": events}
        (output / "trace.json").write_bytes(experiment.encode(trace))
        result = {
            "sessionId": request["sessionId"],
            "requestSha256": request_hash,
            "status": status,
            "simulation": simulation,
            "finalMessage": final,
            "providerCalls": calls,
            "observedModelVersions": model_observations,
            "requestedModel": request["model"],
            "observedModel": observed_model,
            "effort": effort,
            "protocolDeviations": deviations,
            "sourceOmissions": {
                key: bundle.inventory[key]
                for key in ("missingSubmodules", "missingLfsObjects", "limitations")
            },
            "measurementExclusions": [
                key + " unavailable" for key, value in effort.items() if value is None
            ]
            + (["observedModel unavailable"] if observed_model is None else []),
            "correctCompletion": None,
            "scoringPerformed": False,
        }
        (output / "run.json").write_bytes(experiment.encode(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    try:
        request, config, *_ = load_session(args.manifest, args.assignment, args.session_id)
        if args.live:
            live_ready(config)
            raise ValueError(
                "live CLI launch remains closed until the model-specific tokenizer/transport adapter is frozen and qualified"
            )
        print(
            json.dumps(
                {
                    "sessionId": request["sessionId"],
                    "validated": True,
                    "liveQualified": all(config["qualifications"].values()),
                    "launched": False,
                }
            )
        )
    except (ValueError, KeyError, TypeError, OSError, tarfile.TarError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
