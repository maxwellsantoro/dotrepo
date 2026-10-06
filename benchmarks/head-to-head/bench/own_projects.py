"""Bounded operator study on eight fixed tasks in four maintainer-owned projects.

Source decisions are manually preregistered, not independent agent decisions.
Freeze precedes profile requests. Only fixed source commands run; an unfamiliar
accepted profile is logged as an unexecuted context mismatch and falls back.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .arms.lookup_first import consumer
from .tasks import ARMS, markdown, score, validate_selection

EXECUTION_ROOT = Path(__file__).resolve().parents[3]

REVISIONS = {
    "RamenOS": "eba7fb7ce53807a6b9b5a85bd3caaf9f7749d917",
    "sha256-benchmark-atlas": "866fe127542178c35515f51afed30c41616bdd77",
    "ries-rs": "cfa959ed21a5a5e5f3d9538d9d1714c2401611e5",
    "pagedigest": "f880f813cc0df49603482dbd879ff4ef49b3a519",
}
REPEAT_REVISIONS = {
    **REVISIONS,
    "RamenOS": "4faea185ccd0b5bf310f2b949ce51b31fcbe0503",
}
CONTEXTUAL_REVISIONS = {
    **REVISIONS,
    "RamenOS": "8dc5ff88ddc404528c384aead9ea77f17bf63d40",
    "sha256-benchmark-atlas": "71eda5d6480e0b9e39f914f3641d91f98402e943",
}
# Commands and scope were selected from pinned upstream sources, before coverage.
CASES = [
    (
        "RamenOS",
        "host-build",
        "just build-host",
        ".",
        "host components",
        "docs/GETTING_STARTED.md",
        ["just codegen (included by wrapper)", "pinned Rust nightly and just"],
        [],
    ),
    (
        "RamenOS",
        "host-proof",
        "just foundry-agent-task-proof-rt",
        ".",
        "host task proof",
        "README.md",
        ["pinned Rust nightly and just"],
        [],
    ),
    (
        "sha256-benchmark-atlas",
        "build",
        "uv run sha256-atlas build",
        ".",
        None,
        "README.md",
        ["uv sync", "README quick-start compiler/toolchain prerequisites"],
        ["uv sync"],
    ),
    (
        "sha256-benchmark-atlas",
        "correctness",
        "uv run sha256-atlas correctness --cases 1000 --skip-million",
        ".",
        None,
        "README.md",
        [
            "uv sync",
            "README quick-start compiler/toolchain prerequisites",
            "uv run sha256-atlas build",
        ],
        ["uv sync", "uv run sha256-atlas build"],
    ),
    (
        "ries-rs",
        "core-build",
        "cargo build",
        ".",
        "Rust core and CLI",
        "CONTRIBUTING.md",
        ["Rust/Cargo"],
        [],
    ),
    (
        "ries-rs",
        "core-test",
        "cargo test",
        ".",
        "Rust core and CLI",
        "AGENTS.md",
        ["Rust/Cargo"],
        [],
    ),
    (
        "pagedigest",
        "consumer-test",
        "uv run --locked python -m unittest discover -s tests -v",
        "implementations/python-consumer",
        "Python consumer",
        "AGENTS.md",
        ["uv and locked consumer environment"],
        [],
    ),
    (
        "pagedigest",
        "generator-test",
        "cargo test --locked",
        "implementations/rust-generator",
        "Rust generator",
        "AGENTS.md",
        ["Rust/Cargo"],
        [],
    ),
]
TIMEOUT = 300
MAX_BODY = 8 * 1024 * 1024
SDK_ROOT = Path("/tmp/dotrepo-readiness-tools/zig-sdk-compat")


def study_inputs(study):
    if study == "initial":
        return REVISIONS, CASES
    if study == "contextual-campaign":
        # Same commands and completion oracles; replace old human scope labels
        # with the actual directories owning each task's requested surface.
        components = [
            "services",
            "services/store_service",
            None,
            None,
            "src",
            "src",
            "implementations/python-consumer",
            "implementations/rust-generator",
        ]
        cases = []
        for original, component in zip(CASES, components, strict=True):
            case = list(original)
            case[4] = component
            if case[1] == "host-proof":
                case[6] = ["just codegen (included by wrapper)", "pinned Rust nightly and just"]
            cases.append(tuple(case))
        return CONTEXTUAL_REVISIONS, cases
    if study not in {"readiness-repeat", "atlas-sdk-followup", "atlas-sdk-scoped"}:
        raise ValueError("unknown fixed study")
    if study.startswith("atlas-sdk"):
        cases = []
        for original in CASES[2:4]:
            case = list(original)
            case[6] = [*original[6], "task-local Zig 0.14 compatible SDK selection"]
            cases.append(tuple(case))
        return REPEAT_REVISIONS, cases
    cases = list(CASES)
    case = list(cases[1])
    case[6] = ["just codegen (included by wrapper)", "pinned Rust nightly and just"]
    cases[1] = tuple(case)
    return REPEAT_REVISIONS, cases


def tool_versions():
    return {
        "java": subprocess.check_output(["javac", "-version"], text=True).strip(),
        "zig": subprocess.check_output(["zig", "version"], text=True).strip(),
    }


def python_shim():
    uv = shlex.quote(shutil.which("uv"))
    return (
        '#!/bin/sh\nif [ -x "$DOTREPO_STUDY_PROJECT_PYTHON" ]; then\n'
        f'  exec {uv} run --no-project "$DOTREPO_STUDY_PROJECT_PYTHON" "$@"\n'
        "fi\n"
        f'exec {uv} run --no-project {shlex.quote(sys.executable)} "$@"\n'
    )


def sdk_shim():
    return (
        '#!/bin/sh\nif [ "$#" -eq 3 ] && [ "$1" = "--sdk" ] && '
        '[ "$2" = "macosx" ] && [ "$3" = "--show-sdk-path" ]; then\n'
        '  printf "%s\\n" "$DOTREPO_STUDY_ZIG_SDK"\n'
        'else\n  exec /usr/bin/xcrun "$@"\nfi\n'
    )


def zig_shim(executable, selector_directory):
    return (
        f'#!/bin/sh\nPATH={shlex.quote(str(selector_directory))}:"$PATH"\nexport PATH\n'
        f'exec {shlex.quote(str(executable))} "$@"\n'
    )


def study_environment(study):
    return {"DOTREPO_STUDY_ZIG_SDK": str(SDK_ROOT)} if study.startswith("atlas-sdk") else {}


def preparation_environment(study, repo):
    if study == "contextual-campaign" and repo == "sha256-benchmark-atlas":
        return {"DOTREPO_STUDY_ZIG_SDK": str(SDK_ROOT)}
    return {}


def uses_sdk(study):
    return study.startswith("atlas-sdk") or study == "contextual-campaign"


def runtime_versions():
    return {
        "python": sys.version,
        "uv": subprocess.check_output(["uv", "--version"], text=True).strip(),
    }


def validate_runtime(workload):
    if workload.get("study") == "contextual-campaign":
        if workload.get("runtimeVersions") != runtime_versions():
            raise ValueError("Python or uv runtime changed after freeze")


def sdk_source():
    stub = SDK_ROOT / "usr/lib/libSystem.tbd"
    includes = (SDK_ROOT / "usr/include").resolve()
    settings = includes.parent.parent / "SDKSettings.json"
    return {
        "root": str(SDK_ROOT),
        "libSystemSource": str(stub.resolve()),
        "libSystemSha256": hashlib.sha256(stub.read_bytes()).hexdigest(),
        "headerSource": str(includes),
        "sdkSettingsSha256": hashlib.sha256(settings.read_bytes()).hexdigest(),
        "selectionShimSha256": hashlib.sha256(sdk_shim().encode()).hexdigest(),
    }


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def fetch(url):
    request = Request(url, headers={"User-Agent": "dotrepo-own-project-study/1.0"})
    try:
        response = urlopen(request, timeout=30)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("study response exceeds byte limit")
        return response.status, body


def execution_sources():
    """Bind every local benchmark dependency, the dynamic client and lockfiles."""
    root = EXECUTION_ROOT
    paths = sorted((root / "benchmarks/head-to-head/bench").rglob("*.py"))
    paths += [
        root / "examples/external-consumer/lookup_before_scrape.py",
        root / "pyproject.toml",
        root / "uv.lock",
    ]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def retain_execution_sources(output):
    manifest = execution_sources()
    root = EXECUTION_ROOT
    for relative in manifest:
        target = output / "execution-source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    return manifest


def validate_execution_sources(workload, output):
    manifest = workload.get("executionSources")
    if not manifest or manifest != execution_sources():
        raise ValueError("execution dependency changed after freeze; freeze a new packet")
    for relative, digest in manifest.items():
        raw = (output / "execution-source" / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("retained execution source differs from freeze")
    if workload["consumerPolicy"] != consumer.INSTRUCTION_POLICY:
        raise ValueError("consumer policy differs from freeze")


def select_profile_instruction(identity, status, body, purpose, request=None):
    result = consumer.interpret_http_response(identity=identity, status_code=status, body=body)
    return consumer.select_instruction(result, purpose, request=request)


def screen_instruction_for_task(selected, expected):
    """Equivalence is exact equality of every instruction field; no flag repair.

    Record selection has already happened independently of this task oracle.
    Unsupported or incorrect accepted answers are logged before source fallback.
    """
    if selected is None or selected == expected:
        return selected, None
    return None, {
        "origin": "profile",
        "instruction": selected,
        "exitCode": None,
        "oraclePassed": False,
        "executionError": "accepted instruction differs from frozen task context; not executed",
    }


def execute_instruction(plan, setup_commands, root, env, timeout, oracle_name):
    """Execute the selected plan; setup is a separately declared environment input.

    Prerequisite descriptions are never interpreted as shell commands. The caller
    must establish them through its frozen preparation contract first.
    """
    commands = []
    command_env = {**env, **plan["environment"]}
    for command in [*setup_commands, plan["command"]]:
        result = execute(command, root / plan["workingDirectory"], command_env, timeout)
        commands.append(result)
        if result["exitCode"] != 0 or result["executionError"]:
            break
    passed = len(commands) == len(setup_commands) + 1 and oracle(oracle_name, root, commands[-1])
    return commands, passed


def freeze(output, sources, meta_path, inventory_path, study="initial"):
    if output.exists() and any(output.iterdir()):
        raise ValueError("freeze requires an empty output directory")
    output.mkdir(parents=True, exist_ok=True)
    meta = json.loads(meta_path.read_bytes())
    write(output / "meta.json", meta)
    write(output / "inventory.json", json.loads(inventory_path.read_bytes()))
    revisions, cases = study_inputs(study)
    versions = tool_versions() if study != "initial" else None
    if versions and (not versions["java"].startswith("javac 21.") or versions["zig"] != "0.14.0"):
        raise ValueError("readiness repeat requires source-pinned Java 21 and Zig 0.14.0")
    tasks = []
    for repo, name, command, cwd, component, source, prerequisites, setup in cases:
        root = sources / repo
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        if actual != revisions[repo]:
            raise ValueError("source revision differs from selected revision")
        evidence = root / source
        if command not in evidence.read_text():
            raise ValueError(f"selected command absent from source: {repo}/{source}")
        if study == "contextual-campaign":
            for path in (cwd, component):
                if path and not (root / path).is_dir():
                    raise ValueError("requested task component or directory is absent")
        purpose = "build" if name.endswith("build") else "test"
        plan = {
            "command": command,
            "workingDirectory": cwd,
            "scope": "component" if component else "repository",
            "component": component,
            "prerequisites": prerequisites,
            "parameters": {},
            "environment": study_environment(study),
            "sourcePaths": [source],
            "purpose": purpose,
        }
        tasks.append(
            {
                "id": f"{repo}-{name}",
                "taskClass": name,
                "identity": f"github.com/maxwellsantoro/{repo}",
                "revision": actual,
                "environmentId": "operator-macos-arm64-zig-sdk-v3"
                if study == "atlas-sdk-followup"
                else "operator-macos-arm64-readiness-v2"
                if study == "readiness-repeat"
                else "operator-macos-arm64-uv-shims-v1",
                "acceptableInstructions": [plan],
                "setupCommands": setup,
                "oracle": name,
                "timeoutSecondsPerCommand": TIMEOUT if study == "initial" else 900,
                "evidence": [
                    {
                        "url": f"https://github.com/maxwellsantoro/{repo}/blob/{actual}/{source}",
                        "locator": command,
                        "checkedAt": now(),
                        "sourceRevision": actual,
                        "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                    }
                ],
            }
        )
        if study == "contextual-campaign":
            tasks[-1]["preparationEnvironment"] = preparation_environment(study, repo)
            tasks[-1]["instructionRequest"] = {
                "scope": plan["scope"],
                "component": component,
                "workingDirectory": cwd,
            }
            tasks[-1]["environmentId"] = "operator-macos-arm64-contextual-v4"
    write(
        output / "workload.json",
        {
            "version": 1,
            "study": study,
            "frozenAt": now(),
            "selectionBeforeCoverageInspection": True,
            "consumerClass": "operator-controlled",
            "cacheState": "warm",
            "snapshotId": meta["snapshotId"],
            "consumerPolicy": consumer.INSTRUCTION_POLICY,
            "executionSources": retain_execution_sources(output),
            "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "toolVersions": versions,
            "sdkSource": sdk_source() if uses_sdk(study) else None,
            "runtimeVersions": runtime_versions() if study == "contextual-campaign" else None,
            "tasks": tasks,
            "selection": "All four substantive other public projects; exclude dotrepo self-test and throwaway canary. Two tasks each; no post-coverage substitutions.",
            "measurementBoundary": "Warm shared tool/download caches; fresh checkout and build outputs per arm. Explicit source/profile HTTP, checkout, setup, command execution and oracle are timed. Clone/bootstrap/source adjudication and package-manager network counts are outside transport totals. No modeled or net-cost claim.",
        },
    )
    if study != "initial":
        path = output / "workload.json"
        workload = json.loads(path.read_bytes())
        parent = Path(__file__).parents[1] / "results/own-projects-2026-10-04/workload.json"
        workload["repeatOfWorkloadSha256"] = hashlib.sha256(parent.read_bytes()).hexdigest()
        workload["knownCoverage"] = True
        workload["selection"] = (
            "Targeted readiness repeat of the original eight preregistered tasks. "
            "Original selection preceded coverage inspection; coverage is now known. "
            "No task substitutions. RamenOS uses the proposed prerequisite-fix commit; "
            "other revisions and commands are unchanged. This is not a held-out study."
        )
        if study.startswith("atlas-sdk"):
            previous = parent.parent.parent / "own-projects-readiness-2026-10-05/workload.json"
            workload["followUpOfWorkloadSha256"] = hashlib.sha256(previous.read_bytes()).hexdigest()
            workload["selection"] = (
                "Targeted SDK follow-up for the two Atlas tasks that failed setup in the "
                "eight-task readiness repeat. Same source revision, commands, cohort, "
                "oracles and 900-second budget. The preceding 6/8 result stays unchanged; "
                "this two-task packet is scored separately, not a replacement denominator."
            )
            workload["sdkSelectionScope"] = (
                "zig-child-only" if study == "atlas-sdk-scoped" else "all-build-tools"
            )
            if study == "atlas-sdk-scoped":
                failed = previous.parent.parent / "own-projects-atlas-sdk-2026-10-05/workload.json"
                workload["priorSdkAttemptWorkloadSha256"] = hashlib.sha256(
                    failed.read_bytes()
                ).hexdigest()
        if study == "contextual-campaign":
            workload["selectionBeforeCoverageInspection"] = False
            workload["selectionFrozenBeforeExecution"] = True
            workload["selection"] = (
                "Known-coverage contextual follow-up on the same eight commands and oracles. "
                "Merged RamenOS main and Atlas's merged full-cohort prerequisite documentation. "
                "Physical component paths replace historical human labels. Atlas SDK selection "
                "belongs to preparationEnvironment, never to the profile instruction. "
                "RamenOS's aggregate host wrappers remain source fallback cases; no single "
                "component context is asserted for their multi-component execution. "
                "This source-inspected operator campaign is not held out or independent adoption."
            )
            workload["sdkSelectionScope"] = "zig-child-only"
        write(path, workload)


def execute(command, cwd, env, timeout=TIMEOUT):
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(
            shlex.split(command),
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        error = None
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            error = f"command exceeded frozen {timeout}-second limit"
        stdout.seek(0)
        stderr.seek(0)
        return {
            "command": command,
            "exitCode": process.returncode,
            "stdout": stdout.read().decode(errors="replace"),
            "stderr": stderr.read().decode(errors="replace"),
            "executionError": error,
        }


def oracle(name, root, result):
    if result["exitCode"] != 0 or result["executionError"]:
        return False
    stdout, stderr = result["stdout"], result["stderr"]
    if name == "host-proof":
        report = json.loads((root / "out/agent-task-proof-rt/report.json").read_bytes())
        return (
            report["validation"]["outcome"] == "valid"
            and report["candidate"]["content_id"] == report["accepted"]["content_id"]
            and report["denied_operation"]["status"] == 1
            and report["denied_operation"]["mapping_cap"] == 0
            and report["receipt_replay_checked"] is True
        )
    if name == "host-build":
        return (root / "target/debug/store_cli").is_file() and "CODEGEN: ok" in stdout
    if name == "core-build":
        return (root / "target/debug/ries-rs").is_file()
    if name in {"core-test", "generator-test"}:
        return bool(re.search(r"test result: ok\. [1-9][0-9]* passed", stdout))
    if name == "consumer-test":
        return bool(re.search(r"Ran [1-9][0-9]* tests?", stderr)) and "\nOK" in stderr
    if name == "build":
        return len(re.findall(r"^\[ok\]", stdout, re.M)) == 19
    if name == "correctness":
        report = json.loads(stdout)
        return report["passed"] is True and len(report["implementations"]) == 19
    raise ValueError("unknown frozen oracle")


def validate_fixed_tasks(workload):
    revisions, cases = study_inputs(workload.get("study", "initial"))
    if len(workload["tasks"]) != len(cases):
        raise ValueError("workload differs from fixed source tasks")
    for task, case in zip(workload["tasks"], cases, strict=True):
        repo, name, command, cwd, component, source, prerequisites, setup = case
        if workload.get("study") == "contextual-campaign" and (
            task.get("preparationEnvironment")
            != preparation_environment("contextual-campaign", repo)
            or task.get("instructionRequest")
            != {
                "scope": "component" if component else "repository",
                "component": component,
                "workingDirectory": cwd,
            }
        ):
            raise ValueError("workload differs from frozen preparation or task request")
        plans = task["acceptableInstructions"]
        if (
            task["id"] != f"{repo}-{name}"
            or task["identity"] != f"github.com/maxwellsantoro/{repo}"
            or task["revision"] != revisions[repo]
            or task["setupCommands"] != setup
            or task["oracle"] != name
            or task["timeoutSecondsPerCommand"]
            != (TIMEOUT if workload.get("study", "initial") == "initial" else 900)
            or len(plans) != 1
            or plans[0]
            != {
                "command": command,
                "workingDirectory": cwd,
                "scope": "component" if component else "repository",
                "component": component,
                "prerequisites": prerequisites,
                "parameters": {},
                "environment": study_environment(workload.get("study", "initial")),
                "sourcePaths": [source],
                "purpose": "build" if name.endswith("build") else "test",
            }
        ):
            raise ValueError("workload differs from fixed source tasks")


def run(output, sources):
    if (output / "observations.json").exists() or (output / "attempts").exists():
        raise ValueError("observations are immutable; use a new frozen packet")
    raw = (output / "workload.json").read_bytes()
    workload = json.loads(raw)
    validate_fixed_tasks(workload)
    validate_selection(workload)
    validate_execution_sources(workload, output)
    validate_runtime(workload)
    if workload["runnerSha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("runner changed after freeze; freeze a new packet")
    if (
        workload.get("study", "initial") != "initial"
        and workload["toolVersions"] != tool_versions()
    ):
        raise ValueError("tool versions changed after freeze")
    if uses_sdk(workload.get("study", "")) and workload["sdkSource"] != sdk_source():
        raise ValueError("SDK inputs changed after freeze")
    (output / "attempts").mkdir()
    (output / "http").mkdir()
    write(
        output / "environment.json",
        {
            "platform": platform.platform(),
            "python": sys.version,
            "runtimeVersions": runtime_versions(),
            "runnerRevision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cache": "Existing shared download caches; fresh project targets and venvs. Alternate order does not remove download-cache carryover.",
            "pythonLaunch": "Upstream python/python3 names use uv with the project's .venv interpreter when available, otherwise the runner interpreter. Source files unchanged.",
            "toolVersions": workload.get("toolVersions"),
            "sdkSource": workload.get("sdkSource"),
            "sdkSelectionScope": workload.get("sdkSelectionScope"),
            "transport": "Only explicit source/profile HTTP is counted; package-manager traffic is uninstrumented. Bootstrap metadata/source clones excluded and disclosed.",
            "modelUsage": "No model calls in runner. Operator preparation and this coding session are unallocated; totals remain unknown.",
        },
    )
    runs = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-own-project-runs-") as temporary:
        temporary = Path(temporary)
        shims = temporary / "uv-shims"
        shims.mkdir()
        for name in ("python", "python3"):
            shim = shims / name
            shim.write_text(python_shim())
            shim.chmod(0o755)
        if uses_sdk(workload.get("study", "")):
            selector_directory = shims
            if workload["study"] in {"atlas-sdk-scoped", "contextual-campaign"}:
                selector_directory = temporary / "zig-sdk-selector"
                selector_directory.mkdir()
                shim = shims / "zig"
                shim.write_text(zig_shim(shutil.which("zig"), selector_directory))
                shim.chmod(0o755)
            shim = selector_directory / "xcrun"
            shim.write_text(sdk_shim())
            shim.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = str(shims) + os.pathsep + env["PATH"]
        # Ambient build/venv overrides must not share project outputs between arms.
        for key in (
            "CARGO_TARGET_DIR",
            "VIRTUAL_ENV",
            "UV_PROJECT_ENVIRONMENT",
            "RAMEN_TASK_EVIDENCE_DIR",
            "DOTREPO_STUDY_ZIG_SDK",
        ):
            env.pop(key, None)
        for index, task in enumerate(workload["tasks"]):
            repo = task["identity"].split("/")[-1]
            gold = task["acceptableInstructions"][0]
            for arm in ARMS if index % 2 == 0 else reversed(ARMS):
                started, timer = now(), time.perf_counter()
                transport = {"httpRequests": 0, "decodedBytes": 0, "cacheHits": 0}

                def request(url, suffix):
                    transport["httpRequests"] += 1
                    status, body = fetch(url)
                    transport["decodedBytes"] += len(body)
                    filename = f"{task['id']}-{arm}-{suffix}"
                    (output / "http" / filename).write_bytes(body)
                    write(
                        output / "http" / (filename + ".receipt.json"),
                        {
                            "url": url,
                            "status": status,
                            "sha256": hashlib.sha256(body).hexdigest(),
                        },
                    )
                    return status, body

                lookup, selected = None, None
                if arm == "lookup-first":
                    url = f"https://dotrepo.org/v0/snapshots/{workload['snapshotId']}/repos/{task['identity']}/profile.json"
                    status, body = request(url, "profile")
                    result = consumer.interpret_http_response(
                        identity=task["identity"], status_code=status, body=body
                    )
                    selection = consumer.select_instruction(
                        result, gold["purpose"], request=task.get("instructionRequest")
                    )
                    selected = selection["instruction"]
                    execution = (result.profile or {}).get("execution", {})
                    value_present = isinstance(execution, dict) and bool(
                        execution.get(gold["purpose"])
                        or execution.get(gold["purpose"] + "Candidates")
                    )
                    lookup = {
                        "snapshotId": workload["snapshotId"],
                        "policy": workload["consumerPolicy"],
                        "valuePresent": value_present,
                        "accepted": selected is not None,
                        "instruction": selected,
                        "provenance": selection["provenance"],
                        "fallbackReasons": selection["fallbackReasons"],
                    }
                attempts = []
                selected, mismatch = screen_instruction_for_task(selected, gold)
                if mismatch:
                    attempts.append(mismatch)
                if selected is None:
                    source = gold["sourcePaths"][0]
                    url = f"https://raw.githubusercontent.com/maxwellsantoro/{repo}/{task['revision']}/{source}"
                    status, body = request(url, "source")
                    if (
                        status != 200
                        or hashlib.sha256(body).hexdigest() != task["evidence"][0]["sha256"]
                    ):
                        raise ValueError("upstream response differs from frozen source")
                root = temporary / f"{task['id']}-{arm}"
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "--quiet",
                        "--shared",
                        "--no-hardlinks",
                        str(sources / repo),
                        str(root),
                    ],
                    check=True,
                    env=env,
                )
                subprocess.run(
                    ["git", "checkout", "--quiet", task["revision"]], cwd=root, check=True, env=env
                )
                commands = []
                env["DOTREPO_STUDY_PROJECT_PYTHON"] = str(root / ".venv/bin/python")
                task_env = {**env, **gold["environment"], **task.get("preparationEnvironment", {})}
                try:
                    plan = selected if selected is not None else gold
                    commands, passed = execute_instruction(
                        plan,
                        task["setupCommands"],
                        root,
                        task_env,
                        task["timeoutSecondsPerCommand"],
                        task["oracle"],
                    )
                    attempt = {
                        "origin": "profile"
                        if selected
                        else "source"
                        if arm == "source-first"
                        else "fallback",
                        "instruction": plan,
                        "exitCode": commands[-1]["exitCode"],
                        "oraclePassed": passed,
                    }
                    if commands[-1]["executionError"]:
                        attempt["executionError"] = commands[-1]["executionError"]
                except (OSError, ValueError, KeyError) as exc:
                    attempt = {
                        "origin": "fallback" if arm == "lookup-first" else "source",
                        "instruction": gold,
                        "exitCode": None,
                        "oraclePassed": False,
                        "executionError": str(exc),
                    }
                attempts.append(attempt)
                for number, attempt in enumerate(attempts):
                    path = output / "attempts" / f"{task['id']}-{arm}-{number}.json"
                    write(
                        path,
                        {
                            "taskId": task["id"],
                            **attempt,
                            "commands": commands if number == len(attempts) - 1 else [],
                        },
                    )
                    attempt["log"] = {
                        "path": str(path.relative_to(output)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                ended = now()
                runs.append(
                    {
                        "taskId": task["id"],
                        "arm": arm,
                        "revision": task["revision"],
                        "environmentId": task["environmentId"],
                        "cacheState": workload["cacheState"],
                        "startedAt": started,
                        "endedAt": ended,
                        "elapsedMs": (time.perf_counter() - timer) * 1000,
                        "transport": transport,
                        "modelUsage": {"inputTokens": None, "outputTokens": None, "cost": None},
                        "allocatedMaintenanceCost": None,
                        "lookup": lookup,
                        "attempts": attempts,
                    }
                )
                print(f"{task['id']} {arm}: completed={attempts[-1]['oraclePassed']}", flush=True)
                write(output / "progress.json", runs)
    write(
        output / "observations.json",
        {"version": 1, "workloadSha256": hashlib.sha256(raw).hexdigest(), "runs": runs},
    )
    report = score(output / "workload.json", output / "observations.json")
    write(output / "results.json", report)
    (output / "report.md").write_text(markdown(report))
    (output / "progress.json").unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "run"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--meta", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument(
        "--study",
        choices=(
            "initial",
            "readiness-repeat",
            "atlas-sdk-followup",
            "atlas-sdk-scoped",
            "contextual-campaign",
        ),
        default="initial",
    )
    args = parser.parse_args()
    if args.mode == "freeze":
        freeze(args.out, args.sources, args.meta, args.inventory, args.study)
    else:
        run(args.out, args.sources)


if __name__ == "__main__":
    main()
