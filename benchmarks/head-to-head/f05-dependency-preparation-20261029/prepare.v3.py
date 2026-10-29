"""Bounded source-free image build and download-only dependency acquisition.

No upstream scripts/tests/builds, models, profile reads or Docker host mounts.
The output cache descriptor remains unqualified pending independent audit and
offline full-scope requalification. Every Python operation runs through host uv.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import shutil
import subprocess
import tarfile
import time
import uuid

from control import HERE, checked, command, sha, write

SCRATCH = Path("/tmp/dotrepo-f05-dependency-preparation-20261029")
FIRST = HERE.parent / "f05-qualification-20261029"
LIMIT = 1024**3
ARCHIVE_LIMIT = 512 * 1024**2


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            digest.update(raw)
    return digest.hexdigest()


def current():
    return datetime.now(timezone.utc).isoformat()


def verify_plan():
    plan = json.loads((HERE / "plan.v3.json").read_text())
    for name, digest in plan["scripts"].items():
        assert file_sha(HERE / name) == digest, name
    assert file_sha(FIRST / "execution-freeze.v4.json") == plan["priorExecutionFreezeSha256"]
    return plan


def flags(name, image, online=False):
    return [
        "docker",
        "create",
        "--name",
        name,
        "--pull=never",
        "--platform=linux/arm64",
        "--init",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--network=" + ("bridge" if online else "none"),
        "--ipc=private",
        "--cgroupns=private",
        "--user=1000:1000",
        "--workdir=/workspace",
        "--memory=4g",
        "--memory-swap=4g",
        "--cpus=3",
        "--pids-limit=256",
        "--ulimit",
        "nofile=4096:4096",
        "--tmpfs",
        "/workspace:rw,exec,nosuid,nodev,size=4g,uid=1000,gid=1000,mode=0700",
        "--tmpfs",
        "/tmp:rw,exec,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=0700",
        "--tmpfs",
        "/workspace/dependency-cache:rw,exec,nosuid,nodev,size=1g,uid=1000,gid=1000,mode=0700",
        "--env",
        "HOME=/workspace/home",
        "--env",
        "TMPDIR=/workspace/tmp",
        "--env",
        "LANG=C.UTF-8",
        "--env",
        "CARGO_HOME=/workspace/dependency-cache/cargo",
        "--env",
        "CARGO_TARGET_DIR=/workspace/not-exported-target",
        "--env",
        "GOPATH=/workspace/dependency-cache/go",
        "--env",
        "GOCACHE=/workspace/not-exported-go-build",
        "--env",
        "GOTOOLCHAIN=local",
        "--env",
        "GOENV=off",
        "--env",
        "GOMAXPROCS=3",
        "--env",
        "GOPROXY=https://proxy.golang.org",
        "--env",
        "GOSUMDB=sum.golang.org",
        "--env",
        "GIT_CONFIG_GLOBAL=/dev/null",
        "--env",
        "GIT_CONFIG_NOSYSTEM=1",
        "--env",
        "GIT_TERMINAL_PROMPT=0",
        "--env",
        "NPM_CONFIG_CACHE=/workspace/dependency-cache/npm-cache",
        "--env",
        "NPM_CONFIG_USERCONFIG=/dev/null",
        "--env",
        "NPM_CONFIG_REGISTRY=https://registry.npmjs.org",
        "--env",
        "NPM_CONFIG_IGNORE_SCRIPTS=true",
        "--env",
        "NPM_CONFIG_AUDIT=false",
        "--env",
        "NPM_CONFIG_FUND=false",
        "--entrypoint=/bin/sh",
        image,
        "-c",
        "while :; do sleep 3600; done",
    ]


def admission(folder, name, image):
    response = checked(folder, "container-inspect", ["docker", "inspect", name])
    row = json.loads(response["stdout"])[0]
    host = row["HostConfig"]
    assert not row["Mounts"] and row["Image"] == image
    assert not host["Privileged"] and host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"]
    assert host["PidMode"] != "host" and host["Memory"] == 4 * 1024**3
    assert host["PidsLimit"] == 256 and host["NanoCpus"] == 3 * 10**9
    assert row["Config"]["User"] == "1000:1000"
    assert "no-new-privileges" in host["SecurityOpt"]


def call(folder, name, label, argv, **kwargs):
    return checked(
        folder,
        label,
        ["docker", "exec", *(["-i"] if kwargs.get("data") else []), name, *argv],
        **kwargs,
    )


def shell(folder, name, label, text, **kwargs):
    return call(folder, name, label, ["/bin/sh", "-eu", "-c", text], **kwargs)


def build(plan):
    folder = HERE / "image-attempt-3"
    folder.mkdir()
    context = SCRATCH / "context"
    context.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "Dockerfile.v3", context / "Dockerfile")
    for wrapper in ("npm", "npx"):
        shutil.copyfile(HERE / wrapper, context / wrapper)
        (context / wrapper).chmod(0o755)
    for number, image in enumerate(plan["inputImages"]):
        raw = checked(folder, f"input-image-{number}", ["docker", "image", "inspect", image])
        row = json.loads(raw["stdout"])[0]
        assert row["Id"] == image and row["Os"] == "linux" and row["Architecture"] == "arm64"
        assert not row["Config"].get("Volumes") and not row["Config"].get("OnBuild")
    for number, (image, alias) in enumerate(
        zip(plan["inputImages"], plan["localAliases"], strict=True)
    ):
        checked(folder, f"bind-local-alias-{number}", ["docker", "tag", image, alias])
        row = checked(folder, f"verify-local-alias-{number}", ["docker", "image", "inspect", alias])
        assert json.loads(row["stdout"])[0]["Id"] == image
    checked(
        folder,
        "build",
        [
            "docker",
            "build",
            "--network=none",
            "--pull=false",
            "--no-cache",
            "--progress=plain",
            "--tag=dotrepo-f05-common:20261029",
            str(context),
        ],
        timeout=600,
    )
    for number, (image, alias) in enumerate(
        zip(plan["inputImages"], plan["localAliases"], strict=True)
    ):
        row = checked(
            folder, f"verify-local-alias-after-{number}", ["docker", "image", "inspect", alias]
        )
        assert json.loads(row["stdout"])[0]["Id"] == image
    raw = checked(
        folder, "image-inspect", ["docker", "image", "inspect", "dotrepo-f05-common:20261029"]
    )
    image = json.loads(raw["stdout"])[0]
    assert image["Os"] == "linux" and image["Architecture"] == "arm64"
    assert not image["Config"].get("Volumes") and not image["Config"].get("OnBuild")
    assert {x.split("=", 1)[0] for x in image["Config"]["Env"]} == {
        "PATH",
        "RUSTUP_HOME",
        "CARGO_HOME",
        "GOTOOLCHAIN",
        "GOENV",
    }
    name = "dotrepo-f05-common-control-" + uuid.uuid4().hex[:10]
    try:
        checked(folder, "create", flags(name, image["Id"]))
        checked(folder, "start", ["docker", "start", name])
        admission(folder, name, image["Id"])
        shell(folder, name, "initialize", "mkdir -p /workspace/home /workspace/tmp")
        shell(
            folder,
            name,
            "tools",
            "rustc -vV; cargo --version; node --version; npm --version; npx --version; go version; uv --version; git --version; cc --version; uname -a; cat /etc/os-release; dpkg-query -W libpcap-dev libpcap0.8-dev libasound2-dev",
        )
        shell(
            folder,
            name,
            "packages",
            "dpkg-query -W -f='${Package}\\t${Version}\\t${Architecture}\\n'",
        )
        shell(folder, name, "environment", "env | sort")
        shell(
            folder,
            name,
            "credential-path-control",
            'test ! -e /root/.aws; test ! -e /root/.config/gcloud; test ! -e /root/.cargo/credentials; test ! -e /usr/local/cargo/credentials; test ! -e /var/run/docker.sock; test ! -e /workspace/repository; test -z "$(find /workspace/dependency-cache -mindepth 1 -print -quit)"',
        )
        write(
            HERE / "common-image.json",
            {
                "imageId": image["Id"],
                "recipeSha256": file_sha(HERE / "Dockerfile.v3"),
                "planSha256": file_sha(HERE / "plan.v3.json"),
                "inputImages": plan["inputImages"],
                "checkedAt": current(),
                "state": "source-free candidate; tool availability control only",
                "taskQualified": False,
                "all12EnvironmentEquivalence": False,
                "costUsd": None,
                "limitations": [
                    "No task source/setup/test executed in image control.",
                    "Known credential paths and exact image/environment provenance inspected; not an exhaustive credential-content audit.",
                ],
            },
        )
    finally:
        command(folder, "cleanup", ["docker", "rm", "-f", name])


def export_tar(folder, name, roots, target):
    """Capture bounded binary archive to disk, outside the 2MiB text trace cap."""
    argv = ["docker", "exec", name, "tar", "-C", "/workspace/dependency-cache", "-cf", "-", *roots]
    started, stamp = time.monotonic(), current()
    host_env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    error = None
    stderr_path = folder / "cache-export-stderr.txt"
    with target.open("xb") as output, stderr_path.open("xb") as stderr:

        def limit_file():
            resource.setrlimit(resource.RLIMIT_FSIZE, (ARCHIVE_LIMIT, ARCHIVE_LIMIT))

        process = subprocess.Popen(
            argv, stdout=output, stderr=stderr, env=host_env, preexec_fn=limit_file
        )
        while process.poll() is None:
            if time.monotonic() - started > 180:
                error = "archive-export-timeout"
            elif target.stat().st_size > ARCHIVE_LIMIT:
                error = "archive-byte-limit"
            elif stderr_path.stat().st_size > 2 * 1024**2:
                error = "stderr-byte-limit"
            if error:
                process.kill()
                break
            time.sleep(0.1)
        process.wait(timeout=10)
    receipt = {
        "argv": argv,
        "startedAt": stamp,
        "elapsedSeconds": time.monotonic() - started,
        "exitCode": process.returncode,
        "error": error,
        "archivePath": str(target),
        "archiveBytes": target.stat().st_size,
        "archiveSha256": file_sha(target),
        "stderrSha256": file_sha(stderr_path),
        "costUsd": None,
    }
    write(folder / "cache-export-receipt.json", receipt)
    assert process.returncode == 0 and error is None and target.stat().st_size <= ARCHIVE_LIMIT


def normalize(raw_path, output, roots, source_bytes):
    files, exclusions, expanded = {}, [], 0
    with tarfile.open(raw_path, mode="r:") as incoming, tarfile.open(output, mode="x") as archive:
        for member in incoming:
            name = member.name.rstrip("/")
            path = PurePosixPath(name)
            assert not path.is_absolute() and ".." not in path.parts
            assert any(name == root or name.startswith(root + "/") for root in roots)
            if member.isdir():
                continue
            assert member.isfile(), (
                f"nonregular cache member requires refusal/projection adjudication: {name}"
            )
            assert name not in files and member.size <= 128 * 1024**2
            expanded += member.size
            assert expanded <= LIMIT and expanded + source_bytes <= 2 * LIMIT
            assert len(files) < 200000
            raw = incoming.extractfile(member).read()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(raw), 0o755 if member.mode & 0o111 else 0o644
            info.uid = info.gid = info.mtime = 0
            import io

            archive.addfile(info, io.BytesIO(raw))
            files[name] = sha(raw)
    assert files and output.stat().st_size <= ARCHIVE_LIMIT
    return files, expanded, exclusions


def prepare(plan, task_id):
    folder = HERE / task_id
    folder.mkdir()
    scratch = SCRATCH / task_id
    scratch.mkdir(parents=True)
    spec = plan["tasks"][task_id]
    image = json.loads((HERE / "common-image.json").read_text())["imageId"]
    source = json.loads((FIRST / spec["sourceFolder"] / "acquisition.json").read_text())
    archive = Path(source["runtimeArchivePath"])
    assert file_sha(archive) == spec["sourceArchiveSha256"] == source["runtimeArchiveSha256"]
    assert source["task"]["revision"] == spec["revision"]
    name = "dotrepo-f05-cache-" + task_id + "-" + uuid.uuid4().hex[:10]
    result = {
        "taskId": task_id,
        "state": "incomplete",
        "imageId": image,
        "sourceArchiveSha256": spec["sourceArchiveSha256"],
        "sourceRevision": spec["revision"],
        "startedAt": current(),
        "costUsd": None,
        "costExclusions": ["No metered container/host/download charge source."],
        "upstreamScriptsOrTestsExecuted": False,
        "indexConsulted": False,
        "modelCalls": 0,
        "cacheAuditQualified": False,
    }
    start = time.monotonic()
    try:
        checked(folder, "create", flags(name, image, online=True))
        checked(folder, "start", ["docker", "start", name])
        admission(folder, name, image)
        shell(
            folder,
            name,
            "initialize",
            "mkdir -p /workspace/repository /workspace/home /workspace/tmp /workspace/dependency-cache",
        )
        call(
            folder,
            name,
            "source-provision",
            [
                "tar",
                "--extract",
                "--no-same-owner",
                "--no-same-permissions",
                "-C",
                "/workspace/repository",
            ],
            data=archive.read_bytes(),
            timeout=180,
        )
        shell(
            folder,
            name,
            "network-before",
            "cat /sys/class/net/eth0/statistics/rx_bytes /sys/class/net/eth0/statistics/tx_bytes",
        )
        prep_start = time.monotonic()
        for number, text in enumerate(spec["commands"]):
            remaining = 900 - (time.monotonic() - prep_start)
            assert remaining > 0
            shell(
                folder,
                name,
                f"download-{number}",
                "cd /workspace/repository; " + text,
                timeout=remaining,
            )
            size = shell(folder, name, f"cache-size-{number}", "du -sb /workspace/dependency-cache")
            assert int(size["stdout"].split()[0]) <= LIMIT
        result["setupSeconds"] = time.monotonic() - prep_start
        shell(folder, name, "tools-after-download", spec["toolProbe"])
        shell(
            folder,
            name,
            "network-after",
            "cat /sys/class/net/eth0/statistics/rx_bytes /sys/class/net/eth0/statistics/tx_bytes",
        )
        before = [int(x) for x in (folder / "logs/network-before/stdout.txt").read_text().split()]
        after = [int(x) for x in (folder / "logs/network-after/stdout.txt").read_text().split()]
        result["networkBytes"] = {
            "received": after[0] - before[0],
            "sent": after[1] - before[1],
            "basis": "container interface counters including headers/incidental traffic",
        }
        checked(folder, "disconnect-network", ["docker", "network", "disconnect", "bridge", name])
        inspected = checked(folder, "offline-inspect", ["docker", "inspect", name])
        assert not json.loads(inspected["stdout"])[0]["NetworkSettings"]["Networks"]
        raw_path, cache_path = scratch / "cache-export.tar", scratch / "cache.tar"
        export_tar(folder, name, spec["roots"], raw_path)
        files, expanded, exclusions = normalize(
            raw_path, cache_path, spec["roots"], source["sourceBytes"]
        )
        inventory = {
            "revision": spec["revision"],
            "files": files,
            "missingSubmodules": [],
            "missingLfsObjects": [],
            "limitations": [
                "Dependency download roots only; not upstream source or a checkout.",
                "Independent content/member audit and offline task requalification pending.",
            ],
        }
        write(folder / "inventory.json", inventory)
        provenance = {
            "revision": spec["revision"],
            "archiveSha256": file_sha(cache_path),
            "url": "https://" + source["task"]["repository"],
            "checkedAt": current(),
            "imageId": image,
            "sourceArchiveSha256": spec["sourceArchiveSha256"],
            "planSha256": file_sha(HERE / "plan.v3.json"),
            "roots": spec["roots"],
            "expandedBytes": expanded,
            "archiveBytes": cache_path.stat().st_size,
            "normalization": "Regular files only; UID/GID/mtime zero and permissions644/755; bytes unchanged. No links silently dropped.",
            "exclusions": exclusions,
            "independentAuditPending": True,
        }
        write(folder / "provenance.json", provenance)
        result.update(
            {
                "state": "download-cache-retained-unqualified",
                "archivePath": str(cache_path),
                "archiveSha256": provenance["archiveSha256"],
                "cacheExpandedBytes": expanded,
                "cacheArchiveBytes": cache_path.stat().st_size,
                "cacheFiles": len(files),
            }
        )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        result["elapsedSeconds"] = time.monotonic() - start
        command(folder, "cleanup", ["docker", "rm", "-f", name])
        write(folder / "result.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["build", "prepare"])
    parser.add_argument("--task", choices=["rust-02", "typescript-02", "go-03"])
    args = parser.parse_args()
    plan = verify_plan()
    if args.mode == "build":
        assert args.task is None
        build(plan)
    else:
        assert args.task is not None
        prepare(plan, args.task)


if __name__ == "__main__":
    main()
