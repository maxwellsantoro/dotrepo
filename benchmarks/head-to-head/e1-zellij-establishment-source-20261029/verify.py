"""Read retained bytes only; never import or execute upstream Rust/tooling."""

import base64
import hashlib
import json
from pathlib import Path
import re
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    declaration = json.loads((HERE / "declaration.json").read_text())
    freeze = json.loads((HERE / "DECLARATION-FREEZE.json").read_text())
    assert sha((HERE / freeze["path"]).read_bytes()) == freeze["sha256"]
    bindings = json.loads((HERE / "source-bindings.json").read_text())
    sources = {}
    assert bindings["requests"] == len(bindings["sources"]) == 2 <= 4
    for row in bindings["sources"]:
        request_raw = (HERE / row["requestPath"]).read_bytes()
        assert sha(request_raw) == row["requestSha256"]
        request = json.loads(request_raw)
        assert request["args"] in [row["args"] for row in declaration["requests"]]
        assert request["args"]["ref"] == declaration["revision"]
        data = request["result"]["structuredContent"]
        raw = base64.b64decode(data["content"])
        assert raw == (HERE / row["retainedPath"]).read_bytes()
        assert len(raw) == row["bytes"] <= 2097152
        assert sha(raw) == row["sha256"]
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert blob == row["gitBlobSha1"] == data["sha"]
        sources[row["upstreamPath"]] = raw
    report = json.loads((HERE / "disposition.json").read_text())
    for name, binding in report["reusedSourceBindings"].items():
        raw = (ROOT / binding["retainedPath"]).read_bytes()
        assert sha(raw) == binding["sha256"]
        sources[name] = raw
    for claim in report["claims"]:
        for passage in claim["support"]:
            raw = sources[passage["path"]]
            assert sha(raw) == passage["wholeFileSha256"]
            lines = raw.splitlines(keepends=True)
            start, end = passage["startLine"], passage["endLine"]
            assert 1 <= start <= end <= len(lines)
            assert sha(b"".join(lines[start - 1 : end])) == passage["passageSha256"]
    main = sources["xtask/src/main.rs"].decode()
    member_source = main[main.index("fn workspace_members()") : main.index("fn main()")]
    members = re.findall(r'crate_name: "([^"]+)"', member_source)
    cargo = tomllib.loads(sources["Cargo.toml"].decode())["workspace"]["members"]
    assert len(members) == 19 and len(cargo) == 21
    assert sorted(set(cargo) - set(members)) == ["xtask", "zellij-integration-tests"]
    print(
        json.dumps(
            {
                "status": "pass",
                "sourceFiles": 2,
                "requests": 2,
                "sourceBytes": sum(row["bytes"] for row in bindings["sources"]),
                "boundClaims": len(report["claims"]),
                "testListEntries": 19,
                "cargoWorkspaceMembers": 21,
                "upstreamExecution": False,
            }
        )
    )


if __name__ == "__main__":
    main()
