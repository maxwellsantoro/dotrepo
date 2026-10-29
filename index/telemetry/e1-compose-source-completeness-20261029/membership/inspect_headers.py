"""Data-only bounded tar/header retention; never imports or executes inspected code."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
ROUTING = {
    "BUILDING.md",
    "Makefile",
    "docker-bake.hcl",
    "Dockerfile",
    "go.mod",
    "relay/go.mod",
    "AGENTS.md",
    ".dockerignore",
    ".go-version",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def header(raw):
    # Inspect only comments/whitespace and the package declaration. Reject rather
    # than guessing when the first code does not have this supported spelling.
    text = raw.decode("utf-8")
    position = 1 if text.startswith("\ufeff") else 0
    while True:
        space = re.match(r"\s*", text[position:])
        position += space.end()
        if text.startswith("//", position):
            end = text.find("\n", position)
            if end < 0:
                raise ValueError("no package after comment within header cap")
            position = end + 1
        elif text.startswith("/*", position):
            end = text.find("*/", position + 2)
            if end < 0:
                raise ValueError("unclosed comment within header cap")
            position = end + 2
        else:
            break
    match = re.match(r"package[ \t]+([A-Za-z_][A-Za-z_0-9]*)[ \t]*(?:\r?\n|;|$)", text[position:])
    if match is None:
        raise ValueError("unsupported package declaration/header limit")
    end = position + match.end()
    selected = text[:end].encode()
    assert raw.startswith(selected)
    return selected, match[1], text[:position]


def main():
    plan = json.loads((HERE / "plan.json").read_bytes())
    archive = Path(plan["archive"]["path"])
    assert archive.stat().st_size == plan["archive"]["bytes"]
    assert sha(archive.read_bytes()) == plan["archive"]["sha256"]
    inventory = json.loads((HERE / "acquisition-inventory.json").read_bytes())
    headers, observed, routing, total = [], {}, [], 0
    with tarfile.open(archive, "r:") as source:
        for member in source:
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and ".." not in path.parts
            assert member.name not in observed and member.name in inventory["entries"]
            row = inventory["entries"][member.name]
            if member.issym():
                raw = member.linkname.encode()
                assert row["mode"] == "120000"
            else:
                assert member.isfile() and row["mode"] in {"100644", "100755"}
                raw = source.extractfile(member).read()
                assert (member.mode & 0o777) == int(row["mode"][-3:], 8)
            assert len(raw) == row["bytes"] and sha(raw) == row["sha256"]
            assert (
                hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                == row["gitOid"]
            )
            observed[member.name] = row
            if member.name.endswith(".go"):
                selected, package, comments = header(raw[:32768])
                assert len(selected) <= 32768
                total += len(selected)
                assert total <= 16 * 1024**2 and len(headers) < 10000
                dest = HERE / "headers" / member.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("xb") as stream:
                    stream.write(selected)
                headers.append(
                    {
                        "path": member.name,
                        "sourceSha256": row["sha256"],
                        "gitBlobSha1": row["gitOid"],
                        "sourceBytes": row["bytes"],
                        "headerSha256": sha(selected),
                        "headerBytes": len(selected),
                        "package": package,
                        "goBuild": re.findall(r"^//go:build (.+)$", comments, re.M),
                        "plusBuild": re.findall(r"^// \+build (.+)$", comments, re.M),
                    }
                )
            elif member.name in ROUTING:
                dest = HERE / "routing" / member.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("xb") as stream:
                    stream.write(raw)
                routing.append({"path": member.name, **row})
    assert observed == inventory["entries"]
    assert len(routing) <= 12 and sum(row["bytes"] for row in routing) <= 1048576
    result = {
        "state": "inert-header-and-routing-inventory-not-go-list",
        "repository": inventory["repository"],
        "revision": inventory["revision"],
        "archiveSha256": plan["archive"]["sha256"],
        "memberCountVerified": len(observed),
        "goFiles": len(headers),
        "aggregateHeaderBytes": total,
        "headers": headers,
        "routing": routing,
        "upstreamExecuted": False,
    }
    with (HERE / "headers.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {
                "goFiles": len(headers),
                "aggregateHeaderBytes": total,
                "routingFiles": len(routing),
                "constraints": sorted({c for r in headers for c in r["goBuild"]}),
            }
        )
    )


if __name__ == "__main__":
    main()
