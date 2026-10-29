"""No-daemon offline setup controls using owned files and deterministic fake receipts."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile

import setup

HERE = Path(__file__).resolve().parent


def metadata(plan):
    environment = {
        "PATH": "x",
        "RUSTUP_HOME": "x",
        "CARGO_HOME": "x",
        "GOTOOLCHAIN": "local",
        "GOENV": "off",
        **plan["environment"],
    }
    return {
        "Image": setup.IMAGE,
        "Mounts": [],
        "Config": {"User": "1000:1000", "Env": [f"{k}={v}" for k, v in environment.items()]},
        "HostConfig": {
            "Binds": [],
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "PidMode": "",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "UsernsMode": "",
            "UTSMode": "",
            "Init": True,
            "CapAdd": None,
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
                "/workspace": "rw,exec,nosuid,nodev,size=8g",
                "/tmp": "rw,exec,nosuid,nodev,size=512m",
                "/workspace/dependency-cache": "rw,exec,nosuid,nodev,size=1g",
            },
        },
        "NetworkSettings": {"Networks": {"none": {"IPAddress": "", "Gateway": ""}}},
    }


class Fake:
    def __init__(self, plan, failure=None, clock=None):
        self.plan, self.failure, self.clock, self.calls = plan, failure, clock, []

    def command(self, folder, label, argv, **kwargs):
        self.calls.append((label, argv))
        row = {"exitCode": 0, "error": None, "stdout": "", "stderr": "", "stdinSha256": "0" * 64}
        if label == self.failure:
            return {**row, "exitCode": 1, "error": "owned synthetic failure"}
        if label == "image-inspect":
            row["stdout"] = json.dumps(
                [
                    {
                        "Id": setup.IMAGE,
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
        elif label in ("container-inspect", "offline-final-inspect"):
            state = metadata(self.plan)
            if self.failure == "network":
                state["HostConfig"]["NetworkMode"] = "bridge"
            if self.failure == "mount":
                state["Mounts"] = [{"Source": "/host"}]
            row["stdout"] = json.dumps([state])
        elif label in ("source-provision", "cache-provision"):
            row["stdinSha256"] = setup.SOURCE if label == "source-provision" else setup.CACHE
            if self.failure == "stream-hash":
                row["stdinSha256"] = "0" * 64
        elif label.startswith("tools-"):
            row["stdout"] = "\n".join(self.plan["expectedToolLines"]) + "\n"
            if label == "tools-after" and self.failure == "tool-change":
                row["stdout"] += "changed\n"
        elif label == "npm-config":
            row["stdout"] = json.dumps(
                {
                    "offline": True,
                    "ignore-scripts": False,
                    "cache": "/workspace/dependency-cache/npm-cache",
                    "registry": "https://registry.npmjs.org",
                    "userconfig": "/dev/null",
                }
            )
            if self.failure == "config":
                row["stdout"] = '{"offline":false}'
        elif label == "npm-ci":
            row["stdout"] = "\n".join(self.plan["expectedHookMarkers"])
            if self.failure == "hook-observation":
                row["stdout"] = "no observed hooks"
            if self.failure == "deadline":
                self.clock[0] = 901
        elif label == "package-observations":
            observed = {
                "versions": self.plan["expectedPackageVersions"],
                "files": {
                    name: {"contained": True, "isFile": True, "mode": 493}
                    for name in self.plan["requiredObservedFiles"]
                },
            }
            if self.failure == "versions":
                observed["versions"] = {}
            if self.failure == "binlinks":
                observed["files"][self.plan["requiredObservedFiles"][0]] = None
            if self.failure == "outside":
                observed["files"][self.plan["requiredObservedFiles"][0]]["contained"] = False
            row["stdout"] = json.dumps(observed)
        elif label == "post-cleanup-inspect":
            row["exitCode"] = 1
        elif label == "post-cleanup-list" and self.failure == "absence":
            row["stdout"] = "still-present\n"
        return row


def main():
    plan = setup.load_plan()
    checks = []
    with tempfile.TemporaryDirectory(prefix="synthetic-only-", dir=HERE) as temporary:
        temp = Path(temporary)
        audit = temp / "independent-audit.json"
        audit.write_text('{"syntheticControlData":true}\n')
        acceptance = {
            "synthetic": False,
            "state": "coordinator-accepted-go01-cache-for-offline-npm-setup",
            "sourceArchiveSha256": setup.SOURCE,
            "imageId": setup.IMAGE,
            "cacheArchiveSha256": setup.CACHE,
            "cacheSpecSha256": plan["cacheSpecSha256"],
            "auditFreeze": {"path": str(audit.resolve()), "sha256": setup.file_sha(audit)},
            "publishedTaskPayloadDisposition": {
                "state": "allowed-only-for-offline-npm-setup-observation",
                "payloadsSha256": plan["publishedTaskPayloadsSha256"],
                "nativeTaskAdmitted": False,
                "campaignAdmitted": False,
            },
        }
        accept = temp / "acceptance.json"
        setup.write(accept, acceptance)
        output, scratch = temp / "authorized-output", temp / "authorized-scratch"
        auth = {
            "synthetic": False,
            "state": "coordinator-authorized-single-offline-npm-setup",
            "planSha256": setup.file_sha(HERE / "plan.json"),
            "output": str(output.resolve()),
            "scratch": str(scratch.resolve()),
            "command": setup.COMMAND,
            "limits": setup.LIMITS,
            "maxAttempts": 1,
            "cacheAcceptance": {"path": str(accept.resolve()), "sha256": setup.file_sha(accept)},
        }
        authpath = temp / "authorization.json"
        setup.write(authpath, auth)
        setup.authorize(plan, authpath, output, scratch)
        checks.append(
            {"case": "owned valid authorization assertion shape", "passed": True, "daemonCalls": 0}
        )
        for name in [
            "synthetic",
            "plan",
            "paths",
            "command",
            "bounds",
            "missing-acceptance",
            "acceptance-false",
            "wrong-cache",
            "changed-audit",
            "missing-payload-disposition",
            "wrong-payload-disposition",
            "native-admission",
            "campaign-admission",
        ]:
            a = deepcopy(auth)
            b = deepcopy(acceptance)
            if name == "synthetic":
                a["synthetic"] = True
            if name == "plan":
                a["planSha256"] = "0" * 64
            if name == "paths":
                a["output"] += "/different"
            if name == "command":
                a["command"] = "npm ci"
            if name == "bounds":
                a["limits"] = {**setup.LIMITS, "cpus": True}
            if name == "missing-acceptance":
                a["cacheAcceptance"] = {"path": str(temp / "absent"), "sha256": "0" * 64}
            if name == "acceptance-false":
                b["synthetic"] = True
            if name == "wrong-cache":
                b["cacheArchiveSha256"] = "0" * 64
            if name == "changed-audit":
                b["auditFreeze"] = {**b["auditFreeze"], "sha256": "0" * 64}
            if name == "missing-payload-disposition":
                b.pop("publishedTaskPayloadDisposition")
            if name == "wrong-payload-disposition":
                b["publishedTaskPayloadDisposition"]["payloadsSha256"] = "0" * 64
            if name == "native-admission":
                b["publishedTaskPayloadDisposition"]["nativeTaskAdmitted"] = True
            if name == "campaign-admission":
                b["publishedTaskPayloadDisposition"]["campaignAdmitted"] = True
            if b != acceptance:
                f = temp / (name + "-acceptance.json")
                setup.write(f, b)
                a["cacheAcceptance"] = {"path": str(f.resolve()), "sha256": setup.file_sha(f)}
            f = temp / (name + "-auth.json")
            setup.write(f, a)
            try:
                setup.authorize(plan, f, output, scratch)
            except (ValueError, FileNotFoundError, KeyError):
                pass
            else:
                raise AssertionError("accepted invalid auth " + name)
            checks.append({"case": "reject-" + name, "passed": True, "daemonCalls": 0})
        for failure in [
            None,
            "unauthorized",
            "preflight",
            "create",
            "network",
            "mount",
            "stream-hash",
            "config",
            "npm-ci",
            "hook-observation",
            "deadline",
            "versions",
            "binlinks",
            "outside",
            "tool-change",
            "tracked-source-check",
            "cleanup",
            "absence",
        ]:
            tag = failure or "success"
            clock = [0]
            fake = Fake(plan, failure, clock)
            out, work = temp / (tag + "-out"), temp / (tag + "-scratch")

            def authorize(*args):
                if failure == "unauthorized":
                    raise ValueError("synthetic missing acceptance/authorization")
                return {"syntheticControlOnly": True}

            def inputs(*args):
                if failure == "preflight":
                    raise ValueError("synthetic archive hash mismatch")
                return (
                    temp / "fake-source.tar",
                    temp / "fake-cache.tar",
                    {"README": {"sha256": "0" * 64}},
                    {"npm-cache/_cacache/known": {"sha256": "1" * 64}},
                )

            result = setup.run(
                authpath,
                out,
                work,
                backend=fake,
                plan_loader=lambda: deepcopy(plan),
                authorization_check=authorize,
                input_check=inputs,
                clock=lambda: clock[0],
            )
            assert (out / "attempt.json").exists() and (out / "result.json").exists()
            assert (
                result["synthetic"] is True
                and result["taskOutcomeObserved"] is False
                and result["nativeCollectionOccurred"] is False
                and result["costUsd"] is None
            )
            if failure is None:
                assert (
                    result["state"] == "offline-npm-setup-observed"
                    and result["containerAbsent"] is True
                )
            else:
                assert result["state"].startswith("incomplete")
            labels = [label for label, _ in fake.calls]
            if failure in ["unauthorized", "preflight"]:
                assert labels == []
            elif "create" in labels:
                assert "cleanup" in labels and "post-cleanup-list" in labels
            checks.append(
                {
                    "case": "synthetic-" + tag,
                    "passed": True,
                    "state": result["state"],
                    "virtualCalls": labels,
                    "realDaemonCalls": 0,
                }
            )
        helpers = dict(setup.HELPERS)
        try:
            setup.HELPERS["prepare.py"] = "0" * 64
            fake = Fake(plan)
            result = setup.run(authpath, temp / "helper-out", temp / "helper-scratch", backend=fake)
            assert result["state"] == "incomplete" and result["stage"] == "plan-verification"
            assert fake.calls == [] and (temp / "helper-out/result.json").exists()
            assert "changed frozen helper" in result["error"]
            checks.append(
                {
                    "case": "helper verification failure retains attempt before daemon",
                    "passed": True,
                    "daemonCalls": 0,
                }
            )
        finally:
            setup.HELPERS.clear()
            setup.HELPERS.update(helpers)
        baseline = metadata(plan)
        environment = dict(v.split("=", 1) for v in baseline["Config"]["Env"])
        for caps in [None, []]:
            row = deepcopy(baseline)
            row["HostConfig"]["CapAdd"] = caps
            setup.inspect(row, environment)
            checks.append(
                {
                    "case": "exact default-private inspect with CapAdd=" + repr(caps),
                    "passed": True,
                    "realDaemonCalls": 0,
                }
            )
        mutations = [
            ("shared-pid", "PidMode", "container:another"),
            ("host-pid", "PidMode", "host"),
            ("unknown-pid", "PidMode", "private"),
            ("added-capability", "CapAdd", ["SYS_ADMIN"]),
            ("host-ipc", "IpcMode", "host"),
            ("shared-ipc", "IpcMode", "container:another"),
            ("unknown-ipc", "IpcMode", ""),
            ("host-cgroupns", "CgroupnsMode", "host"),
            ("unknown-cgroupns", "CgroupnsMode", ""),
            ("host-userns", "UsernsMode", "host"),
            ("host-uts", "UTSMode", "host"),
            ("extra-seccomp-override", "SecurityOpt", ["no-new-privileges", "seccomp=unconfined"]),
            (
                "extra-apparmor-override",
                "SecurityOpt",
                ["no-new-privileges", "apparmor=unconfined"],
            ),
            ("duplicate-securityopt", "SecurityOpt", ["no-new-privileges", "no-new-privileges"]),
            ("disabled-nonewprivs", "SecurityOpt", ["no-new-privileges=false"]),
            ("missing-init", "Init", False),
            ("device", "Devices", [{"PathOnHost": "/dev/owned-synthetic"}]),
            ("device-request", "DeviceRequests", [{}]),
            ("volumes-from", "VolumesFrom", ["another"]),
            ("links", "Links", ["another"]),
            ("port-publication", "PortBindings", {"80/tcp": [{"HostPort": "80"}]}),
            ("publish-all", "PublishAllPorts", True),
        ]
        for name, key, value in mutations:
            row = deepcopy(baseline)
            row["HostConfig"][key] = value
            try:
                setup.inspect(row, environment)
            except (ValueError, KeyError, TypeError):
                pass
            else:
                raise AssertionError("accepted inspect mutation " + name)
            checks.append({"case": "reject-inspect-" + name, "passed": True, "realDaemonCalls": 0})
        for key in ["PidMode", "IpcMode", "CgroupnsMode", "CapAdd", "SecurityOpt"]:
            row = deepcopy(baseline)
            del row["HostConfig"][key]
            try:
                setup.inspect(row, environment)
            except (ValueError, KeyError, TypeError):
                pass
            else:
                raise AssertionError("accepted absent inspect field " + key)
            checks.append(
                {"case": "reject-missing-inspect-" + key, "passed": True, "realDaemonCalls": 0}
            )
        original = json.loads((HERE.parent / "plan.json").read_text())
        for key in [
            "sourceArchiveSha256",
            "cache",
            "cacheSpecSha256",
            "publishedTaskPayloadsSha256",
            "imageId",
            "revision",
            "command",
            "environment",
            "limits",
            "expectedToolLines",
            "npmConfigProbe",
            "packageObservation",
            "expectedPackageVersions",
            "requiredObservedFiles",
            "expectedHookMarkers",
        ]:
            assert plan[key] == original[key], key
        checks.append(
            {
                "case": "original source/cache/image/commands/observations/environment/bounds unchanged",
                "passed": True,
                "realDaemonCalls": 0,
            }
        )
        argv = setup.flags("owned-synthetic", plan["environment"])
        assert (
            "--network=none" in argv
            and "--network=bridge" not in argv
            and "--pid=host" not in argv
            and "-v" not in argv
            and "--mount" not in argv
        )
        assert (
            plan["environment"]["NPM_CONFIG_IGNORE_SCRIPTS"] == "false"
            and plan["environment"]["NPM_CONFIG_OFFLINE"] == "true"
        )
        assert setup.COMMAND == "cd /workspace/repository; npm ci --offline --foreground-scripts"
        checks.append({"case": "frozen offline argv and hook-enabled command", "passed": True})
    setup.write(
        HERE / "controls.json",
        {
            "passed": len(checks),
            "controls": checks,
            "actualSetupOccurred": False,
            "realDaemonNetworkProviderCalls": 0,
            "nativeCollectionOccurred": False,
        },
    )
    print(json.dumps({"passed": len(checks), "actualSetupOccurred": False}))


if __name__ == "__main__":
    main()
