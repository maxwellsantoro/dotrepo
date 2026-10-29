"""One authorized source-free owned interpreter probe, never dependency setup."""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tarfile
import time
from types import SimpleNamespace
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PARENT = Path("/tmp/dotrepo-f05-python01-environment-plan-20261029")
BASE = Path("/Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head")
IMAGE = "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
PY_SHA = "304aa87a76ebb13fd22d253ac157f14980ff2cdb23e6274f3b045571405e07dc"
UV_SHA = "5bafa105c458ae95676218df743de5cd193376f9f231b06ee5f38d6e7dcfb450"
TEXT_LIMIT = 2097152


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(path):
    path = Path(path)
    require(stat.S_ISREG(path.lstat().st_mode), "not regular binding")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def load(raw):
    def pairs(rows):
        value = {}
        for k, v in rows:
            require(k not in value, "duplicate JSON key")
            value[k] = v
        return value

    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda _: require(False, "nonfinite JSON"),
    )


def check_freeze(root, digest):
    require(sha(root / "FREEZE.json") == digest, "freeze identity")
    freeze = load((root / "FREEZE.json").read_bytes())
    for name, b in freeze["artifacts"].items():
        path = root / name
        require(path.is_relative_to(root) and ".." not in Path(name).parts, "freeze path")
        require(
            sha(path) == b["sha256"] and path.stat().st_size == b["bytes"],
            "changed frozen artifact",
        )
    return freeze


def load_plan():
    p = load((HERE / "plan.json").read_bytes())
    check_freeze(PARENT, p["parentFreezeSha256"])
    require(sha(PARENT / "plan.json") == p["parentPlanSha256"], "parent plan")
    parent = load((PARENT / "plan.json").read_bytes())
    require(
        sha(Path(p["environmentPlanReview"]["path"])) == p["environmentPlanReview"]["sha256"],
        "environment plan review binding",
    )
    require(p["probe"] == parent["probe"] and p["imageId"] == IMAGE, "probe/image drift")
    require(p["executionAuthorized"] is False, "plan not authorization")
    for name, digest in p["scripts"].items():
        require(sha(HERE / name) == digest, "driver source binding")
    for path, digest in p["reusedSources"].items():
        require(sha(Path(path)) == digest, "reused source binding")
    require(sha(PARENT / "probe.py") == p["probe"]["sourceSha256"], "probe source binding")
    return p


def isolation(plan):
    def extract(path, names, namespace):
        tree = ast.parse(Path(path).read_bytes())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        require(len(nodes) == len(names), "missing isolation functions")
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        return SimpleNamespace(**{n: namespace[n] for n in names})

    first = extract(
        BASE / "f05-go01-dependency-preparation-20261029/prepare.py", {"flags"}, {"IMAGE": IMAGE}
    )
    second = extract(
        BASE / "f05-go01-offline-setup-plan-20261029/amendment-1/setup.py",
        {"flags", "inspect"},
        {"prior": first, "IMAGE": IMAGE, "require": require},
    )
    return extract(
        BASE / "f05-go01-collection-driver-20261029/amendment-3/collection.py",
        {"flags", "inspect"},
        {"boundary": second, "require": require},
    )


def authorize(plan, path, output, scratch):
    auth = load(Path(path).read_bytes())
    require(
        auth.get("state") == "coordinator-authorized-single-python01-source-free-probe"
        and auth.get("synthetic") is False,
        "authorization state",
    )
    require(
        auth.get("planSha256") == sha(HERE / "plan.json")
        and auth.get("authorFreezeSha256") == sha(HERE / "FREEZE.json"),
        "authorization subject",
    )
    freeze = check_freeze(HERE, auth["authorFreezeSha256"])
    require(
        set(plan["scripts"]) | {"plan.json"} <= set(freeze["artifacts"]),
        "incomplete author closure",
    )
    require(
        auth.get("output") == str(output) and auth.get("scratch") == str(scratch),
        "authorization canonical paths",
    )
    require(type(auth.get("maxAttempts")) is int and auth["maxAttempts"] == 1, "attempt budget")
    require(
        auth.get("commands") == plan["probe"]["commands"] and auth.get("limits") == plan["limits"],
        "authorization bounds",
    )
    review = auth["review"]
    require(sha(Path(review["path"])) == review["sha256"], "review hash")
    r = load(Path(review["path"]).read_bytes())
    require(
        r.get("subject")
        == {
            "planSha256": sha(HERE / "plan.json"),
            "authorFreezeSha256": sha(HERE / "FREEZE.json"),
            "packetIdentity": plan["identity"],
        }
        and r.get("state") == "independent-python01-source-free-probe-driver-review-passed"
        and r.get("scope") == "owned-source-free-python-probe-only"
        and r.get("synthetic") is False
        and r.get("findings") == []
        and r.get("staticOnly") is True,
        "review subject/state",
    )
    return {"path": str(Path(path).resolve()), "sha256": sha(path), "synthetic": False}


