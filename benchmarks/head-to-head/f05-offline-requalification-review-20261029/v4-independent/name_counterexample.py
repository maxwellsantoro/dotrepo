"""Reproduce wrong terminal Rust case accepted through an expected-name suffix."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent.parent / "f05-offline-requalification-20261029"
sys.path.insert(0, str(PACKET))
from oracle_v4 import rust_default_outcome  # noqa: E402


def main():
    plan = json.loads((PACKET / "plan.v4.json").read_text())
    task = plan["tasks"]["rust-02"]
    expected = task["expectedTests"][0]
    native = {
        "stdout": (PACKET / "source-bindings-v4/historical-rust-stdout.txt")
        .read_text()
        .replace("link_type::tests::" + expected, "link_type::tests::unrelated_" + expected),
        "stderr": (PACKET / "source-bindings-v4/historical-rust-stderr.txt").read_text(),
        "exitCode": 0,
        "error": None,
    }
    observed = rust_default_outcome(native, task["expectedTests"], task["rustDefaultPolicy"])
    assert observed["qualified"] is True, "v4 finding no longer reproduces; check frozen input"
    print(
        json.dumps(
            {
                "syntheticOnly": True,
                "case": "wrong-test-name-sharing-expected-suffix",
                "expectedQualified": False,
                "observed": observed,
                "native": native,
                "finding": "A different terminal basename is reported as the expected case.",
                "actualDockerCalls": 0,
                "upstreamExecution": False,
                "modelCalls": 0,
                "indexConsulted": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
