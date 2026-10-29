"""Read-only consistency checks for the two exact-tree source bodies."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    prior = HERE.parent / "closure-1"
    assert (
        sha((prior / "FREEZE.json").read_bytes())
        == "5b1b3c17c0409011eaebd715ef9d031e4717087b196a66e7978e758390c75b4b"
    )
    for row in json.loads((prior / "artifact-hashes.json").read_text()):
        assert sha((prior / row["path"]).read_bytes()) == row["sha256"]
    tree = json.loads(
        json.loads((prior / "requests/02-root-tree.json").read_text())["result"][
            "structuredContent"
        ]["content"]
    )
    entries = {row["path"]: row for row in tree["tree"]}
    observations = json.loads((HERE / "observations.json").read_text())
    total = 0
    for row in observations["sources"]:
        request_raw = (HERE / row["requestPath"]).read_bytes()
        assert sha(request_raw) == row["requestSha256"]
        request = json.loads(request_raw)
        assert not request["result"].get("isError")
        raw = request["result"]["structuredContent"]["content"].encode()
        assert raw == (HERE / row["retainedPath"]).read_bytes()
        assert sha(raw) == row["sha256"]
        assert len(raw) == row["bytes"] == entries[row["path"]]["size"] <= 2097152
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert (
            blob == row["gitBlobSha1"] == request["args"]["blob_sha"] == entries[row["path"]]["sha"]
        )
        total += len(raw)
    assert len(observations["sources"]) == 2
    assert total == observations["newSourceBytes"] == 13
    assert observations["totalClosureCalls"] == 5 <= 6
    make = observations["makefileInspection"]
    raw = (ROOT / make["localPath"]).read_bytes()
    assert sha(raw) == make["wholeFileSha256"]
    assert len(raw.splitlines()) == make["linesInspected"] == 186
    assert make["explicitIncludeOverrideDefineUndefineDirectives"] == []
    assert "GNUmakefile" not in entries and "makefile" not in entries and "Makefile" in entries
    assert "Dockerfile.dockerignore" not in entries
    print(
        json.dumps(
            {
                "status": "pass",
                "bodyRequests": 2,
                "combinedClosureCalls": 5,
                "sourceBytes": 13,
                "treeBlobBindingsMatched": True,
                "priorClosureUnchanged": True,
                "upstreamExecution": False,
            }
        )
    )


if __name__ == "__main__":
    main()
