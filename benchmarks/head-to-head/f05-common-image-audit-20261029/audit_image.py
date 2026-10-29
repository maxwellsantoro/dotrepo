"""Inspect/export one never-started local image; never extract, start or exec."""

from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IMAGE = "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
ENV = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
MAX_BYTES = 4 * 1024**3
MAX_MEMBERS = 200000
JSON_CAP = 16 * 1024**2


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(name, value):
    path = HERE / name
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def capture(label, args, *, allow_failure=False):
    start = time.monotonic()
    result = subprocess.run(["docker", *args], env=ENV, capture_output=True, timeout=60)
    assert len(result.stdout) + len(result.stderr) <= 2 * 1024**2
    (HERE / (label + "-stdout.txt")).write_bytes(result.stdout)
    (HERE / (label + "-stderr.txt")).write_bytes(result.stderr)
    receipt = {
        "argv": ["docker", *args],
        "exitCode": result.returncode,
        "elapsedSeconds": time.monotonic() - start,
        "stdoutSha256": digest(result.stdout),
        "stderrSha256": digest(result.stderr),
        "costUsd": None,
    }
    save(label + "-receipt.json", receipt)
    if not allow_failure:
        assert result.returncode == 0, (label, result.returncode)
    return result


class ExportReader(io.RawIOBase):
    def __init__(self, process, target, deadline):
        self.process, self.target, self.deadline = process, target, deadline
        self.bytes = 0
        self.sha = hashlib.sha256()

    def read(self, size=-1):
        assert time.monotonic() < self.deadline, "export time limit"
        size = min(1024**2, size) if size >= 0 else 1024**2
        raw = self.process.stdout.read(min(size, MAX_BYTES - self.bytes + 1))
        self.bytes += len(raw)
        assert self.bytes <= MAX_BYTES, "export byte limit"
        self.sha.update(raw)
        self.target.write(raw)
        return raw


