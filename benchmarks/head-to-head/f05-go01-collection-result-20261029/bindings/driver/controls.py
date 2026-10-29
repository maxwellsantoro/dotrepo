"""Owned deterministic collection controls; no real process or socket is allowed."""

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import tarfile

import collection
import listing

HERE = Path(__file__).resolve().parent


def denied(*args, **kwargs):
    raise AssertionError("Real process/network prohibited in author controls")


subprocess.Popen = denied
socket.socket = denied
socket.create_connection = denied


def package_rows():
    return [
        {
            "ImportPath": name,
            "Dir": listing.CWD + name.removeprefix(listing.PREFIX),
            "Name": name.rsplit("/", 1)[-1],
            "GoFiles": ["owned.go"],
            "TestGoFiles": ["owned_test.go"] if name in listing.REQUIRED else [],
            "Module": {"Path": listing.PREFIX, "Dir": listing.CWD},
        }
        for name in [*listing.REQUIRED, listing.PREFIX + "/owned_zero_tests"]
    ]


def events(rows):
    result = []
    for row in rows:
        name = row["ImportPath"]
        result.append({"Action": "start", "Package": name})
        if row["TestGoFiles"]:
            result.append(
                {
                    "Action": "output",
                    "Package": name,
                    "Output": "TestOwnedListing\nBenchmarkOwnedListing\n",
                }
            )
            result.append({"Action": "pass", "Package": name})
        else:
            result.append(
                {"Action": "output", "Package": name, "Output": "? " + name + " [no test files]\n"}
            )
            result.append({"Action": "skip", "Package": name})
    return result


def metadata(plan):
    env = {
        "PATH": "x",
        "RUSTUP_HOME": "x",
        "CARGO_HOME": "x",
        "GOTOOLCHAIN": "local",
        "GOENV": "off",
        **plan["environment"],
    }
    return {
        "Image": collection.IMAGE,
        "Mounts": [],
        "Config": {"User": "1000:1000", "Env": [f"{k}={v}" for k, v in env.items()]},
        "HostConfig": {
            "Binds": [],
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "CapAdd": None,
            "SecurityOpt": ["no-new-privileges"],
            "PidMode": "",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "UsernsMode": "",
            "UTSMode": "",
            "Init": True,
            "Devices": [],
            "DeviceRequests": None,
            "VolumesFrom": None,
            "Links": None,
            "PortBindings": {},
            "PublishAllPorts": False,
            "Memory": 4294967296,
            "MemorySwap": 4294967296,
            "NanoCpus": 3000000000,
            "PidsLimit": 256,
            "NetworkMode": "none",
            "Tmpfs": {
                "/workspace": "rw,exec,nosuid,nodev,size=8g,uid=1000,gid=1000,mode=0700",
                "/tmp": "rw,exec,nosuid,nodev,size=512m,uid=1000,gid=1000,mode=0700",
                "/workspace/dependency-cache": "rw,exec,nosuid,nodev,size=1g,uid=1000,gid=1000,mode=0700",
            },
        },
        "NetworkSettings": {"Networks": {"none": {"IPAddress": "", "Gateway": ""}}},
    }


FILES = {"README": {"sha256": hashlib.sha256(b"owned").hexdigest(), "bytes": 5, "mode": 0o644}}


for package in package_rows():
    for field in ["GoFiles", "CgoFiles", "TestGoFiles", "XTestGoFiles"]:
        for name in package.get(field, []):
            FILES[package["Dir"].removeprefix("/workspace/repository/") + "/" + name] = dict(
                FILES["README"]
            )


def synthetic_subject(plan, temporary):
    """Owned shape fixture, never a real review/admission artifact."""
    source = collection.HERE
    destination = temporary / "subject"
    destination.mkdir()
    for name in ["plan.json", *plan["scripts"], *plan["localFiles"]]:
        (destination / name).write_bytes((source / name).read_bytes())
    collection.write(
        destination / "FREEZE.json",
        {
            "identity": plan["identity"],
            "driverPlanSha256": collection.file_sha(destination / "plan.json"),
            "artifactSha256": {
                name: collection.file_sha(destination / name)
                for name in ["plan.json", *plan["scripts"], *plan["localFiles"]]
            },
            "syntheticOwnedSubjectFixture": True,
        },
    )
    collection.HERE = destination
    return collection.current_subject(plan)


def passed_review(subject):
    return {
        "state": "independent-go01-collection-driver-review-passed",
        "synthetic": False,
        "scope": "go01-collection-only",
        "subject": subject,
        "findings": [],
        "executionAuthorized": False,
        "nativeTaskAdmitted": False,
        "campaignAdmitted": False,
        "cacheGloballyQualified": False,
        "fixtureDisclosure": "Owned synthetic shape only, not a real independent review or execution authorization",
    }


