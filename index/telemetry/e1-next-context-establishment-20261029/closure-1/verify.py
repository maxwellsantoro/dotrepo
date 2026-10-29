"""Read-only retained Git tree and source identity checks, no upstream imports."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def git_hash(kind, data):
    return hashlib.sha1(kind + b" " + str(len(data)).encode() + b"\0" + data).hexdigest()


def main():
    observations = json.loads((HERE / "observations.json").read_text())
    objects = {}
    for row in observations["requests"]:
        raw = (HERE / row["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        request = json.loads(raw)
        assert not request["result"].get("isError")
        objects[Path(row["path"]).name] = json.loads(
            request["result"]["structuredContent"]["content"]
        )
    assert len(objects) == observations["readOnlyApiCalls"] == 3 <= 6
    commit = objects["01-commit.json"]
    root_tree = objects["02-root-tree.json"]
    relay_tree = objects["03-relay-tree.json"]
    assert commit["sha"] == observations["revision"]
    assert commit["tree"]["sha"] == root_tree["sha"]
    for tree in [root_tree, relay_tree]:
        assert tree["truncated"] is False
        entries = sorted(
            tree["tree"], key=lambda e: (e["path"] + ("/" if e["type"] == "tree" else "")).encode()
        )
        raw = b"".join(
            e["mode"].lstrip("0").encode()
            + b" "
            + e["path"].encode()
            + b"\0"
            + bytes.fromhex(e["sha"])
            for e in entries
        )
        assert git_hash(b"tree", raw) == tree["sha"]
    root_entries = {entry["path"]: entry for entry in root_tree["tree"]}
    relay_entries = {entry["path"]: entry for entry in relay_tree["tree"]}
    assert root_entries["relay"]["sha"] == relay_tree["sha"]
    assert "go.work" not in root_entries and "go.work.sum" not in root_entries
    defaults = json.loads((HERE / "plan.json").read_text())["defaultBakeFiles"]
    assert [name for name in defaults if name in root_entries] == ["docker-bake.hcl"]
    for binding in observations["retainedSourceTreeBindings"]:
        raw = (ROOT / binding["localPath"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == binding["sha256"]
        assert git_hash(b"blob", raw) == binding["gitBlobSha1"]
        entries = relay_entries if binding["path"].startswith("relay/") else root_entries
        name = binding["path"].removeprefix("relay/")
        assert entries[name]["sha"] == binding["gitBlobSha1"]
        assert entries[name]["mode"] == binding["mode"] == "100644"
    print(
        json.dumps(
            {
                "status": "pass",
                "apiCalls": 3,
                "newSourceBodies": 0,
                "gitTreesReconstructed": 2,
                "retainedBlobsMatched": len(observations["retainedSourceTreeBindings"]),
                "defaultBakeFilesPresent": ["docker-bake.hcl"],
                "rootGoWorkAbsent": True,
                "sourceExecution": False,
            }
        )
    )


if __name__ == "__main__":
    main()
