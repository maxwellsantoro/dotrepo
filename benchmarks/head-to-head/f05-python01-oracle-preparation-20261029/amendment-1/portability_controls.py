"""Relocation and immutable-input controls; owned Python/data and read-only Git only."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
EXPECTED_MANIFEST = "e141c87f452f021a3a9e7ced5c3bb1b2efc8691a06d925cde0cebdabddf09339"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(*args, cwd, success=True):
    value = subprocess.run(
        ["uv", "run", "--offline", "python", "-B", *map(str, args)],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
        check=False,
    )
    assert (value.returncode == 0) is success, (args, value.returncode, value.stderr.decode())
    return json.loads(value.stdout) if success else {"rejected": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    observations = []
    with tempfile.TemporaryDirectory(prefix="temporary-control-", dir=HERE) as scratch:
        scratch = Path(scratch)
        relocated = scratch / "relocated-packet"

        def ignore(path, names):
            excluded = {"__pycache__"}
            if Path(path) == HERE:
                excluded.update({"FREEZE.json", scratch.name})
            return set(names) & excluded

        shutil.copytree(HERE, relocated, ignore=ignore)
        # A temporary control-only manifest lets verification execute before the
        # author's final closure is frozen. It is never claimed as the final freeze.
        artifacts = {
            str(path.relative_to(relocated)): {
                "sha256": sha(path.read_bytes()),
                "bytes": path.stat().st_size,
            }
            for path in sorted(relocated.rglob("*"))
            if path.is_file()
        }
        (relocated / "FREEZE.json").write_text(json.dumps({"artifacts": artifacts}))
        derived = scratch / "derived.json"
        result = run(relocated / "derive_fixture.py", "--output", derived, cwd=scratch)
        assert result["sha256"] == EXPECTED_MANIFEST
        assert derived.read_bytes() == (HERE / "synthetic-case-manifest.json").read_bytes()
        observations.append({"name": "relocated-derivation-exact", "sha256": result["sha256"]})
        result = run(
            relocated / "verify.py", "--no-repository", "--parent", args.parent, cwd=scratch
        )
        assert not result["historicalGitRecheckPerformed"]
        assert not result["fullArchiveAudit"]["performed"]
        assert result["originalParentArtifactAudit"] == {"performed": True, "artifacts": 41}
        observations.append({"name": "relocated-without-repository-or-archive", "result": result})
        gitdir = (
            subprocess.run(
                ["git", "-C", str(args.repo_root), "rev-parse", "--absolute-git-dir"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            .stdout.decode()
            .strip()
        )
        mirror = scratch / "owned-mutable-working-tree"
        mirror.mkdir()
        (mirror / ".git").write_text("gitdir: " + gitdir + "\n")
        (mirror / "ROADMAP.md").write_text("owned mutated current ROADMAP regression fixture\n")
        runtime = mirror / "benchmarks/head-to-head/bench/agent_runtime.py"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("owned changed current runtime fixture; never imported\n")
        result = run(relocated / "verify.py", "--repo-root", mirror, cwd=scratch)
        assert result["historicalGitRecheckPerformed"] and result["retainedHistoricalInputs"] == 12
        assert len(result["observedWorkingTreeSnapshots"]) == 2
        assert all(not row["attributedToBase"] for row in result["observedWorkingTreeSnapshots"])
        observations.append(
            {"name": "mutated-current-ROADMAP-and-runtime-with-historical-Git", "result": result}
        )
        result = run(relocated / "verify.py", cwd=mirror)
        assert result["historicalGitRecheckPerformed"]
        observations.append({"name": "discover-Git-root-from-owned-working-tree", "result": result})
        wrong = scratch / "wrong-archive.tar"
        wrong.write_bytes(b"owned invalid archive")
        result = run(
            relocated / "verify.py",
            "--no-repository",
            "--archive",
            wrong,
            cwd=scratch,
            success=False,
        )
        observations.append({"name": "explicit-wrong-archive-rejected", "result": result})
        if args.archive is not None:
            result = run(
                relocated / "verify.py", "--no-repository", "--archive", args.archive, cwd=scratch
            )
            assert result["fullArchiveAudit"]["files"] == 128
            observations.append({"name": "explicit-exact-archive-audit", "result": result})
        result = run(relocated / "controls.py", "--output", scratch / "controls.json", cwd=scratch)
        assert result["allPassed"] and result["count"] == 73
        observations.append({"name": "relocated-original-73-controls", "result": result})
        manifest = (
            relocated
            / "bound-inputs/benchmarks/head-to-head/f05-python01-oracle-decision-20261029/static-test-inventory.json"
        )
        manifest.write_bytes(manifest.read_bytes() + b" ")
        observations.append(
            {
                "name": "changed-retained-inventory-rejected",
                "result": run(
                    relocated / "derive_fixture.py",
                    "--output",
                    scratch / "bad.json",
                    cwd=scratch,
                    success=False,
                ),
            }
        )
    report = {
        "allPassed": True,
        "count": len(observations),
        "cases": observations,
        "actualAdmission": False,
        "sourceCodeExecuted": False,
        "temporaryFreezeIsControlOnly": True,
        "originalRepositoryFilesWritten": False,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"allPassed": True, "count": len(observations), "actualAdmission": False}))


if __name__ == "__main__":
    main()
