"""Owned fake-daemon fixtures only; never execute a process, helper or target."""

import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile

import runtime as r


def unit_events():
    package = "dotrepo.invalid/go01-source-registry-experiment"
    events = [{"Action": "start", "Package": package}]
    for top in r.TOP_TESTS:
        events.append({"Action": "run", "Package": package, "Test": top})
        for child in [n for n in r.EXPECTED_TESTS if n.startswith(top + "/")]:
            events += [
                {"Action": "run", "Package": package, "Test": child},
                {"Action": "pass", "Package": package, "Test": child},
            ]
        events.append({"Action": "pass", "Package": package, "Test": top})
    events.append({"Action": "pass", "Package": package})
    return b"".join((json.dumps(event) + "\n").encode() for event in events)


def fixture_wire(plan, diagnostics=False):
    # Valid-shaped empty declaration lists are synthetic, never semantic gold.
    provenance = json.loads((r.HELPER / "input-provenance.json").read_text())
    packages = json.loads(Path(provenance["packageInventoryPath"]).read_text())
    state = "source-derived-uncompiled"
    rows = [
        {
            "importPath": name,
            **{key: [] for key in ["tests", "benchmarks", "fuzzTargets", "examples", "testMains"]},
            "diagnostics": [],
            "state": state,
            "compileValidityUnestablished": True,
        }
        for name in sorted(packages)
    ]
    if diagnostics:
        chosen = next(row for row in rows if packages[row["importPath"]].get("TestGoFiles"))
        native = packages[chosen["importPath"]]
        source_path = (
            native["Dir"].removeprefix("/workspace/repository/") + "/" + native["TestGoFiles"][0]
        )
        chosen["diagnostics"] = [
            {
                "code": "parse-error",
                "sourcePath": source_path,
                "message": "Owned synthetic fixture diagnostic, not an actual parser observation.",
            }
        ]
        chosen["state"] = state = "unresolved-source-discovery"
    value = {
        "schema": "go01-source-registry-output-v1",
        "state": state,
        "sourceContext": plan["sourceContext"],
        "helperGoVersion": "go1.27.3",
        "helperGOOS": "linux",
        "helperGOARCH": "arm64",
        "inputSha256": plan["input"]["sha256"],
        "packages": rows,
        "universalCompileValidityUnestablished": True,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
    }
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0, compresslevel=9) as output:
        output.write(json.dumps(value, separators=(",", ":")).encode())
    return stream.getvalue()


