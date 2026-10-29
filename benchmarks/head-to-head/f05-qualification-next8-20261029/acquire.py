"""Source-only exact Git-object acquisition for the unchanged remaining eight tasks.

No checkout, filters, hooks, upstream project commands, index/profile access or
model calls. Git object/archive bytes stay under the declared /tmp scratch root.
"""

from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import resource
import signal
import subprocess
import tarfile
import time

from control import HERE, sha, write

FROZEN = HERE.parent / "f05-agent-tasks-20261029"
SCRATCH = Path("/tmp/dotrepo-f05-qualification-next8-20261029")
IDS = (
    "rust-01",
    "rust-03",
    "python-01",
    "python-02",
    "python-03",
    "typescript-01",
    "typescript-03",
    "go-02",
)
COMPRESSED = 512 * 1024**2
PER_SOURCE = 1024**3
TRANCHE = 2 * 1024**3
PER_FILE = 128 * 1024**2
FILE_COUNT = 200000


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024 * 1024):
            digest.update(raw)
    return digest.hexdigest()


def object_bytes(repo):
    root = repo / "objects"
    return (
        sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        if root.exists()
        else 0
    )


def invoke(folder, label, argv, cwd, env, *, repo=None):
    logs = folder / "logs" / label
    logs.mkdir(parents=True)
    start, stamp, error = time.monotonic(), datetime.now(timezone.utc).isoformat(), None

    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (COMPRESSED, COMPRESSED))

    with (logs / "stdout.bin").open("wb") as stdout, (logs / "stderr.bin").open("wb") as stderr:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            preexec_fn=limits,
        )
        try:
            while process.poll() is None:
                if time.monotonic() - start > 600:
                    error = "timeout"
                elif repo and object_bytes(repo) > COMPRESSED:
                    error = "compressed-object-byte-limit"
                elif (logs / "stdout.bin").stat().st_size + (
                    logs / "stderr.bin"
                ).stat().st_size > 64 * 1024**2:
                    error = "command-output-byte-limit"
                if error:
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.1)
        finally:
            process.wait(timeout=10)
    receipt = {
        "argv": argv,
        "cwd": str(cwd),
        "environment": env,
        "startedAt": stamp,
        "elapsedSeconds": time.monotonic() - start,
        "exitCode": process.returncode,
        "error": error,
        "stdoutSha256": file_sha(logs / "stdout.bin"),
        "stderrSha256": file_sha(logs / "stderr.bin"),
        "costUsd": None,
        "transportBytes": None,
        "measurementExclusions": [
            "No metered host/download charge; Git transport byte count unavailable. Object/archive bytes measured separately."
        ],
    }
    write(logs / "receipt.json", receipt)
    assert process.returncode == 0 and error is None, (label, process.returncode, error)
    return (logs / "stdout.bin").read_bytes()


