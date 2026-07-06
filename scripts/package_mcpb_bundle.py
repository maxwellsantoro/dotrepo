#!/usr/bin/env -S uv run python
"""Package the dotrepo MCP server as an MCPB bundle for the MCP registry.

Builds one `dotrepo-mcp-<version>.mcpb` (a zip with an MCPB manifest and the
per-platform `dotrepo-mcp` binaries) from the release tarballs produced by
`scripts/package_release_binaries.py`. The bundle covers every platform the
release ships; MCPB `platform_overrides` select the right binary at install
time. The zip is deterministic (fixed timestamps, sorted entries) so the same
inputs always produce the same `fileSha256`.
"""

import argparse
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

# Maps the release target triple to (MCPB platform key, bundle subdirectory).
# MCPB platform keys follow Node's process.platform: darwin, linux, win32.
TARGET_PLATFORMS = {
    "aarch64-apple-darwin": ("darwin", "server/darwin-arm64"),
    "x86_64-apple-darwin": ("darwin", "server/darwin-x64"),
    "x86_64-unknown-linux-gnu": ("linux", "server/linux-x64"),
    "aarch64-unknown-linux-gnu": ("linux", "server/linux-arm64"),
    "x86_64-pc-windows-msvc": ("win32", "server/win32-x64"),
}

FIXED_ZIP_DATE = (2020, 1, 1, 0, 0, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package dotrepo-mcp release binaries as an MCPB bundle."
    )
    parser.add_argument(
        "--tarball",
        action="append",
        required=True,
        help=(
            "Release tarball from package_release_binaries.py "
            "(dotrepo-<version>-<target>.tar.gz); may be repeated per platform."
        ),
    )
    parser.add_argument("--version", required=True, help="Release version, e.g. 1.0.0")
    parser.add_argument("--output-dir", required=True, help="Directory for the .mcpb bundle")
    parser.add_argument(
        "--update-server-json",
        help=(
            "Path to an MCP registry server.json to update in place with this "
            "bundle's version, release-asset identifier URL, and fileSha256."
        ),
    )
    return parser.parse_args()


def target_from_tarball_name(name: str, version: str) -> str:
    prefix = f"dotrepo-{version}-"
    stem = name.removesuffix(".tar.gz")
    if not stem.startswith(prefix):
        raise SystemExit(f"tarball name {name!r} does not match dotrepo-{version}-<target>.tar.gz")
    return stem.removeprefix(prefix)


def extract_mcp_binary(tarball: Path, version: str, target: str) -> bytes:
    member_path = f"dotrepo-{version}-{target}/bin/dotrepo-mcp"
    if target.endswith("windows-msvc"):
        member_path += ".exe"
    with tarfile.open(tarball, "r:gz") as archive:
        try:
            member = archive.getmember(member_path)
        except KeyError:
            raise SystemExit(f"{tarball} does not contain {member_path}")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise SystemExit(f"{tarball} member {member_path} is not a regular file")
        return extracted.read()


def build_manifest(version: str, platform_binaries: dict[str, str]) -> dict:
    platforms = sorted({TARGET_PLATFORMS[target][0] for target in platform_binaries})
    default_target = sorted(platform_binaries)[0]
    default_command = platform_binaries[default_target]
    overrides = {}
    for target, command in sorted(platform_binaries.items()):
        platform_key = TARGET_PLATFORMS[target][0]
        overrides[platform_key] = {"command": f"${{__dirname}}/{command}"}
    return {
        "manifest_version": "0.3",
        "name": "dotrepo-mcp",
        "display_name": "dotrepo",
        "version": version,
        "description": (
            "Trust-aware repository metadata: validate, query, and look up "
            ".repo records and the dotrepo.org public index without scraping."
        ),
        "author": {"name": "Maxwell Santoro", "url": "https://dotrepo.org"},
        "repository": {
            "type": "git",
            "url": "https://github.com/maxwellsantoro/dotrepo",
        },
        "homepage": "https://dotrepo.org",
        "license": "MIT",
        "server": {
            "type": "binary",
            "entry_point": platform_binaries[default_target],
            "mcp_config": {
                "command": f"${{__dirname}}/{default_command}",
                "args": [],
                "env": {},
                "platform_overrides": overrides,
            },
        },
        "compatibility": {"platforms": platforms},
    }


def write_deterministic_zip(path: Path, entries: dict[str, tuple[bytes, int]]) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            payload, mode = entries[name]
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DATE)
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    path.write_bytes(buffer.getvalue())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    platform_binaries: dict[str, str] = {}
    entries: dict[str, tuple[bytes, int]] = {}
    for raw in args.tarball:
        tarball = Path(raw)
        target = target_from_tarball_name(tarball.name, args.version)
        if target not in TARGET_PLATFORMS:
            raise SystemExit(f"unknown release target {target!r}; add it to TARGET_PLATFORMS")
        _, subdir = TARGET_PLATFORMS[target]
        binary_name = "dotrepo-mcp.exe" if target.endswith("windows-msvc") else "dotrepo-mcp"
        bundle_path = f"{subdir}/{binary_name}"
        entries[bundle_path] = (extract_mcp_binary(tarball, args.version, target), 0o755)
        platform_binaries[target] = bundle_path

    manifest = build_manifest(args.version, platform_binaries)
    entries["manifest.json"] = (
        (json.dumps(manifest, indent=2, sort_keys=False) + "\n").encode("utf-8"),
        0o644,
    )

    bundle_path = output_dir / f"dotrepo-mcp-{args.version}.mcpb"
    write_deterministic_zip(bundle_path, entries)
    digest = sha256(bundle_path)
    (output_dir / f"{bundle_path.name}.sha256").write_text(f"{digest}  {bundle_path.name}\n")

    if args.update_server_json:
        server_json_path = Path(args.update_server_json)
        server = json.loads(server_json_path.read_text())
        server["version"] = args.version
        packages = server.get("packages")
        if not isinstance(packages, list) or len(packages) != 1:
            raise SystemExit(f"{server_json_path} must contain exactly one package entry to update")
        packages[0]["identifier"] = (
            "https://github.com/maxwellsantoro/dotrepo/releases/download/"
            f"v{args.version}/{bundle_path.name}"
        )
        packages[0]["version"] = args.version
        packages[0]["fileSha256"] = digest
        server_json_path.write_text(json.dumps(server, indent=2) + "\n")
        print(f"updated {server_json_path}")

    print(bundle_path)
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
