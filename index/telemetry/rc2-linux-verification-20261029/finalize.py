"""Verify retained Linux evidence and write an append-only artifact inventory via uv."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATTEMPT = HERE / "attempt-2"
VERSION = "2.0.0-rc.2"
COMMIT = "94e02bd43d7cae1e5b6cd37ebd7a2a66a9b2b773"
IMAGE = "sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


for receipt in HERE.glob("**/logs/*/receipt.json"):
    row = read(receipt)
    assert row["stdoutSha256"] == digest(receipt.parent / "stdout.txt"), receipt
    assert row["stderrSha256"] == digest(receipt.parent / "stderr.txt"), receipt
assert read(HERE / "attempt-1-disposition.json")["status"] == "verifier-configuration-failure"
assert read(HERE / "logs/attempt-1-cleanup/receipt.json")["exitCode"] == 0
assert read(ATTEMPT / "logs/cleanup/receipt.json")["exitCode"] == 0
assert digest(HERE / "controlled-source.tar") == digest(ATTEMPT / "controlled-source.tar")
assert (
    digest(HERE / "controlled-source.tar")
    == read(HERE / "preparation.json")["controlledSourceArchiveSha256"]
)
inspection = read(ATTEMPT / "logs/container-inspect/stdout.txt")[0]
assert inspection["Image"] == IMAGE
assert inspection["HostConfig"]["ReadonlyRootfs"] is True
assert inspection["HostConfig"]["CapDrop"] == ["ALL"]
assert "no-new-privileges" in inspection["HostConfig"]["SecurityOpt"]
assert inspection["Config"]["User"] == "1000:1000"
assert not inspection["Mounts"] and not inspection["NetworkSettings"]["Networks"]
assert all("exec" in flags.split(",") for flags in inspection["HostConfig"]["Tmpfs"].values())
for package in ("dotrepo-cli", "dotrepo-mcp", "dotrepo-lsp", "dotrepo"):
    metadata = read(ATTEMPT / f"registry-{package}.json")["version"]
    assert metadata["num"] == VERSION and metadata["crate"] == package and not metadata["yanked"]
    installs = read(ATTEMPT / f"logs/installed-metadata-{package}/stdout.txt")["installs"]
    assert len(installs) == 1
    assert next(iter(installs)).startswith(f"{package} {VERSION} (registry+")
    assert read(ATTEMPT / f"logs/crate-vcs-{package}/stdout.txt")["git"]["sha1"] == COMMIT
    assert not read(ATTEMPT / f"logs/crate-vcs-{package}/stdout.txt")["git"].get("dirty", False)
    checksum = (ATTEMPT / f"logs/crate-checksum-{package}/stdout.txt").read_text().split()[0]
    assert checksum == metadata["checksum"]
    assert read(ATTEMPT / f"logs/install-{package}/receipt.json")["exitCode"] == 0
controls = read(ATTEMPT / "controls-complete.json")
assert controls["safetyChecks"] == 40 and controls["nativeElfArm64Binaries"] == 5
assert controls["mcpResponses"] == 7 and controls["lspInitializeDiagnosticsShutdown"] == "passed"
assert controls["scriptSha256"] == digest(ATTEMPT / "check_linux.py")
assert all(row["result"] == "passed" for row in read(ATTEMPT / "safety-results.json")["results"])
write(
    HERE / "verification.json",
    {
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
        "status": "passed-with-retained-initial-verifier-configuration-failure",
        "version": VERSION,
        "sourceCommit": COMMIT,
        "imageId": IMAGE,
        "packages": ["dotrepo-cli", "dotrepo-mcp", "dotrepo-lsp", "dotrepo"],
        "exactLockedRegistryInstallations": 4,
        "packagedSourceAndRegistryChecksumMatches": 4,
        "controlledSafetyChecks": 40,
        "nativeArm64ElfBinaries": 5,
        "cliHelpChecks": 3,
        "standaloneAliasValidation": "passed",
        "mcpStdio": "passed-seven-responses",
        "lspStdio": "passed-initialize-diagnostics-shutdown-exit",
        "containersRemoved": True,
        "limits": [
            "Linux ARM64 container execution on macOS ARM64; not native Linux host execution",
            "No x86_64 release bundle executed",
            "Public Docker bridge network during registry installation, disconnected for controls",
            "Fresh Cargo home; sequential packages share container cache; host/VM caches uncontrolled",
            "Dotrepo-owned controlled fixtures only; no upstream project commands or model calls",
            "Packaging and safety evidence, not independent consumer usefulness",
        ],
    },
)
inventory = {
    str(path.relative_to(HERE)): digest(path)
    for path in sorted(HERE.rglob("*"))
    if path.is_file() and "__pycache__" not in path.parts and path.name != "artifact-hashes.json"
}
write(HERE / "artifact-hashes.json", {"algorithm": "sha256", "files": inventory})
print(f"Verified {len(inventory)} retained artifacts; four installs and 40 safety checks passed.")
