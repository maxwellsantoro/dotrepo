"""Freeze local input/driver bindings only; no Docker, download or source execution."""

import json
from pathlib import Path

from boundaries import file_sha, sha, write
from prepare import COMMANDS, IMAGE, LIMITS, REVISION, ROOTS, SOURCE

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def main():
    previous = (
        REPO
        / "benchmarks/head-to-head/f05-dependency-preparation-review-20261029/protected-content-digests.json"
    )
    protected = json.loads(previous.read_text())
    digests = set(protected["digests"])
    extras = []
    for folder in [
        REPO / "benchmarks/head-to-head/f05-agent-tasks-20261029/curator/gold",
        REPO / "benchmarks/head-to-head/f05-agent-tasks-20261029/curator/oracles",
        REPO / "benchmarks/head-to-head/f05-go01-oracle-preparation-20261029",
    ]:
        for path in sorted(folder.rglob("*")):
            if path.suffix not in (".json", ".py") or "__pycache__" in path.parts:
                continue
            raw = path.read_bytes()
            values = {sha(raw)}
            try:
                values.add(
                    sha(
                        (
                            json.dumps(json.loads(raw), indent=2, sort_keys=True, allow_nan=False)
                            + "\n"
                        ).encode()
                    )
                )
            except (ValueError, UnicodeDecodeError):
                pass
            digests.update(values)
            extras.append({"path": str(path), "digests": sorted(values)})
    write(
        HERE / "protected-digests.json",
        {
            "inheritedInventory": str(previous),
            "inheritedSha256": file_sha(previous),
            "extraArtifacts": extras,
            "digests": sorted(digests),
            "emptyBytesDisposition": "Empty bytes convey no gold/profile content; no blanket task-source/license hash deny. Exact/raw+canonical alias checking only, not substring/semantic/compressed-package safety.",
        },
    )
    base = REPO / "benchmarks/head-to-head"
    bindings = [
        previous,
        base / "f05-go01-requalification-proposal-20261029/freeze.json",
        base / "f05-go01-requalification-proposal-20261029/proposal.json",
        base / "f05-qualification-20261029/go-01-full/acquisition.json",
        base / "f05-qualification-20261029/go-01-full/inventory.json",
        base / "f05-common-image-audit-20261029/FREEZE.json",
        base / "f05-dependency-preparation-review-20261029/freeze.json",
        base / "f05-go01-oracle-preparation-20261029/amendment-1/freeze.json",
        base / "f05-go01-oracle-review-20261029/amendment-1/freeze.json",
        base / "f05-dependency-preparation-20261029/image-attempt-3/logs/tools/stdout.txt",
        HERE / "source-download-config.json",
    ]
    plan = {
        "identity": "go01-single-download-only-preparation-v1",
        "base": "595303f9b8bfa58366c9f2c93fb619ca54591ea2",
        "state": "plan and driver only; external coordinator authorization required",
        "executionAuthorized": False,
        "repository": "github.com/microsoft/TypeScript",
        "revision": REVISION,
        "imageId": IMAGE,
        "source": {
            "archivePath": "/tmp/dotrepo-f05-qualification-20261029-tranche-1/go-01-full/runtime-source.tar",
            "archiveSha256": SOURCE,
            "archiveBytes": 280422400,
            "expandedBytes": 218783760,
            "inventoryPath": str(base / "f05-qualification-20261029/go-01-full/inventory.json"),
        },
        "commands": COMMANDS,
        "exportRoots": list(ROOTS),
        "limits": LIMITS,
        "environment": {
            "HOME": "/workspace/home",
            "TMPDIR": "/workspace/tmp",
            "LANG": "C.UTF-8",
            "GOPATH": "/workspace/dependency-cache/go",
            "GOCACHE": "/workspace/go-build",
            "GOTOOLCHAIN": "local",
            "GOENV": "off",
            "GOMAXPROCS": "3",
            "GOGC": "50",
            "GOPROXY": "https://proxy.golang.org",
            "GOSUMDB": "sum.golang.org",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "NPM_CONFIG_CACHE": "/workspace/dependency-cache/npm-cache",
            "NPM_CONFIG_USERCONFIG": "/dev/null",
            "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org",
            "NPM_CONFIG_IGNORE_SCRIPTS": "true",
            "NPM_CONFIG_AUDIT": "false",
            "NPM_CONFIG_FUND": "false",
        },
        "toolProbe": "node --version; npm --version; go version; uv --version; git --version",
        "expectedToolLines": [
            "v24.22.2",
            "11.19.1",
            "go version go1.27.3 linux/arm64",
            "uv 0.13.6 (aarch64-unknown-linux-musl)",
            "git version 2.39.5",
        ],
        "draftAuditFlags": {
            "downloadOnly": False,
            "buildOutputsExcluded": False,
            "taskSourceExcluded": False,
            "credentialsExcluded": False,
        },
        "bindings": {str(path): file_sha(path) for path in bindings},
        "scripts": {
            name: file_sha(HERE / name)
            for name in [
                "prepare.py",
                "process_io.py",
                "boundaries.py",
                "controls.py",
                "make_plan.py",
                "io_controls.py",
                "protected-digests.json",
            ]
        },
        "limitsOfEvidence": [
            "No daemon/network/preparation call authorized by this plan.",
            "Bridge network has pinned public package-manager endpoints, not an egress firewall; source scripts are disabled.",
            "Cache tmpfs hard capacity and quarter-second apparent-size sampling bound growth; transient logical growth is not an instantaneous universal filesystem proof.",
            "Every attempt/failure retained, one accepted attempt only. Separate60second cleanup/absence grace; actual work overrun is an incomplete result.",
            "Independent package-lock/go.sum integrity, source/member classification, credentials/protected-content audit and later offline requalification remain required.",
            "Npm install-hook equivalence, native collection and exclusion-policy acceptance remain separate; no campaign admission.",
        ],
    }
    write(HERE / "plan.json", plan)


if __name__ == "__main__":
    main()
