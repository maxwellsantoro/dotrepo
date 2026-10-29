"""Data-only frozen source verification; no Git/upstream process or extraction."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

HERE = Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024**2):
            value.update(block)
    return value.hexdigest()


def main():
    frozen = json.loads((HERE / "FREEZE.json").read_bytes())
    for name, expected in frozen["artifacts"].items():
        p = HERE / name
        assert p.is_file() and not p.is_symlink()
        assert p.stat().st_size == expected["bytes"] and digest(p) == expected["sha256"], name
    inventory = json.loads((HERE / "inventory.json").read_bytes())
    entries, trees = inventory["entries"], inventory["trees"]
    commit = (HERE / "logs/commit-object/stdout.bin").read_bytes()
    assert (
        hashlib.sha1(f"commit {len(commit)}\0".encode() + commit).hexdigest()
        == inventory["revision"]
    )
    assert commit.splitlines()[0] == b"tree " + inventory["rootTreeSha1"].encode()

    def parent(name):
        value = PurePosixPath(name).parent.as_posix()
        return "" if value == "." else value

    for directory, expected in trees.items():
        rows = [
            (PurePosixPath(n).name, v["mode"], v["gitOid"])
            for n, v in entries.items()
            if parent(n) == directory
        ]
        rows += [
            (PurePosixPath(n).name, "40000", oid)
            for n, oid in trees.items()
            if n and parent(n) == directory
        ]
        rows.sort(key=lambda r: r[0].encode() + (b"/" if r[1] == "40000" else b""))
        raw = b"".join(
            mode.encode() + b" " + n.encode() + b"\0" + bytes.fromhex(oid) for n, mode, oid in rows
        )
        assert hashlib.sha1(f"tree {len(raw)}\0".encode() + raw).hexdigest() == expected
    names = set()
    with tarfile.open(HERE / "source.tar", "r:") as archive:
        for member in archive:
            assert member.name in entries and member.name not in names
            names.add(member.name)
            row = entries[member.name]
            if row["mode"] == "120000":
                assert member.issym() and member.linkname == row["target"]
                raw = member.linkname.encode()
            else:
                assert member.isfile() and member.size == row["bytes"]
                assert member.mode == (0o755 if row["mode"] == "100755" else 0o644)
                raw = archive.extractfile(member).read()
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
            assert hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == row["gitOid"]
    assert names == set(entries)
    print(
        f"{len(frozen['artifacts'])} artifacts, {len(names)} source members, {len(trees)} trees match"
    )


if __name__ == "__main__":
    main()
