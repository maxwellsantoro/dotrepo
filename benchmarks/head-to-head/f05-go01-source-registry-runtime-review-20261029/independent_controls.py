"""Independent fake-only runner/transport controls; no Docker or Go processes."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
AUTHOR = Path(json.loads((HERE / "author-binding.json").read_text())["packet"])
sys.path.insert(0, str(AUTHOR))
import runtime as r  # noqa: E402
import controls as fixtures  # noqa: E402
import transport_controls as transport_fixtures  # noqa: E402


def refused(operation):
    try:
        operation()
    except (ValueError, KeyError, TypeError):
        return True
    raise AssertionError("invalid fixture accepted")


def main():
    plan = r.load_plan()
    assert r.subject(plan) == {
        "planSha256": "29533c84b635a7244b1b0f022a6200c53c8f7ca628ff1fd64dd428a1249ddd96",
        "authorFreezeSha256": "6f22704c8c02e71e0db0bf21e80c9ffd96ef1544242e07090ad32762987c6972",
        "packetIdentity": "go01-owned-source-registry-runtime-v1",
    }
    cases = [{"case": "exact current closure subject", "passed": True}]
    events = [json.loads(line) for line in fixtures.unit_events().splitlines()]
    package = events[0]["Package"]
    for label, mutate in [
        (
            "unknown suffix identity",
            lambda rows: rows.insert(
                2, {"Action": "run", "Package": package, "Test": r.TOP_TESTS[0] + "Other"}
            ),
        ),
        (
            "missing child",
            lambda rows: rows.__setitem__(
                slice(None), [row for row in rows if row.get("Test") != r.EXPECTED_TESTS[-1]]
            ),
        ),
        ("skip child", lambda rows: rows[3].update(Action="skip")),
        (
            "test before package start",
            lambda rows: rows.insert(
                0, {"Action": "run", "Package": package, "Test": r.TOP_TESTS[0]}
            ),
        ),
        ("duplicate package start", lambda rows: rows.insert(1, deepcopy(rows[0]))),
        (
            "event after package terminal",
            lambda rows: rows.append({"Action": "output", "Package": package, "Output": "late"}),
        ),
        (
            "parent before children",
            lambda rows: rows.insert(
                2, {"Action": "pass", "Package": package, "Test": r.TOP_TESTS[0]}
            ),
        ),
        ("wrong package", lambda rows: rows[2].update(Package="unowned/module")),
    ]:
        changed = deepcopy(events)
        mutate(changed)
        raw = b"\n".join(json.dumps(row).encode() for row in changed)
        assert refused(lambda: r.unit_outcome(raw, r.EXPECTED_TESTS))
        cases.append({"case": "reject " + label, "passed": True})
    assert r.unit_outcome(fixtures.unit_events(), r.EXPECTED_TESTS)["ownedTestsPassed"]
    cases.append({"case": "valid complete 29-ID unit coverage", "passed": True})
    with tempfile.TemporaryDirectory(prefix="dotrepo-registry-runtime-review-") as temporary:
        root = Path(temporary)
        for label in ["create-exception", "cancel-tests", "preflight-error", "deadline"]:
            clock = [0]

            class Fake(fixtures.Fake):
                def command(self, folder, name, argv, **kwargs):
                    if label == "create-exception" and name == "create":
                        self.labels.append(name)
                        raise RuntimeError("owned fake partial-create transport error")
                    result = super().command(folder, name, argv, **kwargs)
                    if label == "cancel-tests" and name == "owned-tests":
                        result.update(cancelled=True, error="KeyboardInterrupt: owned fake")
                    if label == "deadline" and name == "owned-tests":
                        clock[0] = 901
                    return result

            fake = Fake(plan)
            options = {}
            if label == "preflight-error":
                options["plan_loader"] = lambda: (_ for _ in ()).throw(
                    ValueError("owned preflight failure")
                )
            result = r.run(
                None,
                root / label,
                root / (label + "-scratch"),
                backend=fake,
                authorization_check=lambda *args: {"syntheticFixture": True},
                clock=lambda: clock[0],
                **options,
            )
            assert result["state"] == "incomplete" and result["error"]
            assert result["costUsd"] is None and result["synthetic"]
            assert not result["taskOutcomeObserved"] and not result["nativeCollectionOccurred"]
            if label == "preflight-error":
                assert result["daemonCalls"] == 0 and not fake.labels
            else:
                assert result["containerAbsent"] is True
                assert fake.labels[-3:] == ["cleanup", "post-cleanup-inspect", "post-cleanup-list"]
            if label == "cancel-tests":
                assert result["cancelled"] is True
            if label == "deadline":
                assert result["workBudgetExceeded"] is True and "owned-build" not in fake.labels
            assert (root / label / "attempt.json").is_file()
            assert (root / label / "result.json").is_file()
            cases.append(
                {
                    "case": label,
                    "passed": True,
                    "daemonCallsAreSynthetic": result["daemonCalls"],
                    "containerAbsent": result["containerAbsent"],
                }
            )
        _, _, transport = r.dependencies(plan)
        originals = (
            transport.subprocess.Popen,
            transport.selectors.DefaultSelector,
            transport.os.set_blocking,
            transport.os.read,
            transport.os.write,
            transport.time.monotonic,
        )
        try:
            for label in ["partial-stdin", "early-closed-pipe"]:
                payload = b"owned fixture input only\n" * 8
                source = root / (label + ".stdin")
                source.write_bytes(payload)
                process = transport_fixtures.Process(b"", b"")
                process.stdin = transport_fixtures.Stream(900003, [])
                sent = bytearray()

                class Selector:
                    def __init__(self):
                        self.values = {}

                    def register(self, stream, events, role):
                        self.values[stream.fileno()] = SimpleNamespace(
                            fileobj=stream, fd=stream.fileno(), data=role
                        )

                    def unregister(self, stream):
                        del self.values[stream.fileno()]

                    def get_map(self):
                        return self.values

                    def select(self, *args):
                        return [(key, None) for key in list(self.values.values())]

                    def close(self):
                        pass

                def fake_write(fd, raw):
                    assert fd == 900003
                    if label == "early-closed-pipe":
                        raise BrokenPipeError("owned fake")
                    amount = min(3, len(raw))
                    sent.extend(raw[:amount])
                    return amount

                transport.subprocess.Popen = lambda *args, **kwargs: process
                transport.selectors.DefaultSelector = Selector
                transport.os.set_blocking = lambda *args: None
                transport.os.read = lambda fd, length: (
                    process.stdout if fd == 900001 else process.stderr
                ).chunks.pop(0)
                transport.os.write = fake_write
                transport.time.monotonic = lambda: 0
                receipt = transport.DockerBackend().command(
                    root, label, ["NEVER_EXECUTED"], deadline=10, stdin_path=source
                )
                if label == "partial-stdin":
                    assert bytes(sent) == payload and receipt["stdinBytes"] == len(payload)
                    assert receipt["stdinSha256"] == hashlib.sha256(payload).hexdigest()
                    assert receipt["error"] is None and receipt["exitCode"] == 0
                else:
                    assert "pipe closed early" in receipt["error"] and process.killed
                    assert receipt["stdinBytes"] == 0 and receipt["exitCode"] == -9
                cases.append(
                    {
                        "case": label,
                        "passed": True,
                        "stdinBytes": receipt["stdinBytes"],
                        "error": receipt["error"],
                    }
                )
        finally:
            (
                transport.subprocess.Popen,
                transport.selectors.DefaultSelector,
                transport.os.set_blocking,
                transport.os.read,
                transport.os.write,
                transport.time.monotonic,
            ) = originals
    result = {
        "state": "passed-independent-fake-only-controls",
        "checks": cases,
        "realGoNodeDaemonNetworkUpstreamProcesses": 0,
        "helperAuthorRelationship": "Reviewer authored helper/receiver, not runner; prior source context, not fresh blind trial.",
    }
    with (HERE / "independent-controls.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"passed": len(cases), "realNativeOrDaemonCalls": 0}))


if __name__ == "__main__":
    main()