class Fake:
    def __init__(self, plan, failure=None):
        self.plan, self.failure, self.labels, self.name = plan, failure, [], None
        base = r.BASE / "f05-go01-collection-result-20261029/amendment-2/evidence/logs"
        self.image = json.loads((base / "image-inspect/stdout.bin").read_text())[0]
        self.inspected = json.loads((base / "container-inspect/stdout.bin").read_text())[0]
        environment = {
            **dict(v.split("=", 1) for v in self.image["Config"]["Env"]),
            **plan["environment"],
        }
        self.inspected["Config"]["Env"] = [k + "=" + v for k, v in environment.items()]

    def command(self, folder, label, argv, *, deadline, stdin_path=None, binary_path=None):
        self.labels.append(label)
        leaf = folder / "logs" / label
        leaf.mkdir(parents=True)
        out, err, payload, exit_code, error = b"", b"", None, 0, None
        if label == "image-inspect":
            out = json.dumps([self.image]).encode()
        elif label == "create":
            self.name = argv[argv.index("--name") + 1]
            out = b"a" * 64 + b"\n"
        elif label.startswith("inspect-"):
            row = copy.deepcopy(self.inspected)
            row.update(Id="a" * 64, Name="/" + self.name)
            if self.failure == "namespace":
                row["HostConfig"]["IpcMode"] = "host"
            if self.failure == "environment":
                row["Config"]["Env"] = [
                    x.replace("GOWORK=off", "GOWORK=/target/go.work") for x in row["Config"]["Env"]
                ]
            out = json.dumps([row]).encode()
        elif label.startswith("tools-"):
            out = (r.GO_SHA + "  /usr/local/go/bin/go\n").encode()
        elif label in {"module-before", "module-after"}:
            payload = r.owned_archive(self.plan)
            if self.failure == "source-after" and label == "module-after":
                buffer = io.BytesIO()
                with r.tarfile.open(fileobj=buffer, mode="w") as archive:
                    item = r.tarfile.TarInfo("upstream.go")
                    item.size = 1
                    archive.addfile(item, io.BytesIO(b"x"))
                payload = buffer.getvalue()
        elif label == "owned-tests":
            out = unit_events()
            if self.failure == "unit-coverage":
                out = (
                    b"\n".join(line for line in out.splitlines() if b"/parse-error" not in line)
                    + b"\n"
                )
            if self.failure == "unit-failed":
                exit_code = 1
        elif label == "owned-binary-sha":
            out = b"b" * 64 + b"  /workspace/owned-bin/registry\n"
        elif label == "owned-cli":
            payload = fixture_wire(self.plan, diagnostics=self.failure == "diagnostics")
            if self.failure == "diagnostics":
                exit_code = 1
            if self.failure == "multimember":
                payload += payload
            if self.failure == "crc":
                payload = payload[:-1] + bytes([payload[-1] ^ 1])
            if self.failure == "exit-state":
                exit_code = 1
            if self.failure == "cli-error":
                exit_code = 2
            if self.failure == "output-cap":
                error = "binary archive transport limit"
        elif label == "post-cleanup-inspect":
            out, err, exit_code = b"[]\n", b"error: no such object\n", 1
        elif label == "post-cleanup-list" and self.failure == "cleanup":
            out = (self.name + "\n").encode()
        if binary_path:
            binary_path.write_bytes(payload or b"")
        (leaf / "stdout.bin").write_bytes(out)
        (leaf / "stderr.bin").write_bytes(err)
        receipt = {
            "argv": argv,
            "startedAt": "synthetic",
            "elapsedSeconds": 0.001,
            "exitCode": exit_code,
            "error": error,
            "cancelled": False,
            "stdinBytes": stdin_path.stat().st_size if stdin_path else 0,
            "stdinSha256": r.file_sha(stdin_path)
            if stdin_path
            else hashlib.sha256(b"").hexdigest(),
            "stdoutSha256": hashlib.sha256(out).hexdigest(),
            "stderrSha256": hashlib.sha256(err).hexdigest(),
            "binaryPath": str(binary_path) if binary_path else None,
            "binaryBytes": len(payload or b"") if binary_path else None,
            "binarySha256": r.file_sha(binary_path) if binary_path else None,
            "costUsd": None,
        }
        r.write(leaf / "receipt.json", receipt)
        return receipt


