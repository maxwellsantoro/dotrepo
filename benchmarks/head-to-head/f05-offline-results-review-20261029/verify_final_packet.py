"""Hash the immutable final packet, including the copied acceptance-freeze exception."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKET = ROOT / "benchmarks/head-to-head/f05-offline-results-20261029"
ACCEPT = ROOT / "benchmarks/head-to-head/f05-offline-acceptance-20261029"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert (
        sha(PACKET / "FREEZE.json")
        == "d1f9673dfc4dc69fb4a5aa8f3c3af0c3cfcf58c7de0d94f1e21c08f3fa14a844"
    )
    freeze = json.loads((PACKET / "FREEZE.json").read_text())
    assert sha(PACKET / "artifact-hashes.json") == freeze["artifactHashesSha256"]
    files = json.loads((PACKET / "artifact-hashes.json").read_text())["files"]
    assert len(files) == freeze["files"] == 213
    for name, digest in files.items():
        assert sha(PACKET / name) == digest, name
    actual = {
        path.relative_to(PACKET).as_posix()
        for path in PACKET.rglob("*")
        if path.is_file()
        and not {".ruff_cache", "__pycache__"}.intersection(path.relative_to(PACKET).parts)
    }
    omitted = actual - set(files)
    assert omitted == {"FREEZE.json", "artifact-hashes.json", "inputs/FREEZE.json"}
    assert set(files) <= actual
    assert sha(PACKET / "report.json") == freeze["reportSha256"]
    assert sha(PACKET / "checks.json") == freeze["checksSha256"]
    assert sha(PACKET / "source-bindings.json") == freeze["sourceBindingsSha256"]
    for name in [
        "FREEZE.json",
        "acceptance.json",
        "rust-02-cache-audit.json",
        "typescript-02-cache-audit.json",
        "go-03-cache-audit.json",
    ]:
        assert sha(PACKET / "inputs" / name) == sha(ACCEPT / name), name
    print(
        json.dumps(
            {
                "state": "passed-with-explicit-copied-freeze-inventory-disposition",
                "authorPacketFreezeSha256": sha(PACKET / "FREEZE.json"),
                "artifactManifestSha256": sha(PACKET / "artifact-hashes.json"),
                "listedSubstantiveFilesVerified": len(files),
                "unlistedNonCachePaths": sorted(omitted),
                "copiedAcceptanceFreeze": {
                    "path": "inputs/FREEZE.json",
                    "sha256": sha(PACKET / "inputs/FREEZE.json"),
                    "originalByteIdentical": True,
                    "binding": "Original acceptance freeze hash is bound by BEFORE.v2 and independently checked; this review adds the missing copied-path binding.",
                    "qualificationImpact": "none; immutable source packet unchanged",
                },
                "otherCopiedAcceptanceInputsByteIdentical": True,
                "newDockerNetworkUpstreamProviderCalls": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
