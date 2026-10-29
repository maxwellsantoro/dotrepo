"""Read-only local source/hash checks for the Zellij assessment."""

import hashlib
import json
from pathlib import Path
import re
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/maxwell/projects/agent/dotrepo")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bindings = json.loads((HERE / "source-bindings.json").read_text())
    assessment = json.loads((HERE / "assessment.json").read_text())
    packets = [
        (
            ROOT / "index/telemetry/e1-next-context-establishment-20261029/zellij-proposal-1",
            bindings["proposalFreezeSha256"],
        ),
        (
            ROOT / "benchmarks/head-to-head/e1-zellij-establishment-source-20261029",
            bindings["sourceFollowupFreezeSha256"],
        ),
    ]
    for packet, digest in packets:
        assert sha(packet / "FREEZE.json") == digest
        freeze = json.loads((packet / "FREEZE.json").read_text())
        assert sha(packet / "artifact-hashes.json") == freeze["artifactManifestSha256"]
        for row in json.loads((packet / "artifact-hashes.json").read_text()):
            path = packet / row["path"]
            assert path.stat().st_size == row["bytes"] and sha(path) == row["sha256"]
    declaration = json.loads((packets[0][0] / "development-declaration.json").read_text())
    for owner in ["goldOwner", "resultOwner"]:
        assert sha(ROOT / declaration[owner]["path"]) == declaration[owner]["sha256"]
    sources = bindings["sources"]
    for row in sources.values():
        assert sha(ROOT / row["retainedPath"]) == row["sha256"]
    passages = 0
    for assertion in assessment["assertions"]:
        for span in assertion["support"]:
            path = ROOT / sources[span["path"]]["retainedPath"]
            lines = path.read_bytes().splitlines(keepends=True)
            assert 1 <= span["startLine"] <= span["endLine"] <= len(lines)
            raw = b"".join(lines[span["startLine"] - 1 : span["endLine"]])
            assert sha(path) == span["wholeFileSha256"]
            assert hashlib.sha256(raw).hexdigest() == span["passageSha256"]
            passages += 1

    def source(name):
        return (ROOT / sources[name]["retainedPath"]).read_text()

    members = re.findall(r'crate_name: "([^"]+)"', source("xtask/src/main.rs"))
    workspace = tomllib.loads(source("Cargo.toml"))["workspace"]["members"]
    assert len(members) == 19 and len(workspace) == 21
    assert set(workspace) - set(members) == {"xtask", "zellij-integration-tests"}
    assert members == assessment["memberComparison"]["maintainedMembers"]
    assert workspace == assessment["memberComparison"]["workspaceMembers"]
    assert sum("plugins" in name for name in members) == 12
    assert assessment["command"] == declaration["commandUnchanged"] == "cargo xtask test"
    assert assessment["taskId"] == declaration["taskId"] == "e1-rust-01-repository-tests"
    print(
        json.dumps(
            {
                "sourceFilesChecked": len(sources),
                "passagesChecked": passages,
                "maintainedMembers": 19,
                "workspaceMembers": 21,
                "actions": "local data only",
            }
        )
    )


if __name__ == "__main__":
    main()
