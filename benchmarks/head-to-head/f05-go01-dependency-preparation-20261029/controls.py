"""Synthetic archive/backend controls only. No subprocess, Docker or download."""

from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile

import boundaries
import prepare
from boundaries import require, sha, write

HERE = Path(__file__).resolve().parent


def sample(path, entries):
    with tarfile.open(path, "w", format=tarfile.PAX_FORMAT) as archive:
        for name, kind, raw in entries:
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(raw), 0o644
            if kind in ("link", "hardlink"):
                entry.type = tarfile.SYMTYPE if kind == "link" else tarfile.LNKTYPE
                entry.linkname, entry.size = raw.decode(), 0
            elif kind == "fifo":
                entry.type, entry.size = tarfile.FIFOTYPE, 0
            archive.addfile(entry, io.BytesIO(raw) if entry.isfile() else None)


def metadata(plan, offline=False):
    base = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "RUSTUP_HOME": "/usr/local/rustup",
        "CARGO_HOME": "/usr/local/cargo",
        "GOTOOLCHAIN": "local",
        "GOENV": "off",
    }
    env = {**base, **plan["environment"]}
    return {
        "Image": prepare.IMAGE,
        "Mounts": [],
        "Config": {"User": "1000:1000", "Env": [f"{k}={v}" for k, v in env.items()]},
        "HostConfig": {
            "Binds": [],
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "PidMode": "",
            "Memory": 4 * 1024**3,
            "MemorySwap": 4 * 1024**3,
            "NanoCpus": 3 * 10**9,
            "PidsLimit": 256,
            "NetworkMode": "bridge",
            "Tmpfs": {
                "/tmp": "rw,exec,nosuid,nodev,size=512m",
                "/workspace": "rw,exec,nosuid,nodev,size=8g",
                "/workspace/dependency-cache": "rw,exec,nosuid,nodev,size=1g",
            },
        },
        "NetworkSettings": {"Networks": {} if offline else {"bridge": {}}},
    }


class FakeBackend:
    def __init__(self, plan, failure=None, clock=None):
        self.plan, self.failure, self.clock, self.calls = plan, failure, clock, []

    def command(self, folder, label, argv, **kwargs):
        self.calls.append((label, argv))
        result = {"exitCode": 0, "error": None, "stdout": "", "stderr": "", "stdinSha256": sha(b"")}
        if label == self.failure:
            return {**result, "exitCode": 1, "error": "synthetic failure"}
        if label == "image-inspect":
            result["stdout"] = json.dumps(
                [
                    {
                        "Id": prepare.IMAGE,
                        "Os": "linux",
                        "Architecture": "arm64",
                        "Config": {
                            "Volumes": None,
                            "OnBuild": None,
                            "Env": [
                                "PATH=x",
                                "RUSTUP_HOME=x",
                                "CARGO_HOME=x",
                                "GOTOOLCHAIN=local",
                                "GOENV=off",
                            ],
                        },
                    }
                ]
            )
        elif label in ("container-inspect", "offline-inspect"):
            row = metadata(self.plan, label == "offline-inspect")
            # Match fake image environment exactly, apart from explicit overrides.
            base = {
                "PATH": "x",
                "RUSTUP_HOME": "x",
                "CARGO_HOME": "x",
                "GOTOOLCHAIN": "local",
                "GOENV": "off",
            }
            row["Config"]["Env"] = [
                f"{k}={v}" for k, v in {**base, **self.plan["environment"]}.items()
            ]
            if self.failure == "mount-admission":
                row["Mounts"] = [{"Source": "/host", "Destination": "/workspace"}]
            result["stdout"] = json.dumps([row])
        elif label == "source-provision":
            result["stdinSha256"] = "0" * 64 if self.failure == "source-stream" else prepare.SOURCE
        elif label.startswith("tools-"):
            result["stdout"] = "\n".join(self.plan["expectedToolLines"]) + "\n"
            if self.failure == "tool-change" and label == "tools-after":
                result["stdout"] += "changed\n"
        elif label.startswith("network-"):
            result["stdout"] = "10\n20\n" if label == "network-before" else "100\n200\n"
        elif label.startswith("cache-size-"):
            result["stdout"] = "1073741825 cache\n" if self.failure == "cache-cap" else "10 cache\n"
        elif label == "download-0" and self.failure == "deadline":
            self.clock[0] = 901
        elif label == "cache-export":
            entries = [
                ("npm-cache/_cacache/dependency", "regular", b"dependency"),
                ("go/pkg/mod/module/go.mod", "regular", b"module synthetic"),
            ]
            if self.failure == "export-link":
                entries.append(("go/pkg/mod/link", "link", b"module"))
            sample(kwargs["binary_path"], entries)
        elif label == "post-cleanup-inspect":
            result["exitCode"] = 1
        return result


