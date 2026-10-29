"""Data-only regular archive and protected-alias boundaries for one Go01 packet."""

import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOTS = ("npm-cache/_cacache", "go/pkg/mod")
EXPANDED_LIMIT = 1024**3
TRANSPORT_LIMIT = 512 * 1024**2
FILE_LIMIT = 128 * 1024**2
COUNT_LIMIT = 200000


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def safe_path(name):
    return (
        isinstance(name, str)
        and 0 < len(name) <= 4096
        and not any(c in name for c in "\\:")
        and not any(ord(c) < 32 or ord(c) == 127 for c in name)
        and all(part not in ("", ".", "..") for part in name.split("/"))
    )


def canonical_digest(raw):
    try:
        value = json.loads(raw)
        return sha((json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())
    except (ValueError, UnicodeDecodeError, TypeError, RecursionError):
        return None


def protected(raw, deny):
    # Empty bytes do not convey task gold/profile content. Common source/license
    # overlaps require member provenance audit, not a blanket source-hash deny.
    return bool(raw) and bool({sha(raw), canonical_digest(raw)} & deny)


def scan_archive(
    path, *, deadline, inventory=None, roots=None, deny=frozenset(), expanded_limit=EXPANDED_LIMIT
):
    """Stream regular member bytes and hashes; never extract or execute on host."""
    require(Path(path).stat().st_size <= TRANSPORT_LIMIT, "archive transport limit")
    files, seen, total = {}, set(), 0
    with tarfile.open(path, mode="r:") as archive:
        for member in archive:
            deadline()
            name = member.name.rstrip("/") if member.isdir() else member.name
            require(safe_path(name), "unsafe archive path")
            require(name not in seen, "duplicate archive member")
            seen.add(name)
            require(
                roots is None or any(name == root or name.startswith(root + "/") for root in roots),
                "outside export roots",
            )
            require(set(member.pax_headers) <= {"path"}, "unsupported extended archive metadata")
            require(
                not member.pax_headers or member.pax_headers["path"] == member.name,
                "inconsistent archive path metadata",
            )
            if member.isdir():
                continue
            require(member.isfile(), "link or special archive member")
            require(not member.sparse, "sparse archive member unsupported")
            require(roots is None or name not in roots, "download root must remain a directory")
            require(0 <= member.size <= FILE_LIMIT, "member byte limit")
            require(len(files) < COUNT_LIMIT, "member count limit")
            total += member.size
            require(total <= expanded_limit, "expanded byte limit")
            stream = archive.extractfile(member)
            digest, data, remaining = hashlib.sha256(), [], member.size
            while remaining:
                deadline()
                chunk = stream.read(min(1024**2, remaining))
                require(bool(chunk), "truncated archive member")
                digest.update(chunk)
                data.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(data)
            require(not protected(raw, deny), "protected raw/canonical content alias")
            if inventory is not None:
                require(inventory.get(name) == digest.hexdigest(), "source member hash mismatch")
            files[name] = {"sha256": digest.hexdigest(), "bytes": member.size, "mode": member.mode}
    require(bool(files), "empty archive")
    if inventory is not None:
        require(set(files) == set(inventory), "source inventory path set mismatch")
    return files, total


def normalize_archive(
    source, target, *, deadline, source_bytes, deny, expanded_limit=EXPANDED_LIMIT
):
    files, expanded = scan_archive(
        source, deadline=deadline, roots=ROOTS, deny=deny, expanded_limit=expanded_limit
    )
    require(source_bytes + expanded <= 2 * EXPANDED_LIMIT, "source plus cache limit")
    with Path(target).open("xb") as raw_output, tarfile.open(source, mode="r:") as incoming:
        output = tarfile.open(
            fileobj=LimitedWriter(raw_output, TRANSPORT_LIMIT), mode="w|", format=tarfile.PAX_FORMAT
        )
        try:
            for member in incoming:
                deadline()
                if member.isdir():
                    continue
                raw = incoming.extractfile(member).read()
                require(
                    sha(raw) == files[member.name]["sha256"],
                    "cache bytes changed during normalization",
                )
                entry = tarfile.TarInfo(member.name)
                entry.size = len(raw)
                entry.mode = 0o755 if member.mode & 0o111 else 0o644
                output.addfile(entry, io.BytesIO(raw))
                files[member.name]["mode"] = entry.mode
        finally:
            output.close()
    require(Path(target).stat().st_size <= TRANSPORT_LIMIT, "normalized transport limit")
    return files, expanded


class LimitedWriter:
    def __init__(self, stream, limit):
        self.stream, self.limit, self.written = stream, limit, 0

    def write(self, raw):
        require(self.written + len(raw) <= self.limit, "normalized archive transport limit")
        self.written += len(raw)
        return self.stream.write(raw)
