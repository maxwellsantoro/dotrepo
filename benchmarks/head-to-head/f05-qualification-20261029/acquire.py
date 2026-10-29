"""Retain exact source archives and recursive Git blob inventories; host uv only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import time
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / "f05-agent-tasks-20261029"
SCRATCH = Path("/tmp/dotrepo-f05-qualification-20261029-tranche-1")
IDS = ("rust-02", "typescript-02", "go-01", "go-03")
LIMIT = 512 * 1024 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def fetch(url, path, limit):
    start = time.monotonic()
    request = Request(url, headers={"User-Agent": "dotrepo-f05-source-qualification"})
    with urlopen(request, timeout=120) as response, path.open("xb") as output:
        count = 0
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > limit or time.monotonic() - start > 600:
                raise ValueError("source fetch exceeded declared byte/time limit")
            output.write(chunk)
        metadata = {
            "url": url,
            "finalUrl": response.url,
            "status": response.status,
            "headers": dict(response.headers),
            "bytes": count,
            "elapsedSeconds": time.monotonic() - start,
            "sha256": sha(path.read_bytes()),
        }
    return metadata


def acquire(task):
    folder = HERE / task["id"]
    folder.mkdir()
    scratch = SCRATCH / task["id"]
    scratch.mkdir(parents=True)
    start = time.monotonic()
    record = {
        "task": task,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "archiveCostUsd": None,
        "costExclusions": [
            "No metered infrastructure/download dollar receipt is available; elapsed time and bytes retained."
        ],
        "indexConsulted": False,
        "upstreamCodeExecuted": False,
    }
    try:
        owner_repo = task["repository"].removeprefix("github.com/")
        revision = task["revision"]
        record["treeDownload"] = fetch(
            f"https://api.github.com/repos/{owner_repo}/git/trees/{revision}?recursive=1",
            folder / "recursive-tree.json",
            32 * 1024 * 1024,
        )
        tree = json.loads((folder / "recursive-tree.json").read_text())
        assert not tree.get("truncated"), "recursive Git tree was truncated"
        entries = {row["path"]: row for row in tree["tree"] if row["type"] != "tree"}
        record["archiveDownload"] = fetch(
            f"https://codeload.github.com/{owner_repo}/tar.gz/{revision}",
            scratch / "upstream.tar.gz",
            LIMIT,
        )
        files, links, total = {}, {}, 0
        runtime = scratch / "runtime-source.tar"
        with (
            tarfile.open(scratch / "upstream.tar.gz", "r:gz") as source,
            tarfile.open(runtime, "w") as output,
        ):
            prefix = None
            for member in source:
                parts = PurePosixPath(member.name).parts
                assert parts and not member.name.startswith("/") and ".." not in parts
                prefix = prefix or parts[0]
                assert parts[0] == prefix
                name = "/".join(parts[1:])
                if not name or member.isdir():
                    continue
                assert name in entries and name not in files and name not in links
                entry = entries[name]
                if member.issym():
                    raw = member.linkname.encode()
                    assert entry["mode"] == "120000"
                    links[name] = {"target": member.linkname, "gitBlobSha": entry["sha"]}
                else:
                    assert member.isfile() and entry["type"] == "blob"
                    raw = source.extractfile(member).read()
                    total += len(raw)
                    assert total <= 1024 * 1024 * 1024, "uncompressed source exceeds one GiB"
                    files[name] = {
                        "sha256": sha(raw),
                        "bytes": len(raw),
                        "mode": entry["mode"],
                        "gitBlobSha": entry["sha"],
                    }
                    normalized = tarfile.TarInfo(name)
                    normalized.size = len(raw)
                    normalized.mode = 0o755 if entry["mode"] == "100755" else 0o644
                    output.addfile(normalized, io.BytesIO(raw))
                actual = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
                assert actual == entry["sha"], f"upstream Git blob mismatch: {name}"
        submodules = [name for name, entry in entries.items() if entry["type"] == "commit"]
        assert set(files) | set(links) | set(submodules) == set(entries), (
            "archive/tree coverage differs"
        )
        catalog = json.loads((FROZEN / "source-catalog.json").read_text())
        matched = []
        for row in catalog:
            if row["repository"] == task["repository"] and row["kind"] == "source":
                assert files[row["path"]]["sha256"] == row["sha256"]
                assert files[row["path"]]["gitBlobSha"] == row["gitBlobSha"]
                matched.append(row["path"])
        lfs = []
        with tarfile.open(runtime) as archive:
            for member in archive:
                if member.size < 1024 and archive.extractfile(member).read().startswith(
                    b"version https://git-lfs.github.com/spec/v1\n"
                ):
                    lfs.append(member.name)
        inventory = {
            "revision": revision,
            "files": {name: row["sha256"] for name, row in files.items()},
            "missingSubmodules": submodules,
            "missingLfsObjects": lfs,
            "limitations": (
                [
                    "Runtime regular-file archive excludes retained upstream symlinks; campaign admission unresolved."
                ]
                if links
                else []
            ),
        }
        write(folder / "inventory.json", inventory)
        write(
            folder / "file-details.json",
            {"files": files, "symlinks": links, "gitlinks": submodules},
        )
        record.update(
            {
                "status": "source-acquired",
                "sourceFiles": len(files),
                "sourceBytes": total,
                "frozenSourceFilesMatched": matched,
                "missingSubmodules": submodules,
                "missingLfsObjects": lfs,
                "symlinks": links,
                "archivePath": str(scratch / "upstream.tar.gz"),
                "runtimeArchivePath": str(runtime),
                "runtimeArchiveSha256": sha(runtime.read_bytes()),
                "runtimeArchiveBytes": runtime.stat().st_size,
                "sourceBundleReady": not (submodules or lfs or links),
            }
        )
        write(
            folder / "provenance.json",
            {
                "revision": revision,
                "archiveSha256": record["runtimeArchiveSha256"],
                "url": record["archiveDownload"]["url"],
                "checkedAt": datetime.now(timezone.utc).isoformat(),
                "upstreamArchiveSha256": record["archiveDownload"]["sha256"],
                "gitTreeSha": tree["sha"],
                "recursiveGitBlobValidation": True,
                "archiveIsGitCheckout": False,
                "generatedGitMetadata": False,
            },
        )
    except Exception as error:
        record.update(
            {"status": "source-acquisition-failed", "error": f"{type(error).__name__}: {error}"}
        )
    record["elapsedSeconds"] = time.monotonic() - start
    write(folder / "acquisition.json", record)
    print(task["id"], record["status"], record.get("sourceFiles"), record.get("error"), flush=True)
    return record


if __name__ == "__main__":
    assert (
        sha((FROZEN / "SOURCE_FREEZE.json").read_bytes())
        == "fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41"
    )
    SCRATCH.mkdir(exist_ok=False)
    tasks = [
        task
        for task in json.loads((FROZEN / "tasks.json").read_text())["tasks"]
        if task["id"] in IDS
    ]
    write(
        HERE / "tranche-plan.json",
        {
            "baseCommit": "eb43ab20ac0368c4926660ae060347305197f936",
            "taskIds": list(IDS),
            "tasks": tasks,
            "frozenSourceSha256": sha((FROZEN / "SOURCE_FREEZE.json").read_bytes()),
            "sourceOnly": True,
            "indexConsulted": False,
            "maximumCompressedSourceBytesPerTask": LIMIT,
            "maximumUncompressedSourceBytesPerTask": 1024 * 1024 * 1024,
            "maximumFetchSeconds": 600,
            "setupSecondsPerTask": 900,
            "executionSecondsPerTask": 1200,
            "cpuLimit": 3,
            "memoryBytes": 4 * 1024**3,
            "pidsLimit": 256,
            "costUsd": None,
            "costExclusions": ["No metered host/container dollar receipt; no zero-cost inference."],
        },
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(acquire, tasks))
    write(
        HERE / "acquisition-summary.json",
        {
            "tasks": rows,
            "allSourcesAcquired": all(row["status"] == "source-acquired" for row in rows),
        },
    )
