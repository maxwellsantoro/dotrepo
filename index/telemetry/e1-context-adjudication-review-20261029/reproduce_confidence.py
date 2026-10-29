"""Pure synthetic original-subject confidence boundary; no provider calls."""

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REVIEW = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=REVIEW / "original-source/scripts/adjudication_openrouter_sidecar.py",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "scripts"))
    sidecar = load("adjudication_openrouter_sidecar", args.sidecar)
    fixtures = load(
        "original_review_fixture",
        REVIEW / "original-source/scripts/tests/test_openrouter_adjudication.py",
    )
    request = fixtures.context_request()
    controls = []
    for confidence in ("low", "medium", "high"):
        answer = fixtures.context_answer(request)
        answer["confidence"] = confidence
        result = sidecar.normalize_response(request, answer, 35)
        controls.append(
            {
                "input": answer,
                "observed": result,
                "expectedConfidence": "medium" if confidence == "high" else confidence,
            }
        )
    for mutation in ("tuple", "source", "citation", "duplicate_citations", "omission"):
        mutated = copy.deepcopy(request)
        answer = fixtures.context_answer(mutated)
        if mutation == "tuple":
            answer["value"] += " "
        elif mutation == "source":
            answer["source"] = ".env"
        elif mutation == "citation":
            answer["citations"] = ["e" * 64]
        elif mutation == "duplicate_citations":
            answer["citations"] *= 2
        else:
            mutated["candidates"][0]["contextEvidence"]["omissions"] = ["missing prerequisite"]
        try:
            sidecar.normalize_response(mutated, answer, 35)
            refused = False
        except sidecar.CompletionError:
            refused = True
        controls.append({"mutation": mutation, "refused": refused})
    answer = fixtures.context_answer(request)
    answer.update(value=None, source=None, citations=[], confidence="low")
    controls.append({"abstention": sidecar.normalize_response(request, answer, 35)})
    output = {
        "sidecarSha256": hashlib.sha256(args.sidecar.read_bytes()).hexdigest(),
        "request": request,
        "controls": controls,
        "providerCalls": 0,
        "scope": "synthetic adapter normalization; not semantic source completeness",
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                "controls": len(controls),
                "confidenceMismatches": sum(
                    "observed" in row and row["observed"]["confidence"] != row["expectedConfidence"]
                    for row in controls
                ),
                "invalidSelectionsRefused": sum(row.get("refused", False) for row in controls),
            }
        )
    )


if __name__ == "__main__":
    main()
