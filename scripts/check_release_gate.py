#!/usr/bin/env python3

import argparse
import json
import os
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
from pathlib import Path

DEFAULT_GENERATED_AT = "2026-03-10T18:30:00Z"
DEFAULT_STALE_AFTER = "2026-03-11T18:30:00Z"
DEFAULT_BASE_PATH = "/dotrepo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the release-surface gate for dotrepo."
    )
    parser.add_argument(
        "--output-root",
        default="release-gate",
        help="Directory where generated gate artifacts will be written (default: release-gate)",
    )
    parser.add_argument(
        "--base-path",
        default=DEFAULT_BASE_PATH,
        help=f"Hosted base path used for public export links (default: {DEFAULT_BASE_PATH})",
    )
    parser.add_argument(
        "--generated-at",
        default=DEFAULT_GENERATED_AT,
        help=f"Deterministic generatedAt timestamp for the public export (default: {DEFAULT_GENERATED_AT})",
    )
    parser.add_argument(
        "--stale-after",
        default=DEFAULT_STALE_AFTER,
        help=f"Deterministic staleAfter timestamp for the public export (default: {DEFAULT_STALE_AFTER})",
    )
    parser.add_argument(
        "--skip-vsix",
        action="store_true",
        help="Skip npm install and VSIX packaging",
    )
    return parser.parse_args()


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"+ {shlex.join(cmd)}", flush=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    subprocess.run(cmd, cwd=cwd, check=True, env=merged_env)


def capture(cmd: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def host_target(repo_root: Path) -> str:
    rustc_info = capture(["rustc", "-vV"], cwd=repo_root)
    for line in rustc_info.splitlines():
        if line.startswith("host: "):
            return line.removeprefix("host: ").strip()
    raise SystemExit("could not detect host target from rustc -vV")


def workspace_version(repo_root: Path) -> str:
    with (repo_root / "Cargo.toml").open("rb") as handle:
        document = tomllib.load(handle)
    return document["workspace"]["package"]["version"]


def extension_version(repo_root: Path) -> str:
    package_json = repo_root / "editors" / "vscode" / "package.json"
    data = json.loads(package_json.read_text())
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit(f"missing VS Code extension version in {package_json}")
    return version


def ensure_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"expected file was not created: {path}")