def export(name, scratch, protected, known_archives):
    path = scratch / "filesystem-export.tar"
    started = time.monotonic()
    process = subprocess.Popen(
        ["docker", "export", name], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    killed = []
    timer = threading.Timer(600, lambda: (killed.append("deadline"), process.kill()))
    timer.daemon = True
    timer.start()
    stderr = bytearray()

    def errors():
        while chunk := process.stderr.read(65536):
            available = 1024**2 - len(stderr)
            stderr.extend(chunk[:available])
            if len(chunk) > available:
                killed.append("stderr-limit")
                process.kill()
                break

    error_thread = threading.Thread(target=errors, daemon=True)
    error_thread.start()
    stats = Counter()
    inventory, protected_matches, archive_matches, credential_paths, canonical_excluded = (
        {},
        [],
        [],
        [],
        [],
    )
    credential_re = re.compile(
        r"(^|/)(\.aws|\.ssh|\.netrc|\.npmrc|\.pypirc|\.git-credentials|\.dockercfg)(/|$)|(^|/)(credentials(?:\.toml)?|auth\.json|id_rsa|id_ed25519|application_default_credentials\.json)$|(^|/)(?:gcloud|\.docker/config\.json)(/|$)",
        re.I,
    )
    try:
        with path.open("xb") as target:
            os.chmod(path, 0o600)
            reader = ExportReader(process, target, started + 600)
            with tarfile.open(fileobj=reader, mode="r|") as archive:
                for member in archive:
                    assert len(inventory) < MAX_MEMBERS, "member limit"
                    assert member.name not in inventory, "duplicate export member"
                    row = {
                        "type": member.type.decode("ascii", errors="backslashreplace"),
                        "mode": oct(member.mode),
                        "uid": member.uid,
                        "gid": member.gid,
                        "size": member.size,
                    }
                    if member.issym() or member.islnk():
                        row["linkTarget"] = member.linkname
                    if member.isfile():
                        hasher = hashlib.sha256()
                        buffered = bytearray() if member.size <= JSON_CAP else None
                        stream = archive.extractfile(member)
                        size = 0
                        while chunk := stream.read(1024**2):
                            size += len(chunk)
                            hasher.update(chunk)
                            if buffered is not None:
                                buffered.extend(chunk)
                        assert size == member.size
                        row["sha256"] = hasher.hexdigest()
                        candidates = {row["sha256"]}
                        if buffered is not None:
                            try:
                                value = json.loads(buffered)
                                canonical = (
                                    json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
                                    + "\n"
                                ).encode()
                                row["canonicalJsonSha256"] = digest(canonical)
                                candidates.add(row["canonicalJsonSha256"])
                                stats["canonicalJsonFiles"] += 1
                            except (ValueError, UnicodeDecodeError, RecursionError):
                                stats["notCanonicalizedNonJsonOrInvalid"] += 1
                        else:
                            canonical_excluded.append({"path": member.name, "bytes": member.size})
                        matches = candidates & protected
                        if matches:
                            if member.size == 0:
                                stats["innocuousEmptyProtectedMatches"] += 1
                            else:
                                protected_matches.append(
                                    {
                                        "path": member.name,
                                        "bytes": member.size,
                                        "digests": sorted(matches),
                                    }
                                )
                        if row["sha256"] in known_archives:
                            archive_matches.append({"path": member.name, "sha256": row["sha256"]})
                        stats["regularFiles"] += 1
                        stats["regularBytes"] += size
                    elif member.isdir():
                        stats["directories"] += 1
                    elif member.issym():
                        stats["symlinks"] += 1
                    elif member.islnk():
                        stats["hardlinks"] += 1
                    else:
                        stats["otherTypes"] += 1
                    inventory[member.name] = row
                    if credential_re.search(member.name) or member.name in (
                        "etc/passwd",
                        "etc/shadow",
                        "etc/gshadow",
                        "etc/group",
                    ):
                        credential_paths.append({"path": member.name, **row})
                    if len(inventory) % 10000 == 0:
                        print(
                            json.dumps({"members": len(inventory), "exportBytes": reader.bytes}),
                            flush=True,
                        )
            while reader.read(1024**2):
                pass
        code = process.wait(timeout=max(1, 600 - (time.monotonic() - started)))
        error_thread.join(timeout=2)
        assert code == 0 and not killed, ("export failed", code, killed)
        save("inventory.json", {"image": IMAGE, "files": inventory})
        save("credential-path-candidates.json", credential_paths)
        save("canonical-exclusions.json", canonical_excluded)
        result = {
            "image": IMAGE,
            "argv": ["docker", "export", name],
            "exitCode": code,
            "elapsedSeconds": time.monotonic() - started,
            "exportPath": str(path),
            "exportBytes": reader.bytes,
            "exportSha256": reader.sha.hexdigest(),
            "members": len(inventory),
            "statistics": dict(stats),
            "nonemptyProtectedMatches": protected_matches,
            "knownSourceArchiveMatches": archive_matches,
            "canonicalCapBytes": JSON_CAP,
            "canonicalSizeExcludedFiles": len(canonical_excluded),
            "credentialPathCandidates": len(credential_paths),
            "noHostExtraction": True,
            "containerNeverStarted": True,
            "costUsd": None,
        }
        save("export-receipt.json", result)
        return result
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        error_thread.join(timeout=2)
        (HERE / "export-stderr.txt").write_bytes(stderr)


def main():
    plan = json.loads((HERE / "plan.json").read_bytes())
    assert digest(Path(__file__).read_bytes()) == plan["scriptSha256"]
    protected_input = json.loads((HERE / "protected-content-digests.json").read_bytes())
    assert (
        digest((HERE / "protected-content-digests.json").read_bytes())
        == plan["protectedDigestInputSha256"]
    )
    known = json.loads((HERE / "known-source-archives.json").read_bytes())
    known_hashes = {digest for item in known for digest in item["digests"]}
    scratch = Path(tempfile.mkdtemp(prefix="dotrepo-f05-common-image-audit-", dir="/tmp"))
    save("scratch.json", {"path": str(scratch)})
    inspected = capture("image-inspect", ["image", "inspect", IMAGE])
    image = json.loads(inspected.stdout)[0]
    assert (
        image["Id"] == IMAGE
        and not image["Config"].get("Volumes")
        and not image["Config"].get("OnBuild")
    )
    assert {value.split("=", 1)[0] for value in image["Config"]["Env"]} == {
        "PATH",
        "RUSTUP_HOME",
        "CARGO_HOME",
        "GOTOOLCHAIN",
        "GOENV",
    }
    name = "dotrepo-f05-common-image-audit-" + uuid.uuid4().hex[:12]
    save("container-handle.json", {"name": name, "image": IMAGE, "neverStart": True})
    try:
        capture(
            "create",
            [
                "create",
                "--name",
                name,
                "--pull=never",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--user=1000:1000",
                "--entrypoint=/bin/true",
                IMAGE,
            ],
        )
        metadata = json.loads(capture("container-inspect", ["inspect", name]).stdout)[0]
        assert metadata["Image"] == IMAGE and not metadata["Mounts"]
        assert not metadata["State"]["Running"] and metadata["State"]["StartedAt"].startswith(
            "0001-"
        )
        assert (
            metadata["HostConfig"]["NetworkMode"] == "none"
            and metadata["HostConfig"]["ReadonlyRootfs"]
        )
        result = export(name, scratch, set(protected_input["digests"]), known_hashes)
        assert not result["nonemptyProtectedMatches"] and not result["knownSourceArchiveMatches"]
    finally:
        capture("cleanup", ["rm", "--force", "--volumes", name], allow_failure=True)
        absent = capture("absence", ["inspect", name], allow_failure=True)
        save(
            "cleanup-check.json",
            {"container": name, "absent": absent.returncode != 0, "neverStarted": True},
        )
        assert absent.returncode != 0


if __name__ == "__main__":
    main()
