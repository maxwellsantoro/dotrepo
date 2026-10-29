"""Synthetic prior-boundary diagnostic; no empirical gold/profile data read."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "scripts/tests"), str(ROOT / "benchmarks/head-to-head")]
from bench import agent_experiment as experiment  # noqa: E402
from bench import agent_runtime as runtime  # noqa: E402
from test_agent_experiment import packet, save, write  # noqa: E402
from test_agent_runtime import bundle_spec, session  # noqa: E402


def main():
    results = []
    for role in ("gold", "oracle"):
        for serialization in ("raw", "compact"):
            with tempfile.TemporaryDirectory(
                prefix="dotrepo-f05-dependency-preparation-review-"
            ) as d:
                p = Path(d)
                campaign = packet.__wrapped__(p)
                path, manifest = campaign
                config = deepcopy(session.__wrapped__(p)[1])
                task = manifest["tasks"][0]
                # Intentionally use a valid noncanonical pretty encoding.
                original = (
                    b'{\n  "zzSyntheticPrivateAnswer": "SYNTHETIC-HIDDEN-TUPLE",\n  "aaSyntheticRole": "'
                    + role.encode()
                    + b'"\n}\n'
                )
                task[role] = write(p, f"synthetic-{role}.json", original)
                source = (
                    original
                    if serialization == "raw"
                    else json.dumps(json.loads(original), separators=(",", ":")).encode()
                )
                config["sourceBundles"] = {
                    task["repository"]: bundle_spec(p, {"README.md": source}, task["revision"])
                }
                manifest["artifacts"]["runtime"] = write(p, "runtime.json", config)
                manifest["artifacts"]["responses"] = write(
                    p,
                    "responses.json",
                    {
                        "snapshotSha256": manifest["artifacts"]["snapshot"]["sha256"],
                        "profiles": {task["repository"]: {"status": 404, "body": ""}},
                    },
                )
                save(campaign)
                experiment.prepare(path, p / "prepared")
                try:
                    loaded = runtime.load_session(
                        path, p / "prepared/assignment.json", f"{task['id']}-r1-source-first"
                    )
                except ValueError as exc:
                    outcome = "rejected"
                    reason = str(exc)
                else:
                    assert loaded[2].files["README.md"] == source
                    outcome = "accepted-source-readable"
                    reason = None
                results.append(
                    {
                        "role": role,
                        "serialization": serialization,
                        "outcome": outcome,
                        "reason": reason,
                        "rawSha256": experiment.digest(original),
                        "sourceSha256": experiment.digest(source),
                        "canonicalSha256": experiment.digest(
                            experiment.encode(json.loads(original))
                        ),
                    }
                )
    assert [r["outcome"] for r in results] == ["rejected"] * 4
    print(
        json.dumps(
            {
                "runtimeSha256": experiment.digest(Path(runtime.__file__).read_bytes()),
                "results": results,
                "actualHiddenBodiesRead": False,
                "backendOrProviderCalled": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
