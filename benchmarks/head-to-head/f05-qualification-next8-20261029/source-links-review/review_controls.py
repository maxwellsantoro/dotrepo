"""Independent offline counterexamples; no daemon, provider, or source execution."""

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "scripts/tests"), str(ROOT / "benchmarks/head-to-head")]
from bench import agent_runtime as runtime  # noqa: E402
from test_agent_runtime import symlink_spec  # noqa: E402
from test_agent_experiment import write  # noqa: E402

PACKET = Path(__file__).resolve().parent.parent / "source-links-qualification"
EXPECTED = "467a8de48c814ca66b4570bf51e65e65f03b484c92eaf6a14cf9bf663a5e7d33"
REVISION = "a" * 40


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    freeze = json.loads((PACKET / "freeze.json").read_bytes())
    assert digest((PACKET / "freeze.json").read_bytes()) == EXPECTED
    for entry in freeze["files"]:
        data = (PACKET / entry["path"]).read_bytes()
        assert digest(data) == entry["sha256"] and len(data) == entry["bytes"]
    assert (
        digest((ROOT / "benchmarks/head-to-head/bench/agent_runtime.py").read_bytes())
        == freeze["runtimeSha256"]
    )
    assert (
        digest((ROOT / "scripts/tests/test_agent_runtime.py").read_bytes()) == freeze["testSha256"]
    )
    checked = []
    cases = [
        (
            "nested-dir-chain",
            {"a/deep/file": b"ok"},
            {"x": "a/deep", "y": "x/../deep/file"},
            {"path": "a/deep/file", "type": "regular"},
        ),
        (
            "sibling-dir-alias",
            {"a/file": b"ok", "b/file": b"ok"},
            {"a/to-b": "../b"},
            {"path": "b", "type": "directory"},
        ),
        ("regular-trailing-slash", {"file": b"ok"}, {"bad": "file/"}, None),
        ("regular-dot", {"file": b"ok"}, {"bad": "file/."}, None),
        ("regular-dotdot", {"file": b"ok"}, {"bad": "file/../file"}, None),
        ("root-dir-alias", {"file": b"ok"}, {"bad": "."}, None),
        ("nested-ancestor-alias", {"a/file": b"ok"}, {"a/up": ".."}, None),
        (
            "three-dir-cycle",
            {"a/f": b"a", "b/f": b"b", "c/f": b"c"},
            {"a/b": "../b", "b/c": "../c", "c/a": "../a"},
            None,
        ),
        ("link-chain-root-escape", {"a/file": b"ok"}, {"one": "a", "bad": "one/../../etc"}, None),
        ("regular-under-link", {"real/f": b"ok", "alias/f": b"bad"}, {"alias": "real"}, None),
    ]
    with tempfile.TemporaryDirectory(prefix="dotrepo-source-links-review-") as directory:
        scratch = Path(directory)
        for number, (name, files, links, expected) in enumerate(cases):
            stage = scratch / str(number)
            spec = symlink_spec(stage, files, links)
            try:
                bundle = runtime.source_bundle(stage, spec, REVISION, set(), 1000000)
            except ValueError as exc:
                assert expected is None, (name, str(exc))
                checked.append({"case": name, "result": "rejected", "reason": str(exc)})
            else:
                assert expected is not None, name
                assert bundle.resolved_links[next(reversed(links))] == expected
                checked.append({"case": name, "result": "accepted", "resolved": expected})
        stage = scratch / "duplicate-directory"
        spec = symlink_spec(stage, {"file": b"ok"}, {})
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            for _ in range(2):
                member = tarfile.TarInfo("dir/")
                member.type = tarfile.DIRTYPE
                tar.addfile(member)
        spec["archive"] = write(stage, "source.tar", buffer.getvalue())
        provenance = json.loads((stage / spec["provenance"]["path"]).read_bytes())
        provenance["archiveSha256"] = spec["archive"]["sha256"]
        spec["provenance"] = write(stage, "source-provenance.json", provenance)
        try:
            runtime.source_bundle(stage, spec, REVISION, set(), 1000000)
        except ValueError as exc:
            assert "duplicate" in str(exc)
            checked.append(
                {"case": "duplicate-directory", "result": "rejected", "reason": str(exc)}
            )
        else:
            raise AssertionError("duplicate directory accepted")
        # Failed first/second phase, and an already-present destination: no retry
        # or success; receipts count only the actually submitted transport phases.
        stage = scratch / "transport"
        spec = symlink_spec(stage, {"data/f": b"ok"}, {"alias": "data/"})
        bundle = runtime.source_bundle(stage, spec, REVISION, set(), 1000000)
        for failure in (0, 1, 2, None):
            calls = []

            def invoke(argv, **kwargs):
                calls.append((argv, kwargs))
                return {
                    "exitCode": 1 if len(calls) - 1 == failure else 0,
                    "error": None,
                    "stdout": "",
                    "stderr": "",
                }

            result = runtime.DockerBackend(invoke).checkout(bundle, 10)
            submitted = [kw["data"] for _, kw in calls if kw.get("data")]
            assert result["sourceCopy"]["stdinBytes"] == sum(map(len, submitted))
            assert len(submitted) == (0 if failure == 0 else 1 if failure == 1 else 2)
            assert result["exitCode"] == (0 if failure is None else 1)
            for entry, data in zip(result["sourceCopy"]["archives"], submitted, strict=True):
                assert entry["sha256"] == digest(data) and entry["stdinBytes"] == len(data)
            checked.append(
                {
                    "case": f"transport-failure-{failure}",
                    "submittedBytes": sum(map(len, submitted)),
                    "phases": len(submitted),
                    "exitCode": result["exitCode"],
                }
            )
        actual = []
        for task in ("python-02", "typescript-01"):
            original = PACKET.parent / task
            acquisition = json.loads((original / "acquisition.json").read_bytes())
            inventory = json.loads((PACKET / f"{task}-link-inventory.json").read_bytes())
            stage = scratch / task
            stage.mkdir()
            # Archive stays retained at its original path: artifact() verifies it
            # from its own parent. Inventory/provenance are scratch-owned bytes.
            archive = Path(acquisition["archivePath"])
            assert not archive.is_symlink()
            spec = {
                "revision": inventory["revision"],
                "archive": {"path": str(archive), "sha256": acquisition["archiveSha256"]},
                "inventory": write(stage, "inventory.json", inventory),
                "provenance": write(
                    stage,
                    "provenance.json",
                    json.loads((original / "provenance.json").read_bytes()),
                ),
            }
            # artifact path contracts require contained relative paths, so reuse
            # exact bytes in scratch without extracting or following source links.
            spec["archive"] = write(stage, "source.tar", archive.read_bytes())
            assert spec["archive"]["sha256"] == acquisition["archiveSha256"]
            admitted = runtime.source_bundle(stage, spec, inventory["revision"], set(), 1024**3)
            actual.append(
                {
                    "task": task,
                    "archiveSha256": digest(admitted.archive),
                    "regularFiles": len(admitted.files),
                    "symlinks": len(admitted.symlinks),
                    "structuralOnlyEmptyProtectedSet": True,
                }
            )
    qualification = json.loads((PACKET / "qualification.json").read_bytes())
    assert qualification["runtimeSha256"] == freeze["runtimeSha256"]
    assert qualification["driverSha256"] == digest((PACKET / "qualify_links.py").read_bytes())
    receipt_checks = []
    for receipt in qualification["docker"]:
        assert receipt["status"] == "passed" and all(receipt["checks"].values())
        operations = receipt["operations"]
        inspection = next(op for op in operations if op["argv"][:2] == ["docker", "inspect"])
        metadata = json.loads(inspection["result"]["stdout"])[0]
        host = metadata["HostConfig"]
        assert metadata["Image"] == qualification["image"]
        assert metadata["Config"]["User"] == "1000:1000"
        assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
        assert not host["Binds"] and not host["Privileged"] and host["CapDrop"] == ["ALL"]
        assert host["SecurityOpt"] == ["no-new-privileges"]
        assert set(host["Tmpfs"]) == {"/tmp", "/workspace"}
        assert not metadata["Mounts"]
        copies = [op for op in operations if "/bin/tar" in op["argv"]]
        copy = receipt["checkout"]["sourceCopy"]
        assert copy["originalArchiveSha256"] == qualification["ownedFixtureArchiveSha256"]
        assert copy["stdinBytes"] == sum(op["stdinBytes"] for op in copies) == 20480
        assert [a["stdinBytes"] for a in copy["archives"]] == [op["stdinBytes"] for op in copies]
        assert receipt["secondCheckout"]["exitCode"] != 0
        assert receipt["secondCheckout"]["sourceCopy"]["stdinBytes"] == 0
        assert (
            receipt["cleanup"]["exitCode"] == 0 and receipt["absentAfterCleanup"]["exitCode"] != 0
        )
        assert (
            receipt["read"]["stdout"] == "data/\ndocs/message\nowned control original\n755\n1000\n"
        )
        receipt_checks.append(
            {
                "container": receipt["container"],
                "sourceCopyBytes": copy["stdinBytes"],
                "nonrootReadonlyNetworkNoneNoHostMounts": True,
                "freshRefusal": True,
                "cleanupRetained": True,
            }
        )
    print(
        json.dumps(
            {
                "result": "pass",
                "qualificationFilesVerified": len(freeze["files"]),
                "runtimeSha256": freeze["runtimeSha256"],
                "controls": checked,
                "actualStaticAdmission": actual,
                "retainedOwnedDockerReceipts": receipt_checks,
                "newNetworkRequests": 0,
                "upstreamExecution": False,
                "dockerDaemonCalls": 0,
                "providerCalls": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
