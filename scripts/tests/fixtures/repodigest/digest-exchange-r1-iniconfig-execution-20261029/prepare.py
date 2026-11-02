"""Freeze already acquired source/Git metadata and the prepared tool environment."""

import argparse
import ast
import io
import json
import subprocess
import tarfile
import tomllib
from pathlib import Path

from runner import PACKET, create, docker, inspect, sha, terminate, validate_limits


def prepare(checkout):
    if (PACKET / "INPUTS.json").exists():
        raise FileExistsError("inputs already frozen; preserve the original freeze")
    spec = json.loads((PACKET / "SPEC.json").read_text())
    old = PACKET.parent / spec["parentExperiment"]
    source_freeze = json.loads((old / "SOURCE-FREEZE.json").read_text())
    files = {
        name.removeprefix("sources/checkout/"): info["sha256"]
        for name, info in source_freeze["files"].items()
        if name.startswith("sources/checkout/")
    }
    for name, expected in files.items():
        if sha((checkout / name).read_bytes()) != expected:
            raise ValueError("acquired checkout differs from frozen source: " + name)

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(checkout), "-c", "core.fsmonitor=false", *args], text=True
        ).strip()

    if git("rev-parse", "HEAD") != spec["task"]["revision"] or git("status", "--porcelain"):
        raise ValueError("source checkout is dirty or has the wrong revision")
    image = (
        docker(
            "image",
            "inspect",
            "digest-exchange-iniconfig-execution:20261029",
            "--format",
            "{{.Id}}",
        )
        .stdout.decode()
        .strip()
    )
    reference = json.loads(
        docker(
            "image",
            "inspect",
            "digest-exchange-iniconfig-execution:20261029",
            "--format",
            "{{json .RepoDigests}}",
        ).stdout
    )[0]
    identity = create(reference, network="none")
    try:
        info = inspect(identity)
        validate_limits(info)
        tools = {
            name: docker("exec", identity, *command).stdout.decode().strip()
            for name, command in {
                "uv": ["uv", "--version"],
                "git": ["git", "--version"],
                "python": [
                    "uv",
                    "run",
                    "--no-project",
                    "--offline",
                    "--python",
                    "/usr/local/bin/python3.12",
                    "python",
                    "--version",
                ],
                "debianPackages": ["dpkg-query", "-W"],
            }.items()
        }
    finally:
        teardown = terminate(identity)
    (PACKET / "environment.json").write_text(
        json.dumps(
            {
                "imageId": image,
                "tools": tools,
                "container": info,
                "preparationProbeTeardown": teardown,
            },
            indent=2,
        )
        + "\n"
    )
    definitions = [
        node.name
        for node in ast.parse((checkout / "testing/test_iniconfig.py").read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    manifest = (json.dumps(files, indent=2) + "\n").encode()
    archive = PACKET / "source-checkout.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        stream.add(checkout, arcname="checkout")
        member = tarfile.TarInfo("source-manifest.json")
        member.size, member.mode = len(manifest), 0o644
        stream.addfile(member, io.BytesIO(manifest))
    if archive.stat().st_size > spec["budgets"]["sourceArchiveBytes"]:
        raise ValueError("source archive exceeds frozen budget")
    receipt = {
        "imageId": image,
        "imageReference": reference,
        "sourceArchiveSha256": sha(archive.read_bytes()),
        "sourceArchiveBytes": archive.stat().st_size,
        "codeSha256": {
            name: sha((PACKET / name).read_bytes())
            for name in ("Dockerfile", "prepare.py", "runner.py", "controller.py")
        },
        "expected": {
            "revision": spec["task"]["revision"],
            "tree": git("rev-parse", "HEAD^{tree}"),
            "architecture": "aarch64",
            "files": files,
            "testDefinitions": definitions,
            "lockedTools": {
                p["name"]: p["version"]
                for p in tomllib.loads((checkout / "uv.lock").read_text())["package"]
                if p["name"] in {"pytest", "pytest-xdist"}
            },
        },
        "gitDescribe": git("describe", "--tags", "--always"),
        "gitReferences": git("show-ref"),
        "gitShallow": git("rev-parse", "--is-shallow-repository"),
        "interpretation": "Full source checkout and Git metadata; synthesized recipe, not replay of the upstream sparse/wheel CI job.",
    }
    (PACKET / "INPUTS.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "imageId": image,
                "sourceArchiveBytes": archive.stat().st_size,
                "gitDescribe": receipt["gitDescribe"],
                "tools": {k: v for k, v in tools.items() if k != "debianPackages"},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    prepare(parser.parse_args().checkout.resolve())
