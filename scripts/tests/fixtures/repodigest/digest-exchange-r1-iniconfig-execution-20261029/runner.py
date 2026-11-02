"""Host orchestrator: bounded containers, retained failures, inspected teardown."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import uuid
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

PACKET = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def docker(*args, timeout=15, input=None, check=True):
    return subprocess.run(
        ["docker", *args],
        input=input,
        capture_output=True,
        timeout=timeout,
        check=check,
    )


def create(image, *, network="bridge"):
    args = [
        "create",
        "--pull=never",
        "--name",
        "digest-exchange-iniconfig-" + uuid.uuid4().hex[:12],
        "--label",
        "digest-exchange.experiment=" + PACKET.name,
        "--network",
        network,
        "--cpus",
        "1",
        "--memory",
        "768m",
        "--memory-swap",
        "768m",
        "--pids-limit",
        "64",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "1000:1000",
        "--tmpfs",
        "/work:rw,exec,nosuid,size=384m,uid=1000,gid=1000,mode=0700",
        "--tmpfs",
        "/tmp:rw,nosuid,noexec,size=64m,uid=1000,gid=1000,mode=0700",
        "--log-driver",
        "none",
        image,
    ]
    identity = docker(*args).stdout.decode().strip()
    if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("invalid created-container identity")
    docker("start", identity)
    return identity


def inspect(identity):
    return json.loads(docker("inspect", identity).stdout)[0]


def terminate(identity):
    if inspect(identity)["State"]["Running"]:
        docker("kill", identity)
    state = inspect(identity)["State"]
    if state["Running"] or state.get("Restarting"):
        raise RuntimeError("container termination was not established")
    docker("rm", identity)
    return {"containerId": identity, "terminalState": state, "removed": True}


def validate_limits(info):
    host = info["HostConfig"]
    if any(mount.get("Type") == "bind" for mount in info["Mounts"]):
        raise ValueError("host bind mounts are not allowed")
    if (
        host["Memory"] != 768 * 1024 * 1024
        or host["MemorySwap"] != 768 * 1024 * 1024
        or host["NanoCpus"] != 1_000_000_000
        or host["PidsLimit"] != 64
        or not host["ReadonlyRootfs"]
        or "ALL" not in host["CapDrop"]
        or info["Config"]["User"] != "1000:1000"
        or not any("no-new-privileges" in x for x in host["SecurityOpt"])
        or host["Tmpfs"]
        != {
            "/work": "rw,exec,nosuid,size=384m,uid=1000,gid=1000,mode=0700",
            "/tmp": "rw,nosuid,noexec,size=64m,uid=1000,gid=1000,mode=0700",
        }
        or host.get("Binds")
        or host.get("PortBindings")
    ):
        raise ValueError("container resource/isolation contract mismatch")


def isolated_network(observation):
    """Fail closed on incomplete/malformed link or all-table route evidence."""
    if not isinstance(observation, dict) or observation.get("dockerNetworks") != {}:
        return False
    links = observation.get("links")
    if not isinstance(links, list) or not links:
        return False
    names = []
    for link in links:
        if not isinstance(link, dict):
            return False
        name, flags = link.get("ifname"), link.get("flags")
        if not isinstance(name, str) or not isinstance(flags, list):
            return False
        if not all(isinstance(flag, str) for flag in flags):
            return False
        names.append(name)
        if name != "lo" and "UP" in flags:
            return False
    if "lo" not in names or len(set(names)) != len(names):
        return False
    for family in ("routes4", "routes6"):
        routes = observation.get(family)
        if not isinstance(routes, list):
            return False
        if any(not isinstance(route, dict) or route.get("dev") != "lo" for route in routes):
            return False
    return True


def score(probes, xml, expected, networks=None):
    reasons = []
    if networks is None or len(networks) != 2 or not all(map(isolated_network, networks)):
        reasons.append("test-network-not-disconnected")
    if len(probes) != 2:
        reasons.append("missing-before-or-after-provenance")
    for probe in probes:
        if probe["prefix"] != "/work/checkout/.venv" or not probe["pythonExecutable"].startswith(
            "/work/checkout/.venv/bin/python"
        ):
            reasons.append("unexpected-project-interpreter")
        installed = dict(probe["installedPackages"])
        if any(installed.get(name) != version for name, version in expected["lockedTools"].items()):
            reasons.append("locked-tool-version-mismatch")
        if (
            probe["system"] != "Linux"
            or probe["pythonVersion"] != expected["pythonVersion"]
            or probe["architecture"] != expected["architecture"]
        ):
            reasons.append("wrong-platform-or-interpreter")
        if probe["gitHead"] != expected["revision"] or probe["gitTree"] != expected["tree"]:
            reasons.append("wrong-git-identity")
        if probe["trackedSha256"] != expected["files"] or not probe["trackedBytesUnchanged"]:
            reasons.append("source-bytes-changed")
        if probe["packagePath"] != "/work/checkout/src/iniconfig/__init__.py":
            reasons.append("wrong-imported-package")
        if probe["packageSha256"] != expected["files"]["src/iniconfig/__init__.py"]:
            reasons.append("wrong-imported-package-bytes")
        direct = probe.get("directUrl") or {}
        if (
            direct.get("url") != "file:///work/checkout"
            or direct.get("dir_info", {}).get("editable") is not True
        ):
            reasons.append("local-editable-distribution-unestablished")
        if any(
            probe.get(key) != expected[key]
            for key in ("pythonBinarySha256", "packageVersion", "gitDescribe")
        ):
            reasons.append("interpreter-or-build-version-mismatch")
        if probe["gitTrackedStatus"]:
            reasons.append("tracked-checkout-dirty")
    root = ET.fromstring(xml)
    cases = root.findall(".//testcase")
    names = {case.get("name", "").split("[", 1)[0] for case in cases}
    if Counter(case.get("name") for case in cases) != Counter(expected["testCases"]):
        reasons.append("incomplete-test-collection")
    if any(root.findall(".//" + tag) for tag in ("failure", "error", "skipped")):
        reasons.append("test-failure-error-or-skip")
    if any(
        int(suite.get(field, "0"))
        for suite in root.iter()
        for field in ("failures", "errors", "skipped")
    ):
        reasons.append("test-failure-error-or-skip")
    if any(case.get("classname") != "testing.test_iniconfig" for case in cases):
        reasons.append("wrong-test-source")
    return {
        "pass": not reasons,
        "reasons": sorted(set(reasons)),
        "testCases": len(cases),
        "testDefinitions": len(names),
    }


def timeout_control(image):
    identity = create(image, network="none")
    result = {"expectedTimeout": False}
    process = subprocess.Popen(
        ["docker", "exec", identity, "/bin/sh", "-c", "sleep 300 & echo child=$!; wait"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        result["expectedTimeout"] = True
        listing = docker("top", identity, "-eo", "pid,args").stdout.decode()
        result["processesBeforeTermination"] = listing
        result["childObserved"] = any(
            line.rstrip().endswith("sleep 300") for line in listing.splitlines()
        )
    finally:
        result["teardown"] = terminate(identity)
        process.communicate(timeout=5)
    result["pass"] = (
        result["expectedTimeout"]
        and result.get("childObserved", False)
        and not result["teardown"]["terminalState"]["Running"]
    )
    return result


def run(output):
    if output.exists():
        raise FileExistsError("use a new output directory")
    spec_raw = (PACKET / "SPEC.json").read_bytes()
    if sha(spec_raw) != (PACKET / "SPEC.sha256").read_text().split()[0]:
        raise ValueError("frozen execution specification changed")
    inputs = json.loads((PACKET / "INPUTS.json").read_text())
    if inputs.get("activeAmendment"):
        if sha((PACKET / inputs["activeAmendment"]).read_bytes()) != inputs["amendmentSha256"]:
            raise ValueError("frozen replay amendment changed")
    archive = (PACKET / "source-checkout.tar.gz").read_bytes()
    if sha(archive) != inputs["sourceArchiveSha256"]:
        raise ValueError("frozen source archive changed")
    for name, expected in inputs["codeSha256"].items():
        if sha((PACKET / name).read_bytes()) != expected:
            raise ValueError("frozen runner changed: " + name)
    output.mkdir(parents=True)
    (output / "input-receipt.json").write_text(json.dumps(inputs, indent=2) + "\n")
    image, expected = inputs["imageReference"], inputs["expected"]
    started = time.monotonic()
    control = timeout_control(image)
    (output / "timeout-control.json").write_text(json.dumps(control, indent=2) + "\n")
    if not control["pass"]:
        raise RuntimeError("actual container timeout control failed")
    rows = []
    for repeat in range(2):
        if time.monotonic() - started > 600:
            break
        directory = output / f"run-{repeat + 1:03}"
        directory.mkdir()
        identity = create(image)
        row = {"repeat": repeat, "containerId": identity, "pass": False, "failure": None}
        try:
            before = inspect(identity)
            validate_limits(before)
            (directory / "container-before.json").write_text(json.dumps(before, indent=2) + "\n")
            docker(
                "exec",
                "-i",
                identity,
                "/bin/tar",
                "--extract",
                "--gzip",
                "--file=-",
                "--directory=/work",
                "--no-same-owner",
                input=archive,
            )
            setup = docker(
                "exec",
                identity,
                "uv",
                "run",
                "--no-project",
                "--offline",
                "--python",
                "/usr/local/bin/python3.12",
                "python",
                "/controller.py",
                "setup",
                timeout=190,
                check=False,
            )
            (directory / "setup-controller.stdout").write_bytes(setup.stdout)
            (directory / "setup-controller.stderr").write_bytes(setup.stderr)
            for name in ("setup.log", "setup.json"):
                (directory / name).write_bytes(
                    docker("exec", identity, "cat", "/work/" + name).stdout
                )
            if setup.returncode:
                raise RuntimeError("dependency setup failed; retain logs")
            docker("network", "disconnect", "bridge", identity)
            isolated = inspect(identity)
            if isolated["NetworkSettings"]["Networks"]:
                raise RuntimeError("network disconnection not established")
            (directory / "container-isolated.json").write_text(
                json.dumps(isolated, indent=2) + "\n"
            )

            def capture_network(boundary):
                observation = json.loads(
                    docker(
                        "exec",
                        identity,
                        "uv",
                        "run",
                        "--no-project",
                        "--offline",
                        "--python",
                        "/usr/local/bin/python3.12",
                        "python",
                        "/controller.py",
                        "network",
                    ).stdout
                )
                info = inspect(identity)
                (directory / ("container-" + boundary + ".json")).write_text(
                    json.dumps(info, indent=2) + "\n"
                )
                validate_limits(info)
                observation["dockerNetworks"] = info["NetworkSettings"]["Networks"]
                (directory / ("network-" + boundary + ".json")).write_text(
                    json.dumps(observation, indent=2) + "\n"
                )
                if not isolated_network(observation):
                    raise RuntimeError("usable test network was not excluded")
                return observation

            networks = [capture_network("before-import")]
            probe_command = [
                "exec",
                "--workdir",
                "/work/checkout",
                identity,
                "uv",
                "run",
                "--offline",
                "--no-sync",
                "--python",
                "/usr/local/bin/python3.12",
                "python",
                "/controller.py",
                "probe",
            ]
            probes = [json.loads(docker(*probe_command).stdout)]
            (directory / "probe-before.json").write_text(json.dumps(probes[0], indent=2) + "\n")
            test = docker(
                "exec",
                identity,
                "uv",
                "run",
                "--no-project",
                "--offline",
                "--python",
                "/usr/local/bin/python3.12",
                "python",
                "/controller.py",
                "test",
                timeout=70,
                check=False,
            )
            (directory / "test-controller.stdout").write_bytes(test.stdout)
            (directory / "test-controller.stderr").write_bytes(test.stderr)
            for name in ("test.log", "test.json"):
                (directory / name).write_bytes(
                    docker("exec", identity, "cat", "/work/" + name).stdout
                )
            junit = docker("exec", identity, "cat", "/work/results.xml", check=False)
            if junit.returncode == 0:
                (directory / "results.xml").write_bytes(junit.stdout)
            else:
                (directory / "junit-unavailable.stderr").write_bytes(junit.stderr)
            if test.returncode:
                raise RuntimeError("test stage failed; retain logs")
            if junit.returncode:
                raise RuntimeError("test stage produced no JUnit evidence")
            probes.append(json.loads(docker(*probe_command).stdout))
            (directory / "probe-after.json").write_text(json.dumps(probes[-1], indent=2) + "\n")
            (directory / "probes.json").write_text(json.dumps(probes, indent=2) + "\n")
            networks.append(capture_network("after-test"))
            metrics = json.loads((directory / "test.json").read_text())
            if metrics["networkInterfaceBytes"] != 0 or metrics["stopReason"] is not None:
                raise RuntimeError("test network traffic or budget violation")
            row.update(score(probes, (directory / "results.xml").read_bytes(), expected, networks))
        except (
            OSError,
            ValueError,
            RuntimeError,
            subprocess.SubprocessError,
            ET.ParseError,
        ) as exc:
            row["failure"] = type(exc).__name__ + ": " + str(exc)
            if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
                (directory / "failure.stdout").write_bytes(exc.stdout or b"")
                (directory / "failure.stderr").write_bytes(exc.stderr or b"")
        finally:
            row["teardown"] = terminate(identity)
        (directory / "result.json").write_text(json.dumps(row, indent=2) + "\n")
        rows.append(row)
    report = {
        "assignedRuns": 2,
        "completedRuns": len(rows),
        "passedRuns": sum(row["pass"] for row in rows),
        "wallSeconds": time.monotonic() - started,
        "runs": rows,
        "claim": "Observed synthesized recipe on pinned Linux arm64 environment; no public instruction qualification or task-benefit claim.",
    }
    report["outcome"] = (
        "go-for-this-recipe-only"
        if len(rows) == 2 and all(row["pass"] for row in rows) and report["wallSeconds"] <= 600
        else "no-go"
    )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["outcome"] == "go-for-this-recipe-only" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
