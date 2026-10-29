"""Deterministic source-data-only Go download projection. No extraction or execution."""

import argparse
import hashlib
import json
from pathlib import Path
import stat
import tarfile
import time

HERE = Path(__file__).resolve().parent
BASE = Path("/Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head")
PARENT = Path("/private/tmp/dotrepo-go01-dependency-download-cache-20261029-1/cache.tar")
INVENTORY = BASE / "f05-go01-dependency-download-result-20261029/evidence/inventory.json"
PARENT_SHA = "583fad501fa7b1a1a6d85ab8fe4b890786e39c1e016f785d6d3fb9d060383284"
INVENTORY_SHA = "900550d8e44827f96a9e7db46f3b4551db734938564c8921473fe56a6257415c"
SET_SHA = "bf5aefaa56222f9337752edebddd50d2cfc4759ed8954f7f9f74bf3d70765131"
DECLARATION_SHA = "8b08e9a5d06e32cf43843f42c911f4df3464ca81ec837576228dcd139cdbb0d7"
LIMIT = 536870912


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def safe(name):
    return (
        isinstance(name, str)
        and 0 < len(name) <= 4096
        and not any(c in name for c in "\\:")
        and not any(ord(c) < 32 or ord(c) == 127 for c in name)
        and all(x not in ("", ".", "..") for x in name.split("/"))
    )


class Reader:
    def __init__(self, stream, check):
        self.stream, self.check, self.hash, self.count = stream, check, hashlib.sha256(), 0

    def read(self, size=-1):
        self.check()
        require(0 <= size <= 1048576, "reader chunk bound")
        raw = self.stream.read(size)
        self.hash.update(raw)
        self.count += len(raw)
        return raw


class Writer:
    def __init__(self, stream, check):
        self.stream, self.check, self.count = stream, check, 0

    def write(self, data):
        self.check()
        require(self.count + len(data) <= LIMIT, "plain transport cap")
        self.count += len(data)
        return self.stream.write(data)


