"""Offline byte, receipt and package-integrity audit; never extracts or executes."""

import base64
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import tomllib
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[3]
PACKET = ROOT / "benchmarks/head-to-head/f05-dependency-preparation-20261029"
FIRST = ROOT / "benchmarks/head-to-head/f05-qualification-20261029"
IMAGE = "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
PROTECTED_PATH = Path(__file__).resolve().parent / "protected-content-digests.json"
PROTECTED = set(json.loads(PROTECTED_PATH.read_bytes())["digests"])

LEAVES = {
    "rust-02-attempt-2": (
        "269ef91c6067680f1805a632144bf50b8e6c5d16f17f9ff3d40dad8fe9527104",
        "rust-02-full",
    ),
    "typescript-02": (
        "73799214f324edce58980baf15d198240f0e56ee2cf62b73134e6dff3b89ea84",
        "typescript-02",
    ),
    "go-03": ("57088107a36d67643add9ba4f33774a599de71a942cc54ae71b967314c7867cf", "go-03"),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def receipt_check(folder):
    result = []
    for path in sorted((folder / "logs").glob("*/receipt.json")):
        receipt = load(path)
        for stream in ("stdout", "stderr"):
            assert file_sha(path.parent / (stream + ".txt")) == receipt[stream + "Sha256"]
        result.append(
            {
                "path": str(path.relative_to(PACKET)),
                "sha256": file_sha(path),
                "exitCode": receipt["exitCode"],
                "error": receipt["error"],
            }
        )
    return result


def dirhash(files):
    raw = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())
    ).encode()
    return "h1:" + base64.b64encode(hashlib.sha256(raw).digest()).decode()


def source_info(folder):
    acquisition = load(FIRST / folder / "acquisition.json")
    path = Path(acquisition["runtimeArchivePath"])
    assert file_sha(path) == acquisition["runtimeArchiveSha256"]
    selected = {}
    hashes = {}
    with tarfile.open(path, mode="r:") as archive:
        for member in archive:
            if member.isfile():
                data = archive.extractfile(member).read()
                hashes.setdefault(sha(data), []).append(member.name)
                if member.name in (
                    "Cargo.lock",
                    ".cargo/config.toml",
                    ".npmrc",
                    "package-lock.json",
                    "api/go.sum",
                    "api/go.mod",
                ):
                    selected[member.name] = data
    return acquisition, selected, hashes