class Fake:
    def __init__(self, plan, failure=None, clock=None):
        self.plan, self.failure, self.clock, self.calls = plan, failure, clock, []

    def command(self, output, label, argv, **kwargs):
        self.calls.append((label, argv))
        if self.failure == "cancellation" and label == "go-test-list":
            raise KeyboardInterrupt("owned cancellation")
        raw, error, exit_code = b"", None, 0
        if label == "image-inspect":
            raw = json.dumps(
                [
                    {
                        "Id": collection.IMAGE,
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
            ).encode()
        elif label in {"container-inspect", "offline-final-inspect"}:
            state = metadata(self.plan)
            for failure, key, value in [
                ("pid", "PidMode", "container:another"),
                ("ipc", "IpcMode", "host"),
                ("cgroup", "CgroupnsMode", "host"),
                ("caps", "CapAdd", ["SYS_ADMIN"]),
                ("resource", "Memory", 1),
                ("network", "NetworkMode", "bridge"),
            ]:
                if self.failure == failure:
                    state["HostConfig"][key] = value
            if self.failure == "env":
                state["Config"]["Env"].append("CI=true")
            raw = json.dumps([state]).encode()
        elif label in {"tools-before", "tools-after"}:
            raw = self.plan["expectedToolOutput"].encode()
            if self.failure == "tools" and label == "tools-after":
                raw += b"changed"
        elif label in {"source-tree-before", "source-tree-after"}:
            row = collection.tree_expected(FILES)
            if label.endswith("after") and self.failure in {
                "source-added",
                "source-deleted",
                "source-type",
                "source-content",
            }:
                row["sha256"] = "0" * 64
            raw = json.dumps(row).encode()
        elif label == "go-env":
            row = deepcopy(self.plan["expectedGoEnv"])
            if self.failure == "go-context":
                row["CC"] = "gcc"
            raw = json.dumps(row).encode()
        elif label == "go-list":
            rows = package_rows()
            if self.failure == "missing-package":
                rows.pop(0)
            raw = b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"
            if self.failure == "empty-packages":
                raw = b""
            if self.failure == "truncated-packages":
                raw = raw[:-5]
            if self.failure == "malformed-packages":
                raw = b'{"ImportPath":"x","ImportPath":"y"}'
        elif label == "go-test-list":
            rows = events(package_rows())
            if self.failure == "missing-terminal":
                rows.pop()
            if self.failure == "body-event":
                rows[1]["Test"] = "TestOwnedListing"
            if self.failure == "unexpected-skip":
                rows[2]["Action"] = "skip"
            if self.failure == "empty-cases":
                for row in rows:
                    if row.get("Output", "").startswith("Test"):
                        row["Output"] = ""
            if self.failure == "empty-one-required":
                rows[1]["Output"] = ""
            raw = b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"
            if self.failure == "malformed-events":
                raw = b"not JSON\n"
            if self.failure == "truncated-events":
                raw = raw[:-3]
            if self.failure == "invalid-utf8":
                raw = b"\xff\n"
            if self.failure == "output-cap":
                raw = b"x" * (collection.TEXT_LIMIT + 1)
            if self.failure == "exit":
                exit_code = 1
            if self.failure == "timeout":
                error = "attempt deadline exhausted"
            if self.failure == "cancellation-receipt":
                error = "KeyboardInterrupt: owned cancellation"
        elif label == "post-cleanup-inspect":
            exit_code = 1
        elif label == "post-cleanup-list" and self.failure == "absence":
            raw = b"owned-container-still-present\n"
        if label == "cleanup" and self.failure == "cleanup":
            exit_code = 1
        if label == "create" and self.failure == "create":
            exit_code = 1
        if label == "go-list" and self.failure == "work-deadline":
            self.clock[0] = 901
        incoming = kwargs.get("stdin_path")
        digest = collection.file_sha(incoming) if incoming else hashlib.sha256(b"").hexdigest()
        if label == "source-provision":
            digest = collection.SOURCE
        if label == "cache-provision":
            digest = self.plan["projection"]["archive"]["sha256"]
            if self.failure == "cache-stream":
                digest = "0" * 64
        folder = output / "logs" / label
        folder.mkdir(parents=True)
        (folder / "stdout.bin").write_bytes(raw)
        (folder / "stderr.bin").write_bytes(b"")
        receipt = {
            "argv": argv,
            "exitCode": exit_code,
            "error": error,
            "cancelled": self.failure == "cancellation-receipt" and label == "go-test-list",
            "stdout": raw.decode(errors="replace"),
            "stderr": "",
            "stdoutSha256": hashlib.sha256(raw).hexdigest(),
            "stderrSha256": hashlib.sha256(b"").hexdigest(),
            "stdinSha256": digest,
            "stdinBytes": Path(incoming).stat().st_size if incoming else 0,
            "costUsd": None,
        }
        collection.write(
            folder / "receipt.json",
            {key: value for key, value in receipt.items() if key not in {"stdout", "stderr"}},
        )
        return receipt


def main():
    plan = collection.load_plan()
    checks = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-collection-synthetic-") as temporary:
        temp = Path(temporary).resolve()
        for name in ["audit", "source-review"]:
            collection.write(temp / (name + ".json"), {"syntheticOwnedControl": True})
        subject = synthetic_subject(plan, temp)
        collection.write(temp / "driver-review.json", passed_review(subject))
        acceptance = {
            "driverSubject": subject,
            "state": "coordinator-accepted-go01-no-npm-go-projection-collection",
            "synthetic": False,
            **{key: plan[key] for key in ["sourceArchiveSha256", "imageId", "environmentSha256"]},
            "projectionSha256": plan["projection"]["archive"]["sha256"],
            "projectionSpecSha256": plan["projectionSpecSha256"],
            "initAndTestMainExecutionAccepted": True,
            "noNpmProvisioning": True,
            "nativeTaskAdmitted": False,
            "campaignAdmitted": False,
            "cacheGloballyQualified": False,
        }
        for key, name in [
            ("sourceScopeReviewFreeze", "source-review"),
            ("projectionReviewFreeze", "audit"),
            ("driverReviewFreeze", "driver-review"),
        ]:
            path = temp / (name + ".json")
            acceptance[key] = {"path": str(path), "sha256": collection.file_sha(path)}
        acceptance["sourceScopeReviewFreeze"] = deepcopy(plan["collectionScopeReview"])
        acceptance["projectionReviewFreeze"] = deepcopy(plan["collectionScopeReview"])
        accept = temp / "acceptance.json"
        collection.write(accept, acceptance)
        auth = {
            "state": "coordinator-authorized-single-go01-collection-attempt",
            "synthetic": False,
            "planSha256": collection.file_sha(HERE / "plan.json"),
            "authorFreezeSha256": subject["authorFreezeSha256"],
            "output": str(temp / "shape-output"),
            "scratch": str(temp / "shape-scratch"),
            "commands": collection.COMMANDS,
            "limits": plan["limits"],
            "maxAttempts": 1,
            "collectionAcceptance": {"path": str(accept), "sha256": collection.file_sha(accept)},
        }
        authpath = temp / "auth.json"
        collection.write(authpath, auth)
        collection.authorize(plan, authpath, Path(auth["output"]), Path(auth["scratch"]))
        checks.append(
            {"case": "owned valid assertion shape is not real authorization", "passed": True}
        )
        for kind, member_type, name, denied_payload in [
            ("regular-go-cache", tarfile.REGTYPE, "go/pkg/mod/owned", False),
            ("npm-root", tarfile.REGTYPE, "npm-cache/_cacache/owned", False),
            ("cache-symlink", tarfile.SYMTYPE, "go/pkg/mod/owned", False),
            ("cache-hardlink", tarfile.LNKTYPE, "go/pkg/mod/owned", False),
            ("cache-traversal", tarfile.REGTYPE, "go/pkg/mod/../owned", False),
            ("protected-source-alias", tarfile.REGTYPE, "go/pkg/mod/owned", True),
        ]:
            archive = temp / (kind + ".tar")
            data = b"owned synthetic payload"
            with tarfile.open(archive, "w") as stream:
                member = tarfile.TarInfo(name)
                member.type, member.size = (
                    member_type,
                    len(data) if member_type == tarfile.REGTYPE else 0,
                )
                member.linkname = "elsewhere" if member_type != tarfile.REGTYPE else ""
                stream.addfile(member, io.BytesIO(data) if member.size else None)
            try:
                collection.boundary.scan_archive(
                    archive,
                    deadline=lambda: None,
                    roots=("go/pkg/mod",),
                    deny={hashlib.sha256(data).hexdigest()} if denied_payload else set(),
                )
                accepted_archive = True
            except ValueError:
                accepted_archive = False
            assert accepted_archive == (kind == "regular-go-cache")
            checks.append({"case": kind, "passed": True, "archiveAccepted": accepted_archive})
        for name in [
            "state",
            "plan",
            "paths",
            "command",
            "bool-attempts",
            "bool-limit",
            "full-parent-cache",
            "environment",
            "native-admission",
            "campaign",
            "global-cache",
            "npm",
            "init",
            "audit",
        ]:
            a, accepted = deepcopy(auth), deepcopy(acceptance)
            if name == "state":
                a["state"] = "NOT_AUTHORIZED"
            if name == "plan":
                a["planSha256"] = "0" * 64
            if name == "paths":
                a["scratch"] += "/other"
            if name == "command":
                a["commands"] = ["go test ./..."]
            if name == "bool-attempts":
                a["maxAttempts"] = True
            if name == "bool-limit":
                a["limits"] = {**plan["limits"], "cpus": True}
            if name == "full-parent-cache":
                accepted["projectionSha256"] = (
                    "583fad501fa7b1a1a6d85ab8fe4b890786e39c1e016f785d6d3fb9d060383284"
                )
            if name == "environment":
                accepted["environmentSha256"] = "0" * 64
            if name == "native-admission":
                accepted["nativeTaskAdmitted"] = True
            if name == "campaign":
                accepted["campaignAdmitted"] = True
            if name == "global-cache":
                accepted["cacheGloballyQualified"] = True
            if name == "npm":
                accepted["noNpmProvisioning"] = False
            if name == "init":
                accepted["initAndTestMainExecutionAccepted"] = False
            if name == "audit":
                accepted["projectionReviewFreeze"]["sha256"] = "0" * 64
            candidate = temp / (name + "-accept.json")
            collection.write(candidate, accepted)
            a["collectionAcceptance"] = {
                "path": str(candidate),
                "sha256": collection.file_sha(candidate),
            }
            path = temp / (name + "-auth.json")
            collection.write(path, a)
            try:
                collection.authorize(plan, path, Path(auth["output"]), Path(auth["scratch"]))
            except (ValueError, KeyError, FileNotFoundError):
                pass
            else:
                raise AssertionError("bad authorization accepted: " + name)
            checks.append({"case": "reject-authorization-" + name, "passed": True})

        def owned_inputs(*args):
            source, cache = temp / "source.bytes", temp / "cache.bytes"
            source.write_bytes(b"owned")
            cache.write_bytes(b"cache")
            return (
                source,
                cache,
                FILES,
                {"go/pkg/mod/owned": FILES["README"]},
                collection.tree_expected(FILES),
            )

        failures = [
            None,
            "authorization",
            "preflight",
            "create",
            "pid",
            "ipc",
            "cgroup",
            "caps",
            "resource",
            "network",
            "env",
            "cache-stream",
            "go-context",
            "missing-package",
            "empty-packages",
            "truncated-packages",
            "malformed-packages",
            "missing-terminal",
            "body-event",
            "unexpected-skip",
            "empty-cases",
            "empty-one-required",
            "malformed-events",
            "truncated-events",
            "invalid-utf8",
            "output-cap",
            "exit",
            "timeout",
            "cancellation",
            "cancellation-receipt",
            "source-added",
            "source-deleted",
            "source-type",
            "source-content",
            "tools",
            "work-deadline",
            "cleanup",
            "absence",
        ]
        for number, failure in enumerate(failures):
            clock = [0]
            fake = Fake(plan, failure, clock)

            def authorization(*args):
                collection.require(failure != "authorization", "owned auth rejection")
                return {"syntheticOwnedAssertion": True}

            def input_check(*args):
                collection.require(failure != "preflight", "owned preflight rejection")
                return owned_inputs(*args)

            output = temp / ("output-" + str(number))
            result = collection.run(
                authpath,
                output,
                temp / ("scratch-" + str(number)),
                backend=fake,
                plan_loader=lambda: deepcopy(plan),
                authorization_check=authorization,
                input_check=input_check,
                clock=lambda: clock[0],
            )
            assert (
                result["synthetic"] is True
                and result["taskOutcomeObserved"] is False
                and result["campaignAdmitted"] is False
                and result["cacheGloballyQualified"] is False
                and result["costUsd"] is None
            )
            assert (result["state"] == "native-top-level-collection-observed") == (
                failure is None
            ), (failure, result)
            labels = [row[0] for row in fake.calls]
            if result["containerCreateAttempted"]:
                assert "cleanup" in labels and "post-cleanup-list" in labels
            else:
                assert labels == []
            if failure == "go-context":
                assert "go-list" not in labels
            if failure in {"cancellation", "cancellation-receipt"}:
                assert result["cancelled"] is True
            if failure == "work-deadline":
                assert result["workBudgetExceeded"] is True
            checks.append(
                {
                    "case": "driver-" + str(failure),
                    "passed": True,
                    "result": result,
                    "commandLabels": labels,
                }
            )
    collection.write(
        HERE / "controls.json",
        {
            "passed": len(checks),
            "controls": checks,
            "actualCollectionOccurred": False,
            "realDaemonNetworkPackageNativeProviderCalls": 0,
        },
    )
    print(json.dumps({"passed": len(checks), "actualCollectionOccurred": False}))


if __name__ == "__main__":
    main()
