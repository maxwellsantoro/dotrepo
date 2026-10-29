"""Owned fake transport only; no Docker, interpreter probe or process execution."""

from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile

import driver as d

HERE = Path(__file__).resolve().parent


def probe():
    return {
        "schema": "owned-python-interpreter-probe-v1",
        "version": [3, 11, 2, "final", 0],
        "versionText": "synthetic3.11.2",
        "executable": "/usr/bin/python3.11",
        "executableSha256": d.PY_SHA,
        "baseExecutable": "/usr/bin/python3.11",
        "prefix": "/usr",
        "basePrefix": "/usr",
        "platform": "linux",
        "platformTag": "linux-aarch64",
        "soabi": "cpython-311-aarch64-linux-gnu",
        "openssl": "synthetic OpenSSL",
        "isolated": 1,
        "noSite": 1,
        "sysPath": [
            "/usr/lib/python311.zip",
            "/usr/lib/python3.11",
            "/usr/lib/python3.11/lib-dynload",
        ],
        "configurationEnvironment": dict.fromkeys(
            ["PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PYTHON"]
        ),
        "targetImportsPerformed": False,
    }


def archive(plan):
    out = io.BytesIO()
    with d.tarfile.open(fileobj=out, mode="w", format=d.tarfile.USTAR_FORMAT) as t:
        row = d.tarfile.TarInfo(".")
        row.type = d.tarfile.DIRTYPE
        row.mode = 0o755
        t.addfile(row)
        raw = (d.PARENT / "probe.py").read_bytes()
        row = d.tarfile.TarInfo("./probe.py")
        row.mode = 0o644
        row.size = len(raw)
        t.addfile(row, io.BytesIO(raw))
    return out.getvalue()


class Fake:
    def __init__(self, plan, failure=None):
        self.plan, self.failure, self.labels, self.argv = plan, failure, [], []
        source = d.BASE / "f05-go01-collection-result-20261029/amendment-2/evidence/logs"
        self.image = json.loads((source / "image-inspect/stdout.bin").read_bytes())[0]
        self.row = json.loads((source / "container-inspect/stdout.bin").read_bytes())[0]
        env = {
            **dict(v.split("=", 1) for v in self.image["Config"]["Env"]),
            **plan["probe"]["environment"],
        }
        self.row["Config"]["Env"] = [k + "=" + v for k, v in env.items()]

    def command(self, output, label, argv, *, deadline, stdin_path=None):
        self.labels.append(label)
        self.argv.append(argv)
        folder = output / "logs" / label
        folder.mkdir(parents=True)
        raw, err, code, error, cancel = b"", b"", 0, None, False
        if label == "image-inspect":
            value = deepcopy(self.image)
            if self.failure == "image":
                value["Config"]["Env"].append("UNKNOWN=unsafe")
            raw = json.dumps([value]).encode()
        elif label == "create":
            self.name = argv[argv.index("--name") + 1]
            raw = b"a" * 64 + b"\n"
        elif label.startswith("inspect-"):
            row = deepcopy(self.row)
            row.update(Id="a" * 64, Name="/" + self.name)
            if self.failure == "namespace":
                row["HostConfig"]["PidMode"] = "host"
            if self.failure == "resource":
                row["HostConfig"]["Memory"] = 8589934592
            if self.failure == "environment":
                row["Config"]["Env"].append("PYTHONPATH=/target")
            raw = json.dumps([row]).encode()
        elif label.startswith("tools-"):
            raw = (
                d.PY_SHA + "  /usr/bin/python3.11\n" + d.UV_SHA + "  /usr/local/bin/uv\n"
            ).encode()
            if self.failure == "tools-after" and label == "tools-after":
                raw = b"changed\n"
        elif label.startswith("source-"):
            raw = archive(self.plan)
            if self.failure == "source-after" and label == "source-after":
                raw = raw[:512]
        elif label == "uv-version":
            raw = b"uv 0.13.6 (aarch64-unknown-linux-musl)\n"
        elif label == "owned-probe":
            value = probe()
            if self.failure == "version":
                value["version"][1] = 12
            if self.failure == "path":
                value["sysPath"].append("/workspace/repository")
            raw = json.dumps(value).encode() + b"\n"
            if self.failure == "probe-nonzero":
                code = 1
            if self.failure == "probe-cap":
                raw = b" " * 16385
            if self.failure == "cancel":
                error = "KeyboardInterrupt: owned fake cancellation"
                cancel = True
                code = -9
            if self.failure == "timeout":
                error = "attempt deadline exhausted"
                code = -9
            if self.failure == "raw-cap":
                raw = b"x" * (d.TEXT_LIMIT + 1)
        elif label == "post-cleanup-inspect":
            raw, err, code = b"[]\n", b"error: no such object\n", 1
        elif label == "post-cleanup-list" and self.failure == "cleanup":
            raw = (self.name + "\n").encode()
        for role, data in [("stdout", raw), ("stderr", err)]:
            (folder / (role + ".bin")).write_bytes(data)
        receipt = {
            "argv": argv,
            "startedAt": "synthetic",
            "elapsedSeconds": 0.001,
            "exitCode": code,
            "error": error,
            "cancelled": cancel,
            "stdinBytes": stdin_path.stat().st_size if stdin_path else 0,
            "stdinSha256": d.sha(stdin_path) if stdin_path else d.hashlib.sha256(b"").hexdigest(),
            "stdoutSha256": d.hashlib.sha256(raw).hexdigest(),
            "stderrSha256": d.hashlib.sha256(err).hexdigest(),
            "costUsd": None,
        }
        d.write(folder / "receipt.json", receipt)
        return receipt