def audit(leaf, expected, source_folder):
    folder = PACKET / leaf
    spec_path = folder / "dependency-cache-spec.json"
    assert file_sha(spec_path) == expected
    spec = load(spec_path)
    result = load(folder / "result.json")
    scratch = Path(result["archivePath"]).parent
    for role in ("preparation", "script", "trace"):
        assert file_sha(scratch / spec[role]["path"]) == spec[role]["sha256"]
    for role in ("archive", "inventory", "provenance"):
        assert file_sha(scratch / spec["bundle"][role]["path"]) == spec["bundle"][role]["sha256"]
    prep = load(folder / "preparation.json")
    trace = load(folder / "trace.json")
    provenance = load(folder / "provenance.json")
    inventory = load(folder / "inventory.json")
    assert prep["imageDigest"] == result["imageId"] == IMAGE
    assert (
        prep["cacheArchiveSha256"]
        == provenance["archiveSha256"]
        == result["archiveSha256"]
        == spec["bundle"]["archive"]["sha256"]
    )
    assert prep["traceSha256"] == spec["trace"]["sha256"]
    assert prep["scriptSha256"] == spec["script"]["sha256"]
    assert prep["preparationCostUsd"] is None and result["costUsd"] is None
    assert prep["downloadOnly"] is True
    assert all(
        prep[key] is False
        for key in ("buildOutputsExcluded", "taskSourceExcluded", "credentialsExcluded")
    )
    for name, digest in prep["scriptClosure"].items():
        assert file_sha(PACKET / name) == digest
    plan = load(PACKET / ("plan.v4.json" if leaf.startswith("rust") else "plan.v3.json"))
    assert (
        file_sha(PACKET / ("plan.v4.json" if leaf.startswith("rust") else "plan.v3.json"))
        == prep["planSha256"]
        == provenance["planSha256"]
    )
    acquisition, source, source_hashes = source_info(source_folder)
    assert prep["sourceArchiveSha256"] == acquisition["runtimeArchiveSha256"]
    assert prep["revision"] == inventory["revision"] == spec["bundle"]["revision"]
    receipts = receipt_check(folder)
    for name, receipt in trace["receipts"].items():
        assert load(folder / name) == receipt
    download_commands = []
    for path in sorted((folder / "logs").glob("download-*/receipt.json")):
        receipt = load(path)
        assert receipt["exitCode"] == 0 and receipt["error"] is None
        download_commands.append(receipt["argv"][-1])
    assert download_commands == [
        "cd /workspace/repository; " + text for text in plan["tasks"][result["taskId"]]["commands"]
    ]
    original = load(folder / "logs/container-inspect/receipt.json")
    assert original["exitCode"] == 0
    metadata = load(folder / "logs/container-inspect/stdout.txt")[0]
    assert metadata["Image"] == IMAGE and metadata["Config"]["User"] == "1000:1000"
    host = metadata["HostConfig"]
    assert not host["Binds"] and not metadata["Mounts"]
    assert host["NetworkMode"] == "bridge" and host["ReadonlyRootfs"] and not host["Privileged"]
    assert host["CapDrop"] == ["ALL"] and "no-new-privileges" in host["SecurityOpt"]
    assert not load(folder / "logs/offline-inspect/stdout.txt")[0]["NetworkSettings"]["Networks"]
    assert load(folder / "logs/cleanup/receipt.json")["exitCode"] == 0
    archive_path = scratch / "cache.tar"
    members, stats, overlap, data_by_name = {}, Counter(), [], {}
    roots = plan["tasks"][result["taskId"]]["roots"]
    with tarfile.open(archive_path, mode="r:") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            assert member.isfile() and member.name not in members
            assert not path.is_absolute() and all(
                part not in ("", ".", "..") for part in member.name.split("/")
            )
            assert any(member.name.startswith(root + "/") for root in roots)
            assert member.uid == member.gid == member.mtime == 0 and member.mode in (0o644, 0o755)
            data = archive.extractfile(member).read()
            digest = sha(data)
            assert digest == inventory["files"][member.name]
            members[member.name] = digest
            stats["files"] += 1
            stats["expandedBytes"] += len(data)
            if digest in source_hashes:
                overlap.append(
                    {
                        "cachePath": member.name,
                        "sourcePaths": source_hashes[digest],
                        "bytes": len(data),
                    }
                )
            data_by_name[member.name] = data
    export = load(folder / "cache-export-receipt.json")
    raw_archive = Path(export["archivePath"])
    assert file_sha(raw_archive) == export["archiveSha256"]
    assert raw_archive.stat().st_size == export["archiveBytes"]
    assert file_sha(folder / "cache-export-stderr.txt") == export["stderrSha256"]
    assert export["exitCode"] == 0 and export["error"] is None
    raw_files = {}
    with tarfile.open(raw_archive, mode="r:") as archive:
        for member in archive:
            if member.isdir():
                continue
            assert member.isfile() and member.name not in raw_files
            raw_files[member.name] = sha(archive.extractfile(member).read())
    assert raw_files == members
    assert members == inventory["files"]
    assert (
        stats["files"] == result["cacheFiles"]
        and stats["expandedBytes"] == result["cacheExpandedBytes"]
    )
    assert (
        stats["expandedBytes"] <= 1024**3
        and archive_path.stat().st_size == result["cacheArchiveBytes"] <= 512 * 1024**2
    )
    protected_matches = []
    empty_aliases = 0
    nested_bytes = 0
    nested_files = 0
    nested_source_overlaps = Counter()

    def protected_check(name, data, nested=False):
        nonlocal empty_aliases, nested_bytes, nested_files
        if nested:
            nested_bytes += len(data)
            nested_files += 1
            assert nested_bytes <= 2 * 1024**3 and len(data) <= 128 * 1024**2
            if len(data) > 256 and sha(data) in source_hashes:
                nested_source_overlaps.update(source_hashes[sha(data)])
        digests = {sha(data)}
        try:
            canonical = (
                json.dumps(json.loads(data), indent=2, sort_keys=True, allow_nan=False) + "\n"
            ).encode()
            digests.add(sha(canonical))
        except (ValueError, UnicodeDecodeError):
            pass
        matched = sorted(digests & PROTECTED)
        if matched and not data:
            empty_aliases += 1
        elif matched:
            protected_matches.append({"path": name, "bytes": len(data), "matchedDigests": matched})

    for name, data in data_by_name.items():
        protected_check(name, data)
    package_checks = {}
    if leaf.startswith("rust"):
        locked = tomllib.loads(source["Cargo.lock"].decode())
        checksums = {
            (p["name"], p["version"]): p["checksum"] for p in locked["package"] if "checksum" in p
        }
        crate_count = extracted_count = 0
        source_exceptions = []
        for name, data in data_by_name.items():
            if name.endswith(".crate"):
                stem = Path(name).name[:-6]
                matched = [
                    (key, value) for key, value in checksums.items() if stem == "-".join(key)
                ]
                assert len(matched) == 1 and sha(data) == matched[0][1]
                crate_count += 1
                registry = name.split("/cache/")[1].split("/")[0]
                prefix = "cargo/registry/src/" + registry + "/" + stem + "/"
                packaged = {}
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as crate:
                    for entry in crate:
                        if entry.isfile():
                            payload = crate.extractfile(entry).read()
                            protected_check(name + "!" + entry.name, payload, True)
                            packaged[entry.name.split("/", 1)[1]] = payload
                for source_name, payload in data_by_name.items():
                    if source_name.startswith(prefix):
                        relative = source_name[len(prefix) :]
                        if relative in (".cargo-ok", ".cargo-checksum.json"):
                            source_exceptions.append(relative)
                        else:
                            assert relative in packaged and payload == packaged[relative], (
                                source_name
                            )
                            extracted_count += 1
        package_checks = {
            "crateDownloadsMatchSourceCargoLock": crate_count,
            "extractedCrateMembersByteMatched": extracted_count,
            "cargoGeneratedMetadata": dict(Counter(source_exceptions)),
            "sourceCargoConfigSha256": sha(source[".cargo/config.toml"])
            if ".cargo/config.toml" in source
            else None,
        }
    elif leaf.startswith("typescript"):
        content_count = index_count = 0
        integrity_references = set()
        urls = set()
        lock = json.loads(source["package-lock.json"])
        locked_urls = {
            entry["resolved"]: entry.get("integrity")
            for entry in lock["packages"].values()
            if entry.get("resolved", "").startswith("https://")
        }
        locked_tarballs = set()
        extra_tarballs = set()
        sensitive_header_keys = set()
        missing_lock_integrities = set()
        for name, data in data_by_name.items():
            if "/content-v2/sha512/" in name:
                digest = name.split("/content-v2/sha512/")[1].replace("/", "")
                assert hashlib.sha512(data).hexdigest() == digest
                content_count += 1
                if data.startswith(b"\x1f\x8b"):
                    try:
                        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as package:
                            for entry in package:
                                if entry.isfile():
                                    protected_check(
                                        name + "!" + entry.name,
                                        package.extractfile(entry).read(),
                                        True,
                                    )
                    except tarfile.ReadError:
                        pass
            if "/index-v5/" in name:
                for line in data.splitlines():
                    if not line:
                        continue
                    entry_sha, raw = line.split(b"\t", 1)
                    assert hashlib.sha1(raw).hexdigest().encode() == entry_sha
                    entry = json.loads(raw)
                    if entry.get("integrity"):
                        algorithm, encoded = entry["integrity"].split("-", 1)
                        assert algorithm == "sha512"
                        value = base64.b64decode(encoded).hex()
                        path = (
                            "npm-cache/_cacache/content-v2/sha512/"
                            + value[:2]
                            + "/"
                            + value[2:4]
                            + "/"
                            + value[4:]
                        )
                        assert path in data_by_name
                        integrity_references.add(path)
                    key = entry["key"]
                    assert key.startswith("make-fetch-happen:request-cache:")
                    url = key.removeprefix("make-fetch-happen:request-cache:")
                    parsed = urlsplit(url)
                    assert (
                        parsed.scheme == "https"
                        and parsed.hostname == "registry.npmjs.org"
                        and not parsed.username
                        and not parsed.password
                        and not parsed.query
                    )
                    urls.add(url)
                    metadata = entry.get("metadata", {})
                    for headers in ("reqHeaders", "resHeaders"):
                        sensitive_header_keys.update(
                            key
                            for key in metadata.get(headers, {})
                            if key.lower()
                            in (
                                "authorization",
                                "proxy-authorization",
                                "cookie",
                                "set-cookie",
                                "x-api-key",
                            )
                        )
                    if parsed.path.endswith(".tgz"):
                        if url in locked_urls:
                            if locked_urls[url] is None:
                                missing_lock_integrities.add(url)
                            else:
                                assert entry["integrity"] == locked_urls[url]
                            locked_tarballs.add(url)
                        else:
                            extra_tarballs.add(url)
                    index_count += 1
        package_checks = {
            "contentSha512Checked": content_count,
            "indexEntriesChecked": index_count,
            "contentReferences": len(integrity_references),
            "publicRegistryUrls": len(urls),
            "lockMatchedTarballUrls": len(locked_tarballs),
            "tarballUrlsOutsideTaskLock": sorted(extra_tarballs),
            "sensitiveHeaderNamesRetained": sorted(sensitive_header_keys),
            "lockTarballsWithoutSourceIntegrity": sorted(missing_lock_integrities),
            "sourcePackageLockSha256": sha(source["package-lock.json"]),
        }
    else:
        sums = {
            tuple(line.split()[:2]): line.split()[2]
            for line in source["api/go.sum"].decode().splitlines()
        }
        checked = extracted_count = mod_count = 0
        missing = []
        for name, data in data_by_name.items():
            if name.endswith(".zip") and "/cache/download/" in name:
                module, version = name.split("/cache/download/")[1].rsplit("/@v/", 1)
                version = version[:-4]
                module = "".join(
                    c.upper() if i and module[i - 1] == "!" else c
                    for i, c in enumerate(module)
                    if c != "!"
                )
                with zipfile.ZipFile(io.BytesIO(data)) as zipped:
                    files = {
                        item.filename: zipped.read(item)
                        for item in zipped.infolist()
                        if not item.is_dir()
                    }
                for filename, payload in files.items():
                    protected_check(name + "!" + filename, payload, True)
                actual = dirhash(files)
                ziphash_name = name[:-4] + ".ziphash"
                assert data_by_name[ziphash_name].decode() == actual
                encoded_module = name.split("/cache/download/")[1].rsplit("/@v/", 1)[0]
                prefix = "go/pkg/mod/" + encoded_module + "@" + version + "/"
                zip_prefix = module + "@" + version + "/"
                packaged = {
                    filename[len(zip_prefix) :]: payload for filename, payload in files.items()
                }
                for source_name, payload in data_by_name.items():
                    if source_name.startswith(prefix):
                        assert (
                            source_name[len(prefix) :] in packaged
                            and payload == packaged[source_name[len(prefix) :]]
                        ), source_name
                        extracted_count += 1
                expected_sum = sums.get((module, version))
                if expected_sum is None:
                    missing.append({"module": module, "version": version, "observed": actual})
                else:
                    assert actual == expected_sum, (module, version)
                    checked += 1
        for name, data in data_by_name.items():
            if name.endswith(".mod") and "/cache/download/" in name:
                encoded_module, version = name.split("/cache/download/")[1].rsplit("/@v/", 1)
                module = "".join(
                    c.upper() if i and encoded_module[i - 1] == "!" else c
                    for i, c in enumerate(encoded_module)
                    if c != "!"
                )
                version = version[:-4] + "/go.mod"
                if (module, version) in sums:
                    assert dirhash({"go.mod": data}) == sums[(module, version)]
                    mod_count += 1
        package_checks = {
            "moduleExtractedMembersByteMatched": extracted_count,
            "moduleGoModH1MatchesSourceApiGoSum": mod_count,
            "moduleZipH1MatchesSourceApiGoSum": checked,
            "notInSourceApiGoSum": missing,
            "sourceApiGoSumSha256": sha(source["api/go.sum"]),
        }
    del data_by_name
    return {
        "leaf": leaf,
        "specSha256": expected,
        "archiveSha256": file_sha(archive_path),
        "stats": dict(stats),
        "receiptBindings": len(receipts),
        "scriptClosureVerified": True,
        "downloadCommands": download_commands,
        "packageChecks": package_checks,
        "exactSourceContentOverlaps": overlap,
        "auditFlagsRemainFalse": True,
        "protectedHashSetSha256": file_sha(PROTECTED_PATH),
        "nonemptyProtectedMatches": protected_matches,
        "emptyProtectedDigestMatchesInnocuous": empty_aliases,
        "nestedRegularMembersChecked": nested_files,
        "nestedExpandedBytesChecked": nested_bytes,
        "nestedNontrivialSourceHashOverlaps": dict(nested_source_overlaps),
    }


