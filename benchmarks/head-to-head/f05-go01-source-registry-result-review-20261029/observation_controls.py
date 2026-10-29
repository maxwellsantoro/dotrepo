"""Static inspection and mutations of owned captured bytes; no new tool execution."""

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = Path("/private/tmp/dotrepo-go01-owned-registry-result-20261029-1")
HELPER = ROOT / "benchmarks/head-to-head/f05-go01-source-registry-20261029"


def read(path):
    return json.loads(path.read_bytes())


def main():
    sys.path.insert(0, str(HELPER / "amendment-1"))
    builder = importlib.import_module("build_input")
    receiver = importlib.import_module("read_registry")
    comparator = importlib.import_module("crosscheck_registry")
    wire = (RAW / "registry.gz").read_bytes()
    registry = builder.load(receiver.inflate(wire))
    observations = builder.load((HELPER / "partial-listing-observations.json").read_bytes())
    provenance = builder.load((HELPER / "input-provenance.json").read_bytes())
    packages = builder.load(Path(provenance["packageInventoryPath"]).read_bytes())
    cases = []

    def check(name, operation):
        operation()
        cases.append({"case": name, "passed": True})

    def refuse(operation):
        try:
            operation()
        except (ValueError, TypeError, KeyError, zlib.error):
            return
        raise AssertionError("malformed observation accepted")

    for name, value in [
        ("badCRC", wire[:-8] + bytes([wire[-8] ^ 1]) + wire[-7:]),
        ("truncated", wire[:-1]),
        ("second member", wire + wire),
    ]:
        check(name, lambda value=value: refuse(lambda: receiver.inflate(value)))
    wrong_context = deepcopy(registry)
    wrong_context["sourceContext"]["revision"] = "0" * 40
    check(
        "different source context",
        lambda: refuse(lambda: receiver.validate(wrong_context, provenance, packages)),
    )
    fail_name = next(
        n for n, row in observations["packages"].items() if row["nativeListingTerminal"] == "fail"
    )
    positive_name = next(
        n
        for n, row in observations["packages"].items()
        if row["nativeListingTerminal"] == "pass" and row["observedNameLines"]
    )
    empty_name = next(
        n for n, row in observations["packages"].items() if row["nativeListingTerminal"] == "skip"
    )

    def compare_mutation(name, mutate, expected_difference):
        candidate = deepcopy(registry)
        row = next(r for r in candidate["packages"] if r["importPath"] == name)
        mutate(row)
        compared = comparator.compare(candidate, observations)
        assert bool(compared["differences"]) is expected_difference
        assert compared["nativeFullCollectionExists"] is False
        assert compared["compileValidityUnestablished"] is True
        assert compared["taskOutcomeObserved"] is False
        assert compared["collectionGateChanged"] is False
        return compared

    check(
        "wrong positive source name becomes mismatch",
        lambda: compare_mutation(
            positive_name, lambda row: row["tests"][0].update(name="TestWrongOwnedMutation"), True
        ),
    )
    check(
        "spurious no-test declaration becomes mismatch",
        lambda: compare_mutation(
            empty_name, lambda row: row["tests"].append({"name": "TestWrongOwnedMutation"}), True
        ),
    )

    def failed_diagnostic():
        value = compare_mutation(
            fail_name,
            lambda row: row["diagnostics"].append(
                {"code": "owned-mutation", "message": "unresolved retained"}
            ),
            False,
        )
        assert fail_name in value["sourceRegistryDiagnosticsPackages"]
        assert fail_name in value["unvalidatedFailedPackages"]

    check("failed native package diagnostic retained without promotion", failed_diagnostic)
    check(
        "positive diagnostic cannot be hidden as match",
        lambda: compare_mutation(
            positive_name,
            lambda row: row["diagnostics"].append(
                {"code": "owned-mutation", "message": "unresolved retained"}
            ),
            True,
        ),
    )
    plan = read(
        ROOT / "benchmarks/head-to-head/f05-go01-source-registry-runtime-20261029/plan.json"
    )
    for phase in ["before", "after"]:
        inspected = read(RAW / ("logs/inspect-" + phase + "/stdout.bin"))[0]
        host, config = inspected["HostConfig"], inspected["Config"]
        assert inspected["Image"] == plan["imageId"]
        assert config["User"] == "1000:1000" and config["WorkingDir"] == "/workspace"
        assert host["ReadonlyRootfs"] is True and inspected["Mounts"] == []
        assert host["NetworkMode"] == "none" and host["Privileged"] is False
        assert host["PidMode"] in ["", "private"] and host["IpcMode"] == "private"
        assert host["CgroupnsMode"] == "private" and not host["CapAdd"]
        assert host["CapDrop"] == ["ALL"] and host["SecurityOpt"] == ["no-new-privileges"]
        assert host["Memory"] == host["MemorySwap"] == 4 << 30
        assert host["NanoCpus"] == 3000000000 and host["PidsLimit"] == 256
        assert host["Binds"] is None and host["Devices"] == []
        for mount in host["Tmpfs"].values():
            opts = set(mount.split(","))
            assert {"rw", "exec", "nosuid", "nodev", "uid=1000", "gid=1000", "mode=0700"} <= opts
        env = dict(e.split("=", 1) for e in config["Env"])
        for name, expected in plan["environment"].items():
            assert env[name] == expected
        cases.append({"case": "actual isolation and environment " + phase, "passed": True})
    assert (RAW / "logs/post-cleanup-list/stdout.bin").read_bytes() == b""
    assert (RAW / "logs/post-cleanup-inspect/stdout.bin").read_bytes() == b"[]\n"
    assert b"no such object:" in (RAW / "logs/post-cleanup-inspect/stderr.bin").read_bytes()
    cases.append({"case": "same-attempt cleanup absence receipts", "passed": True})
    record = {
        "state": "captured-observation-data-controls-passed",
        "cases": cases,
        "inputWireSha256": hashlib.sha256(wire).hexdigest(),
        "newGoDockerNodeNetworkProviderActions": 0,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
    }
    with (HERE / "observation-controls.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": len(cases)}))


if __name__ == "__main__":
    main()
