"""Developer-defined offline decision control; no held-out or economic claim."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "scripts/tests")]
import test_repodigest_requirements as fixture  # noqa: E402
from repodigest_acquire import canonical, sha  # noqa: E402
from repodigest_service import registry  # noqa: E402
from repodigest_selection import Selection  # noqa: E402
from repodigest_source_cache import Reader  # noqa: E402
from repodigest_store import Store  # noqa: E402


class TemporarySources:
    def mktemp(self, prefix):
        return Path(tempfile.mkdtemp(prefix=prefix + "-"))


start = time.perf_counter()
database, target, receipt = fixture.admitted.__wrapped__(TemporarySources())
setup_seconds = time.perf_counter() - start
store = Store(database)
reader = Reader(store)
_, _, source_hash, body, _ = reader.body(
    target["repository"], target["revision"], "packages/markitdown/pyproject.toml"
)
declaration = tomllib.loads(body.decode())["project"]["requires-python"]
assert declaration == ">=3.10,<3.15"
baseline = {
    "requested": "Declared Python 3.12 support, without runtime qualification",
    "declaration": declaration,
    "answer": "supported",
    "sourceSha256": source_hash,
    "sourceReadAccounting": reader.stats.copy(),
    "returnedSourceBytes": len(body),
}
tools = registry(store, requirements=True)
calls = []


def measured(name):
    function = tools[name][1]

    def call(**arguments):
        before = time.perf_counter()
        value = function(**arguments)
        calls.append(
            {
                "tool": name,
                "resultBytes": len(canonical(value)),
                "elapsedSeconds": time.perf_counter() - before,
            }
        )
        return value

    return call


flow = Selection(store, measured("dotrepo.decision.find"), measured("dotrepo.decision.describe"))
outcomes = []
for expected, key, wanted in [
    ("preliminary-selection", "python.declared-3-12", True),
    ("none-established", "external.libreoffice.required", False),
    ("none-established", "python.declared-3-12", False),
]:
    lead = flow.shortlist(["markitdown"])
    assert any(item["repository"] == target["repository"] for item in lead["repositories"])
    result = flow.decide(lead["selectionId"], [target], [{"key": key, "expected": wanted}])
    assert result["disposition"] == expected
    assert result["authorized"] == "not-granted"
    outcomes.append(result)
flow.shortlist(["deliberately unfinished operator control"])
status = flow.status()
assert status["completed"] == 3 and len(status["unfinished"]) == 1
report = {
    "harnessSha256": sha(Path(__file__).read_bytes()),
    "sourceBase": "6d28f65856b93491b26c55b9885997c5230c1c5b",
    "kind": "developer-defined offline workflow control after source exposure",
    "target": target,
    "assessment": receipt,
    "setupSeconds": setup_seconds,
    "baseline": baseline,
    "decisions": outcomes,
    "ledger": status,
    "calls": calls,
    "scope": "One preselected retained project; existing synthetic reviewed-assessment fixture. Same retained source cache. Declared Python range only; no source execution, independent task/reviewer, adoption, scale, model calls or savings claim.",
    "costLimits": "Result bytes and measured control setup are retained. Original acquisition, semantic review and publisher upkeep remain inherited/unallocated; native tokens, human effort and money unmeasured. These controls do not replace negative consumer studies.",
    "sourceBytes": len(body),
    "sourceSha256": sha(body),
}
store.close()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
output = parser.parse_args().output
assert not output.exists()
output.write_text(json.dumps(report, indent=2) + "\n")
print(
    json.dumps(
        {
            "completed": status["completed"],
            "unfinished": len(status["unfinished"]),
            "baseline": baseline["answer"],
            "sourceBytes": len(body),
        }
    )
)