def derive(output_root):
    output_root = Path(output_root)
    output_root.mkdir()
    start = time.monotonic()
    deadline = start + 120
    result = {
        "state": "incomplete-local-data-projection",
        "outputRoot": str(output_root.resolve()),
        "costUsd": None,
        "costExclusion": "Unmetered local byte-copy/hash work; no setup/native/provider activity.",
        "sourcePackageCodeExecuted": False,
        "daemonNetworkPackageGoCargoProviderCalls": 0,
        "cacheGloballyQualified": False,
        "nativeTaskAdmitted": False,
        "campaignAdmitted": False,
    }
    write(HERE / "attempt.json", result)

    def check():
        require(time.monotonic() < deadline, "120second data projection deadline")

    try:
        require(
            stat.S_ISREG(PARENT.lstat().st_mode) and PARENT.stat().st_size == 366622720 <= LIMIT,
            "parent shape/size",
        )
        require(
            sha(PARENT) == PARENT_SHA and sha(INVENTORY) == INVENTORY_SHA,
            "changed parent archive/inventory",
        )
        declaration = HERE.parent / "go-cache-projection-proposal.json"
        require(sha(declaration) == DECLARATION_SHA, "changed projection declaration")
        all_files = json.loads(INVENTORY.read_text())["members"]
        selected = {k: v for k, v in all_files.items() if k.startswith("go/pkg/mod/")}
        require(
            hashlib.sha256(canonical(selected)).hexdigest() == SET_SHA,
            "changed selected-member map",
        )
        require(
            len(selected) == 14922 and sum(v["bytes"] for v in selected.values()) == 278162103,
            "selected set bound",
        )
        target = output_root / "cache-go-only.tar"
        with tarfile.open(PARENT, "r:") as incoming, target.open("xb") as raw_output:
            members = {}
            for member in incoming:
                check()
                name = member.name.rstrip("/") if member.isdir() else member.name
                require(safe(name) and name not in members, "unsafe/duplicate parent path")
                members[name] = member
            require(set(selected) <= set(members), "missing parent selected members")
            writer = Writer(raw_output, check)
            with tarfile.open(fileobj=writer, mode="w|", format=tarfile.PAX_FORMAT) as outgoing:
                for name, expected in sorted(selected.items()):
                    check()
                    member = members[name]
                    require(
                        member.isfile()
                        and not member.sparse
                        and member.size == expected["bytes"]
                        and member.mode == expected["mode"],
                        "selected regular/type/size/mode mismatch",
                    )
                    require(
                        set(member.pax_headers) <= {"path"}
                        and (not member.pax_headers or member.pax_headers["path"] == member.name),
                        "unsupported parent metadata",
                    )
                    entry = tarfile.TarInfo(name)
                    entry.type = tarfile.REGTYPE
                    entry.size = member.size
                    entry.mode = member.mode
                    entry.uid = entry.gid = 0
                    entry.uname = entry.gname = ""
                    entry.mtime = 0
                    entry.pax_headers = {}
                    reader = Reader(incoming.extractfile(member), check)
                    outgoing.addfile(entry, reader)
                    require(
                        reader.count == member.size
                        and reader.hash.hexdigest() == expected["sha256"],
                        "parent content differs from declared byte identity",
                    )
        actual = {}
        with tarfile.open(target, "r:") as derived:
            for member in derived:
                check()
                name = member.name
                require(
                    safe(name)
                    and name.startswith("go/pkg/mod/")
                    and name not in actual
                    and member.isfile()
                    and not member.sparse,
                    "invalid derived member",
                )
                require(
                    member.uid == member.gid == member.mtime == 0
                    and member.uname == member.gname == "",
                    "derived metadata mismatch",
                )
                require(
                    set(member.pax_headers) <= {"path"}
                    and (not member.pax_headers or member.pax_headers["path"] == member.name),
                    "derived extended metadata mismatch",
                )
                require(
                    name in selected and 0 <= member.size <= 134217728,
                    "unexpected/oversized derived member",
                )
                stream = derived.extractfile(member)
                digest = hashlib.sha256()
                count = 0
                for chunk in iter(lambda: stream.read(1048576), b""):
                    check()
                    digest.update(chunk)
                    count += len(chunk)
                actual[name] = {"sha256": digest.hexdigest(), "bytes": count, "mode": member.mode}
        require(
            actual == selected, "derived byte/path/mode map differs from exact parent selection"
        )
        require(sha(PARENT) == PARENT_SHA, "parent changed after projection")
        inventory = {
            "revision": "25f823dc198a00744b458a7bc6984359f0dd7cac",
            "files": {k: v["sha256"] for k, v in actual.items()},
            "members": actual,
            "expandedBytes": 278162103,
        }
        write(HERE / "inventory.json", inventory)
        provenance = {
            "state": "deterministic-go-only-data-projection-unadmitted",
            "parentArchivePath": str(PARENT),
            "parentArchiveSha256": PARENT_SHA,
            "parentInventoryPath": str(INVENTORY),
            "parentInventorySha256": INVENTORY_SHA,
            "selectedMemberMapSha256": SET_SHA,
            "projectionDeclarationSha256": DECLARATION_SHA,
            "archivePath": str(target.resolve()),
            "archiveSha256": sha(target),
            "archiveBytes": target.stat().st_size,
            "inventorySha256": sha(HERE / "inventory.json"),
            "files": 14922,
            "expandedBytes": 278162103,
            "normalization": "Sorted regular members only. Preserve exact parent content/path/filemode. uid/gid/mtime zero; uname/gname empty; POSIX PAX path metadata only where required. No directory records, npm subtree, build-cache root or synthesized package content.",
            "originalArchiveUnchanged": True,
            "semanticQualification": "Path/byte projection only; Go-module fixture/content roles retain independent audit limitations. No claim that every dependency file is source text or no binary fixtures.",
            "cacheGloballyQualified": False,
            "nativeTaskAdmitted": False,
            "campaignAdmitted": False,
        }
        write(HERE / "provenance.json", provenance)
        result.update(
            state="local-data-projection-verified-unadmitted",
            archivePath=provenance["archivePath"],
            archiveSha256=provenance["archiveSha256"],
            archiveBytes=provenance["archiveBytes"],
            files=14922,
            expandedBytes=278162103,
            parentUnchanged=True,
            allDerivedMembersComparedToParent=True,
        )
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        result["elapsedSeconds"] = time.monotonic() - start
        result["deadlineExceeded"] = result["elapsedSeconds"] > 120
        if result["deadlineExceeded"]:
            result["state"] = "incomplete-data-projection-time-limit"
        write(HERE / "result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    result = derive(args.output_root)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["state"] == "local-data-projection-verified-unadmitted" else 1)