def owned_tar(plan):
    raw = (PARENT / "probe.py").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == plan["probe"]["sourceSha256"], "probe bytes")
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        info = tarfile.TarInfo("probe.py")
        info.size = len(raw)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def check_owned(raw, plan):
    require(len(raw) <= TEXT_LIMIT, "probe archive cap")
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        members = archive.getmembers()
        require(len(members) == 2, "unexpected owned directory entries")
        require(members[0].name == "." and members[0].isdir(), "probe directory row")
        file = members[1]
        require(
            file.name == "./probe.py" and file.isfile() and file.mode & 0o777 == 0o644,
            "probe file/type/mode",
        )
        body = archive.extractfile(file).read()
        require(hashlib.sha256(body).hexdigest() == plan["probe"]["sourceSha256"], "probe changed")
    return {"probeSha256": plan["probe"]["sourceSha256"], "entries": 2}


def check_probe(raw):
    require(len(raw) <= 16384, "probe metadata cap")
    v = load(raw)
    keys = {
        "schema",
        "version",
        "versionText",
        "executable",
        "executableSha256",
        "baseExecutable",
        "prefix",
        "basePrefix",
        "platform",
        "platformTag",
        "soabi",
        "openssl",
        "isolated",
        "noSite",
        "sysPath",
        "configurationEnvironment",
        "targetImportsPerformed",
    }
    require(
        isinstance(v, dict)
        and set(v) == keys
        and v["schema"] == "owned-python-interpreter-probe-v1",
        "probe schema",
    )
    require(
        isinstance(v["version"], list)
        and len(v["version"]) == 5
        and all(type(x) is int for x in [*v["version"][:3], v["version"][4]])
        and v["version"][:2] == [3, 11]
        and v["version"][3] == "final",
        "interpreter version",
    )
    require(
        v["executable"] == "/usr/bin/python3.11"
        and v["executableSha256"] == PY_SHA
        and v["baseExecutable"] == "/usr/bin/python3.11",
        "interpreter identity",
    )
    require(
        v["platform"] == "linux"
        and v["platformTag"] == "linux-aarch64"
        and isinstance(v["soabi"], str)
        and v["soabi"].startswith("cpython-311-"),
        "platform ABI",
    )
    require(
        type(v["isolated"]) is int
        and v["isolated"] == 1
        and type(v["noSite"]) is int
        and v["noSite"] == 1,
        "isolated probe",
    )
    require(
        isinstance(v["sysPath"], list)
        and v["sysPath"]
        and all(
            isinstance(p, str) and p.startswith("/usr/") and ".." not in Path(p).parts
            for p in v["sysPath"]
        ),
        "unexpected import roots",
    )
    require(
        v["configurationEnvironment"]
        == dict.fromkeys(["PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PYTHON"])
        and v["targetImportsPerformed"] is False,
        "unexpected Python configuration",
    )
    require(
        all(
            isinstance(v[k], str) and len(v[k]) < 4096
            for k in ["versionText", "prefix", "basePrefix", "openssl"]
        ),
        "metadata strings",
    )
    return v


def raw_streams(output, label, receipt):
    result = {}
    for role in ["stdout", "stderr"]:
        p = output / "logs" / label / (role + ".bin")
        require(stat.S_ISREG(p.lstat().st_mode), "nonregular raw trace")
        require(p.stat().st_size <= TEXT_LIMIT, "raw cap")
        raw = p.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == receipt[role + "Sha256"], "raw binding")
        result[role] = raw
    require(sum(map(len, result.values())) <= TEXT_LIMIT, "combined raw cap")
    return result


def backend_module():
    for name in ["boundaries", "process_io"]:
        spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
        value = importlib.util.module_from_spec(spec)
        sys.modules[name] = value
        spec.loader.exec_module(value)
    return value


