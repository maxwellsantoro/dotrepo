"""Independent fake/data-only controls; no process, network or Go allowed."""

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BINDING = json.loads((HERE / "author-binding.json").read_text())
sys.path.insert(0, BINDING["scriptCopy"])
collection = importlib.import_module("collection")
listing = importlib.import_module("listing")
controls = importlib.import_module("controls")  # Denies real process/socket entrypoints.


def accepted(operation):
    try:
        operation()
        return True
    except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        return False


def main():
    plan = collection.load_plan()
    rows = controls.package_rows()
    inventory = listing.packages(b"\n".join(json.dumps(row).encode() for row in rows))
    events = controls.events(rows)
    checks = []

    def record(name, expected, observed):
        checks.append(
            {
                "case": name,
                "expectedAccepted": expected,
                "actualAccepted": observed,
                "matched": expected == observed,
            }
        )

    record(
        "ordinary-synthetic-package-and-listing",
        True,
        accepted(
            lambda: listing.collection(
                json.dumps(events[0]).encode()
                + b"\n"
                + b"\n".join(json.dumps(row).encode() for row in events[1:]),
                inventory,
            )
        ),
    )
    for name, raw in [
        ("duplicate-key", b'{"Package":"x","Package":"y"}'),
        ("non-object", b"[]"),
        ("non-json-number", b'{"x":NaN}'),
        ("truncated-object", b'{"Package":'),
        ("invalid-utf8", b"\xff"),
        ("non-json-tail", b"{}\nnon-json"),
        ("empty-stream", b"\n\t"),
    ]:
        record(name, False, accepted(lambda: listing.objects(raw)))
    for name, mutate in [
        ("pid-container-join", lambda h: h.update(PidMode="container:other")),
        ("ipc-host", lambda h: h.update(IpcMode="host")),
        ("added-cap", lambda h: h.update(CapAdd=["SYS_ADMIN"])),
        (
            "security-unconfined",
            lambda h: h.update(SecurityOpt=["no-new-privileges", "seccomp=unconfined"]),
        ),
        (
            "tmpfs-workspace-larger-last",
            lambda h: h["Tmpfs"].update({"/workspace": "rw,exec,nosuid,nodev,size=8g,size=16g"}),
        ),
        (
            "tmpfs-workspace-suid-last",
            lambda h: h["Tmpfs"].update({"/workspace": "rw,exec,nosuid,nodev,size=8g,suid"}),
        ),
        (
            "tmpfs-dependency-extra-overlay",
            lambda h: h["Tmpfs"].update({"/workspace/extra": "rw,exec,nosuid,nodev,size=8g"}),
        ),
    ]:
        state = controls.metadata(plan)
        mutate(state["HostConfig"])
        env = dict(value.split("=", 1) for value in state["Config"]["Env"])
        record(name, False, accepted(lambda: collection.inspect(state, env)))
    for name, mutate in [
        (
            "missing-event-package",
            lambda e: e.__setitem__(0, dict(e[0], Package="github.com/other")),
        ),
        ("event-body-identity", lambda e: e[1].update(Test="TestUnexpected")),
        ("event-after-terminal", lambda e: e.append(deepcopy(e[1]))),
        ("missing-package-terminal", lambda e: e.pop()),
        ("duplicate-start", lambda e: e.insert(1, deepcopy(e[0]))),
    ]:
        candidate = deepcopy(events)
        mutate(candidate)
        record(
            name,
            False,
            accepted(
                lambda: listing.collection(
                    b"\n".join(json.dumps(row).encode() for row in candidate), inventory
                )
            ),
        )
    for name, mutate in [
        ("package-directory-alias", lambda rs: rs[0].update(Dir=listing.CWD + "/wrong-directory")),
        ("selected-source-dotdot", lambda rs: rs[0].update(GoFiles=[".."])),
        ("selected-source-duplicate", lambda rs: rs[0].update(GoFiles=["owned.go", "owned.go"])),
    ]:
        candidate = deepcopy(rows)
        mutate(candidate)
        record(
            name,
            False,
            accepted(
                lambda: listing.packages(b"\n".join(json.dumps(row).encode() for row in candidate))
            ),
        )
    value = {
        "synthetic": True,
        "checks": checks,
        "matched": sum(row["matched"] for row in checks),
        "total": len(checks),
        "mismatches": [row for row in checks if not row["matched"]],
        "realProcessSocketGoDaemonNativeProviderCalls": 0,
    }
    with (HERE / "challenge-results.json").open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
    print(
        json.dumps(
            {
                "matched": value["matched"],
                "total": value["total"],
                "mismatches": value["mismatches"],
            }
        )
    )


if __name__ == "__main__":
    main()
