"""Static retained-byte audit. No extraction, subprocesses, daemon or network."""

import ast
import base64
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.parse import urlsplit
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = ROOT / "benchmarks/head-to-head/f05-go01-dependency-download-result-20261029"
PREP = ROOT / "benchmarks/head-to-head/f05-go01-dependency-preparation-20261029"
LIMIT_JSON = 16 * 1024**2


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def dirhash(files):
    raw = "".join(f"{sha(data)}  {name}\n" for name, data in sorted(files.items())).encode()
    return "h1:" + base64.b64encode(hashlib.sha256(raw).digest()).decode()


def unescape(module):
    return re.sub(r"!([a-z])", lambda match: match[1].upper(), module)


def main():
    frozen = load(PACKET / "freeze.json")
    for name, digest in frozen["artifactSha256"].items():
        assert file_sha(PACKET / name) == digest, name
    plan = load(PREP / "plan.json")
    result = load(PACKET / "evidence/result.json")
    prep = load(PACKET / "evidence/preparation.json")
    provenance = load(PACKET / "evidence/provenance.json")
    inventory = load(PACKET / "evidence/inventory.json")
    spec = load(PACKET / "evidence/dependency-cache-spec.json")
    authorization = load(PACKET / "authorization.json")
    trace = load(PACKET / "evidence/trace.json")
    assert file_sha(PREP / "plan.json") == result["planSha256"] == authorization["planSha256"]
    assert result["imageId"] == plan["imageId"] == prep["imageDigest"]
    assert result["sourceArchiveSha256"] == plan["source"]["archiveSha256"]
    assert authorization["commands"] == plan["commands"] and authorization["maxAttempts"] == 1
    assert result["authorizationSha256"] == file_sha(PACKET / "authorization.json")
    assert result["cacheAuditQualified"] is False
    assert all(flag is False for flag in result["draftAuditFlags"].values())
    assert all(prep[key] is False for key in result["draftAuditFlags"])
    assert result["costUsd"] is None and prep["preparationCostUsd"] is None
    assert result["nativeCollectionOccurred"] is False and result["taskOutcomeObserved"] is False
    assert result["modelCalls"] == 0 and not result["workBudgetExceeded"]
    assert not result["cleanupBudgetExceeded"]
    for name, digest in prep["scriptClosure"].items():
        assert file_sha(PREP / name) == digest
    for role in ("preparation", "trace", "inventory", "provenance"):
        binding = spec.get(role) or spec["bundle"][role]
        assert file_sha(PACKET / "evidence" / binding["path"]) == binding["sha256"]
    assert file_sha(PREP / spec["script"]["path"]) == spec["script"]["sha256"]
    receipts = []
    for folder in (PACKET / "evidence/logs", PACKET / "host-absence/logs"):
        for path in sorted(folder.glob("*/receipt.json")):
            receipt = load(path)
            for stream in ("stdout", "stderr"):
                assert file_sha(path.parent / f"{stream}.bin") == receipt[f"{stream}Sha256"]
            assert receipt["error"] is None
            assert receipt["costUsd"] is None
            if path.parent.name not in ("post-cleanup-inspect", "inspect"):
                assert receipt["exitCode"] == 0
            receipts.append(str(path.relative_to(PACKET)))
    assert len(receipts) == 26
    provision = load(PACKET / "evidence/logs/source-provision/receipt.json")
    assert provision["stdinSha256"] == plan["source"]["archiveSha256"]
    assert provision["stdinBytes"] == plan["source"]["archiveBytes"]
    initial = load(PACKET / "evidence/logs/initial-source-check/receipt.json")
    final = load(PACKET / "evidence/logs/tracked-source-check/receipt.json")
    assert initial["stdinSha256"] == final["stdinSha256"]
    assert initial["stdinBytes"] == final["stdinBytes"]
    assert (PACKET / "evidence/logs/tools-before/stdout.bin").read_bytes() == (
        PACKET / "evidence/logs/tools-after/stdout.bin"
    ).read_bytes()
    for name, receipt in trace["receipts"].items():
        assert load(PACKET / "evidence" / name) == receipt
    driver = ast.parse((PREP / "prepare.py").read_text())
    watcher = next(
        node
        for node in driver.body
        if isinstance(node, ast.FunctionDef) and node.name == "watched_download"
    )
    tail = ast.literal_eval(watcher.body[0].value.right)
    for index, command in enumerate(plan["commands"]):
        receipt = load(PACKET / f"evidence/logs/download-{index}/receipt.json")
        assert receipt["argv"] == [
            "docker",
            "exec",
            result["ownedContainer"],
            "/bin/sh",
            "-eu",
            "-c",
            command + tail,
        ]
    inspect = load(PACKET / "evidence/logs/container-inspect/stdout.bin")[0]
    host = inspect["HostConfig"]
    assert inspect["Image"] == result["imageId"] and inspect["Config"]["User"] == "1000:1000"
    assert not host["Binds"] and not inspect["Mounts"] and host["ReadonlyRootfs"]
    assert not host["Privileged"] and host["CapDrop"] == ["ALL"]
    assert "no-new-privileges" in host["SecurityOpt"]
    environment = dict(entry.split("=", 1) for entry in inspect["Config"]["Env"])
    assert all(environment.get(key) == value for key, value in plan["environment"].items())
    image = load(PACKET / "evidence/logs/image-inspect/stdout.bin")[0]
    expected_environment = dict(entry.split("=", 1) for entry in image["Config"]["Env"])
    expected_environment.update(plan["environment"])
    assert environment == expected_environment
    for key, expected in (
        ("Memory", 4294967296),
        ("MemorySwap", 4294967296),
        ("NanoCpus", 3000000000),
        ("PidsLimit", 256),
    ):
        assert host[key] == expected
    assert not load(PACKET / "evidence/logs/offline-inspect/stdout.bin")[0]["NetworkSettings"][
        "Networks"
    ]
    assert load(PACKET / "host-absence.json")["absent"] is True
    for suffix in ("evidence/logs/post-cleanup-inspect", "host-absence/logs/inspect"):
        assert load(PACKET / suffix / "receipt.json")["exitCode"] == 1
        assert b"no such object" in (PACKET / suffix / "stderr.bin").read_bytes().lower()
    assert (PACKET / "host-absence/logs/list/stdout.bin").read_bytes() == b""
    assert load(PACKET / "host-absence/logs/list/receipt.json")["exitCode"] == 0
    source_path = Path(plan["source"]["archivePath"])
    assert file_sha(source_path) == result["sourceArchiveSha256"]
    source_hashes = defaultdict(list)
    selected = {}
    with tarfile.open(source_path, mode="r:") as archive:
        for member in archive:
            if member.isfile():
                data = archive.extractfile(member).read()
                source_hashes[sha(data)].append(member.name)
                if member.name in (
                    "package-lock.json",
                    "tsc/go.sum",
                    "tools/go.sum",
                    "go.work.sum",
                ):
                    selected[member.name] = data
    source_manifest = "".join(
        f"{digest}  ./{name}\n"
        for name, digest in sorted(
            (name, digest) for digest, names in source_hashes.items() for name in names
        )
    ).encode()
    assert sha(source_manifest) == initial["stdinSha256"]
    assert len(source_manifest) == initial["stdinBytes"]
    protected = set()
    for name in ("protected-digests-82.json", "protected-digests-125.json"):
        protected.update(load(HERE / name)["digests"])
    stats = Counter()
    matches, overlaps, credentials = [], [], []
    marker_patterns = {
        "private-key-pem": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        "github-token-shaped": re.compile(
            rb"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})"
        ),
        "aws-access-key-shaped": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    }

    def screen(name, data, nested=False):
        stats["nestedFiles" if nested else "outerFiles"] += 1
        if nested:
            stats["nestedExpandedBytes"] += len(data)
            assert stats["nestedFiles"] <= 500000 and stats["nestedExpandedBytes"] <= 2 * 1024**3
        assert len(data) <= 128 * 1024**2
        digest = sha(data)
        digests = {digest}
        if len(data) <= LIMIT_JSON:
            try:
                encoded = (
                    json.dumps(json.loads(data), indent=2, sort_keys=True, allow_nan=False) + "\n"
                ).encode()
                digests.add(sha(encoded))
                stats["canonicalJsonParsed"] += 1
            except (ValueError, UnicodeDecodeError):
                stats["notCanonicalJson"] += 1
        else:
            stats["canonicalJsonSizeExcluded"] += 1
        if digests & protected:
            if data:
                matches.append(
                    {"path": name, "bytes": len(data), "digests": sorted(digests & protected)}
                )
            else:
                stats["emptyProtectedAliases"] += 1
        if digest in source_hashes:
            if not data:
                stats["emptySourceOverlaps"] += 1
            else:
                overlaps.append(
                    {
                        "path": name,
                        "bytes": len(data),
                        "sha256": digest,
                        "sourcePathCount": len(source_hashes[digest]),
                        "sourcePaths": source_hashes[digest][:100],
                    }
                )
        for kind, pattern in marker_patterns.items():
            if pattern.search(data):
                credentials.append({"path": name, "marker": kind, "sha256": digest})
        if PurePosixPath(name).name.lower() in (
            ".npmrc",
            ".netrc",
            "credentials",
            "id_rsa",
            "id_ed25519",
            "config.json",
        ):
            credentials.append({"path": name, "marker": "credential-like-name", "sha256": digest})

    archive_path = Path(result["cacheArchivePath"])
    assert file_sha(archive_path) == result["cacheArchiveSha256"] == provenance["archiveSha256"]
    assert archive_path.stat().st_size == provenance["archiveBytes"] <= 512 * 1024**2
    data_by_name = {}
    with tarfile.open(archive_path, mode="r:") as archive:
        for member in archive:
            assert member.isfile() and member.name not in data_by_name
            assert not PurePosixPath(member.name).is_absolute()
            assert all(part not in ("", ".", "..") for part in member.name.split("/"))
            assert any(member.name.startswith(prefix + "/") for prefix in plan["exportRoots"])
            assert member.uid == member.gid == member.mtime == 0 and member.mode in (0o644, 0o755)
            data = archive.extractfile(member).read()
            assert inventory["files"][member.name] == sha(data)
            assert inventory["members"][member.name] == {
                "sha256": sha(data),
                "bytes": len(data),
                "mode": member.mode,
            }
            data_by_name[member.name] = data
            stats["outerExpandedBytes"] += len(data)
            assert len(data_by_name) <= 100000 and stats["outerExpandedBytes"] <= 1024**3
            screen(member.name, data)
    assert set(data_by_name) == set(inventory["files"])
    assert stats["outerFiles"] == result["cacheFiles"] == 15246
    assert stats["outerExpandedBytes"] == result["cacheExpandedBytes"] == 351962210
    export = load(PACKET / "evidence/logs/cache-export/receipt.json")
    raw_path = Path(export["binaryPath"])
    assert (
        file_sha(raw_path) == export["binarySha256"]
        and raw_path.stat().st_size == export["binaryBytes"]
    )
    raw_members = {}
    with tarfile.open(raw_path, mode="r:") as archive:
        for member in archive:
            if member.isdir():
                continue
            assert member.isfile() and member.name not in raw_members
            raw_members[member.name] = sha(archive.extractfile(member).read())
    assert raw_members == inventory["files"]
    (HERE / "static-stage1.json").write_text(
        json.dumps(
            {
                "artifactBindings": len(frozen["artifactSha256"]),
                "receiptBindings": len(receipts),
                "stats": dict(stats),
                "protectedDigests": len(protected),
                "sourceHashCount": len(source_hashes),
            },
            indent=2,
        )
        + "\n"
    )
    lock = json.loads(selected["package-lock.json"])
    locked_urls = {
        entry["resolved"]: entry.get("integrity")
        for entry in lock["packages"].values()
        if entry.get("resolved", "").startswith("https://")
    }
    npm_urls, npm_unknown, sensitive_headers = set(), set(), []
    npm_stats = Counter()
    sums = {}
    for name in ("tsc/go.sum", "tools/go.sum", "go.work.sum"):
        for line in selected.get(name, b"").decode().splitlines():
            module, version, digest = line.split()
            key = (module, version)
            assert key not in sums or sums[key] == digest
            sums[key] = digest
    go_stats = Counter()
    go_missing, unknown_files = [], []
    covered_go = set()
    for name, data in data_by_name.items():
        if "/content-v2/sha512/" in name:
            assert hashlib.sha512(data).hexdigest() == name.split("/content-v2/sha512/")[1].replace(
                "/", ""
            )
            npm_stats["contentSha512"] += 1
            if data.startswith(b"\x1f\x8b"):
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as package:
                    for entry in package:
                        if entry.isfile():
                            assert entry.size <= 128 * 1024**2
                            screen(name + "!" + entry.name, package.extractfile(entry).read(), True)
                        else:
                            npm_stats["nestedType:" + repr(entry.type)] += 1
        elif "/index-v5/" in name:
            for line in data.splitlines():
                if not line:
                    continue
                entry_sha, raw = line.split(b"\t", 1)
                assert hashlib.sha1(raw).hexdigest().encode() == entry_sha
                entry = json.loads(raw)
                algorithm, encoded = entry["integrity"].split("-", 1)
                assert algorithm == "sha512"
                digest = base64.b64decode(encoded).hex()
                content = (
                    "npm-cache/_cacache/content-v2/sha512/"
                    + digest[:2]
                    + "/"
                    + digest[2:4]
                    + "/"
                    + digest[4:]
                )
                assert content in data_by_name
                assert entry["key"].startswith("make-fetch-happen:request-cache:")
                url = entry["key"].removeprefix("make-fetch-happen:request-cache:")
                parsed = urlsplit(url)
                assert parsed.scheme == "https" and parsed.hostname == "registry.npmjs.org"
                assert not parsed.username and not parsed.password and not parsed.query
                npm_urls.add(url)
                for group in ("reqHeaders", "resHeaders"):
                    for key in entry.get("metadata", {}).get(group, {}):
                        if key.lower() in (
                            "authorization",
                            "proxy-authorization",
                            "cookie",
                            "set-cookie",
                            "x-api-key",
                        ):
                            sensitive_headers.append({"path": name, "group": group, "key": key})
                if parsed.path.endswith(".tgz"):
                    if url in locked_urls:
                        assert locked_urls[url] == entry["integrity"], url
                        npm_stats["lockMatchedTarballs"] += 1
                    else:
                        npm_unknown.add(url)
                npm_stats["indexEntries"] += 1
        elif name.startswith("npm-cache/"):
            unknown_files.append(name)
        if name.endswith(".zip") and "/cache/download/" in name:
            encoded_module, version = name.split("/cache/download/")[1].rsplit("/@v/", 1)
            module, version = unescape(encoded_module), version[:-4]
            with zipfile.ZipFile(io.BytesIO(data)) as zipped:
                files = {}
                for entry in zipped.infolist():
                    assert entry.filename not in files
                    if not entry.is_dir():
                        assert entry.file_size <= 128 * 1024**2
                        files[entry.filename] = zipped.read(entry)
                        screen(name + "!" + entry.filename, files[entry.filename], True)
            actual = dirhash(files)
            assert data_by_name[name[:-4] + ".ziphash"].decode() == actual
            if (module, version) in sums:
                assert sums[(module, version)] == actual, (module, version)
                go_stats["sourceGoSumZipMatches"] += 1
            else:
                go_missing.append({"module": module, "version": version, "h1": actual})
            prefix = "go/pkg/mod/" + encoded_module + "@" + version + "/"
            packaged_prefix = module + "@" + version + "/"
            for cache_name, payload in data_by_name.items():
                if cache_name.startswith(prefix):
                    original = packaged_prefix + cache_name[len(prefix) :]
                    assert original in files and payload == files[original], cache_name
                    covered_go.add(cache_name)
                    go_stats["extractedMembersByteMatched"] += 1
            go_stats["ziphashMatches"] += 1
        if name.endswith(".mod") and "/cache/download/" in name:
            encoded_module, version = name.split("/cache/download/")[1].rsplit("/@v/", 1)
            key = (unescape(encoded_module), version[:-4] + "/go.mod")
            if key in sums:
                assert dirhash({"go.mod": data}) == sums[key], key
                go_stats["sourceGoSumModMatches"] += 1
            else:
                go_missing.append(
                    {"module": key[0], "version": key[1], "h1": dirhash({"go.mod": data})}
                )
    for name in data_by_name:
        if (
            name.startswith("go/pkg/mod/")
            and not name.startswith("go/pkg/mod/cache/")
            and name not in covered_go
        ):
            unknown_files.append(name)
    output = {
        "state": "static-audit-observations-not-admission",
        "artifactBindings": len(frozen["artifactSha256"]),
        "receiptBindings": len(receipts),
        "image": result["imageId"],
        "cacheSha256": result["cacheArchiveSha256"],
        "stats": dict(stats),
        "protectedDigestCount": len(protected),
        "nonemptyProtectedMatches": matches,
        "exactSourceOverlaps": overlaps,
        "credentialMarkers": credentials,
        "npm": {
            "stats": dict(npm_stats),
            "publicRegistryUrls": len(npm_urls),
            "tarballsOutsideSourceLock": sorted(npm_unknown),
            "sourceLockExternalUrls": len(locked_urls),
            "sensitiveHeaderNames": sensitive_headers,
        },
        "go": {"stats": dict(go_stats), "checksumsMissingFromSelectedSourceSums": go_missing},
        "unclassifiedOuterFiles": unknown_files,
        "allDescriptorFlagsRemainFalse": True,
        "newDaemonNetworkProviderUpstreamCalls": 0,
    }
    (HERE / "audit.json").write_text(json.dumps(output, indent=2) + "\n")
    print(
        json.dumps(
            {
                "stats": dict(stats),
                "npm": output["npm"],
                "go": output["go"],
                "protectedMatches": len(matches),
                "sourceOverlaps": len(overlaps),
                "credentialMarkers": len(credentials),
                "unclassifiedOuterFiles": len(unknown_files),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
