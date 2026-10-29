"""Independent retained-byte checks; never extract or execute package content."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROPOSAL = ROOT / "benchmarks/head-to-head/f05-go01-next-qualification-20261029"
PROJECTION = PROPOSAL / "go-only-projection-1"
PARENT_PACKET = ROOT / "benchmarks/head-to-head/f05-go01-dependency-download-result-20261029"
PARENT = Path("/private/tmp/dotrepo-go01-dependency-download-cache-20261029-1/cache.tar")
DERIVED = Path("/private/tmp/dotrepo-go01-go-cache-projection-20261029-1/cache-go-only.tar")
SOURCE = Path("/tmp/dotrepo-f05-qualification-20261029-tranche-1/go-01-full/runtime-source.tar")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def require(value, reason):
    if not value:
        raise AssertionError(reason)


def freeze_check(directory, expected):
    require(sha(directory / "freeze.json") == expected, "freeze digest")
    items = load(directory / "freeze.json")["artifactSha256"]
    for name, digest in items.items():
        require(sha(directory / name) == digest, f"frozen artifact {name}")
    return len(items)


def safe(name):
    return (
        0 < len(name) <= 4096
        and not any(c in name for c in "\\:")
        and not any(ord(c) < 32 or ord(c) == 127 for c in name)
        and all(part not in ("", ".", "..") for part in name.split("/"))
    )


def inspect_archive(path, expected, normalized):
    actual = {}
    order = []
    with tarfile.open(path, "r:") as archive:
        for member in archive:
            name = member.name
            require(safe(name) and name not in actual, f"path {name}")
            require(member.isfile() and not member.sparse, f"regular member {name}")
            require(name in expected and member.size <= 134217728, f"expected member {name}")
            require(set(member.pax_headers) <= {"path"}, f"PAX metadata {name}")
            if member.pax_headers:
                require(member.pax_headers["path"] == name, f"PAX path {name}")
            if normalized:
                require(
                    member.uid == member.gid == member.mtime == 0
                    and member.uname == member.gname == "",
                    f"normalized metadata {name}",
                )
            stream = archive.extractfile(member)
            digest = hashlib.sha256()
            count = 0
            while chunk := stream.read(1048576):
                digest.update(chunk)
                count += len(chunk)
            require(count == member.size, f"short member {name}")
            actual[name] = {"sha256": digest.hexdigest(), "bytes": count, "mode": member.mode}
            order.append(name)
    require(actual == expected, "entire path/bytes/mode map")
    if normalized:
        require(order == sorted(order), "sorted derived member order")
    return {
        "files": len(actual),
        "expandedBytes": sum(item["bytes"] for item in actual.values()),
        "allRegularMemberPathsBytesModesEqual": True,
        "normalizedMetadataAndOrder": normalized,
    }


def main(output):
    start = time.monotonic()
    report = {
        "state": "incomplete-independent-byte-check",
        "execution": "Local stdlib reads/hashes only; no source extraction/execution or daemon/network calls",
    }
    try:
        report["proposalArtifacts"] = freeze_check(
            PROPOSAL, "c2f6160768d023eee42f62e51511a5af53d448fff0d7f1edc807bc4a9623a09d"
        )
        report["projectionArtifacts"] = freeze_check(
            PROJECTION, "424d9381ba042a60ba562cae5236279225d27c984a17636a8fa7e8d1d7e256ad"
        )
        bindings = {
            SOURCE: "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f",
            PARENT: "583fad501fa7b1a1a6d85ab8fe4b890786e39c1e016f785d6d3fb9d060383284",
            DERIVED: "76ea2bfa6725335b889d44fed07f40f6eeb804d124d683ad4f2c0a6a2607bcfd",
            PARENT_PACKET
            / "evidence/inventory.json": "900550d8e44827f96a9e7db46f3b4551db734938564c8921473fe56a6257415c",
        }
        for path, expected in bindings.items():
            require(path.is_file() and sha(path) == expected, f"input digest {path}")
        report["inputs"] = {
            str(p): {"sha256": h, "bytes": p.stat().st_size} for p, h in bindings.items()
        }

        selected_source = load(PROPOSAL / "selected-source-members.json")
        selected_source.update(load(PROPOSAL / "additional-source-members.json"))
        spans = load(PROPOSAL / "source-spans.json")
        tool_sources = load(PROPOSAL / "retained-go-tool-source.json")
        tools = tool_sources["members"]
        wanted = set(selected_source) | {s["source"] for s in spans if s["source"] not in tools}
        source_bytes = {}
        with tarfile.open(SOURCE, "r:") as archive:
            for member in archive:
                if member.name in wanted:
                    require(member.isfile() and member.size < 8388608, "bounded source member")
                    source_bytes[member.name] = archive.extractfile(member).read()
        require(set(source_bytes) == wanted, "all retained source paths")
        export = Path(tool_sources["retainedExportPath"])
        require(
            sha(export) == tool_sources["exportSha256FromFrozenAudit"], "Go image export digest"
        )
        with tarfile.open(export, "r:") as archive:
            for member in archive:
                if member.name in tools:
                    require(member.isfile() and member.size < 8388608, "bounded tool source")
                    raw = archive.extractfile(member).read()
                    require(
                        tools[member.name]["text"].encode() == raw
                        and sha_bytes(raw) == tools[member.name]["sha256"],
                        f"retained Go source {member.name}",
                    )
                    source_bytes[member.name] = raw
        require(set(tools) <= set(source_bytes), "all Go tool source paths")
        for name, item in selected_source.items():
            raw = source_bytes[name]
            require(sha_bytes(raw) == item["sha256"], f"source digest {name}")
            require(item["text"].encode() == raw, f"source raw text including CRLF {name}")
        for span in spans:
            raw = source_bytes[span["source"]]
            require(sha_bytes(raw) == span["sourceSha256"], "source span binding")
            # Display excerpts use LF; original exact bytes remain in text records/archive.
            lines = raw.decode().splitlines()
            shown = "\n".join(lines[span["startLine"] - 1 : span["endLine"]]) + "\n"
            require(shown == span["excerpt"], f"display span {span['source']}")
        report["sourceChecks"] = {
            "exactRawTextAndShaMembers": len(selected_source),
            "lineAndHashBoundDisplaySpans": len(spans),
            "exactGoToolSourcesFromFrozenImageExport": len(tools),
            "spanDisplayNewlines": "LF; checked against raw source splitlines, not a claim of raw excerpt bytes",
        }
        all_members = load(PARENT_PACKET / "evidence/inventory.json")["members"]
        selected = {n: v for n, v in all_members.items() if n.startswith("go/pkg/mod/")}
        selected_sha = sha_bytes(
            (json.dumps(selected, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )
        require(
            selected_sha == "bf5aefaa56222f9337752edebddd50d2cfc4759ed8954f7f9f74bf3d70765131",
            "selected map digest",
        )
        require(
            load(PROJECTION / "inventory.json")["members"] == selected,
            "projection inventory exact set",
        )
        report["parentArchive"] = inspect_archive(PARENT, all_members, False)
        report["derivedArchive"] = inspect_archive(DERIVED, selected, True)
        report["selectedMemberMapSha256"] = selected_sha
        report["ordinaryGoPackageJsAssets"] = sorted(
            n for n in selected if n.endswith(".js") or n.endswith("/package.json")
        )
        report["selectionInterpretation"] = (
            "All and only go/pkg/mod/ regular members; no npm subtree/build-cache root. Ordinary Go-package JS/package.json assets retained; no universal no-JavaScript claim."
        )
        for path, expected in bindings.items():
            require(sha(path) == expected, f"input unchanged {path}")
        report["state"] = "passed-independent-source-and-projection-byte-check"
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["elapsedSeconds"] = time.monotonic() - start
        with output.open("x") as stream:
            stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "inputs"}, indent=2))


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", required=True, type=Path, help="New exclusive JSON receipt path"
    )
    main(parser.parse_args().output)