def expect_single(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        rendered = ", ".join(str(path) for path in paths) or "<none>"
        raise SystemExit(f"expected exactly one {description}, found {rendered}")
    return paths[0]


def verify_public_meta(public_dir: Path, expected_base_path: str) -> None:
    meta_path = public_dir / "v0" / "meta.json"
    inventory_path = public_dir / "v0" / "repos" / "index.json"
    ensure_file(meta_path)
    ensure_file(inventory_path)
    ensure_file(public_dir / "index.html")
    ensure_file(public_dir / ".nojekyll")

    meta = json.loads(meta_path.read_text())
    if not isinstance(meta.get("apiVersion"), str) or not meta["apiVersion"]:
        raise SystemExit(f"public export metadata is missing apiVersion: {meta_path}")
    if not isinstance(meta.get("snapshotDigest"), str) or not meta["snapshotDigest"]:
        raise SystemExit(f"public export metadata is missing snapshotDigest: {meta_path}")

    inventory = json.loads(inventory_path.read_text())
    repositories = inventory.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise SystemExit(f"public export inventory is empty: {inventory_path}")

    normalized_base = "/" if expected_base_path == "/" else expected_base_path.rstrip("/")
    for repo in repositories:
        links = repo.get("links")
        if not isinstance(links, dict):
            raise SystemExit(f"public export inventory entry is missing links: {repo}")
        summary_link = links.get("self")
        trust_link = links.get("trust")
        query_template = links.get("queryTemplate")
        if not isinstance(summary_link, str) or not summary_link.startswith(normalized_base):
            raise SystemExit(f"summary link does not honor base path {normalized_base}: {summary_link}")
        if not isinstance(trust_link, str) or not trust_link.startswith(normalized_base):
            raise SystemExit(f"trust link does not honor base path {normalized_base}: {trust_link}")
        if not summary_link.endswith("/index.json"):
            raise SystemExit(f"summary link should point at the exported index.json file: {summary_link}")
        if not trust_link.endswith("/trust.json"):
            raise SystemExit(f"trust link should point at the exported trust.json file: {trust_link}")
        if not isinstance(query_template, str) or not query_template.startswith(normalized_base):
            raise SystemExit(
                f"query template does not honor base path {normalized_base}: {query_template}"
            )
        for link in (summary_link, trust_link):
            relative = link.removeprefix(normalized_base).lstrip("/")
            ensure_file(public_dir / relative)


def verify_tar_contains_prefix(archive_path: Path, prefix: str) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
    if not any(name.startswith(prefix) for name in names):
        raise SystemExit(f"{archive_path} does not contain expected root prefix {prefix}")


def smoke_test_release_bundle(
    archive_path: Path, version: str, target: str, repo_root: Path
) -> None:
    """Extract the release tarball and run the shipped binaries."""
    with tempfile.TemporaryDirectory(prefix="dotrepo-smoke-") as tmp:
        extract_dir = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(extract_dir)

        bin_dir = extract_dir / f"dotrepo-{version}-{target}" / "bin"
        if not bin_dir.is_dir():
            raise SystemExit(f"extracted bundle missing bin/ directory: {bin_dir}")

        for binary in ["dotrepo", "dotrepo-lsp", "dotrepo-mcp"]:
            binary_path = bin_dir / binary
            if not binary_path.is_file():
                raise SystemExit(f"extracted bundle missing binary: {binary_path}")

            print(f"  smoke: {binary} --help", flush=True)
            result = subprocess.run(
                [str(binary_path), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise SystemExit(
                    f"{binary} --help failed (exit {result.returncode}): {result.stderr}"
                )

        example_root = repo_root / "examples" / "native-minimal"
        if example_root.is_dir():
            dotrepo_bin = str(bin_dir / "dotrepo")
            print("  smoke: dotrepo validate (from release binary)", flush=True)
            result = subprocess.run(
                [dotrepo_bin, "--root", str(example_root), "validate"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise SystemExit(
                    f"dotrepo validate failed (exit {result.returncode}): {result.stderr}"
                )


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_root = (repo_root / args.output_root).resolve()
    public_dir = output_root / "public"
    public_bundle_dir = output_root / "public-bundle"
    release_bundle_dir = output_root / "release-bundle"
    vsix_dir = output_root / "vsix"
    npm_cache_dir = output_root / "npm-cache"

    if output_root.exists():
        shutil.rmtree(output_root)
    public_bundle_dir.mkdir(parents=True, exist_ok=True)
    release_bundle_dir.mkdir(parents=True, exist_ok=True)
    vsix_dir.mkdir(parents=True, exist_ok=True)
    npm_cache_dir.mkdir(parents=True, exist_ok=True)

    run(["cargo", "run", "-p", "dotrepo-cli", "--", "validate-index"], cwd=repo_root)
    run(
        [
            "cargo",
            "test",
            "-p",
            "dotrepo-core",
            "--test",
            "public_export_fixture_pack",
            "--test",
            "public_query_fixture_pack",
            "--test",
            "public_error_fixture_pack",
            "--test",
            "public_contract_compatibility",
        ],
        cwd=repo_root,
    )
    run(
        [
            "cargo",
            "run",
            "-p",
            "dotrepo-cli",
            "--",
            "public",
            "export",
            "--index-root",
            "index",
            "--out-dir",
            str(public_dir),
            "--base-path",
            args.base_path,
            "--generated-at",
            args.generated_at,
            "--stale-after",
            args.stale_after,
        ],
        cwd=repo_root,
    )
    run(
        ["python3", "scripts/render_public_pages_landing.py", "--input", str(public_dir)],
        cwd=repo_root,
    )
    run(
        [
            "python3",
            "scripts/package_public_export.py",
            "--input",
            str(public_dir),
            "--output-dir",
            str(public_bundle_dir),
        ],
        cwd=repo_root,
    )

    run(
        ["cargo", "build", "--release", "-p", "dotrepo-cli", "-p", "dotrepo-lsp", "-p", "dotrepo-mcp"],
        cwd=repo_root,
    )
    target = host_target(repo_root)
    version = workspace_version(repo_root)
    run(
        [
            "python3",
            "scripts/package_release_binaries.py",
            "--bin-dir",
            "target/release",
            "--output-dir",
            str(release_bundle_dir),
            "--target",
            target,
        ],
        cwd=repo_root,
    )

    vsix_path = None
    if not args.skip_vsix:
        npm_env = {"npm_config_cache": str(npm_cache_dir)}
        run(["npm", "ci"], cwd=repo_root / "editors" / "vscode", env=npm_env)
        extension_version_value = extension_version(repo_root)
        vsix_path = vsix_dir / f"dotrepo-vscode-v{extension_version_value}.vsix"
        run(
            [
                "npx",
                "--yes",
                "@vscode/vsce",
                "package",
                "--out",
                str(vsix_path),
            ],
            cwd=repo_root / "editors" / "vscode",
            env=npm_env,
        )

    verify_public_meta(public_dir, args.base_path)

    public_bundle = expect_single(sorted(public_bundle_dir.glob("*.tar.gz")), "public export bundle")
    verify_tar_contains_prefix(public_bundle, public_bundle.stem.removesuffix(".tar"))

    release_bundle = expect_single(sorted(release_bundle_dir.glob("*.tar.gz")), "release binary bundle")
    release_checksum = release_bundle_dir / f"dotrepo-{version}-{target}.sha256"
    ensure_file(release_checksum)
    verify_tar_contains_prefix(release_bundle, f"dotrepo-{version}-{target}/")

    if vsix_path is not None:
        ensure_file(vsix_path)

    print("")
    print("release install smoke test")
    smoke_test_release_bundle(release_bundle, version, target, repo_root)
    print("  all release binaries passed smoke test")

    print("")
    print("release gate artifacts")
    print(f"  public tree: {public_dir}")
    print(f"  public bundle: {public_bundle}")
    print(f"  release bundle: {release_bundle}")
    if vsix_path is not None:
        print(f"  vsix: {vsix_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
