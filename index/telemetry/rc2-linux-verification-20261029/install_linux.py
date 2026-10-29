"""Fresh exact-version locked public-registry installs; run via host uv only."""

import json
from urllib.request import Request, urlopen
import uuid

from linux_session import (
    COMMIT,
    HERE,
    IMAGE,
    PACKAGES,
    VERSION,
    command,
    digest,
    execute,
    stamp,
    write,
)

for package in PACKAGES:
    url = f"https://crates.io/api/v1/crates/{package}/{VERSION}"
    with urlopen(
        Request(url, headers={"User-Agent": "dotrepo-release-verification"}), timeout=60
    ) as response:
        raw = response.read()
    (HERE / f"registry-{package}.json").write_bytes(raw)
    version = json.loads(raw)["version"]
    assert version["num"] == VERSION and version["crate"] == package and not version["yanked"]

name = "dotrepo-rc2-linux-" + uuid.uuid4().hex[:12]
argv = [
    "docker",
    "create",
    "--name",
    name,
    "--platform=linux/arm64",
    "--pull=never",
    "--init",
    "--read-only",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--user=1000:1000",
    "--network=bridge",
    "--workdir=/work",
    "--memory=5g",
    "--memory-swap=5g",
    "--cpus=3",
    "--pids-limit=256",
    "--tmpfs",
    "/work:rw,nosuid,nodev,size=4g,uid=1000,gid=1000,mode=0700",
    "--tmpfs",
    "/tmp:rw,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=0700",
    "--env",
    "HOME=/work/home",
    "--env",
    "CARGO_HOME=/work/cargo",
    "--env",
    "TMPDIR=/tmp",
    "--env",
    "CARGO_TARGET_DIR=/work/cargo-target",
    "--env",
    "CARGO_BUILD_JOBS=3",
    "--env",
    "CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse",
    "--entrypoint=/bin/sh",
    IMAGE,
    "-c",
    "while :; do sleep 3600; done",
]
assert command("create", argv)[0] == 0
write(
    HERE / "container-handle.json",
    {
        "name": name,
        "imageId": IMAGE,
        "createdAt": stamp(),
        "sourceCommit": COMMIT,
        "scriptSha256": digest(__import__("pathlib").Path(__file__)),
    },
)
assert command("start", ["docker", "start", name])[0] == 0
assert (
    execute("initialize", ["/bin/mkdir", "-p", "/work/home", "/work/source", "/work/cargo"])[0] == 0
)
for label, args in (
    ("kernel", ["uname", "-a"]),
    ("compiler", ["rustc", "-vV"]),
    ("cargo", ["cargo", "--version"]),
    ("identity", ["id"]),
    ("container-environment", ["env"]),
    ("fresh-cargo-home", ["ls", "-la", "/work/cargo"]),
):
    assert execute(label, args)[0] == 0
assert (
    execute(
        "provision-control-source",
        ["tar", "-xf", "-", "-C", "/work/source"],
        data=(HERE / "controlled-source.tar").read_bytes(),
    )[0]
    == 0
)
for package in PACKAGES:
    print(f"Installing exact locked {package} {VERSION} in fresh Linux ARM64 container", flush=True)
    result = execute(
        "install-" + package,
        [
            "cargo",
            "install",
            package,
            "--locked",
            "--version",
            "=" + VERSION,
            "--root",
            "/work/install-" + package,
            "--target-dir",
            "/work/cargo-target",
        ],
        timeout=3600,
    )
    assert result[0] == 0, f"{package} install failed; retained receipt/logs"
    assert (
        execute("installed-metadata-" + package, ["cat", f"/work/install-{package}/.crates2.json"])[
            0
        ]
        == 0
    )
    assert (
        execute(
            "installed-list-" + package,
            ["cargo", "install", "--list", "--root", f"/work/install-{package}"],
        )[0]
        == 0
    )
    assert (
        execute(
            "crate-vcs-" + package,
            [
                "/bin/sh",
                "-c",
                f"cat /work/cargo/registry/src/*/{package}-{VERSION}/.cargo_vcs_info.json",
            ],
        )[0]
        == 0
    )
    assert (
        execute(
            "crate-checksum-" + package,
            ["/bin/sh", "-c", f"sha256sum /work/cargo/registry/cache/*/{package}-{VERSION}.crate"],
        )[0]
        == 0
    )
    vcs = json.loads((HERE / "logs" / ("crate-vcs-" + package) / "stdout.txt").read_text())
    assert vcs["git"]["sha1"] == COMMIT and not vcs["git"].get("dirty", False)
    observed = (HERE / "logs" / ("crate-checksum-" + package) / "stdout.txt").read_text().split()[0]
    expected = json.loads((HERE / f"registry-{package}.json").read_text())["version"]["checksum"]
    assert observed == expected
    print(f"Installed {package}; exact package/source/checksum checks passed", flush=True)
assert command("disconnect-network", ["docker", "network", "disconnect", "bridge", name])[0] == 0
assert command("container-inspect", ["docker", "inspect", name])[0] == 0
write(
    HERE / "installation-complete.json",
    {
        "completedAt": stamp(),
        "version": VERSION,
        "sourceCommit": COMMIT,
        "packages": list(PACKAGES),
        "networkDisconnectedBeforeControls": True,
        "sourceProvenanceAndRegistryChecksumsMatched": True,
    },
)
print(
    "All four registry installations complete; container network disconnected for controls.",
    flush=True,
)
