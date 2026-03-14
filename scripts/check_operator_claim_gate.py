#!/usr/bin/env python3

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the maintainer/operator claim workflow gate for dotrepo."
    )
    parser.add_argument(
        "--output-root",
        default="operator-gate",
        help="Directory where generated inspection artifacts will be written (default: operator-gate)",
    )
    return parser.parse_args()


def run(cmd: list[str], *, cwd: Path) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def capture(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    print(f"+ {' '.join(cmd)}", flush=True)
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def fixture_root(repo_root: Path, name: str) -> Path:
    return (
        repo_root
        / "crates"
        / "dotrepo-core"
        / "tests"
        / "fixtures"
        / "claims"
        / name
    )


def claim_path(claim_id: str) -> str:
    return f"repos/github.com/acme/widget/claims/{claim_id}"


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_root = (repo_root / args.output_root).resolve()
    reports_dir = output_root / "reports"

    if output_root.exists():
        shutil.rmtree(output_root)
    reports_dir.mkdir(parents=True, exist_ok=True)

    run(["cargo", "run", "-p", "dotrepo-cli", "--", "validate-index"], cwd=repo_root)
    run(["cargo", "test", "-p", "dotrepo-core", "--test", "claim_fixture_pack"], cwd=repo_root)
    run(["cargo", "test", "-p", "dotrepo-cli", "--test", "claim_command_contract"], cwd=repo_root)

    accepted = capture(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "--root",
            str(fixture_root(repo_root, "accepted-clean")),
            "claim",
            claim_path("2026-03-10-maintainer-claim-01"),
            "--json",
        ],
        cwd=repo_root,
    )
    accepted_json = json.loads(accepted.stdout)
    ensure(accepted_json["state"] == "accepted", "accepted-clean fixture should report accepted state")
    ensure(
        accepted_json["target"]["handoff"] == "superseded",
        "accepted-clean fixture should report superseded handoff",
    )
    ensure(
        accepted_json["resolution"]["canonical_record_path"] == ".repo",
        "accepted-clean fixture should expose canonical record path",
    )
    (reports_dir / "accepted-clean.json").write_text(accepted.stdout)

    corrected = capture(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "--root",
            str(fixture_root(repo_root, "corrected")),
            "claim",
            claim_path("2026-03-15-maintainer-claim-01"),
            "--json",
        ],
        cwd=repo_root,
    )
    corrected_json = json.loads(corrected.stdout)
    ensure(corrected_json["state"] == "accepted", "corrected fixture should report accepted state")
    ensure(
        corrected_json["target"]["handoff"] == "pending_canonical",
        "corrected fixture should report pending_canonical handoff",
    )
    ensure(
        corrected_json.get("resolution") is None,
        "corrected fixture should not expose canonical resolution",
    )
    ensure(
        len(corrected_json["events"]) == 3,
        "corrected fixture should expose the rejected and corrected history",
    )
    (reports_dir / "corrected.json").write_text(corrected.stdout)

    invalid = subprocess.run(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "validate-index",
            "--index-root",
            str(fixture_root(repo_root, "invalid-history")),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    ensure(
        invalid.returncode == 1,
        f"invalid-history fixture should fail validate-index with exit code 1, got {invalid.returncode}",
    )
    ensure(not invalid.stdout.strip(), "invalid-history fixture should not write stdout")
    ensure(
        "claim events must use contiguous sequence numbers starting at 1" in invalid.stderr,
        "invalid-history fixture should report event sequence validation failure",
    )
    ensure(
        "claim.state is Accepted" in invalid.stderr,
        "invalid-history fixture should report state mismatch validation failure",
    )
    (reports_dir / "invalid-history.stderr.txt").write_text(invalid.stderr)

    summary = {
        "checks": [
            "seed index validate-index",
            "claim fixture pack",
            "claim command contract",
            "accepted-clean claim inspection",
            "corrected claim inspection",
            "invalid-history rejection",
        ],
        "reports": {
            "accepted_clean": str((reports_dir / "accepted-clean.json").relative_to(output_root)),
            "corrected": str((reports_dir / "corrected.json").relative_to(output_root)),
            "invalid_history_stderr": str(
                (reports_dir / "invalid-history.stderr.txt").relative_to(output_root)
            ),
        },
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print("")
    print("operator gate artifacts")
    print(f"  accepted-clean report: {reports_dir / 'accepted-clean.json'}")
    print(f"  corrected report: {reports_dir / 'corrected.json'}")
    print(f"  invalid-history stderr: {reports_dir / 'invalid-history.stderr.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
