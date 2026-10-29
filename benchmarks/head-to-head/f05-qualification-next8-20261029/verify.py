"""Verify retained source-only evidence without network or upstream execution.

uv run python <this-file> [--output fresh-checks.json]
Full source tar/gzip inputs must still exist in the declared scratch directory.
This validates byte/identity consistency, not source authenticity or task success.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / "f05-agent-tasks-20261029"
SOURCE_FREEZE = "fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            digest.update(raw)
    return digest.hexdigest()


def git_object(kind, raw):
    return hashlib.sha1(f"{kind} {len(raw)}\0".encode() + raw).hexdigest()


def tree_sha(files):
    root = {}
    for path, row in files.items():
        current = root
        parts = path.split("/")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        assert parts[-1] not in current
        current[parts[-1]] = (row["mode"], row["gitBlobSha"])

    def digest(node):
        raw = bytearray()
        for name, entry in sorted(
            node.items(),
            key=lambda item: (item[0] + ("/" if isinstance(item[1], dict) else "")).encode(),
        ):
            mode, object_sha = ("40000", digest(entry)) if isinstance(entry, dict) else entry
            raw.extend(mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(object_sha))
        return git_object("tree", raw)

    return digest(root)


def archive_files(archive):
    files = {}
    with tarfile.open(fileobj=archive, mode="r:") as stream:
        for member in stream:
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and ".." not in path.parts and str(path) == member.name
            assert member.name not in files
            if member.issym():
                raw = member.linkname.encode()
                mode = "120000"
            else:
                assert member.isfile(), f"unsupported member kind {member.name}"
                raw = stream.extractfile(member).read()
                assert member.mode in (0o644, 0o755)
                mode = "100755" if member.mode == 0o755 else "100644"
            files[member.name] = {
                "sha256": sha(raw),
                "bytes": len(raw),
                "mode": mode,
                "gitBlobSha": git_object("blob", raw),
            }
    return files


def controls():
    def sample(name="a", data=b"source", mode=0o644, duplicate=False):
        result = io.BytesIO()
        with tarfile.open(fileobj=result, mode="w") as stream:
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(data), mode
            stream.addfile(member, io.BytesIO(data))
            if duplicate:
                stream.addfile(member, io.BytesIO(data))
        result.seek(0)
        return result

    assert archive_files(sample())["a"]["sha256"] == sha(b"source")
    rejected = []
    for label, value in [
        ("absolute-path", sample("/escape")),
        ("parent-path", sample("a/../escape")),
        ("duplicate-member", sample(duplicate=True)),
        ("unbound-mode", sample(mode=0o777)),
    ]:
        try:
            archive_files(value)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError(f"accepted {label}")
    assert tree_sha(
        {"a": {"mode": "100644", "gitBlobSha": git_object("blob", b"source")}}
    ) != tree_sha({"a": {"mode": "100644", "gitBlobSha": git_object("blob", b"changed")}})
    return {"positive": 1, "negative": rejected, "treeContentChangeDetected": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checked_controls = controls()
    assert file_sha(FROZEN / "SOURCE_FREEZE.json") == SOURCE_FREEZE
    original = json.loads((FROZEN / "SOURCE_FREEZE.json").read_text())
    for row in original["files"]:
        raw = (FROZEN / row["path"]).read_bytes()
        assert len(raw) == row["bytes"] and sha(raw) == row["sha256"]
    freeze = json.loads((HERE / "source-acquisition-freeze.json").read_text())
    assert file_sha(HERE / "acquire.py") == freeze["scriptSha256"]
    plan = json.loads((HERE / "execution-proposal.json").read_text())
    tasks = []
    receipt_count = 0
    for task in freeze["tasks"]:
        task_id = task["id"]
        acquisition = json.loads((HERE / task_id / "acquisition.json").read_text())
        provenance = json.loads((HERE / task_id / "provenance.json").read_text())
        details = json.loads((HERE / task_id / "file-details.json").read_text())
        expected = dict(details["files"])
        for path, row in details["symlinks"].items():
            expected[path] = {
                "sha256": row["sha256"],
                "gitBlobSha": row["gitBlobSha"],
                "mode": "120000",
                "bytes": len(row["target"].encode()),
            }
        assert details["gitlinks"] == {}
        assert acquisition["task"] == task == plan["tasks"][task_id]["task"]
        assert acquisition["state"] == "source-acquired"
        assert provenance["revision"] == task["revision"]
        assert (
            provenance["archiveIsGitCheckout"] is False
            and provenance["generatedGitMetadata"] is False
        )
        for path, key in [
            ("archivePath", "archiveSha256"),
            ("compressedArchivePath", "compressedArchiveSha256"),
        ]:
            assert file_sha(Path(acquisition[path])) == acquisition[key]
        with Path(acquisition["archivePath"]).open("rb") as stream:
            files = archive_files(stream)
        for path, row in files.items():
            assert all(expected[path][key] == value for key, value in row.items()), path
        assert set(files) == set(expected)
        actual_tree = tree_sha(files)
        assert actual_tree == provenance["gitTreeSha"]
        inventory = json.loads((HERE / task_id / "inventory.json").read_text())
        assert {
            name: row["sha256"] for name, row in files.items() if row["mode"] != "120000"
        } == inventory["files"]
        for source in plan["tasks"][task_id]["sourceBindings"]:
            assert (
                file_sha(HERE / source["retained"])
                == files[source["path"]]["sha256"]
                == source["sha256"]
            )
        for receipt in (HERE / task_id / "logs").glob("*/receipt.json"):
            row = json.loads(receipt.read_text())
            for suffix in ["stdout", "stderr"]:
                assert file_sha(receipt.parent / f"{suffix}.bin") == row[f"{suffix}Sha256"]
            assert row["exitCode"] == 0 and row["error"] is None
            receipt_count += 1
        tasks.append(
            {
                "task": task_id,
                "entries": len(files),
                "bytes": sum(row["bytes"] for row in files.values()),
                "gitTreeSha": actual_tree,
                "links": sum(row["mode"] == "120000" for row in files.values()),
                "archiveSha256": acquisition["archiveSha256"],
            }
        )
    for path in (HERE / "oracle-revision").glob("freeze.json"):
        for name, value in json.loads(path.read_text())["files"].items():
            assert file_sha(path.parent / name) == value
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "controls": checked_controls,
        "sourceFreezeSha256": SOURCE_FREEZE,
        "originalFrozenArtifactsVerified": len(original["files"]),
        "tasks": tasks,
        "totalEntries": sum(row["entries"] for row in tasks),
        "totalBytes": sum(row["bytes"] for row in tasks),
        "totalLinks": sum(row["links"] for row in tasks),
        "commandReceiptsVerified": receipt_count,
        "status": "passed",
        "limits": "Local bytes/Git object Merkle consistency only; no external fetch, project execution, environment qualification, native oracle result, index/profile access, model call or consumer benefit.",
    }
    if args.output:
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
