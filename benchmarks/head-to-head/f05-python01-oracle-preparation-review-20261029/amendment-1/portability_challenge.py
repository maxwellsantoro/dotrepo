"""Independent relocated retained-input checks; Python/data and read-only Git."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
AUTHOR = Path("/tmp/dotrepo-f05-python01-oracle-preparation-20261029/amendment-1")
REPO = Path.cwd()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    assert hashlib.sha256((AUTHOR / "FREEZE.json").read_bytes()).hexdigest() == (
        "994f8d9b6196252b763dbb56756dcb96b5c82b61c000164c71bbad23bdcef893"
    )
    reports = []
    with tempfile.TemporaryDirectory(prefix="independent-relocation-", dir=HERE) as temporary:
        temporary = Path(temporary)
        relocated = temporary / "packet"
        shutil.copytree(AUTHOR, relocated, ignore=shutil.ignore_patterns("__pycache__"))
        verifier = module("owned_successor_verify", relocated / "verify.py")
        derive = module("owned_successor_derive", relocated / "derive_fixture.py")
        reads, original_read = [], Path.read_bytes

        def contained_read(path):
            path = path.resolve()
            assert relocated in path.parents, "implicit external input: " + str(path)
            reads.append(str(path.relative_to(relocated)))
            return original_read(path)

        with patch.object(Path, "read_bytes", contained_read):
            result = verifier.verify(packet=relocated, no_repository=True)
            data = derive.derive(packet=relocated)
        assert not result["historicalGitRecheckPerformed"]
        assert not result["fullArchiveAudit"]["performed"]
        assert not result["originalParentArtifactAudit"]["performed"]
        raw = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
        assert hashlib.sha256(raw).hexdigest() == (
            "e141c87f452f021a3a9e7ced5c3bb1b2efc8691a06d925cde0cebdabddf09339"
        )
        assert data["nativeIdsEstablished"] is False and len(data["cases"]) == 157
        reports.append(
            {
                "case": "relocated-no-external-reads",
                "readCount": len(reads),
                "verification": result,
                "derivedFixtureByteExact": True,
            }
        )
        gitdir = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--absolute-git-dir"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        mirror = temporary / "current"
        mirror.mkdir()
        (mirror / ".git").write_text("gitdir: " + gitdir + "\n")
        (mirror / "ROADMAP.md").write_text("owned changed-current roadmap\n")
        fake_runtime = mirror / "benchmarks/head-to-head/bench/agent_runtime.py"
        fake_runtime.parent.mkdir(parents=True)
        fake_runtime.write_text("owned changed current runtime; never imported\n")
        result = verifier.verify(packet=relocated, repo_root=mirror)
        assert result["historicalGitRecheckPerformed"] and result["retainedHistoricalInputs"] == 12
        assert len(result["observedWorkingTreeSnapshots"]) == 2
        assert all(not row["attributedToBase"] for row in result["observedWorkingTreeSnapshots"])
        reports.append({"case": "changed-current-roadmap-and-runtime", "verification": result})

        def rejects(name, action):
            try:
                action()
            except (ValueError, OSError, AssertionError) as error:
                reports.append(
                    {"case": name, "errorType": type(error).__name__, "error": str(error)}
                )
            else:
                raise AssertionError("unexpected acceptance: " + name)

        snapshot = relocated / "bound-inputs/ROADMAP.md"
        saved = snapshot.read_bytes()
        snapshot.write_bytes(saved + b"changed retained evidence\n")
        rejects(
            "changed-observed-snapshot",
            lambda: verifier.verify(packet=relocated, no_repository=True),
        )
        snapshot.write_bytes(saved)
        resolution = relocated / "input-resolution.json"
        saved = resolution.read_bytes()
        value = json.loads(saved)
        observed = next(row for row in value["rows"] if row.get("path") == "ROADMAP.md")
        observed["resolution"] = "retained-snapshot-and-matching-git-base"
        observed["gitCommit"] = verifier.BASE
        observed["gitBlob"] = (
            verifier.git(REPO, "rev-parse", verifier.BASE + ":ROADMAP.md").decode().strip()
        )
        resolution.write_text(json.dumps(value))
        rejects(
            "observed-roadmap-falsely-attributed-to-base",
            lambda: verifier.verify(packet=relocated, repo_root=mirror),
        )
        resolution.write_bytes(saved)
        wrong = temporary / "wrong.tar"
        wrong.write_bytes(b"owned invalid archive")
        rejects(
            "explicit-wrong-archive",
            lambda: verifier.verify(packet=relocated, no_repository=True, archive=wrong),
        )
        rejects(
            "explicit-missing-archive",
            lambda: verifier.verify(
                packet=relocated, no_repository=True, archive=temporary / "missing"
            ),
        )
        inventory = relocated / "bound-inputs" / derive.INVENTORY_RELATIVE
        wrong_inventory = temporary / "wrong-inventory.json"
        wrong_inventory.write_bytes(inventory.read_bytes() + b" ")
        rejects(
            "explicit-wrong-inventory",
            lambda: derive.derive(packet=relocated, inventory_path=wrong_inventory),
        )
        result = verifier.verify(
            packet=relocated,
            no_repository=True,
            archive=Path("/tmp/dotrepo-f05-qualification-next8-20261029/python-01/source.tar"),
            parent=AUTHOR.parent,
        )
        assert (
            result["fullArchiveAudit"]["performed"] and result["fullArchiveAudit"]["files"] == 128
        )
        assert result["originalParentArtifactAudit"]["artifacts"] == 41
        reports.append({"case": "explicit-exact-archive-and-parent", "verification": result})
    report = {
        "state": "independent-portability-controls-passed",
        "count": len(reports),
        "cases": reports,
        "actualAdmission": False,
        "newNativeDaemonNetworkProviderActions": 0,
    }
    with (HERE / "portability-challenge.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"allPassed": True, "count": len(reports)}))


if __name__ == "__main__":
    main()
