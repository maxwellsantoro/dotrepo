"""Authorized owned Node fs/crypto controls only; no project or upstream imports."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

import collection

HERE = Path(__file__).resolve().parent


def observe_python(root):
    rows, total = [], 0
    for folder, directories, names in os.walk(root, followlinks=False):
        parent = Path(folder)
        relative = parent.relative_to(root).as_posix()
        rows.append([relative, "directory"])
        for name in list(directories):
            path = parent / name
            if path.is_symlink():
                rows.append([path.relative_to(root).as_posix(), "symlink", os.readlink(path)])
                directories.remove(name)
        for name in names:
            path = parent / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                rows.append([relative, "symlink", os.readlink(path)])
            elif stat.S_ISREG(info.st_mode):
                rows.append([relative, "file", collection.file_sha(path), info.st_size])
                total += info.st_size
            else:
                rows.append([relative, "special"])
    rows.sort(key=lambda row: row[0].encode())
    raw = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    ).encode()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "entries": len(rows), "bytes": total}, rows


def main():
    node = Path(shutil.which("node")).resolve(strict=True)
    algorithm = (HERE / "tree-observer.js").read_text()
    checks = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-observer-control-") as temporary:
        parent = Path(temporary).resolve()
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(parent)}
        version = (
            subprocess.run(
                [str(node), "--version"],
                capture_output=True,
                check=True,
                timeout=5,
                env=environment,
            )
            .stdout.decode()
            .strip()
        )
        root = parent / "source"
        (root / "nested").mkdir(parents=True)
        (root / "empty/subdir").mkdir(parents=True)
        fixtures = {"a": b"owned\x00\xff", "nested/\ue000": b"BMP", "nested/\U00010000": b"astral"}
        for name, data in fixtures.items():
            (root / name).write_bytes(data)

        def check(name):
            expected, rows = observe_python(root)
            observed = subprocess.run(
                [str(node), "-e", algorithm, str(root)],
                capture_output=True,
                check=True,
                timeout=5,
                env=environment,
            )
            assert not observed.stderr and len(observed.stdout) < 4096
            actual = json.loads(observed.stdout)
            assert actual == expected, (name, actual, expected)
            checks.append(
                {"case": name, "passed": True, "observed": actual, "rowsSha256": expected["sha256"]}
            )
            return actual, rows

        baseline, rows = check("ordinary-binary-bytes-and-Unicode-BMP-astral")
        files = {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in fixtures.items()
        }
        assert collection.tree_expected(files, {"empty/subdir"}) == baseline
        utf16 = sorted((row[0] for row in rows), key=lambda name: name.encode("utf-16-be"))
        assert utf16 != [row[0] for row in rows]
        (root / "new").write_bytes(b"")
        added, _ = check("addition")
        assert added != baseline
        (root / "a").unlink()
        deleted, _ = check("deletion")
        assert deleted != added
        (root / "new").unlink()
        (root / "new").mkdir()
        typed, _ = check("file-to-directory")
        assert typed != deleted
        (root / "new").rmdir()
        (parent / "outside-sentinel").write_bytes(b"must-not-be-followed")
        (root / "new").symlink_to("../outside-sentinel")
        linked, _ = check("file-to-symlink-no-follow")
        assert linked != typed and linked["bytes"] == typed["bytes"]
        (root / "nested/\ue000").write_bytes(b"changed")
        changed, _ = check("regular-byte-change")
        assert changed != linked
    collection.write(
        HERE / "observer-controls.json",
        {
            "passed": len(checks),
            "controls": checks,
            "node": {
                "resolvedPath": str(node),
                "sha256": collection.file_sha(node),
                "version": version,
                "runtimeRole": "host owned data-observer validation, not frozen image/upstream execution",
            },
            "algorithmSha256": collection.file_sha(HERE / "tree-observer.js"),
            "utf8VsUtf16OrderingDiffersOnFixture": True,
            "nodeBuiltinImportsOnly": ["node:fs", "node:path", "node:crypto"],
            "upstreamNativeCollectionOrTaskRan": False,
            "networkDaemonPackageGoCargoProviderCalls": 0,
        },
    )
    print(
        json.dumps(
            {
                "passed": len(checks),
                "nodeVersion": version,
                "upstreamNativeCollectionOrTaskRan": False,
            }
        )
    )


if __name__ == "__main__":
    main()