def authorization_controls(plan, root):
    original_subject = r.subject
    current = {
        "planSha256": "a" * 64,
        "authorFreezeSha256": "b" * 64,
        "packetIdentity": plan["identity"],
    }
    r.subject = lambda _: current
    outcomes = []
    try:
        for i, mutation in enumerate(
            [
                None,
                "stale-runtime",
                "unrelated-helper",
                "findings",
                "wrong-scope",
                "executed-review",
                "input",
                "commands",
                "limits",
                "paths",
                "attempts",
            ]
        ):
            folder = root / str(i)
            folder.mkdir()
            auth = {
                "state": "coordinator-authorized-single-owned-registry-attempt",
                "synthetic": False,
                "runtimeSubject": current,
                "helperSubject": plan["helperSubject"],
                "output": str(folder / "out"),
                "scratch": str(folder / "scratch"),
                "maxAttempts": 1,
                "commands": r.COMMANDS,
                "limits": plan["limits"],
                "inputSha256": plan["input"]["sha256"],
            }
            for role, subject in [("runtime", current), ("helper", plan["helperSubject"])]:
                value = {
                    "state": f"independent-owned-registry-{role}-review-passed",
                    "scope": "owned-source-registry-only",
                    "subject": subject,
                    "findings": [],
                    "synthetic": False,
                    "staticOnly": True,
                    **{
                        key: False
                        for key in [
                            "executionAuthorized",
                            "nativeTaskAdmitted",
                            "campaignAdmitted",
                            "oracleQualified",
                            "ownedGoTestsExecuted",
                            "helperCLIExecuted",
                        ]
                    },
                }
                if mutation == "stale-runtime" and role == "runtime":
                    value["subject"] = {**subject, "planSha256": "c" * 64}
                if mutation == "unrelated-helper" and role == "helper":
                    value["subject"] = {**subject, "packetIdentity": "other"}
                if mutation == "findings":
                    value["findings"] = ["synthetic unresolved finding"]
                if mutation == "wrong-scope":
                    value["scope"] = "native-task"
                if mutation == "executed-review":
                    value["ownedGoTestsExecuted"] = True
                path = folder / (role + "-review.json")
                r.write(path, value)
                auth[role + "Review"] = {"path": str(path), "sha256": r.file_sha(path)}
            if mutation == "input":
                auth["inputSha256"] = "d" * 64
            if mutation == "commands":
                auth["commands"] = ["go test ./..."]
            if mutation == "limits":
                auth["limits"] = {**plan["limits"], "cpus": 4}
            if mutation == "paths":
                auth["output"] = "/different/path"
            if mutation == "attempts":
                auth["maxAttempts"] = 2
            path = folder / "auth.json"
            r.write(path, auth)
            error = None
            try:
                r.authorize(plan, path, folder / "out", folder / "scratch")
                observed = True
            except (ValueError, KeyError) as exc:
                observed, error = False, str(exc)
            r.require(observed == (mutation is None), "authorization control: " + str(mutation))
            outcomes.append(
                {
                    "case": mutation or "synthetic-valid-shaped-current-reviews",
                    "accepted": observed,
                    "error": error,
                }
            )
    finally:
        r.subject = original_subject
    return outcomes


def main():
    plan = r.load_plan()
    checks = []
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-owned-registry-runtime-controls-"
    ) as temporary:
        root = Path(temporary)
        for i, failure in enumerate(
            [
                None,
                "diagnostics",
                "namespace",
                "environment",
                "source-after",
                "unit-coverage",
                "unit-failed",
                "multimember",
                "crc",
                "exit-state",
                "cli-error",
                "output-cap",
                "cleanup",
            ]
        ):
            fake = Fake(plan, failure)
            result = r.run(
                None,
                root / f"result-{i}",
                root / f"scratch-{i}",
                backend=fake,
                authorization_check=lambda *args: {"syntheticFixture": True},
            )
            accepted = result["state"] == "owned-helper-observed-uncompiled-source-registry"
            r.require(
                accepted == (failure in {None, "diagnostics"}),
                f"unexpected fake lifecycle result: {failure}: {result}",
            )
            r.require(
                result["synthetic"]
                and result["taskOutcomeObserved"] is False
                and result["nativeCollectionOccurred"] is False,
                "fake result qualification",
            )
            r.require(
                all(
                    label in fake.labels
                    for label in ["cleanup", "post-cleanup-inspect", "post-cleanup-list"]
                ),
                "cleanup not attempted",
            )
            checks.append(
                {
                    "case": failure or "valid-shaped-empty-synthetic-output",
                    "observed": accepted,
                    "stage": result["stage"],
                    "error": result.get("error"),
                    "syntheticDaemonCalls": result["daemonCalls"],
                }
            )
        fake = Fake(plan)
        result = r.run(
            None,
            root / "auth-refusal",
            root / "auth-refusal-scratch",
            backend=fake,
            authorization_check=lambda *args: (_ for _ in ()).throw(
                ValueError("synthetic authorization refusal")
            ),
        )
        r.require(
            result["daemonCalls"] == 0 and not fake.labels, "authorization refusal reached daemon"
        )
        checks.append({"case": "authorization-refusal", "observed": False, "daemonCalls": 0})
        auth_root = root / "authorization-shapes"
        auth_root.mkdir()
        authorization_cases = authorization_controls(plan, auth_root)
    print(
        json.dumps(
            {
                "synthetic": True,
                "nativeProcessDaemonNetworkCalls": 0,
                "checks": checks,
                "authorizationShapeFixtures": authorization_cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