def main():
    freeze_path = PACKET / "packet-freeze.json"
    assert (
        file_sha(freeze_path) == "3888a19462854a37c20803fa9c62f525223af9f4f3d8aa9cfa2bf46affdd2f84"
    )
    freeze = load(freeze_path)
    for name, digest in freeze["files"].items():
        assert file_sha(PACKET / name) == digest
    owned = load(PACKET / "artifact-hashes.json")["files"]
    for name, entry in owned.items():
        assert (
            file_sha(PACKET / name) == entry["sha256"]
            and (PACKET / name).stat().st_size == entry["bytes"]
        )
    common = load(PACKET / "common-image.json")
    assert common["imageId"] == IMAGE
    assert file_sha(PACKET / "Dockerfile.v3") == common["recipeSha256"]
    assert file_sha(PACKET / "plan.v3.json") == common["planSha256"]
    plan = load(PACKET / "plan.v3.json")
    for name, digest in plan["scripts"].items():
        assert file_sha(PACKET / name) == digest
    all_receipts = []
    for path in sorted(PACKET.rglob("receipt.json")):
        receipt = load(path)
        for stream in ("stdout", "stderr"):
            assert file_sha(path.parent / (stream + ".txt")) == receipt[stream + "Sha256"]
        all_receipts.append(str(path.relative_to(PACKET)))
    common_receipts = receipt_check(PACKET / "image-attempt-3")
    metadata = load(PACKET / "image-attempt-3/logs/image-inspect/stdout.txt")[0]
    assert (
        metadata["Id"] == IMAGE
        and not metadata["Config"].get("Volumes")
        and not metadata["Config"].get("OnBuild")
    )
    assert {s.split("=", 1)[0] for s in metadata["Config"]["Env"]} == {
        "PATH",
        "RUSTUP_HOME",
        "CARGO_HOME",
        "GOTOOLCHAIN",
        "GOENV",
    }
    results = []
    for leaf, (digest, source_folder) in LEAVES.items():
        results.append(audit(leaf, digest, source_folder))
    print(
        json.dumps(
            {
                "result": "pass",
                "frozenOwnedFilesVerified": len(owned),
                "packetFreezeSha256": file_sha(freeze_path),
                "commonImage": IMAGE,
                "commonReceiptBindings": len(common_receipts),
                "allNativeTextReceiptsVerified": len(all_receipts),
                "caches": results,
                "newNetworkRequests": 0,
                "dockerDaemonCalls": 0,
                "providerCalls": 0,
                "upstreamExecution": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