def run(
    auth,
    output,
    scratch,
    *,
    backend=None,
    clock=time.monotonic,
    plan_loader=load_plan,
    authorization_check=authorize,
):
    output, scratch = Path(output).resolve(), Path(scratch).resolve()
    output.mkdir()  # Existing output is a refusal, never overwritten.
    start = clock()
    # Entire source-free probe stage (including observations) fits its 60s
    # allowance; this is also charged to, and below, the shared 900s work cap.
    deadline = min(start + 900, start + 60)
    r = {
        "state": "incomplete",
        "synthetic": backend is not None,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "daemonCalls": 0,
        "containerCreateAttempted": False,
        "containerAbsent": None,
        "probeAttempted": False,
        "ownedProbeObserved": False,
        "actualAdmission": False,
        "nativeCollectionOccurred": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
        "costUsd": None,
    }
    write(output / "attempt.json", r)
    name = "dotrepo-python-probe-" + uuid.uuid4().hex[:12]
    created = False
    r["ownedContainer"] = name

    def call(label, argv, *, stdin_path=None, call_deadline=None, exits=(0,)):
        require(clock() < deadline, "shared work deadline")
        r["stage"] = label
        r["daemonCalls"] += 1
        receipt = backend.command(
            output,
            label,
            argv,
            deadline=min(deadline, call_deadline or deadline),
            stdin_path=stdin_path,
        )
        require(receipt["argv"] == argv, "receipt argv mismatch")
        raw = raw_streams(output, label, receipt)
        if receipt.get("cancelled"):
            raise KeyboardInterrupt(receipt.get("error"))
        require(
            not receipt.get("error") and receipt["exitCode"] in exits, "command failed: " + label
        )
        require(
            receipt["stdinBytes"] == (stdin_path.stat().st_size if stdin_path else 0), "stdin bytes"
        )
        if stdin_path:
            require(receipt["stdinSha256"] == sha(stdin_path), "stdin hash")
        return receipt, raw

    def shell(label, text):
        return call(label, ["docker", "exec", name, "/bin/sh", "-eu", "-c", text])

    try:
        plan = plan_loader()
        r["authorization"] = authorization_check(plan, auth, output, scratch)
        require(
            not scratch.exists()
            and not scratch.is_relative_to(output)
            and not output.is_relative_to(scratch),
            "scratch exists/aliases output",
        )
        require(
            all(
                not p.is_relative_to(base)
                for p in [output, scratch]
                for base in [HERE, PARENT, BASE]
            ),
            "protected output alias",
        )
        scratch.mkdir()
        isolate = isolation(plan)
        backend = backend or backend_module().DockerBackend()
        payload = scratch / "probe.tar"
        payload.write_bytes(owned_tar(plan))
        r["provisionTarSha256"] = sha(payload)
        r["provisionTarBytes"] = payload.stat().st_size
        _, raw = call("image-inspect", ["docker", "image", "inspect", IMAGE])
        image = load(raw["stdout"])[0]
        require(
            image["Id"] == IMAGE
            and image["Os"] == "linux"
            and image["Architecture"] == "arm64"
            and not image["Config"].get("Volumes")
            and not image["Config"].get("OnBuild"),
            "image identity/side effects",
        )
        require(image["Config"]["Env"] == plan["imageEnvironment"], "image environment drift")
        env = {
            **dict(v.split("=", 1) for v in image["Config"]["Env"]),
            **plan["probe"]["environment"],
        }
        created = True
        r["containerCreateAttempted"] = True
        _, raw = call("create", isolate.flags(name, plan["probe"]["environment"]))
        cid = raw["stdout"].decode("ascii").strip()
        require(len(cid) == 64 and all(c in "0123456789abcdef" for c in cid), "container ID")
        call("start", ["docker", "start", name])

        def inspect(label):
            _, raw = call(label, ["docker", "inspect", name])
            row = load(raw["stdout"])[0]
            require(row["Id"] == cid and row["Name"] == "/" + name, "container identity")
            isolate.inspect(row, env)

        inspect("inspect-before")
        shell(
            "initialize",
            "test ! -e /workspace/owned-probe; test ! -e /workspace/home; test ! -e /workspace/tmp; mkdir /workspace/owned-probe /workspace/home /workspace/tmp",
        )
        call(
            "provision",
            [
                "docker",
                "exec",
                "-i",
                name,
                "tar",
                "--extract",
                "--no-same-owner",
                "-C",
                "/workspace/owned-probe",
            ],
            stdin_path=payload,
        )
        tools = (PY_SHA + "  /usr/bin/python3.11\n" + UV_SHA + "  /usr/local/bin/uv\n").encode()
        for phase in ["before", "after"]:
            _, raw = shell("tools-" + phase, "sha256sum /usr/bin/python3.11 /usr/local/bin/uv")
            require(raw["stdout"] == tools and raw["stderr"] == b"", "tool identity")
            _, raw = shell(
                "source-" + phase, "tar --create --format=ustar -C /workspace/owned-probe ."
            )
            write(output / ("source-" + phase + ".json"), check_owned(raw["stdout"], plan))
            if phase == "after":
                break
            probe_deadline = min(deadline, clock() + 60)
            _, raw = call(
                "uv-version",
                [
                    "docker",
                    "exec",
                    "--workdir",
                    "/workspace/owned-probe",
                    name,
                    *plan["probe"]["commands"][0],
                ],
                call_deadline=probe_deadline,
            )
            require(
                raw["stdout"] == b"uv 0.13.6 (aarch64-unknown-linux-musl)\n"
                and raw["stderr"] == b"",
                "uv version",
            )
            r["probeAttempted"] = True
            _, raw = call(
                "owned-probe",
                [
                    "docker",
                    "exec",
                    "--workdir",
                    "/workspace/owned-probe",
                    name,
                    *plan["probe"]["commands"][1],
                ],
                call_deadline=probe_deadline,
            )
            r["probeStderrBytes"] = len(raw["stderr"])
            r["probeStderrSha256"] = hashlib.sha256(raw["stderr"]).hexdigest()
            write(output / "probe-observation.json", check_probe(raw["stdout"]))
            r["ownedProbeObserved"] = True
        inspect("inspect-after")
        require(sha(PARENT / "probe.py") == plan["probe"]["sourceSha256"], "host probe changed")
        require(clock() < deadline, "work deadline after observations")
        r.update(
            state="owned-source-free-python-probe-observed", sourceToolsBeforeAfterMatched=True
        )
    except BaseException as exc:
        r.update(
            error=f"{type(exc).__name__}: {exc}",
            cancelled=isinstance(exc, (KeyboardInterrupt, SystemExit)),
        )
    finally:
        if created:
            cleanup_start = clock()
            cleanup_deadline = cleanup_start + 60
            clean = {}
            for label, argv in [
                ("cleanup", ["docker", "rm", "-f", name]),
                ("post-cleanup-inspect", ["docker", "inspect", name]),
                (
                    "post-cleanup-list",
                    ["docker", "ps", "-a", "--filter", "name=" + name, "--format", "{{.Names}}"],
                ),
            ]:
                try:
                    r["daemonCalls"] += 1
                    receipt = backend.command(output, label, argv, deadline=cleanup_deadline)
                    clean[label] = {"receipt": receipt, "raw": raw_streams(output, label, receipt)}
                except BaseException as exc:
                    clean[label] = {"error": f"{type(exc).__name__}: {exc}"}
            rm, ins, ls = [
                clean.get(n, {}) for n in ["cleanup", "post-cleanup-inspect", "post-cleanup-list"]
            ]
            r["containerAbsent"] = bool(
                rm.get("receipt", {}).get("exitCode") == 0
                and not rm.get("receipt", {}).get("error")
                and ins.get("receipt", {}).get("exitCode") == 1
                and not ins.get("receipt", {}).get("error")
                and ins.get("raw", {}).get("stdout", b"x").strip() == b"[]"
                and b"no such object" in ins.get("raw", {}).get("stderr", b"").lower()
                and ls.get("receipt", {}).get("exitCode") == 0
                and not ls.get("receipt", {}).get("error")
                and not ls.get("raw", {}).get("stdout", b"x").strip()
            )
            r["cleanupSeconds"] = clock() - cleanup_start
            if not r["containerAbsent"]:
                r.update(state="incomplete", cleanupUnresolved=True)
        r["elapsedSeconds"] = clock() - start
        r["workBudgetExceeded"] = r["elapsedSeconds"] - r.get("cleanupSeconds", 0) > 900
        r["probeBudgetExceeded"] = r["elapsedSeconds"] - r.get("cleanupSeconds", 0) > 60
        if r["workBudgetExceeded"] or r["probeBudgetExceeded"]:
            r["state"] = "incomplete"
        write(
            output / "trace.json",
            {
                "receipts": {
                    str(p.relative_to(output)): load(p.read_bytes())
                    for p in sorted((output / "logs").glob("*/receipt.json"))
                },
                "synthetic": r["synthetic"],
            },
        )
        write(output / "result.json", r)
    return r


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args()
    if args.authorization:
        require(args.output is not None and args.scratch is not None, "output/scratch required")
        result = run(args.authorization, args.output, args.scratch)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["state"] == "owned-source-free-python-probe-observed" else 1)
    print(json.dumps({"state": "not-authorized", "plan": load_plan()}, indent=2))
