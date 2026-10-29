"""Read-only byte/provenance consistency checks; never import upstream sources."""

import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ledger = json.loads((HERE / "request-ledger.json").read_text())
    report = json.loads((HERE / "disposition.json").read_text())
    revision = ledger["revision"]
    assert ledger["apiCalls"] == len(ledger["requests"]) == 9 <= 12
    sources = {}
    total = 0
    for row in ledger["requests"]:
        raw = (HERE / row["requestFile"]).read_bytes()
        assert sha(raw) == row["requestSha256"]
        request = json.loads(raw)
        assert not request["result"].get("isError")
        if "sourcePath" not in row:
            assert request["result"]["structuredContent"]["commit"]["sha"] == revision
            continue
        assert request["args"]["ref"] == revision
        data = request["result"]["structuredContent"]
        source = base64.b64decode(data["content"], validate=False)
        assert len(source) == row["bytes"] <= 2097152
        assert source == (HERE / row["retainedPath"]).read_bytes()
        # Request and source digests are separate bindings.
        assert sha(source) == row["sha256"]
        blob = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        assert blob == row["gitBlobSha1"] == data["sha"]
        assert f"/blob/{revision}/" in row["url"]
        sources[row["sourcePath"]] = source
        total += len(source)
    assert len(sources) == ledger["fullSourceFiles"] == 8
    assert total == ledger["totalSourceBytes"] <= 8388608
    for name, binding in report["reusedSourceBindings"].items():
        source = (ROOT / binding["localPath"]).read_bytes()
        assert sha(source) == binding["sha256"]
        sources[name] = source
    for claim in report["claims"]:
        for passage in claim["support"]:
            source = sources[passage["path"]]
            assert sha(source) == passage["wholeFileSha256"]
            lines = source.splitlines(keepends=True)
            start, end = passage["startLine"], passage["endLine"]
            assert 1 <= start <= end <= len(lines)
            assert sha(b"".join(lines[start - 1 : end])) == passage["passageSha256"]
    print(
        json.dumps(
            {
                "status": "pass",
                "apiRequests": 9,
                "newFullSourceFiles": 8,
                "newSourceBytes": total,
                "claimsWithBoundPassages": len(report["claims"]),
                "upstreamImportsOrExecution": False,
            }
        )
    )


if __name__ == "__main__":
    main()
