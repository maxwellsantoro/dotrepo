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


def live_seed_repo_root(repo_root: Path, owner: str, repo: str) -> Path:
    return repo_root / "index" / "repos" / "github.com" / owner / repo


def copy_repo(source_repo: Path, dest_root: Path, owner: str, repo: str) -> None:
    dest_repo = dest_root / "repos" / "github.com" / owner / repo
    dest_repo.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_repo / "record.toml", dest_repo / "record.toml")
    shutil.copy2(source_repo / "evidence.md", dest_repo / "evidence.md")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_root = (repo_root / args.output_root).resolve()
    reports_dir = output_root / "reports"
    live_seed_index_dir = output_root / "live-seed-handoff-index"
    live_seed_public_dir = output_root / "live-seed-handoff-public"

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

    copy_repo(live_seed_repo_root(repo_root, "cli", "cli"), live_seed_index_dir, "cli", "cli")

    run(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "--root",
            str(live_seed_index_dir),
            "claim-init",
            "--host",
            "github.com",
            "--owner",
            "cli",
            "--repo",
            "cli",
            "--claim-id",
            "2026-03-19-maintainer-claim-01",
            "--claimant-name",
            "GitHub CLI maintainers",
            "--asserted-role",
            "maintainer",
            "--contact",
            "maintainers@github.com",
            "--record-source",
            "https://github.com/cli/cli",
            "--canonical-repo-url",
            "https://github.com/cli/cli",
            "--review-md",
        ],
        cwd=repo_root,
    )
    run(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "--root",
            str(live_seed_index_dir),
            "claim-event",
            "repos/github.com/cli/cli/claims/2026-03-19-maintainer-claim-01",
            "--kind",
            "submitted",
            "--actor",
            "claimant",
            "--summary",
            "Submitted maintainer claim.",
        ],
        cwd=repo_root,
    )
    run(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "--root",
            str(live_seed_index_dir),
            "claim-event",
            "repos/github.com/cli/cli/claims/2026-03-19-maintainer-claim-01",
            "--kind",
            "accepted",
            "--actor",
            "index-reviewer",
            "--summary",
            "Accepted claim after maintainer review.",
            "--canonical-record-path",
            ".repo",
            "--canonical-mirror-path",
            "repos/github.com/cli/cli/record.toml",
        ],
        cwd=repo_root,
    )
    run(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "public",
            "export",
            "--index-root",
            str(live_seed_index_dir),
            "--out-dir",
            str(live_seed_public_dir),
            "--generated-at",
            "2026-03-10T18:30:00Z",
            "--stale-after",
            "2026-03-11T18:30:00Z",
        ],
        cwd=repo_root,
    )

    live_summary_path = (
        live_seed_public_dir / "v0" / "repos" / "github.com" / "cli" / "cli" / "index.json"
    )
    live_trust_path = (
        live_seed_public_dir / "v0" / "repos" / "github.com" / "cli" / "cli" / "trust.json"
    )
    live_summary = json.loads(live_summary_path.read_text())
    live_trust = json.loads(live_trust_path.read_text())
    ensure(
        live_summary["selection"]["record"]["claim"]["handoff"] == "superseded",
        "live seed handoff export should surface superseded claim context in summary",
    )
    ensure(
        live_trust["selection"]["record"]["claim"]["handoff"] == "superseded",
        "live seed handoff export should surface superseded claim context in trust",
    )

    readme = "\n".join(
        [
            "dotrepo operator gate artifacts",
            "",
            "This directory is a proof artifact written by scripts/check_operator_claim_gate.py.",
            "",
            "What is checked in:",
            "- the real seed index under ./index/ remains overlay-only today",
            "- no accepted maintainer claim is committed for a real public repository yet",
            "",
            "What is staged here:",
            "- reports/accepted-clean.json and reports/corrected.json come from checked-in claim fixtures",
            "- reports/invalid-history.stderr.txt captures the expected validate-index failure path",
            "- live-seed-handoff-index/ is a temporary copy of index/repos/github.com/cli/cli with a staged claim",
            "- live-seed-handoff-public/ is the public export generated from that staged copy",
            "",
            "Why this exists:",
            "- it proves the operator workflow and claim-aware public export path end to end",
            "- it avoids publishing a fake accepted maintainer claim in the checked-in seed index",
            "",
            "The staged handoff is a proof artifact, not the live public seed index.",
            "",
        ]
    )
    (output_root / "README.txt").write_text(readme)

    summary = {
        "checks": [
            "seed index validate-index",
            "claim fixture pack",
            "claim command contract",
            "accepted-clean claim inspection",
            "corrected claim inspection",
            "invalid-history rejection",
            "live seed overlay handoff export",
        ],
        "reports": {
            "accepted_clean": str((reports_dir / "accepted-clean.json").relative_to(output_root)),
            "corrected": str((reports_dir / "corrected.json").relative_to(output_root)),
            "invalid_history_stderr": str(
                (reports_dir / "invalid-history.stderr.txt").relative_to(output_root)
            ),
            "live_seed_summary": str(live_summary_path.relative_to(output_root)),
            "live_seed_trust": str(live_trust_path.relative_to(output_root)),
        },
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print("")
    print("operator gate artifacts")
    print(f"  accepted-clean report: {reports_dir / 'accepted-clean.json'}")
    print(f"  corrected report: {reports_dir / 'corrected.json'}")
    print(f"  invalid-history stderr: {reports_dir / 'invalid-history.stderr.txt'}")
    print(f"  readme: {output_root / 'README.txt'}")
    print(f"  live seed summary: {live_summary_path}")
    print(f"  live seed trust: {live_trust_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
