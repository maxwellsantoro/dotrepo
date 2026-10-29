"""Independent synthetic controls; prohibit all subprocess and network calls."""

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent


def denied(*args, **kwargs):
    raise AssertionError("Real process/network forbidden in independent review")


subprocess.Popen = denied
socket.socket = denied
socket.create_connection = denied
sys.path.insert(0, str(HERE / "isolated-copy"))
import controls  # noqa: E402
import setup  # noqa: E402


def main():
    plan = setup.load_plan()
    results = []
    base = controls.metadata(plan)
    for name, change in [
        (
            "shared-pid-namespace",
            lambda state: state["HostConfig"].update(PidMode="container:another"),
        ),
        ("capability-added-back", lambda state: state["HostConfig"].update(CapAdd=["SYS_ADMIN"])),
        ("host-ipc", lambda state: state["HostConfig"].update(IpcMode="host")),
        ("bridge", lambda state: state["HostConfig"].update(NetworkMode="bridge")),
        ("unexpected-environment", lambda state: state["Config"]["Env"].append("TOKEN=synthetic")),
    ]:
        state = deepcopy(base)
        change(state)
        try:
            setup.inspect(state, dict(value.split("=", 1) for value in base["Config"]["Env"]))
            accepted = True
        except ValueError:
            accepted = False
        results.append(
            {"case": name, "inspectorAccepted": accepted, "state": state, "realDaemonCalls": 0}
        )
    with tempfile.TemporaryDirectory(prefix="owned-counterexamples-", dir=HERE) as temporary:
        folder = Path(temporary)
        for name, entry_name, entry_type, data, deny in [
            ("cache-symlink", "npm-cache/_cacache/link", tarfile.SYMTYPE, b"", frozenset()),
            ("cache-hardlink", "go/pkg/mod/link", tarfile.LNKTYPE, b"", frozenset()),
            ("cache-traversal", "npm-cache/_cacache/../bad", tarfile.REGTYPE, b"x", frozenset()),
            (
                "cache-outside-root",
                "repository/package-lock.json",
                tarfile.REGTYPE,
                b"x",
                frozenset(),
            ),
            (
                "protected-source-payload",
                "go/pkg/mod/cache/data",
                tarfile.REGTYPE,
                b"owned protected answer",
                frozenset([hashlib.sha256(b"owned protected answer").hexdigest()]),
            ),
            (
                "ordinary-regular-cache",
                "go/pkg/mod/cache/data",
                tarfile.REGTYPE,
                b"owned ordinary library",
                frozenset(),
            ),
        ]:
            archive = folder / (name + ".tar")
            with tarfile.open(archive, "w") as output:
                entry = tarfile.TarInfo(entry_name)
                entry.type = entry_type
                entry.size = len(data)
                entry.linkname = "elsewhere" if entry_type != tarfile.REGTYPE else ""
                output.addfile(entry, io.BytesIO(data) if data else None)
            try:
                setup.scan_archive(
                    archive, deadline=lambda: None, roots=setup.prior.ROOTS, deny=deny
                )
                accepted, reason = True, None
            except ValueError as error:
                accepted, reason = False, str(error)
            assert accepted == (name == "ordinary-regular-cache")
            results.append(
                {"case": name, "archiveAccepted": accepted, "reason": reason, "realDaemonCalls": 0}
            )
        auth = folder / "auth.json"
        auth.write_text("{}\n")
        clock = [0]
        fake = controls.Fake(plan, clock=clock)

        def expired_inputs(*args):
            clock[0] = 901
            return (
                folder / "source.tar",
                folder / "cache.tar",
                {"README": {"sha256": "0" * 64}},
                {"go/pkg/mod/x": {"sha256": "1" * 64}},
            )

        outcome = setup.run(
            auth,
            folder / "expired-out",
            folder / "expired-scratch",
            backend=fake,
            plan_loader=lambda: deepcopy(plan),
            authorization_check=lambda *args: {"syntheticControlOnly": True},
            input_check=expired_inputs,
            clock=lambda: clock[0],
        )
        assert fake.calls == [] and outcome["workBudgetExceeded"] is True
        assert (folder / "expired-out/result.json").exists() and outcome["costUsd"] is None
        results.append(
            {
                "case": "preflight-consumes-work-budget-before-any-daemon",
                "outcome": outcome,
                "realDaemonCalls": 0,
            }
        )
    setup.write(
        HERE / "counterexamples.json",
        {
            "cases": results,
            "realDaemonNetworkPackageNativeProviderCalls": 0,
            "inspectorGaps": [row["case"] for row in results if row.get("inspectorAccepted")],
        },
    )
    print(
        json.dumps(
            {
                "cases": len(results),
                "inspectorGaps": [row["case"] for row in results if row.get("inspectorAccepted")],
            }
        )
    )


if __name__ == "__main__":
    main()