def acquire(task, ledger):
    task_id, revision = task["id"], task["revision"]
    folder, scratch = HERE / task_id, SCRATCH / task_id
    folder.mkdir()
    scratch.mkdir()
    home = scratch / "empty-home"
    home.mkdir()
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    git = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "credential.helper=",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.https.allow=always",
        "-c",
        "pack.windowMemory=128m",
        "-c",
        "pack.deltaCacheSize=32m",
        "-c",
        "pack.threads=1",
        "-c",
        "core.bigFileThreshold=32m",
    ]
    record = {
        "task": task,
        "state": "not-acquired",
        "indexConsulted": False,
        "modelCalls": 0,
        "upstreamProjectCodeExecuted": False,
        "costUsd": None,
        "sourceAcquisitionLimits": {
            "compressedBytes": COMPRESSED,
            "expandedSourceBytes": PER_SOURCE,
            "expandedTrancheBytes": TRANCHE,
            "fileBytes": PER_FILE,
            "filesTranche": FILE_COUNT,
        },
        "costExclusions": ["No metered host/container/download charge source."],
        "scratch": str(scratch),
        "partialExpandedBytes": 0,
    }
    started = time.monotonic()
    process = None
    try:
        assert ledger["expandedBytes"] < TRANCHE and ledger["files"] < FILE_COUNT, (
            "tranche source budget exhausted before fetch"
        )
        invoke(folder, "git-init", [*git, "init", "--bare", "objects.git"], scratch, env)
        repo = scratch / "objects.git"
        url = "https://" + task["repository"] + ".git"
        invoke(
            folder,
            "git-fetch",
            [*git, "fetch", "--depth=1", "--no-tags", "--no-recurse-submodules", url, revision],
            repo,
            env,
            repo=repo,
        )
        record["compressedGitObjectBytes"] = object_bytes(repo)
        assert record["compressedGitObjectBytes"] <= COMPRESSED
        actual = (
            invoke(folder, "revision", [*git, "rev-parse", "FETCH_HEAD"], repo, env)
            .decode()
            .strip()
        )
        assert actual == revision
        commit = invoke(folder, "commit-object", [*git, "cat-file", "-p", revision], repo, env)
        assert hashlib.sha1(f"commit {len(commit)}\0".encode() + commit).hexdigest() == revision
        tree_sha = (
            invoke(folder, "tree", [*git, "rev-parse", "FETCH_HEAD^{tree}"], repo, env)
            .decode()
            .strip()
        )
        frozen_metadata = FROZEN / "sources" / task["repository"] / "_commit.json"
        assert tree_sha == json.loads(frozen_metadata.read_text())["commit"]["tree"]["sha"]
        record["completeGitObjectsAcquired"] = True
        listing = invoke(folder, "files", [*git, "ls-tree", "-r", "-z", "FETCH_HEAD"], repo, env)
        entries = []
        for raw in listing.split(b"\0"):
            if not raw:
                continue
            metadata, name = raw.split(b"\t", 1)
            mode, kind, blob = metadata.decode().split()
            name = name.decode()
            path = PurePosixPath(name)
            assert not path.is_absolute() and all(
                part not in (".", "..", ".git") for part in path.parts
            )
            entries.append((mode, kind, blob, name))
        ledger["files"] += len(entries)
        assert ledger["files"] <= FILE_COUNT, "tranche file count limit"
        files, symlinks, submodules, lfs, total = {}, {}, {}, [], 0
        archive = scratch / "source.tar"
        process = subprocess.Popen(
            [*git, "cat-file", "--batch"],
            cwd=repo,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        with tarfile.open(archive, "w") as output:
            for mode, kind, blob, name in entries:
                if kind == "commit":
                    submodules[name] = blob
                    continue
                process.stdin.write(blob.encode() + b"\n")
                process.stdin.flush()
                header = process.stdout.readline().decode().split()
                assert header[:2] == [blob, "blob"]
                size = int(header[2])
                assert size <= PER_FILE, f"file-byte-limit: {name}: {size}"
                assert total + size <= PER_SOURCE, "expanded source byte limit"
                assert ledger["expandedBytes"] + size <= TRANCHE, "expanded tranche byte limit"
                raw = process.stdout.read(size)
                assert len(raw) == size and process.stdout.read(1) == b"\n"
                assert hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == blob
                ledger["expandedBytes"] += size
                total += size
                record["partialExpandedBytes"] = total
                member = tarfile.TarInfo(name)
                if mode == "120000":
                    member.type, member.linkname = tarfile.SYMTYPE, raw.decode()
                    symlinks[name] = {
                        "target": raw.decode(),
                        "gitBlobSha": blob,
                        "sha256": sha(raw),
                    }
                    output.addfile(member)
                else:
                    assert mode in ("100644", "100755")
                    member.size, member.mode = len(raw), (0o755 if mode == "100755" else 0o644)
                    output.addfile(member, io.BytesIO(raw))
                    files[name] = {
                        "sha256": sha(raw),
                        "bytes": size,
                        "mode": mode,
                        "gitBlobSha": blob,
                    }
                    if raw.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                        lfs.append(name)
        process.stdin.close()
        assert process.wait(timeout=10) == 0
        process.stdout.close()
        process.stderr.close()
        process = None
        assert len(files) + len(symlinks) + len(submodules) == len(entries)
        matched = []
        for row in json.loads((FROZEN / "source-catalog.json").read_text()):
            if row["repository"] == task["repository"] and row["kind"] == "source":
                assert files[row["path"]]["sha256"] == row["sha256"]
                assert files[row["path"]]["gitBlobSha"] == row["gitBlobSha"]
                matched.append(row["path"])
        compressed = scratch / "source.tar.gz"
        with archive.open("rb") as source, compressed.open("xb") as target:
            with gzip.GzipFile(fileobj=target, mode="wb", mtime=0) as output:
                while raw := source.read(1024 * 1024):
                    output.write(raw)
                    assert target.tell() <= COMPRESSED, "compressed archive byte limit"
        assert compressed.stat().st_size <= COMPRESSED
        limitations = (
            [
                "Full tracked upstream symlinks preserved in source tar; current regular-only runtime source validator cannot admit this archive."
            ]
            if symlinks
            else []
        )
        limitations += ["No generated Git metadata; source tar is not a Git checkout."]
        write(
            folder / "inventory.json",
            {
                "revision": revision,
                "files": {name: row["sha256"] for name, row in files.items()},
                "missingSubmodules": sorted(submodules),
                "missingLfsObjects": lfs,
                "limitations": limitations,
            },
        )
        write(
            folder / "file-details.json",
            {"files": files, "symlinks": symlinks, "gitlinks": submodules},
        )
        write(
            folder / "provenance.json",
            {
                "revision": revision,
                "archiveSha256": file_sha(archive),
                "url": url,
                "checkedAt": datetime.now(timezone.utc).isoformat(),
                "gitTreeSha": tree_sha,
                "frozenCommitMetadataSha256": file_sha(frozen_metadata),
                "allGitBlobsValidated": True,
                "archiveIsGitCheckout": False,
                "generatedGitMetadata": False,
            },
        )
        record.update(
            {
                "state": "source-acquired",
                "sourceFiles": len(files),
                "sourceBytes": total,
                "symlinks": symlinks,
                "missingSubmodules": submodules,
                "missingLfsObjects": lfs,
                "frozenInspectedFilesMatched": matched,
                "archivePath": str(archive),
                "archiveSha256": file_sha(archive),
                "archiveBytes": archive.stat().st_size,
                "compressedArchivePath": str(compressed),
                "compressedArchiveSha256": file_sha(compressed),
                "compressedArchiveBytes": compressed.stat().st_size,
                "sourceBundleReady": not (symlinks or submodules or lfs),
            }
        )
    except Exception as error:
        record.update(
            {
                "state": "source-acquisition-incomplete",
                "failure": f"{type(error).__name__}: {error}",
            }
        )
    finally:
        if process is not None:
            process.kill()
            process.wait(timeout=10)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        record["elapsedSeconds"] = time.monotonic() - started
        write(folder / "acquisition.json", record)
    print(
        task_id,
        record["state"],
        record.get("sourceFiles"),
        record.get("sourceBytes"),
        record.get("failure"),
        flush=True,
    )
    return record


if __name__ == "__main__":
    assert (
        file_sha(FROZEN / "SOURCE_FREEZE.json")
        == "fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41"
    )
    SCRATCH.mkdir(exist_ok=False)
    tasks = [
        task
        for task in json.loads((FROZEN / "tasks.json").read_text())["tasks"]
        if task["id"] in IDS
    ]
    assert {task["id"] for task in tasks} == set(IDS)
    write(
        HERE / "source-acquisition-freeze.json",
        {
            "identity": "f05-next8-source-only-v1",
            "sourceFreezeSha256": file_sha(FROZEN / "SOURCE_FREEZE.json"),
            "tasks": tasks,
            "scriptSha256": file_sha(Path(__file__)),
            "limits": {
                "compressedPerTask": COMPRESSED,
                "expandedPerTask": PER_SOURCE,
                "expandedTotal": TRANCHE,
                "fileBytes": PER_FILE,
                "filesTotal": FILE_COUNT,
            },
            "hostOperations": "Trusted Git object transfer/parsing and Python data archive processing only; no checkout or upstream execution.",
            "nextEightUpstreamExecutionAuthorized": False,
            "indexConsulted": False,
            "modelCalls": 0,
        },
    )
    ledger = {"expandedBytes": 0, "files": 0}
    results = [acquire(task, ledger) for task in tasks]
    write(
        HERE / "source-acquisition-summary.json",
        {
            "tasks": results,
            "consumedSourceBudget": ledger,
            "allSourcesAcquired": all(row["state"] == "source-acquired" for row in results),
            "upstreamProjectCodeExecuted": False,
            "costUsd": None,
        },
    )
