"""Read-only replay of exported tar and evidence bindings; no Docker calls."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(path):
    return json.loads(path.read_bytes())


def sha_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    freeze = load(HERE / "plan-freeze.json")
    for name, digest in freeze["files"].items():
        assert sha_file(HERE / name) == digest
    receipt = load(HERE / "export-receipt.json")
    inventory = load(HERE / "inventory.json")["files"]
    archive = Path(receipt["exportPath"])
    assert archive.stat().st_size == receipt["exportBytes"] <= 4 * 1024**3
    assert sha_file(archive) == receipt["exportSha256"]
    assert len(inventory) == receipt["members"] <= 200000 and receipt["elapsedSeconds"] < 600
    count = Counter()
    seen = set()
    selected = {}
    with tarfile.open(archive, mode="r:") as exported:
        for member in exported:
            assert member.name not in seen
            seen.add(member.name)
            row = inventory[member.name]
            assert (row["mode"], row["uid"], row["gid"], row["size"], row["type"]) == (
                oct(member.mode),
                member.uid,
                member.gid,
                member.size,
                member.type.decode("ascii", errors="backslashreplace"),
            )
            if member.isfile():
                stream = exported.extractfile(member)
                digest = hashlib.sha256()
                capture = (
                    bytearray()
                    if member.name
                    in (
                        "etc/shadow",
                        "etc/gshadow",
                        "etc/group",
                        "etc/passwd",
                        "usr/local/lib/node_modules/npm/.npmrc",
                        "usr/local/go/test/typeparam/issue51219.out",
                        "usr/share/gcc/python/libstdcxx/__init__.py",
                    )
                    else None
                )
                size = 0
                while chunk := stream.read(1024**2):
                    digest.update(chunk)
                    size += len(chunk)
                    if capture is not None:
                        capture.extend(chunk)
                assert digest.hexdigest() == row["sha256"] and size == member.size
                if capture is not None:
                    selected[member.name] = bytes(capture)
                count["regularFiles"] += 1
                count["regularBytes"] += size
            if member.issym() or member.islnk():
                assert row["linkTarget"] == member.linkname
    assert seen == set(inventory)
    assert count["regularFiles"] == receipt["statistics"]["regularFiles"]
    assert count["regularBytes"] == receipt["statistics"]["regularBytes"]
    for name in ("etc/shadow", "etc/gshadow"):
        assert all(line.split(b":")[1][:1] in (b"*", b"!") for line in selected[name].splitlines())
    for name in ("etc/passwd", "etc/group"):
        assert all(
            line.split(b":")[1] in (b"x", b"*", b"!") for line in selected[name].splitlines()
        )
    assert not selected["usr/local/lib/node_modules/npm/.npmrc"]
    assert selected["usr/local/go/test/typeparam/issue51219.out"] == b"{}\n"
    assert selected["usr/share/gcc/python/libstdcxx/__init__.py"] == b"\n"
    assert (
        len(load(HERE / "canonical-exclusions.json")) == receipt["canonicalSizeExcludedFiles"] == 15
    )
    assert not receipt["nonemptyProtectedMatches"] and not receipt["knownSourceArchiveMatches"]
    for path in sorted(HERE.glob("*-receipt.json")):
        if path.name == "export-receipt.json":
            continue
        value = load(path)
        label = path.name.removesuffix("-receipt.json")
        assert sha_file(HERE / (label + "-stdout.txt")) == value["stdoutSha256"]
        assert sha_file(HERE / (label + "-stderr.txt")) == value["stderrSha256"]
    image = load(HERE / "image-inspect-stdout.txt")[0]
    before = load(HERE / "container-inspect-stdout.txt")[0]
    assert image["Id"] == before["Image"] == receipt["image"]
    assert not before["Mounts"] and not before["State"]["Running"]
    assert before["State"]["StartedAt"].startswith("0001-")
    assert before["HostConfig"]["NetworkMode"] == "none" and before["HostConfig"]["ReadonlyRootfs"]
    assert load(HERE / "cleanup-receipt.json")["exitCode"] == 0
    assert (
        load(HERE / "absence-receipt.json")["exitCode"] != 0
        and load(HERE / "cleanup-check.json")["absent"]
    )
    for item in load(HERE / "source-content-overlaps.json")["inventoryBindings"]:
        assert sha_file(ROOT / item["path"]) == item["sha256"]
    print(
        json.dumps(
            {
                "result": "pass",
                "rawExportSha256": receipt["exportSha256"],
                "rawExportBytes": receipt["exportBytes"],
                "allMemberMetadataVerified": len(seen),
                "regularFilesRehashed": count["regularFiles"],
                "regularBytesRehashed": count["regularBytes"],
                "systemAccountsLockedOrPlaceholder": True,
                "smallGenericSourceMatchesVerified": True,
                "planAndReceiptAndSourceInventoryBindingsVerified": True,
                "neverStartedAndCleanupEvidenceVerified": True,
                "newDockerOrNetworkOrProviderCalls": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
