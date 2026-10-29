"""Retest the frozen v4 name-collision defect against v5, using synthetic output."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent.parent / "f05-offline-requalification-20261029"
sys.path.insert(0, str(PACKET))
from oracle_v4 import rust_default_outcome as before  # noqa: E402
from oracle_v5 import rust_default_outcome as after  # noqa: E402


def main():
    old = json.loads((PACKET / "plan.v4.json").read_bytes())["tasks"]["rust-02"]
    new = json.loads((PACKET / "plan.v5.json").read_bytes())["tasks"]["rust-02"]
    name = new["expectedTests"][0]
    stdout = (PACKET / "source-bindings-v4/historical-rust-stdout.txt").read_text()
    stderr = (PACKET / "source-bindings-v4/historical-rust-stderr.txt").read_text()
    native = {
        "stdout": stdout.replace(
            "link_type::tests::" + name, "link_type::tests::unrelated_" + name
        ),
        "stderr": stderr,
        "exitCode": 0,
        "error": None,
    }
    previous = before(native, old["expectedTests"], old["rustDefaultPolicy"])
    corrected = after(native, new["expectedTests"], new["rustDefaultPolicy"])
    assert previous["qualified"] is True and corrected["qualified"] is False
    print(
        json.dumps(
            {
                "syntheticOnly": True,
                "case": "exact-frozen-v4-wrong-basename-sharing-expected-suffix",
                "native": native,
                "beforeV4": previous,
                "afterV5": corrected,
                "actualDockerNetworkProviderCalls": 0,
                "upstreamExecution": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