def main():
    plan = prepare.load_plan()
    results = []
    with tempfile.TemporaryDirectory(prefix="synthetic-only-", dir=HERE) as temp:
        temp = Path(temp)
        good = ("npm-cache/_cacache/dependency", "regular", b"dependency")
        sample(temp / "good.tar", [good])
        files, size = boundaries.normalize_archive(
            temp / "good.tar",
            temp / "good-out.tar",
            deadline=lambda: None,
            source_bytes=1,
            deny=set(),
        )
        require(size == len(good[2]) and len(files) == 1, "positive packer control")
        results.append({"case": "regular bytes preserved", "passed": True})
        for name, entries in {
            "parent": [("go/pkg/mod/../escape", "regular", b"x")],
            "absolute": [("/go/pkg/mod/escape", "regular", b"x")],
            "empty-component": [("go/pkg/mod//x", "regular", b"x")],
            "colon": [("go/pkg/mod/x:y", "regular", b"x")],
            "outside-root": [("repository/Herebyfile.mjs", "regular", b"x")],
            "duplicate": [good, good],
            "symlink": [("go/pkg/mod/link", "link", b"x")],
            "hardlink": [("go/pkg/mod/link", "hardlink", b"x")],
            "fifo": [("go/pkg/mod/fifo", "fifo", b"")],
            "root-replaced-file": [("go/pkg/mod", "regular", b"x")],
        }.items():
            source = temp / (name + ".tar")
            sample(source, entries)
            try:
                boundaries.normalize_archive(
                    source,
                    temp / (name + "-out.tar"),
                    deadline=lambda: None,
                    source_bytes=1,
                    deny=set(),
                )
            except ValueError:
                results.append({"case": "reject-" + name, "passed": True})
            else:
                raise AssertionError(name)
        for name, raw, deny in [
            ("raw-gold-alias", b'{"synthetic":"hidden"}', {sha(b'{"synthetic":"hidden"}')}),
            (
                "canonical-gold-alias",
                b'{ "synthetic" : "hidden" }',
                {boundaries.canonical_digest(b'{"synthetic":"hidden"}')},
            ),
        ]:
            source = temp / (name + ".tar")
            sample(source, [(good[0], "regular", raw)])
            try:
                boundaries.normalize_archive(
                    source,
                    temp / (name + "-out.tar"),
                    deadline=lambda: None,
                    source_bytes=1,
                    deny=deny,
                )
            except ValueError:
                results.append({"case": name, "passed": True})
            else:
                raise AssertionError(name)
        try:
            boundaries.normalize_archive(
                temp / "good.tar",
                temp / "expanded-out.tar",
                deadline=lambda: None,
                source_bytes=1,
                deny=set(),
                expanded_limit=1,
            )
        except ValueError:
            results.append({"case": "expanded-cap", "passed": True})
        else:
            raise AssertionError("expanded cap")
        try:
            boundaries.normalize_archive(
                temp / "good.tar",
                temp / "sum-out.tar",
                deadline=lambda: None,
                source_bytes=2 * 1024**3,
                deny=set(),
            )
        except ValueError:
            results.append({"case": "source-cache-sum-cap", "passed": True})
        else:
            raise AssertionError("sum cap")
        try:
            boundaries.LimitedWriter(io.BytesIO(), 1).write(b"xx")
        except ValueError:
            results.append({"case": "stream-write-cap-before-write", "passed": True})
        else:
            raise AssertionError("transport cap")
        large = temp / "member-cap.tar"
        header = tarfile.TarInfo("go/pkg/mod/oversize")
        header.size = boundaries.FILE_LIMIT + 1
        large.write_bytes(header.tobuf() + b"\0" * 1024)
        try:
            boundaries.scan_archive(large, deadline=lambda: None, roots=boundaries.ROOTS)
        except ValueError:
            results.append({"case": "member-cap-before-body-read", "passed": True})
        else:
            raise AssertionError("member cap")
        auth = temp / "not-live-authorization.json"
        auth.write_text(json.dumps({"synthetic": True}))
        archive = temp / "synthetic-source.tar"
        sample(archive, [("README.md", "regular", b"synthetic source only")])

        def source_check(unused_plan, check):
            check()
            return archive, {"README.md": {"sha256": sha(b"synthetic source only")}}, 1, set()

        for name in [
            "success",
            "preflight",
            "unauthorized",
            "create",
            "download-1",
            "cache-cap",
            "deadline",
            "export-link",
            "disconnect",
            "mount-admission",
            "source-stream",
            "tool-change",
            "cleanup",
            "post-cleanup-list",
        ]:
            clock = [0]
            fake = FakeBackend(
                plan, None if name in ("success", "preflight", "unauthorized") else name, clock
            )

            def fail_preflight(unused_plan, check):
                raise ValueError("synthetic archive hash mismatch")

            outcome = prepare.run(
                auth,
                temp / (name + "-result"),
                temp / (name + "-scratch"),
                backend=fake,
                plan_loader=lambda: deepcopy(plan),
                source_check=fail_preflight if name == "preflight" else source_check,
                authorization_check=prepare.authorize
                if name == "unauthorized"
                else lambda p, a, o, s: {"synthetic": True},
                clock=lambda: clock[0],
            )
            require(
                outcome["synthetic"] is True
                and outcome["costUsd"] is None
                and outcome["taskOutcomeObserved"] is False
                and all(v is False for v in outcome["draftAuditFlags"].values()),
                name + " mislabeled evidence",
            )
            labels = [label for label, _ in fake.calls]
            if name == "success":
                require(
                    outcome["state"] == "download-cache-retained-unqualified"
                    and outcome["containerAbsent"] is True,
                    "positive fake flow",
                )
                require(labels.index("disconnect") < labels.index("cache-export"), "online export")
            else:
                require(
                    outcome["state"] != "download-cache-retained-unqualified", name + " accepted"
                )
            if name in ("preflight", "unauthorized"):
                require(
                    not fake.calls and (temp / (name + "-result") / "result.json").is_file(),
                    "failure lost or daemon called",
                )
            elif "create" in labels:
                require(
                    "cleanup" in labels and "post-cleanup-list" in labels, "failure cleanup missing"
                )
            results.append(
                {
                    "case": "synthetic-backend-" + name,
                    "passed": True,
                    "state": outcome["state"],
                    "stage": outcome["stage"],
                    "virtualCalls": labels,
                    "realDaemonCalls": 0,
                }
            )
        args = prepare.flags("synthetic-name", plan["environment"])
        require(
            not any(arg.startswith(("-v", "--volume", "--mount", "--pid=host")) for arg in args),
            "host isolation flags",
        )
        require(
            "--memory=4g" in args and "--memory-swap=4g" in args and "--network=bridge" in args,
            "resource flags",
        )
        results.append({"case": "frozen-container-argv", "passed": True})
    write(
        HERE / "controls.json",
        {
            "state": "synthetic controls only",
            "passed": len(results),
            "controls": results,
            "actualPreparationOccurred": False,
            "nativeCollectionOccurred": False,
            "realDockerNetworkProviderCalls": 0,
        },
    )


if __name__ == "__main__":
    main()
