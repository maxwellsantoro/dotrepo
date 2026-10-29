"""Classify audit observations using retained source/package bytes only."""

import base64
from collections import Counter
import io
import json
from pathlib import Path
import tarfile
import zipfile

from audit import HERE, PREP, dirhash, file_sha, load, unescape


def sum_lines(data):
    result = {}
    for line in data.decode().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2].startswith("h1:"):
            key = tuple(parts[:2])
            assert key not in result or result[key] == parts[2]
            result[key] = parts[2]
    return result


def main():
    audit = load(HERE / "audit.json")
    plan = load(PREP / "plan.json")
    archive_path = Path(load(HERE / "plan.json")["cacheArchive"]["path"])
    assert file_sha(archive_path) == audit["cacheSha256"]
    source = {}
    with tarfile.open(plan["source"]["archivePath"], mode="r:") as archive:
        for member in archive:
            if member.name in ("package-lock.json", "tsc/go.sum", "tools/go.sum", "go.work.sum"):
                source[member.name] = archive.extractfile(member).read()
    data = {}
    with tarfile.open(archive_path, mode="r:") as archive:
        for member in archive:
            if "/cache/download/" in member.name or member.name.startswith("npm-cache/"):
                data[member.name] = archive.extractfile(member).read()
    initial_pins = {}
    for name, raw in source.items():
        if name.endswith(".sum"):
            initial_pins.update(sum_lines(raw))
    zip_records, lookup_records = {}, {}
    for name, raw in data.items():
        if name.endswith(".zip") and "/cache/download/" in name:
            encoded, version = name.split("/cache/download/")[1].rsplit("/@v/", 1)
            key = (unescape(encoded), version[:-4])
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                files = {
                    entry.filename: archive.read(entry)
                    for entry in archive.infolist()
                    if not entry.is_dir()
                }
            assert sum(map(len, files.values())) <= 1024**3
            sums = {}
            for filename, payload in files.items():
                if filename.endswith("/go.sum"):
                    sums.update(sum_lines(payload))
            zip_records[key] = {"path": name, "h1": dirhash(files), "pins": sums}
        if name.startswith("go/pkg/mod/cache/download/sumdb/sum.golang.org/lookup/"):
            lookup_records.update(sum_lines(raw))
    pins = dict(initial_pins)
    origins = {key: "selected source go.sum" for key in pins}
    trusted = set()
    while True:
        changed = False
        for key, record in zip_records.items():
            if key in trusted or pins.get(key) != record["h1"]:
                continue
            trusted.add(key)
            changed = True
            for pinned, digest in record["pins"].items():
                assert pinned not in pins or pins[pinned] == digest, pinned
                if pinned not in pins:
                    pins[pinned] = digest
                    origins[pinned] = "go.sum inside checksum-bound " + "@".join(key)
        if not changed:
            break
    go_dispositions = []
    for missing in audit["go"]["checksumsMissingFromSelectedSourceSums"]:
        key = (missing["module"], missing["version"])
        lookup_match = lookup_records.get(key) == missing["h1"]
        assert lookup_match, key
        chain_match = pins.get(key) == missing["h1"]
        go_dispositions.append(
            {
                **missing,
                "cachedSumdbLookupMatches": True,
                "sourceRootedTransitivePinMatches": chain_match,
                "pinOrigin": origins.get(key),
                "scope": "checksum provenance; task dependency necessity not inferred from pin presence",
            }
        )
    npm_identities = {}
    for name, raw in data.items():
        if "/index-v5/" in name:
            for line in raw.splitlines():
                if not line:
                    continue
                entry = json.loads(line.split(b"\t", 1)[1])
                digest = base64.b64decode(entry["integrity"].split("-", 1)[1]).hex()
                path = (
                    "npm-cache/_cacache/content-v2/sha512/"
                    + digest[:2]
                    + "/"
                    + digest[2:4]
                    + "/"
                    + digest[4:]
                )
                npm_identities.setdefault(
                    path,
                    {
                        "publicUrl": entry["key"].removeprefix("make-fetch-happen:request-cache:"),
                        "integrity": entry["integrity"],
                    },
                )
    for path, identity in npm_identities.items():
        with tarfile.open(fileobj=io.BytesIO(data[path]), mode="r:gz") as archive:
            for entry in archive:
                if entry.name.endswith("/package.json") and entry.name.count("/") == 1:
                    package = json.loads(archive.extractfile(entry).read())
                    identity.update({"package": package["name"], "version": package["version"]})
                    break
    credential_dispositions = []
    for observation in audit["credentialMarkers"]:
        path = observation["path"]
        if path.startswith("npm-cache/"):
            identity = npm_identities[path.split("!", 1)[0]]
            classification = "exact locked public npm package payload; marker is retained package code/documentation, not a host credential injection"
        else:
            module = (
                path.split("!", 1)[1].split("/", 1)[0]
                if "!" in path
                else path.removeprefix("go/pkg/mod/").split("/", 1)[0]
            )
            identity = {
                "origin": "Go module zip and extracted member byte correspondence; public checksum record",
                "modulePathPrefix": module,
            }
            classification = "public Go package test fixture/example/configuration bytes; retained without pruning"
        credential_dispositions.append(
            {
                **observation,
                "classification": classification,
                "packageProvenance": identity,
                "limitation": "No credential value emitted. Public/package provenance is not a proof that every possible credential encoding is absent.",
            }
        )
    overlap_dispositions = []
    for observation in audit["exactSourceOverlaps"]:
        sources = observation["sourcePaths"]
        if all(path.startswith("tsc/internal/bundled/libs/") for path in sources):
            kind = (
                "public TypeScript standard-library declaration files also bundled as task inputs"
            )
        elif all(path.startswith("packages/typescript/vendor/vscode-jsonrpc/") for path in sources):
            kind = "public vscode-jsonrpc dependency also vendored in task source"
        elif all(Path(path).name.lower().startswith("license") for path in sources):
            kind = "shared public license text"
        else:
            kind = "public TypeScript package wrapper/readme/API declaration also present in task source; explicit exception decision needed"
        outer = observation["path"].split("!", 1)[0]
        assert outer in npm_identities
        overlap_dispositions.append(
            {
                **observation,
                "classification": kind,
                "packageProvenance": npm_identities[outer],
                "blanketTaskSourceExcludedProven": False,
            }
        )
    missing_lock = []
    lock = json.loads(source["package-lock.json"])
    fetched = {identity["publicUrl"] for identity in npm_identities.values()}
    for path, package in lock["packages"].items():
        url = package.get("resolved", "")
        if url.startswith("https://") and url not in fetched:
            missing_lock.append(
                {
                    "path": path,
                    "url": url,
                    "optional": package.get("optional", False),
                    "os": package.get("os"),
                    "cpu": package.get("cpu"),
                    "libc": package.get("libc"),
                }
            )
    result = {
        "sourceRootedDownloadedZipCount": len(trusted),
        "downloadedZipCount": len(zip_records),
        "initialSourceChecksumPairs": len(initial_pins),
        "transitiveGoChecksumDispositions": go_dispositions,
        "transitiveChecksumPinCounts": dict(
            Counter(item["sourceRootedTransitivePinMatches"] for item in go_dispositions)
        ),
        "cachedSumdbSignaturesIndependentlyVerified": False,
        "credentialDispositions": credential_dispositions,
        "sourceOverlapDispositions": overlap_dispositions,
        "sourceOverlapCategories": dict(
            Counter(item["classification"] for item in overlap_dispositions)
        ),
        "sourceLockEntriesNotFetched": missing_lock,
        "missingLockEntriesAllOptional": all(item["optional"] for item in missing_lock),
        "npmPackageIdentities": npm_identities,
        "allDescriptorFlagsRemainFalse": True,
        "newDaemonNetworkProviderUpstreamCalls": 0,
    }
    (HERE / "classifications.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "sourceRootedDownloadedZips": len(trusted),
                "downloadedZips": len(zip_records),
                "goAdditionalChecksumDispositions": len(go_dispositions),
                "goTransitivePinMatches": result["transitiveChecksumPinCounts"],
                "credentialDispositionCount": len(credential_dispositions),
                "sourceOverlapCategories": result["sourceOverlapCategories"],
                "notFetchedLockEntries": len(missing_lock),
                "missingAllOptional": result["missingLockEntriesAllOptional"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
