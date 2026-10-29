#!/usr/bin/env -S uv run python
"""Verify actual public RC2 artifacts and local macOS installs; never publish."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import tarfile
import tomllib
import zipfile

VERSION = "2.0.0-rc.2"
TAG = f"v{VERSION}"
EXPECTED_COMMIT = "94e02bd43d7cae1e5b6cd37ebd7a2a66a9b2b773"
REPOSITORY = "maxwellsantoro/dotrepo"
PACKAGES = (
    "dotrepo-schema",
    "dotrepo-transport",
    "dotrepo-core",
    "dotrepo-cli",
    "dotrepo-mcp",
    "dotrepo-lsp",
    "dotrepo",
)
ROOT = Path(__file__).resolve().parents[3]
HISTORICAL = ROOT / "index/telemetry/stable-1.0.3-delivery-20261006/verify_publication.py"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("retained_release_helpers", HISTORICAL)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
helpers.VERSION = VERSION  # Version-bound smoke generation; historical bytes stay unchanged.


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def record_workflow(output, run_id):
    if run_id is None:
        return {"status": "unknown", "reason": "No actual release workflow ID supplied."}
    run = json.loads(helpers.capture(["gh", "api", f"repos/{REPOSITORY}/actions/runs/{run_id}"]))
    jobs = json.loads(
        helpers.capture(
            ["gh", "api", f"repos/{REPOSITORY}/actions/runs/{run_id}/jobs?per_page=100"]
        )
    )
    (output / "release-workflow.json").write_text(json.dumps(run, indent=2) + "\n")
    (output / "release-workflow-jobs.json").write_text(json.dumps(jobs, indent=2) + "\n")
    assert run["head_sha"] == EXPECTED_COMMIT
    assert len(jobs["jobs"]) == jobs["total_count"], "retain all jobs rather than truncate"
    return {
        "url": run["html_url"],
        "status": run["status"],
        "conclusion": run["conclusion"],
        "headSha": run["head_sha"],
        "jobs": [
            {
                "name": row["name"],
                "status": row["status"],
                "conclusion": row["conclusion"],
                "url": row["html_url"],
            }
            for row in jobs["jobs"]
        ],
        "linuxInterpretation": "Linux artifact builds are not public-install execution. Only explicitly observed install/test jobs establish that evidence.",
    }


def verify_mcpb(assets, downloaded):
    path = assets / f"dotrepo-mcp-{VERSION}.mcpb"
    parity = {}
    with zipfile.ZipFile(path) as bundle:
        members = bundle.infolist()
        assert len(members) <= 128 and sum(row.file_size for row in members) <= 128 * 1024 * 1024
        assert all(
            not PurePosixPath(row.filename).is_absolute()
            and ".." not in PurePosixPath(row.filename).parts
            for row in members
        )
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["version"] == VERSION and manifest["name"] == "dotrepo-mcp"
        for target, platform_key, member in [
            ("aarch64-apple-darwin", "darwin", "server/darwin-arm64/dotrepo-mcp"),
            ("x86_64-unknown-linux-gnu", "linux", "server/linux-x64/dotrepo-mcp"),
        ]:
            tarball = assets / f"dotrepo-{VERSION}-{target}.tar.gz"
            with tarfile.open(tarball, "r:gz") as archive:
                helpers.validate_members(archive, f"dotrepo-{VERSION}-{target}")
                raw = archive.extractfile(f"dotrepo-{VERSION}-{target}/bin/dotrepo-mcp").read()
            assert raw == bundle.read(member)
            assert (
                manifest["server"]["mcp_config"]["platform_overrides"][platform_key]["command"]
                == "${__dirname}/" + member
            )
            parity[target] = {
                "member": member,
                "sha256": digest_bytes(raw),
                "execution": "not executed by binary-parity check",
            }
    return {
        "version": manifest["version"],
        "sha256": downloaded[path.name]["sha256"],
        "binaryParity": parity,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--release-run", type=int)
    parser.add_argument("--phase", choices=["bundle", "full"], default="full")
    args = parser.parse_args()
    assert platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}
    output = args.output_root.resolve()
    assert output.parent == Path("/tmp").resolve() and output.name.startswith(
        "dotrepo-rc2-delivery-"
    )
    output.mkdir(exist_ok=False)
    receipt = {
        "version": VERSION,
        "tag": TAG,
        "expectedCommit": EXPECTED_COMMIT,
        "startedAt": helpers.now(),
        "status": "running",
        "stages": [],
        "packages": [],
        "pendingPackages": list(PACKAGES),
        "localPlatform": {"system": platform.system(), "machine": platform.machine()},
        "linuxExecution": {
            "status": "not executed locally",
            "checksumVerificationIsExecution": False,
        },
        "historicalHelper": {
            "path": str(HISTORICAL.relative_to(ROOT)),
            "sha256": helpers.sha(HISTORICAL),
        },
        "limits": "Controlled own-project fixtures and public release provenance only; no third-party builds, publication, settings changes or independent consumer experiment.",
    }

    def checkpoint():
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    checkpoint()
    try:
        receipt["releaseWorkflow"] = record_workflow(output, args.release_run)
        release = json.loads(
            helpers.capture(
                [
                    "gh",
                    "release",
                    "view",
                    TAG,
                    "--repo",
                    REPOSITORY,
                    "--json",
                    "tagName,targetCommitish,publishedAt,isDraft,isPrerelease,assets,url",
                ]
            )
        )
        (output / "release.json").write_text(json.dumps(release, indent=2) + "\n")
        assert release["tagName"] == TAG and not release["isDraft"] and release["isPrerelease"]
        refs = helpers.capture(
            [
                "git",
                "ls-remote",
                f"https://github.com/{REPOSITORY}.git",
                f"refs/tags/{TAG}",
                f"refs/tags/{TAG}^{{}}",
            ]
        )
        (output / "tag-refs.txt").write_text(refs)
        refmap = dict(line.split()[::-1] for line in refs.splitlines())
        commit = refmap.get(f"refs/tags/{TAG}^{{}}", refmap.get(f"refs/tags/{TAG}"))
        assert commit == EXPECTED_COMMIT
        source = output / "source"
        helpers.capture(
            [
                "git",
                "clone",
                "--branch",
                TAG,
                "--depth",
                "1",
                "--single-branch",
                f"https://github.com/{REPOSITORY}.git",
                str(source),
            ],
            timeout=120,
        )
        assert helpers.capture(["git", "rev-parse", "HEAD"], cwd=source).strip() == commit
        assert helpers.capture(["git", "status", "--porcelain"], cwd=source) == ""
        cargo = tomllib.loads((source / "Cargo.toml").read_text())
        assert cargo["workspace"]["package"]["version"] == VERSION
        receipt["source"] = {
            "commit": commit,
            "cargoTomlSha256": helpers.sha(source / "Cargo.toml"),
            "cargoLockSha256": helpers.sha(source / "Cargo.lock"),
        }
        assets = output / "assets"
        assets.mkdir()
        downloaded = {}
        for asset in release["assets"]:
            name = asset["name"]
            assert Path(name).name == name
            assert asset["url"].startswith(
                f"https://github.com/{REPOSITORY}/releases/download/{TAG}/"
            )
            assert re.fullmatch(r"sha256:[0-9a-f]{64}", asset["digest"])
            row = helpers.download(
                asset["url"],
                assets / name,
                4096 if name.endswith(".sha256") else helpers.MAX_DOWNLOAD,
            )
            assert row["bytes"] == asset["size"] and "sha256:" + row["sha256"] == asset["digest"]
            downloaded[name] = row
        for checksum in assets.glob("*.sha256"):
            parts = checksum.read_text().split()
            assert len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0])
            name = parts[1].lstrip("*")
            assert Path(name).name == name and downloaded[name]["sha256"] == parts[0]
            downloaded[name]["matchingChecksum"] = checksum.name
        for name in [
            f"dotrepo-{VERSION}-aarch64-apple-darwin.tar.gz",
            f"dotrepo-{VERSION}-x86_64-unknown-linux-gnu.tar.gz",
            f"dotrepo-mcp-{VERSION}.mcpb",
        ]:
            assert downloaded[name].get("matchingChecksum")
        receipt["assets"] = downloaded
        receipt["mcpb"] = verify_mcpb(assets, downloaded)
        checkpoint()
        registry_url = f"https://registry.modelcontextprotocol.io/v0.1/servers/io.github.maxwellsantoro%2Fdotrepo/versions/{VERSION}"
        helpers.download(registry_url, output / "mcp-registry.json", 2 * 1024 * 1024)
        registry = json.loads((output / "mcp-registry.json").read_text())
        server = registry.get("server", registry)
        assert server["name"] == "io.github.maxwellsantoro/dotrepo" and server["version"] == VERSION
        assert len(server["packages"]) == 1
        package = server["packages"][0]
        expected_url = (
            f"https://github.com/{REPOSITORY}/releases/download/{TAG}/dotrepo-mcp-{VERSION}.mcpb"
        )
        assert package["registryType"] == "mcpb" and package["version"] == VERSION
        assert (
            package["identifier"] == expected_url
            and package["fileSha256"] == receipt["mcpb"]["sha256"]
        )
        receipt["mcpRegistry"] = {
            "url": registry_url,
            "version": VERSION,
            "mcpbChecksumVerified": True,
            "responseSha256": helpers.sha(output / "mcp-registry.json"),
        }
        extraction = output / "extracted"
        extraction.mkdir()
        prefix = f"dotrepo-{VERSION}-aarch64-apple-darwin"
        with tarfile.open(assets / f"{prefix}.tar.gz", "r:gz") as archive:
            archive.extractall(
                extraction, members=helpers.validate_members(archive, prefix), filter="data"
            )
        bins = extraction / prefix / "bin"
        assert (
            f"dotrepo {VERSION} (aarch64-apple-darwin)"
            in (extraction / prefix / "README.txt").read_text()
        )
        receipt["bundleBinaries"] = {
            name: helpers.sha(bins / name)
            for name in ["dotrepo", "dotrepo-public-query", "dotrepo-mcp", "dotrepo-lsp"]
        }
        checks = Path(__file__).with_name("check_installed_safety.py").resolve()
        receipt["controlledChecksSourceSha256"] = helpers.sha(checks)

        def check_cli(binary, label):
            help_text = helpers.capture([str(binary), "--help"], cwd=source)
            assert "Usage: dotrepo" in help_text
            receipt.setdefault("cliIdentity", {})[label] = {
                "binarySha256": helpers.sha(binary),
                "selfReportedVersion": None,
                "versionBinding": "Versioned bundle README/tag or exact registry installation identity; published CLI has no --version flag.",
            }
            receipt["stages"].append(
                helpers.logged(
                    [
                        "uv",
                        "run",
                        "python",
                        str(checks),
                        "--bin",
                        str(binary),
                        "--source",
                        str(source),
                        "--output",
                        str(output / f"{label}-safety.json"),
                    ],
                    output / f"{label}-safety.log",
                    cwd=source,
                    timeout=180,
                )
            )
            return VERSION

        def check_stdio(binary_dir, label):
            for name in ["MCP", "LSP"]:
                smoke = output / f"{label}-{name.lower()}-stdio.py"
                smoke.write_text(
                    helpers.smoke_source(
                        source / ".github/workflows/ci.yml",
                        name,
                        binary_dir / f"dotrepo-{name.lower()}",
                    )
                )
                receipt["stages"].append(
                    helpers.logged(
                        ["uv", "run", "python", str(smoke)],
                        output / f"{label}-{name.lower()}-stdio.log",
                        cwd=source,
                        timeout=45,
                    )
                )

        check_cli(bins / "dotrepo", "bundle")
        check_stdio(bins, "bundle")
        if args.phase == "bundle":
            receipt["status"] = "public_assets_and_local_macos_bundle_checks_passed; crates_pending"
            print(
                f"RC2 asset/macOS bundle receipt; package/install verification pending: {output / 'receipt.json'}"
            )
            return
        packages = output / "packages"
        packages.mkdir()
        for name in PACKAGES:
            metadata_path = packages / f"{name}-metadata.json"
            helpers.download(
                f"https://crates.io/api/v1/crates/{name}/{VERSION}", metadata_path, 2 * 1024 * 1024
            )
            metadata = json.loads(metadata_path.read_text())["version"]
            assert metadata["num"] == VERSION and not metadata["yanked"]
            crate = packages / f"{name}-{VERSION}.crate"
            downloaded_crate = helpers.download(
                f"https://crates.io/api/v1/crates/{name}/{VERSION}/download", crate
            )
            assert downloaded_crate["sha256"] == metadata["checksum"]
            with tarfile.open(crate, "r:gz") as archive:
                vcs = json.loads(
                    archive.extractfile(f"{name}-{VERSION}/.cargo_vcs_info.json").read(4097)
                )
                manifest = tomllib.loads(
                    archive.extractfile(f"{name}-{VERSION}/Cargo.toml").read(1024 * 1024).decode()
                )
                compared = []
                for member in archive.getmembers():
                    relative = PurePosixPath(member.name)
                    assert not relative.is_absolute() and ".." not in relative.parts
                    assert relative.parts[0] == f"{name}-{VERSION}"
                    if not member.isfile():
                        continue
                    suffix = PurePosixPath(*relative.parts[1:])
                    local = source / "crates" / name / str(suffix)
                    if str(suffix) == "Cargo.toml.orig":
                        local = source / "crates" / name / "Cargo.toml"
                    if (
                        local.is_file()
                        and not local.is_symlink()
                        and (
                            suffix.suffix == ".rs"
                            or str(suffix) in {"Cargo.toml.orig", "README.md"}
                        )
                    ):
                        assert archive.extractfile(member).read() == local.read_bytes(), str(suffix)
                        compared.append(str(suffix))
                assert any(path.endswith(".rs") for path in compared), name
            assert vcs["git"]["sha1"] == commit and not vcs["git"].get("dirty", False)
            assert manifest["package"]["name"] == name and manifest["package"]["version"] == VERSION
            receipt["packages"].append(
                {
                    "package": name,
                    "version": VERSION,
                    "sourceCommit": commit,
                    "metadataSha256": helpers.sha(metadata_path),
                    "sourcePathsCompared": compared,
                    **downloaded_crate,
                }
            )
            receipt["pendingPackages"].remove(name)
            checkpoint()
        install_cwd = output / "cargo-working"
        install_cwd.mkdir()
        cargo_home = output / "cargo-home"
        cargo_home.mkdir()
        target = output / "cargo-target"
        env = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "HOME",
                "RUSTUP_HOME",
                "TMPDIR",
                "SDKROOT",
                "MACOSX_DEPLOYMENT_TARGET",
                "LANG",
                "LC_ALL",
                "SSL_CERT_FILE",
                "SSL_CERT_DIR",
            }
        }
        env.update(CARGO_HOME=str(cargo_home), CARGO_TARGET_DIR=str(target))
        receipt["registryInstallIsolation"] = {
            "cargoHome": str(cargo_home),
            "cargoTarget": str(target),
            "registryCacheReused": False,
            "workspacePatchesUsed": False,
            "installedRootsFresh": True,
        }
        registry_bins = output / "registry" / "bin"
        for package in ["dotrepo-cli", "dotrepo-mcp", "dotrepo-lsp", "dotrepo"]:
            install = output / ("registry-alias" if package == "dotrepo" else "registry")
            receipt["stages"].append(
                helpers.logged(
                    [
                        "cargo",
                        "install",
                        package,
                        "--version",
                        f"={VERSION}",
                        "--locked",
                        "--root",
                        str(install),
                    ],
                    output / f"install-{package}.log",
                    cwd=install_cwd,
                    env=env,
                    timeout=1800,
                )
            )
            identities = tomllib.loads((install / ".crates.toml").read_text())["v1"]
            identity = next(
                key for key in identities if key.startswith(f"{package} {VERSION} (registry+")
            )
            receipt.setdefault("registryInstallations", []).append(
                {
                    "package": package,
                    "identity": identity,
                    "binaries": {
                        name: helpers.sha(install / "bin" / name) for name in identities[identity]
                    },
                }
            )
            checkpoint()
        check_cli(registry_bins / "dotrepo", "registry")
        check_cli(output / "registry-alias/bin/dotrepo", "registry-alias")
        check_stdio(registry_bins, "registry")
        receipt["runtime"] = {
            "cargo": helpers.capture(["cargo", "--version"]).strip(),
            "rustc": helpers.capture(["rustc", "-vV"]).strip(),
            "uv": helpers.capture(["uv", "--version"]).strip(),
        }
        assert (
            helpers.capture(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source)
            == ""
        )
        for label in ["bundle", "registry", "registry-alias"]:
            safety = json.loads((output / f"{label}-safety.json").read_text())
            assert safety["sourceCommit"] == commit and safety["version"] == VERSION
            assert len(safety["results"]) == 40 and all(
                row["result"] == "passed" for row in safety["results"]
            )
        receipt["status"] = "public_artifacts_and_local_macos_checks_passed"
    except BaseException as exc:
        receipt["status"] = "failed"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        receipt["completedAt"] = helpers.now()
        checkpoint()
    print(f"RC2 public artifact/local macOS verification receipt: {output / 'receipt.json'}")


if __name__ == "__main__":
    main()
