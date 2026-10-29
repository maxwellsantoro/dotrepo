"""One public bare-Git transfer; source bytes are never checked out or executed."""

from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import resource
import select
import signal
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/maxwell/projects/agent/dotrepo")
REV = "343bb382d2192b88d84af49971bb5cb99bee268c"
TREE = "b10e2fc106b7ea146f5d31f56ca0386688275aa7"
COMPRESSED, EXPANDED, PER_FILE, MEMBERS = 64 * 1024**2, 256 * 1024**2, 16 * 1024**2, 50000


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            digest.update(raw)
    return digest.hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    plan_raw = (HERE / "plan.json").read_bytes()
    plan = json.loads(plan_raw)
    assert plan["scriptSha256"] == file_sha(Path(__file__))
    assert not (HERE / "acquisition.json").exists(), "no retry"
    start = time.monotonic()
    deadline = start + 300
    repo = HERE / "objects.git"
    (HERE / "empty-home").mkdir()
    (HERE / "empty-xdg").mkdir()
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(HERE / "empty-home"),
        "XDG_CONFIG_HOME": str(HERE / "empty-xdg"),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/usr/bin/false",
        "SSH_ASKPASS": "/usr/bin/false",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    git = [
        "/usr/bin/git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "credential.helper=",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.https.allow=always",
        "-c",
        "http.followRedirects=false",
        "-c",
        "fetch.fsckObjects=true",
        "-c",
        "transfer.fsckObjects=true",
        "-c",
        "fetch.unpackLimit=0",
        "-c",
        "gc.auto=0",
        "-c",
        "maintenance.auto=false",
        "-c",
        "pack.threads=1",
        "-c",
        "pack.windowMemory=32m",
    ]
    peak = 0
    receipts = []

    def remaining():
        left = deadline - time.monotonic()
        assert left > 0, "total deadline"
        return left

    def object_bytes():
        return (
            sum(p.stat().st_size for p in (repo / "objects").rglob("*") if p.is_file())
            if repo.exists()
            else 0
        )

    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (COMPRESSED, COMPRESSED))

    def invoke(label, args, cwd, network=False):
        nonlocal peak
        folder = HERE / "logs" / label
        folder.mkdir(parents=True)
        entered, stamp = time.monotonic(), datetime.now(timezone.utc).isoformat()
        error = None
        with (folder / "stdout.bin").open("wb") as out, (folder / "stderr.bin").open("wb") as err:
            proc = subprocess.Popen(
                [*git, *args],
                cwd=cwd,
                env=env,
                stdout=out,
                stderr=err,
                start_new_session=True,
                preexec_fn=limits,
            )
            while proc.poll() is None:
                current = object_bytes()
                peak = max(peak, current)
                if time.monotonic() >= deadline:
                    error = "total-deadline"
                elif current > COMPRESSED:
                    error = "compressed-object-limit"
                elif (folder / "stdout.bin").stat().st_size + (
                    folder / "stderr.bin"
                ).stat().st_size > 8 * 1024**2:
                    error = "command-output-limit"
                if error:
                    os.killpg(proc.pid, signal.SIGKILL)
                    break
                time.sleep(0.05)
            proc.wait(timeout=10)
        receipt = {
            "argv": [*git, *args],
            "cwd": str(cwd),
            "environment": env,
            "networkAttempt": network,
            "startedAt": stamp,
            "elapsedSeconds": time.monotonic() - entered,
            "exitCode": proc.returncode,
            "error": error,
            "stdoutSha256": file_sha(folder / "stdout.bin"),
            "stderrSha256": file_sha(folder / "stderr.bin"),
            "transportBytes": None,
            "costUsd": None,
        }
        (folder / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        receipts.append(receipt)
        assert proc.returncode == 0 and error is None, (label, proc.returncode, error)
        remaining()
        return (folder / "stdout.bin").read_bytes()

    record = {
        "repository": "github.com/docker/compose",
        "revision": REV,
        "expectedTree": TREE,
        "planSha256": sha(plan_raw),
        "state": "incomplete",
        "fetchAttempts": 0,
        "upstreamExecuted": False,
        "checkoutPerformed": False,
        "indexConsulted": False,
        "providerCalls": 0,
        "actualAdmission": False,
        "confidencePromotion": False,
        "costUsd": None,
    }
    batch = None
    try:
        invoke("git-init", ["init", "--bare", "--template=", str(repo)], HERE)
        record["fetchAttempts"] = 1
        invoke(
            "git-fetch",
            [
                "fetch",
                "--depth=1",
                "--no-tags",
                "--no-recurse-submodules",
                "--keep",
                "https://github.com/docker/compose.git",
                REV,
            ],
            repo,
            True,
        )
        record["compressedObjectBytes"] = object_bytes()
        assert record["compressedObjectBytes"] <= COMPRESSED
        actual = invoke("revision", ["rev-parse", "FETCH_HEAD"], repo).decode().strip()
        assert actual == REV
        commit = invoke("commit-object", ["cat-file", "-p", REV], repo)
        assert hashlib.sha1(f"commit {len(commit)}\0".encode() + commit).hexdigest() == REV
        assert commit.splitlines()[0] == b"tree " + TREE.encode()
        listing = invoke("recursive-tree", ["ls-tree", "-r", "-t", "-z", REV], repo)
        entries, trees = {}, {"": TREE}
        for raw in listing.split(b"\0"):
            if not raw:
                continue
            metadata, name_raw = raw.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            name = name_raw.decode("utf-8", errors="strict")
            parts = PurePosixPath(name).parts
            assert (
                parts
                and not name.startswith("/")
                and all(p not in (".", "..", ".git") for p in parts)
            )
            assert (
                "\\" not in name
                and not (len(name) > 1 and name[1] == ":")
                and not any(ord(c) < 32 or ord(c) == 127 for c in name)
                and len(name_raw) <= 4096
            )
            assert name not in entries and name not in trees
            if kind == "tree":
                assert mode == "040000"
                trees[name] = oid
            else:
                assert mode in ("100644", "100755", "120000", "160000")
                assert kind == ("commit" if mode == "160000" else "blob")
                entries[name] = {"mode": mode, "kind": kind, "gitOid": oid}
            assert len(entries) + len(trees) <= MEMBERS, "member limit"

        # Rebuild every directory tree from exact recursive path/mode/object data.
        def parent(name):
            value = PurePosixPath(name).parent.as_posix()
            return "" if value == "." else value

        for directory, expected in trees.items():
            children = []
            for name, row in entries.items():
                if parent(name) == directory:
                    children.append((PurePosixPath(name).name, row["mode"], row["gitOid"]))
            for name, oid in trees.items():
                if name and parent(name) == directory:
                    children.append((PurePosixPath(name).name, "40000", oid))
            children.sort(key=lambda r: r[0].encode() + (b"/" if r[1] == "40000" else b""))
            raw = b"".join(
                mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(oid)
                for name, mode, oid in children
            )
            assert hashlib.sha1(f"tree {len(raw)}\0".encode() + raw).hexdigest() == expected, (
                directory
            )
            remaining()
        stderr = (HERE / "logs/batch-stderr.bin").open("wb")
        batch = subprocess.Popen(
            [*git, "cat-file", "--batch"],
            cwd=repo,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            bufsize=0,
        )
        os.set_blocking(batch.stdout.fileno(), False)

        def read_exact(size):
            output = bytearray()
            while len(output) < size:
                assert select.select([batch.stdout], [], [], remaining())[0], "batch deadline"
                raw = os.read(batch.stdout.fileno(), min(size - len(output), 1024**2))
                assert raw, "batch truncated"
                output.extend(raw)
            return bytes(output)

        total, links, gitlinks, lfs, excerpts = 0, {}, {}, [], {}
        archive = HERE / "source.tar"
        with tarfile.open(archive, "w") as output:
            for name, row in entries.items():
                remaining()
                if row["kind"] == "commit":
                    gitlinks[name] = row["gitOid"]
                    continue
                batch.stdin.write(row["gitOid"].encode() + b"\n")
                header = bytearray()
                while not header.endswith(b"\n"):
                    header.extend(read_exact(1))
                    assert len(header) <= 128
                oid, kind, size = header.decode().split()
                size = int(size)
                assert oid == row["gitOid"] and kind == "blob" and 0 <= size <= PER_FILE
                assert total + size <= EXPANDED
                raw = read_exact(size)
                assert read_exact(1) == b"\n"
                assert hashlib.sha1(f"blob {size}\0".encode() + raw).hexdigest() == oid
                total += size
                row.update({"bytes": size, "sha256": sha(raw)})
                item = tarfile.TarInfo(name)
                item.mode = 0o755 if row["mode"] == "100755" else 0o644
                if row["mode"] == "120000":
                    target = raw.decode("utf-8", errors="strict")
                    assert (
                        target
                        and not target.startswith("/")
                        and not (len(target) > 1 and target[1] == ":")
                        and "\\" not in target
                        and not any(ord(c) < 32 or ord(c) == 127 for c in target)
                    )
                    item.type, item.linkname = tarfile.SYMTYPE, target
                    item.mode = 0o777
                    links[name] = target
                    row["target"] = target
                    output.addfile(item)
                else:
                    item.size = size
                    output.addfile(item, io.BytesIO(raw))
                assert output.offset <= EXPANDED
                if raw.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                    lfs.append(name)
                if name in ("go.mod", "BUILDING.md"):
                    excerpts[name] = raw.decode().splitlines()[:45]
        batch.stdin.close()
        assert batch.wait(timeout=remaining()) == 0
        batch.stdout.close()
        stderr.close()
        batch = None
        assert archive.stat().st_size <= EXPANDED
        archive_names = set()
        with tarfile.open(archive, "r:") as checked:
            for member in checked:
                remaining()
                assert member.name in entries and member.name not in archive_names
                archive_names.add(member.name)
                row = entries[member.name]
                if row["mode"] == "120000":
                    assert member.issym() and member.linkname == row["target"]
                else:
                    assert (
                        member.isfile()
                        and member.size == row["bytes"]
                        and member.mode == (0o755 if row["mode"] == "100755" else 0o644)
                    )
                    assert sha(checked.extractfile(member).read()) == row["sha256"]
        assert archive_names == set(entries) - set(gitlinks)
        logical = set(entries) | set(trees)
        for name, target in links.items():
            todo = list(
                PurePosixPath(name).parent.parts if str(PurePosixPath(name).parent) != "." else ()
            ) + target.split("/")
            done, hops = [], 0
            while todo:
                part = todo.pop(0)
                if part in ("", "."):
                    continue
                if part == "..":
                    assert done, "link escapes root"
                    done.pop()
                    continue
                current = "/".join([*done, part])
                assert current in logical, "dangling link"
                if current in links:
                    hops += 1
                    assert hops <= 40, "cyclic/long link"
                    todo = links[current].split("/") + todo
                else:
                    done.append(part)
                    assert not todo or current in trees, "link crosses file"
        selected = (
            ROOT
            / "benchmarks/head-to-head/e1-qualification-20261029/go/sources/github.com/docker/compose"
        )
        overlap = []
        for p in sorted(selected.rglob("*")):
            if p.is_file():
                name = p.relative_to(selected).as_posix()
                assert entries[name]["sha256"] == file_sha(p), name
                overlap.append({"path": name, "sha256": file_sha(p)})
        assert len(overlap) == 12
        compressed = HERE / "source.tar.gz"
        with archive.open("rb") as src, compressed.open("xb") as dst:
            with gzip.GzipFile(filename="", fileobj=dst, mode="wb", mtime=0) as out:
                while raw := src.read(1024**2):
                    remaining()
                    out.write(raw)
                    assert dst.tell() <= COMPRESSED
        assert compressed.stat().st_size <= COMPRESSED
        write(
            "inventory.json",
            {
                "repository": record["repository"],
                "revision": REV,
                "rootTreeSha1": TREE,
                "entries": entries,
                "trees": trees,
                "fullTrackedGitTree": True,
                "missingSubmodules": gitlinks,
                "lfsPointers": lfs,
                "expandedBlobBytes": total,
            },
        )
        write("excerpts.json", excerpts)
        write("overlap.json", overlap)
        record.update(
            {
                "state": "full-frozen-git-source-acquired",
                "members": len(entries),
                "directories": len(trees),
                "expandedBlobBytes": total,
                "archivePath": str(archive),
                "archiveBytes": archive.stat().st_size,
                "archiveSha256": file_sha(archive),
                "compressedArchivePath": str(compressed),
                "compressedArchiveBytes": compressed.stat().st_size,
                "compressedArchiveSha256": file_sha(compressed),
                "inventorySha256": file_sha(HERE / "inventory.json"),
                "overlapFilesMatched": len(overlap),
                "symlinks": links,
                "missingSubmodules": gitlinks,
                "lfsPointers": lfs,
                "allBlobHashesVerified": True,
                "allRecursiveTreeHashesReconstructed": True,
                "selfContainedTrackedSource": not gitlinks and not lfs,
                "archiveMembersVerified": len(archive_names),
            }
        )
        remaining()
    except Exception as error:
        record["state"] = "source-acquisition-incomplete"
        record["failure"] = type(error).__name__ + ": " + str(error)
    finally:
        if batch is not None:
            batch.kill()
            batch.wait(timeout=10)
        record.update(
            {
                "elapsedSeconds": time.monotonic() - start,
                "peakObservedObjectBytes": peak,
                "compressedObjectBytesFinal": object_bytes(),
                "receipts": receipts,
                "transportAccountingLimit": "Compressed Git-object disk bytes bounded/measured; exact HTTPS wire bytes and metered cost unavailable.",
            }
        )
        write("acquisition.json", record)
    print(
        json.dumps(
            {
                k: record.get(k)
                for k in ("state", "members", "expandedBlobBytes", "archiveSha256", "failure")
            }
        )
    )


if __name__ == "__main__":
    main()
