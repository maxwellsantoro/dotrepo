"""Read-only independent retained-result verification. No backend/probe invocation."""

from datetime import datetime
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile

HERE = Path(__file__).resolve().parent
RESULT = Path("/tmp/dotrepo-f05-python01-probe-result-20261029")
DRIVER = Path("/tmp/dotrepo-f05-python01-probe-driver-20261029")
AUTH = Path("/tmp/dotrepo-f05-python01-probe-authorization-20261029")
REVIEW = Path("/tmp/dotrepo-f05-python01-probe-driver-review-20261029")
sys.dont_write_bytecode = True


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_bytes())


def frozen(root, expected):
    assert sha(root / "FREEZE.json") == expected
    f = read(root / "FREEZE.json")
    for name, v in f["artifacts"].items():
        p = root / name
        assert p.is_file() and not p.is_symlink()
        assert p.stat().st_size == v["bytes"] and sha(p) == v["sha256"], name
    return f


def main():
    f = frozen(RESULT, "1fb5f3756be2411a9923b83113f5786f029b81a48b394bb452157c3500435edb")
    frozen(DRIVER, "9017646e52e660a22d6a3423bb1541dc3a427c5983b3407a453b30eebffffe27")
    frozen(AUTH, "3ff361e82b12771d6cab1120918227bf826fb11d53a3ab689c39cd1bd761a72c")
    frozen(REVIEW, "cc233e27ff5b12b31b0f4728ccf222df418db8a27fd518314f7828a984d20aa7")
    spec = importlib.util.spec_from_file_location("reviewed_probe_driver", DRIVER / "driver.py")
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    plan = d.load_plan()
    auth = read(AUTH / "authorization.json")
    authorization = d.authorize(
        plan, AUTH / "authorization.json", RESULT.resolve(), Path(auth["scratch"])
    )
    result = read(RESULT / "result.json")
    assert authorization == result["authorization"]
    assert f["driverFreezeSha256"] == sha(DRIVER / "FREEZE.json")
    assert f["reviewFreezeSha256"] == sha(REVIEW / "FREEZE.json")
    assert f["authorizationFreezeSha256"] == sha(AUTH / "FREEZE.json")
    assert (
        result["state"] == "owned-source-free-python-probe-observed"
        and result["synthetic"] is False
    )
    assert all(
        result[k] is False
        for k in [
            "actualAdmission",
            "nativeCollectionOccurred",
            "oracleQualified",
            "campaignAdmitted",
            "workBudgetExceeded",
            "probeBudgetExceeded",
        ]
    )
    assert result["costUsd"] is None
    trace = read(RESULT / "trace.json")
    assert trace["synthetic"] is False
    receipts = {p.parent.name: read(p) for p in (RESULT / "logs").glob("*/receipt.json")}
    assert len(receipts) == result["daemonCalls"] == 16
    rows = sorted(receipts.items(), key=lambda item: item[1]["startedAt"])
    labels = [n for n, _ in rows]
    assert labels == [
        "image-inspect",
        "create",
        "start",
        "inspect-before",
        "initialize",
        "provision",
        "tools-before",
        "source-before",
        "uv-version",
        "owned-probe",
        "tools-after",
        "source-after",
        "inspect-after",
        "cleanup",
        "post-cleanup-inspect",
        "post-cleanup-list",
    ]
    raw = {}
    totalelapsed = 0
    for name, r in rows:
        assert trace["receipts"]["logs/" + name + "/receipt.json"] == r
        assert r["error"] is None and r["cancelled"] is False
        assert r["exitCode"] == (1 if name == "post-cleanup-inspect" else 0)
        assert r["costUsd"] is None and r["costExclusions"]
        assert r["elapsedSeconds"] >= 0
        totalelapsed += r["elapsedSeconds"]
        raw[name] = {}
        for role in ["stdout", "stderr"]:
            p = RESULT / "logs" / name / (role + ".bin")
            body = p.read_bytes()
            assert sha(p) == r[role + "Sha256"]
            raw[name][role] = body
        assert sum(map(len, raw[name].values())) <= 2097152
        if name != "post-cleanup-inspect":
            assert raw[name]["stderr"] == b""
        assert r["binaryPath"] is r["binaryBytes"] is r["binarySha256"] is None
        if name != "provision":
            assert r["stdinBytes"] == 0 and r["stdinSha256"] == hashlib.sha256(b"").hexdigest()
    name = result["ownedContainer"]
    expected = {
        "image-inspect": ["docker", "image", "inspect", plan["imageId"]],
        "start": ["docker", "start", name],
        "initialize": [
            "docker",
            "exec",
            name,
            "/bin/sh",
            "-eu",
            "-c",
            "test ! -e /workspace/owned-probe; test ! -e /workspace/home; test ! -e /workspace/tmp; mkdir /workspace/owned-probe /workspace/home /workspace/tmp",
        ],
        "provision": [
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
    }
    for phase in ["before", "after"]:
        expected["inspect-" + phase] = ["docker", "inspect", name]
        expected["tools-" + phase] = [
            "docker",
            "exec",
            name,
            "/bin/sh",
            "-eu",
            "-c",
            "sha256sum /usr/bin/python3.11 /usr/local/bin/uv",
        ]
        expected["source-" + phase] = [
            "docker",
            "exec",
            name,
            "/bin/sh",
            "-eu",
            "-c",
            "tar --create --format=ustar -C /workspace/owned-probe .",
        ]
    for label, argv in expected.items():
        assert receipts[label]["argv"] == argv, label
    acceptance = read(AUTH / "acceptance.json")
    assert (
        acceptance["noDependencyInstallation"]
        and acceptance["noUpstreamSourceOrTaskExecution"]
        and acceptance["noCampaignOrOracleAdmission"]
    )
    assert (
        acceptance["output"] == str(RESULT.resolve()) and acceptance["scratch"] == auth["scratch"]
    )
    isolate = d.isolation(plan)
    assert receipts["create"]["argv"] == isolate.flags(name, plan["probe"]["environment"])
    image = json.loads(raw["image-inspect"]["stdout"])[0]
    assert (
        image["Id"] == plan["imageId"]
        and image["Os"] == "linux"
        and image["Architecture"] == "arm64"
    )
    assert image["Config"]["Env"] == plan["imageEnvironment"]
    assert not image["Config"].get("Volumes") and not image["Config"].get("OnBuild")
    env = {**dict(v.split("=", 1) for v in image["Config"]["Env"]), **plan["probe"]["environment"]}
    cid = raw["create"]["stdout"].decode().strip()
    assert len(cid) == 64
    for stage in ["inspect-before", "inspect-after"]:
        row = json.loads(raw[stage]["stdout"])[0]
        assert row["Id"] == cid and row["Name"] == "/" + name
        isolate.inspect(row, env)
        h = row["HostConfig"]
        assert h["NetworkMode"] == "none" and h["Privileged"] is False and h["CapAdd"] in (None, [])
        assert h["CapDrop"] == ["ALL"] and h["SecurityOpt"] == ["no-new-privileges"]
        assert (
            h["Memory"] == h["MemorySwap"] == 4294967296
            and h["NanoCpus"] == 3000000000
            and h["PidsLimit"] == 256
        )
        assert row["Config"]["User"] == "1000:1000" and h["ReadonlyRootfs"] is True
        assert not row["Mounts"] and not h["Binds"]
    payload = Path(auth["scratch"]) / "probe.tar"
    assert (
        payload.stat().st_size
        == receipts["provision"]["stdinBytes"]
        == result["provisionTarBytes"]
        == 10240
    )
    assert sha(payload) == receipts["provision"]["stdinSha256"] == result["provisionTarSha256"]
    assert payload.read_bytes() == d.owned_tar(plan)
    with tarfile.open(fileobj=io.BytesIO(payload.read_bytes())) as t:
        members = t.getmembers()
        assert len(members) == 1 and members[0].name == "probe.py" and members[0].isfile()
        assert (
            hashlib.sha256(t.extractfile(members[0]).read()).hexdigest()
            == plan["probe"]["sourceSha256"]
        )
    for stage in ["source-before", "source-after"]:
        assert d.check_owned(raw[stage]["stdout"], plan) == read(RESULT / (stage + ".json"))
    assert raw["source-before"]["stdout"] == raw["source-after"]["stdout"]
    tools = (d.PY_SHA + "  /usr/bin/python3.11\n" + d.UV_SHA + "  /usr/local/bin/uv\n").encode()
    assert raw["tools-before"]["stdout"] == raw["tools-after"]["stdout"] == tools
    for i, label in enumerate(["uv-version", "owned-probe"]):
        assert receipts[label]["argv"] == [
            "docker",
            "exec",
            "--workdir",
            "/workspace/owned-probe",
            name,
            *plan["probe"]["commands"][i],
        ]
    assert raw["uv-version"]["stdout"] == b"uv 0.13.6 (aarch64-unknown-linux-musl)\n"
    observed = d.check_probe(raw["owned-probe"]["stdout"])
    assert observed == read(RESULT / "probe-observation.json")
    assert observed["version"] == [3, 11, 2, "final", 0]
    assert observed["soabi"] == "cpython-311-aarch64-linux-gnu"
    assert observed["sysPath"] == [
        "/usr/lib/python311.zip",
        "/usr/lib/python3.11",
        "/usr/lib/python3.11/lib-dynload",
    ]
    assert (
        result["probeStderrBytes"] == 0
        and result["probeStderrSha256"] == hashlib.sha256(b"").hexdigest()
    )
    assert result["sourceToolsBeforeAfterMatched"] and result["ownedProbeObserved"]
    assert receipts["cleanup"]["argv"] == ["docker", "rm", "-f", name]
    assert receipts["post-cleanup-inspect"]["argv"] == ["docker", "inspect", name]
    assert raw["post-cleanup-inspect"]["stdout"].strip() == b"[]"
    assert b"no such object" in raw["post-cleanup-inspect"]["stderr"].lower()
    assert receipts["post-cleanup-list"]["argv"] == [
        "docker",
        "ps",
        "-a",
        "--filter",
        "name=" + name,
        "--format",
        "{{.Names}}",
    ]
    assert not raw["post-cleanup-list"]["stdout"].strip() and result["containerAbsent"]
    assert 0 <= totalelapsed <= result["elapsedSeconds"] < 60
    assert 0 <= result["cleanupSeconds"] < 60
    start = datetime.fromisoformat(result["startedAt"])
    assert datetime.fromisoformat(rows[0][1]["startedAt"]) >= start
    summary = {
        "state": "independent-retained-probe-result-verification-pass",
        "resultFreezeSha256": sha(RESULT / "FREEZE.json"),
        "artifacts": len(f["artifacts"]),
        "rawReceiptTriplets": len(rows),
        "labels": labels,
        "receiptElapsedSubtotalSeconds": totalelapsed,
        "elapsedSeconds": result["elapsedSeconds"],
        "cleanupSeconds": result["cleanupSeconds"],
        "python": observed,
        "provisionBytes": payload.stat().st_size,
        "sourceBeforeAfterSha256": hashlib.sha256(raw["source-before"]["stdout"]).hexdigest(),
        "toolsBeforeAfterSha256": hashlib.sha256(tools).hexdigest(),
        "sameAttemptCleanupAbsent": True,
        "newDaemonCalls": 0,
        "newProbeOrTaskExecution": False,
        "costUsd": None,
        "actualAdmission": False,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
