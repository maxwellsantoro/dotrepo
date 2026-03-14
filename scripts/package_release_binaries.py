#!/usr/bin/env python3

import argparse
import hashlib
import os
import shutil
import stat
import tarfile
import tomllib
from pathlib import Path

DEFAULT_BINARIES = ["dotrepo", "dotrepo-lsp", "dotrepo-mcp"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package release-style dotrepo binaries for one target platform."
    )
    parser.add_argument(
        "--bin-dir",
        default="target/release",
        help="Directory containing built binaries (default: target/release)",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Directory where packaged archives will be written (default: dist)",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target triple used to label the release bundle",
    )
    parser.add_argument(
        "--version",
        help="Override bundle version; defaults to workspace.package.version",
    )
    parser.add_argument(
        "--bin",
        dest="binaries",
        action="append",
        help="Binary to include; may be repeated. Defaults to dotrepo, dotrepo-lsp, dotrepo-mcp.",
    )
    return parser.parse_args()


def workspace_version(repo_root: Path) -> str:
    cargo_toml = repo_root / "Cargo.toml"
    with cargo_toml.open("rb") as handle:
        document = tomllib.load(handle)
    return document["workspace"]["package"]["version"]


def resolve_binary(bin_dir: Path, name: str) -> Path:
    candidates = [bin_dir / name, bin_dir / f"{name}.exe"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(f"missing built binary: {name} in {bin_dir}")


def write_readme(path: Path, version: str, target: str, binaries: list[str]) -> None:
    path.write_text(
        "\n".join(
            [
                f"dotrepo {version} ({target})",
                "",
                "Included binaries:",
                *[f"- {name}" for name in binaries],
                "",
                "Install by copying the binaries from ./bin/ onto your PATH.",
            ]
        )
        + "\n"
    )


def normalize_tarinfo(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    version = args.version or workspace_version(repo_root)
    binaries = args.binaries or DEFAULT_BINARIES
    bin_dir = (repo_root / args.bin_dir).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_name = f"dotrepo-{version}-{args.target}"
    staging_root = output_dir / bundle_name
    if staging_root.exists():
        shutil.rmtree(staging_root)
    (staging_root / "bin").mkdir(parents=True)

    for binary in binaries:
        source = resolve_binary(bin_dir, binary)
        destination = staging_root / "bin" / source.name
        shutil.copy2(source, destination)
        destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    write_readme(staging_root / "README.txt", version, args.target, binaries)

    archive_path = output_dir / f"{bundle_name}.tar.gz"
    if archive_path.exists():
        archive_path.unlink()
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(staging_root.rglob("*")):
            archive.add(
                path,
                arcname=str(Path(bundle_name) / path.relative_to(staging_root)),
                recursive=False,
                filter=normalize_tarinfo,
            )

    checksum_path = output_dir / f"{bundle_name}.sha256"
    checksum_path.write_text(f"{sha256(archive_path)}  {archive_path.name}\n")

    print(archive_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