def authorization_controls(plan, root):
    # Valid-shaped subjects here are owned synthetic fixtures, not live approval.
    closure = root / "auth-closure"
    closure.mkdir()
    for name in ["plan.json", *plan["scripts"]]:
        (closure / name).write_bytes((HERE / name).read_bytes())
    d.write(
        closure / "FREEZE.json",
        {
            "artifacts": {
                n: {"sha256": d.sha(closure / n), "bytes": (closure / n).stat().st_size}
                for n in ["plan.json", *plan["scripts"]]
            }
        },
    )
    original = d.HERE
    d.HERE = closure
    try:
        review = {
            "subject": {
                "planSha256": d.sha(closure / "plan.json"),
                "authorFreezeSha256": d.sha(closure / "FREEZE.json"),
                "packetIdentity": plan["identity"],
            },
            "state": "independent-python01-source-free-probe-driver-review-passed",
            "scope": "owned-source-free-python-probe-only",
            "synthetic": False,
            "findings": [],
            "staticOnly": True,
        }
        cases = []
        for i, change in enumerate(
            [
                None,
                "plan",
                "output",
                "attempts",
                "review-subject",
                "review-findings",
                "review-state",
                "review-synthetic",
            ]
        ):
            value = deepcopy(review)
            if change == "review-subject":
                value["subject"]["planSha256"] = "0" * 64
            if change == "review-findings":
                value["findings"] = ["owned synthetic unresolved finding"]
            if change == "review-state":
                value["state"] = "incomplete"
            if change == "review-synthetic":
                value["synthetic"] = True
            rp = closure / ("review" + str(i) + ".json")
            d.write(rp, value)
            auth = {
                "state": "coordinator-authorized-single-python01-source-free-probe",
                "synthetic": False,
                "planSha256": d.sha(closure / "plan.json"),
                "authorFreezeSha256": d.sha(closure / "FREEZE.json"),
                "output": str(root / "out"),
                "scratch": str(root / "scratch"),
                "maxAttempts": 1,
                "commands": plan["probe"]["commands"],
                "limits": plan["limits"],
                "review": {"path": str(rp), "sha256": d.sha(rp)},
            }
            if change == "plan":
                auth["planSha256"] = "0" * 64
            if change == "output":
                auth["output"] = str(root / "other")
            if change == "attempts":
                auth["maxAttempts"] = 2
            ap = closure / ("auth" + str(i) + ".json")
            d.write(ap, auth)
            error = None
            try:
                d.authorize(plan, ap, root / "out", root / "scratch")
            except ValueError as exc:
                error = str(exc)
            assert (error is None) == (change is None), change
            cases.append(
                {
                    "case": "authorization-" + (change or "valid-shaped-synthetic-only"),
                    "error": error,
                    "synthetic": True,
                    "actualAdmission": False,
                }
            )
        return cases
    finally:
        d.HERE = original


