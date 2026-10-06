#!/usr/bin/env -S uv run python
"""Verify actual published 1.0.3 artifacts; never publish, tag, or dispatch a workflow."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import subprocess
import tarfile
import tomllib
import urllib.request

VERSION = "1.0.3"
TAG = f"v{VERSION}"
REPOSITORY = "maxwellsantoro/dotrepo"
MAX_DOWNLOAD = 64 * 1024 * 1024
PACKAGES = (
    "dotrepo-schema",
    "dotrepo-transport",
    "dotrepo-core",
    "dotrepo-cli",
    "dotrepo-mcp",
    "dotrepo-lsp",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url, destination, limit=MAX_DOWNLOAD):
    request = urllib.request.Request(
        url, headers={"User-Agent": "dotrepo-installed-release-verifier/1.0"}
    )
    started = now()
    count = 0
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=30) as response, destination.open("xb") as output:
        assert response.status == 200
        while chunk := response.read(min(65536, limit + 1 - count)):
            count += len(chunk)
            assert count <= limit, f"download exceeds {limit} bytes: {url}"
            digest.update(chunk)
            output.write(chunk)
    return {
        "url": url,
        "startedAt": started,
        "completedAt": now(),
        "bytes": count,
        "sha256": digest.hexdigest(),
    }


def capture(arguments, timeout=60, cwd=None):
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, (arguments, result.stderr[-65536:])
    return result.stdout


def logged(arguments, logfile, *, cwd, env=None, timeout=60):
    started = now()
    with logfile.open("xb") as output:
        process = subprocess.Popen(
            arguments,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
    assert code == 0, (arguments, code, logfile)
    return {
        "arguments": arguments,
        "startedAt": started,
        "completedAt": now(),
        "exitCode": code,
        "log": str(logfile),
        "logSha256": sha(logfile),
    }


def smoke_source(workflow, name, binary):
    lines = workflow.read_text().splitlines()
    header = f"      - name: Smoke test {name} stdio server"
    start = lines.index(header)
    begin = lines.index("          uv run python - <<'PY'", start) + 1
    end = lines.index("          PY", begin)
    assert all(line.startswith("          ") or not line for line in lines[begin:end])
    code = "\n".join(line[10:] for line in lines[begin:end]) + "\n"
    original = f'["cargo", "run", "-p", "dotrepo-{name.lower()}"]'
    assert code.count(original) == 1, "unexpected smoke command contract"
    code = code.replace(original, repr([str(binary)]))
    anchor = (
        'assert init["result"]["protocolVersion"] == "2025-11-25"'
        if name == "MCP"
        else 'assert init["result"]["serverInfo"]["name"] == "dotrepo-lsp"'
    )
    assert code.count(anchor) == 1
    code = code.replace(
        anchor, anchor + f'\nassert init["result"]["serverInfo"]["version"] == "{VERSION}"'
    )
    return code


def validate_members(archive, prefix):
    members = archive.getmembers()
    assert len(members) <= 512
    for member in members:
        name = PurePosixPath(member.name)
        assert not name.is_absolute() and ".." not in name.parts
        assert name.parts[0] == prefix
        assert member.isfile() or member.isdir(), "links/devices are unsupported"
        assert member.size <= 32 * 1024 * 1024
    return members


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--cargo-target-dir",
        type=Path,
        default=Path("/tmp/dotrepo-roadmap-stable-safety-registry-target"),
    )
    args = parser.parse_args()
    assert re.fullmatch(r"[0-9a-f]{40}", args.expected_commit)
    assert platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}, (
        "this verifier executes the mac ARM bundle"
    )
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "startedAt": now(),
        "version": VERSION,
        "expectedCommit": args.expected_commit,
        "status": "running",
        "stages": [],
        "limits": "Controlled local fixtures; no upstream commands, cloud writes, publication or independent consumer study.",
    }
    receipt_path = output / "receipt.json"

    def checkpoint():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")

    checkpoint()
    try:
        latest = json.loads(
            capture(
                [
                    "gh",
                    "release",
                    "view",
                    "--repo",
                    REPOSITORY,
                    "--json",
                    "tagName,isDraft,isPrerelease,publishedAt,url",
                ]
            )
        )
        assert latest["tagName"] == TAG and not latest["isDraft"] and not latest["isPrerelease"]
        (output / "latest-release.json").write_text(json.dumps(latest, indent=2) + "\n")
        release = json.loads(
            capture(
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
        assert release["tagName"] == TAG and not release["isDraft"] and not release["isPrerelease"]
        refs = capture(
            [
                "git",
                "ls-remote",
                "https://github.com/" + REPOSITORY + ".git",
                "refs/tags/" + TAG,
                "refs/tags/" + TAG + "^{}",
            ]
        )
        (output / "tag-refs.txt").write_text(refs)
        tag_refs = dict(line.split()[::-1] for line in refs.splitlines())
        commit = tag_refs.get("refs/tags/" + TAG + "^{}", tag_refs.get("refs/tags/" + TAG))
        assert commit == args.expected_commit, "published tag source mismatch"
        source = output / "source"
        capture(
            [
                "git",
                "clone",
                "--branch",
                TAG,
                "--depth",
                "1",
                "--single-branch",
                "https://github.com/" + REPOSITORY + ".git",
                str(source),
            ],
            timeout=120,
        )
        assert capture(["git", "rev-parse", "HEAD"], cwd=source).strip() == commit
        assert capture(["git", "status", "--porcelain"], cwd=source) == ""
        owner = tomllib.loads((source / "Cargo.toml").read_text())["workspace"]["package"][
            "version"
        ]
        assert owner == VERSION
        receipt["source"] = {
            "commit": commit,
            "version": owner,
            "cargoTomlSha256": sha(source / "Cargo.toml"),
            "cargoLockSha256": sha(source / "Cargo.lock"),
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
            expected_digest = asset["digest"]
            assert re.fullmatch(r"sha256:[0-9a-f]{64}", expected_digest)
            item = download(
                asset["url"], assets / name, 4096 if name.endswith(".sha256") else MAX_DOWNLOAD
            )
            assert item["bytes"] == asset["size"] and "sha256:" + item["sha256"] == expected_digest
            downloaded[name] = item
        for checksum in assets.glob("*.sha256"):
            parts = checksum.read_text().split()
            assert len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0])
            target = parts[1].lstrip("*")
            assert Path(target).name == target and target in downloaded
            assert downloaded[target]["sha256"] == parts[0]
            downloaded[target]["matchingChecksum"] = checksum.name
        for required in [
            f"dotrepo-{VERSION}-aarch64-apple-darwin.tar.gz",
            f"dotrepo-{VERSION}-x86_64-unknown-linux-gnu.tar.gz",
            f"dotrepo-mcp-{VERSION}.mcpb",
        ]:
            assert downloaded[required].get("matchingChecksum"), required
        receipt["assets"] = downloaded
        checkpoint()
        packages = output / "packages"
        packages.mkdir()
        receipt["packages"] = []
        for package in PACKAGES:
            metadata_path = packages / (package + "-api.json")
            download(
                f"https://crates.io/api/v1/crates/{package}/{VERSION}",
                metadata_path,
                2 * 1024 * 1024,
            )
            metadata = json.loads(metadata_path.read_text())["version"]
            assert metadata["num"] == VERSION and not metadata["yanked"]
            package_path = packages / f"{package}-{VERSION}.crate"
            item = download(
                f"https://crates.io/api/v1/crates/{package}/{VERSION}/download", package_path
            )
            assert item["sha256"] == metadata["checksum"]
            with tarfile.open(package_path, "r:gz") as archive:
                vcs_body = archive.extractfile(f"{package}-{VERSION}/.cargo_vcs_info.json").read(
                    4097
                )
                cargo_body = archive.extractfile(f"{package}-{VERSION}/Cargo.toml").read(
                    1024 * 1024 + 1
                )
                assert len(vcs_body) <= 4096 and len(cargo_body) <= 1024 * 1024
                vcs = json.loads(vcs_body)
                cargo = tomllib.loads(cargo_body.decode())
            assert vcs["git"]["sha1"] == commit and not vcs["git"].get("dirty", False)
            assert cargo["package"]["version"] == VERSION
            receipt["packages"].append(
                {
                    "package": package,
                    "version": VERSION,
                    "sourceCommit": vcs["git"]["sha1"],
                    "metadataSha256": sha(metadata_path),
                    **item,
                }
            )
            checkpoint()
        prefix = f"dotrepo-{VERSION}-aarch64-apple-darwin"
        extraction = output / "extracted"
        extraction.mkdir()
        with tarfile.open(assets / (prefix + ".tar.gz"), "r:gz") as archive:
            members = validate_members(archive, prefix)
            archive.extractall(extraction, members=members, filter="data")
        bundle = extraction / prefix
        assert f"dotrepo {VERSION} (aarch64-apple-darwin)" in (bundle / "README.txt").read_text()
        bins = bundle / "bin"
        receipt["bundleBinaries"] = {
            name: sha(bins / name)
            for name in ["dotrepo", "dotrepo-public-query", "dotrepo-mcp", "dotrepo-lsp"]
        }
        checks = Path(__file__).with_name("check_installed_safety.py")
        receipt["controlledChecksSourceSha256"] = sha(checks)
        receipt["stages"].append(
            logged(
                [
                    "uv",
                    "run",
                    "python",
                    str(checks),
                    "--bin",
                    str(bins / "dotrepo"),
                    "--source",
                    str(source),
                    "--output",
                    str(output / "bundle-safety.json"),
                ],
                output / "bundle-safety.log",
                cwd=source,
                timeout=120,
            )
        )
        for name in ["dotrepo", "dotrepo-public-query", "dotrepo-mcp", "dotrepo-lsp"]:
            receipt["stages"].append(
                logged([str(bins / name), "--help"], output / (name + "-help.log"), cwd=source)
            )
        fixture = source / "examples/native-minimal/.repo"
        before = sha(fixture)
        for name in ["MCP", "LSP"]:
            smoke = output / (name.lower() + "-stdio.py")
            smoke.write_text(
                smoke_source(
                    source / ".github/workflows/ci.yml", name, bins / ("dotrepo-" + name.lower())
                )
            )
            receipt["stages"].append(
                logged(
                    ["uv", "run", "python", str(smoke)],
                    output / (name.lower() + "-stdio.log"),
                    cwd=source,
                    timeout=45,
                )
            )
            assert sha(fixture) == before, "smoke changed source fixture"
        install_cwd = output / "cargo-working"
        install_cwd.mkdir()
        install = output / "registry-install"
        # Isolate Cargo configuration so workspace/global patch overrides cannot
        # turn a registry install into an installation of local candidate code.
        cargo_home = output / "cargo-home"
        cargo_home.mkdir()
        old_cargo_home = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))
        if (old_cargo_home / "registry").is_dir():
            (cargo_home / "registry").symlink_to(
                (old_cargo_home / "registry").resolve(), target_is_directory=True
            )
        env = dict(
            os.environ,
            CARGO_TARGET_DIR=str(args.cargo_target_dir.resolve()),
            CARGO_HOME=str(cargo_home),
        )
        receipt["stages"].append(
            logged(
                [
                    "cargo",
                    "install",
                    "dotrepo-cli",
                    "--version",
                    VERSION,
                    "--locked",
                    "--root",
                    str(install),
                ],
                output / "crates-install.log",
                cwd=install_cwd,
                env=env,
                timeout=1800,
            )
        )
        installed_packages = tomllib.loads((install / ".crates.toml").read_text())["v1"]
        identity = next(
            k for k in installed_packages if k.startswith(f"dotrepo-cli {VERSION} (registry+")
        )
        assert set(installed_packages[identity]) == {"dotrepo", "dotrepo-public-query"}
        receipt["runtime"] = {
            "cargo": capture(["cargo", "--version"]).strip(),
            "rustc": capture(["rustc", "-vV"]).strip(),
            "uv": capture(["uv", "--version"]).strip(),
            "python": capture(["uv", "run", "python", "--version"], cwd=source).strip(),
        }
        receipt["registryInstallation"] = {
            "identity": identity,
            "binarySha256": sha(install / "bin/dotrepo"),
            "cargoTargetDir": env["CARGO_TARGET_DIR"],
        }
        receipt["stages"].append(
            logged(
                [
                    "uv",
                    "run",
                    "python",
                    str(checks),
                    "--bin",
                    str(install / "bin/dotrepo"),
                    "--source",
                    str(source),
                    "--output",
                    str(output / "registry-safety.json"),
                ],
                output / "registry-safety.log",
                cwd=source,
                timeout=120,
            )
        )
        for path in [output / "bundle-safety.json", output / "registry-safety.json"]:
            safety = json.loads(path.read_text())
            assert safety["sourceCommit"] == commit and len(safety["results"]) == 27
            assert all(row["result"] == "passed" for row in safety["results"])
        assert capture(["git", "status", "--porcelain", "--untracked-files=no"], cwd=source) == ""
        receipt["status"] = "passed"
    except BaseException as exc:
        receipt["status"] = "failed"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        receipt["completedAt"] = now()
        checkpoint()
    print(f"Published {VERSION} artifact and installed safety verification passed: {receipt_path}")


if __name__ == "__main__":
    main()