def main():
    plan = d.load_plan()
    cases = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-python-probe-controls-") as directory:
        root = Path(directory).resolve()
        cases.extend(authorization_controls(plan, root))
        for i, failure in enumerate(
            [
                None,
                "image",
                "namespace",
                "resource",
                "environment",
                "tools-after",
                "source-after",
                "version",
                "path",
                "probe-nonzero",
                "probe-cap",
                "cancel",
                "timeout",
                "raw-cap",
                "cleanup",
                "auth",
            ]
        ):
            fake = Fake(plan, failure)

            def auth(*_):
                if failure == "auth":
                    raise ValueError("owned rejected authorization")
                return {"synthetic": True, "state": "owned fake authorization, not live"}

            result = d.run(
                None,
                root / str(i),
                root / ("scratch" + str(i)),
                backend=fake,
                authorization_check=auth,
            )
            assert (result["state"] == "owned-source-free-python-probe-observed") == (
                failure is None
            ), failure
            if failure in ["image", "auth"]:
                assert not result["containerCreateAttempted"], failure
            else:
                assert result["containerAbsent"] == (failure != "cleanup"), failure
            assert all(
                result[k] is False
                for k in [
                    "actualAdmission",
                    "nativeCollectionOccurred",
                    "oracleQualified",
                    "campaignAdmitted",
                ]
            )
            assert result["synthetic"] is True
            if failure == "cancel":
                assert result["cancelled"] is True
            cases.append(
                {
                    "case": failure or "complete-owned-synthetic",
                    "state": result["state"],
                    "daemonCalls": result["daemonCalls"],
                    "containerAbsent": result["containerAbsent"],
                    "error": result.get("error"),
                    "labels": fake.labels,
                    "synthetic": True,
                    "actualAdmission": False,
                }
            )
            if failure is None:
                assert result["daemonCalls"] == 16
                (HERE / "synthetic-command-trace.json").write_text(
                    json.dumps(fake.argv, indent=2) + "\n"
                )
        existing = root / "existing"
        existing.mkdir()
        fake = Fake(plan)
        try:
            d.run(
                None,
                existing,
                root / "scratch-existing",
                backend=fake,
                authorization_check=lambda *_: {"synthetic": True},
            )
        except FileExistsError:
            assert not fake.labels
        else:
            raise AssertionError("existing output reused")
        cases.append(
            {"case": "existing-output", "rejectedBeforeTransport": True, "synthetic": True}
        )
        ticks = iter([0, 901, 901, 901])
        fake = Fake(plan)
        expired = d.run(
            None,
            root / "expired",
            root / "expired-scratch",
            backend=fake,
            authorization_check=lambda *_: {"synthetic": True},
            clock=lambda: next(ticks),
        )
        assert expired["state"] == "incomplete" and expired["workBudgetExceeded"]
        assert not fake.labels and expired["daemonCalls"] == 0
        cases.append(
            {"case": "expired-shared-deadline", "rejectedBeforeTransport": True, "synthetic": True}
        )
    result = {
        "state": "owned-fake-transport-controls-pass",
        "count": len(cases),
        "cases": cases,
        "probeExecuted": False,
        "actualDaemonCalls": 0,
        "actualAdmission": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
    }
    (HERE / "controls.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"state": result["state"], "count": len(cases)}))


if __name__ == "__main__":
    main()
