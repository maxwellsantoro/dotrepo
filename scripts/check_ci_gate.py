#!/usr/bin/env -S uv run python
"""Aggregate scoped CI outcomes into one fail-closed required-check result."""

import json
import os
import sys


SCOPED_JOBS = {
    "rust-and-index": "run_rust_ci",
    "operator-gate": "run_operator_gate",
    "public-surface-gate": "run_public_surface_gate",
    "release-gate": "run_release_gate",
    "minimal-gate": "run_minimal_gate",
}


def check_results(needs: dict) -> list[str]:
    errors = []
    scope = needs.get("change-scope", {})
    if scope.get("result") != "success":
        errors.append("change-scope did not succeed")
    outputs = scope.get("outputs", {})
    selected = 0
    for job, output in SCOPED_JOBS.items():
        planned = outputs.get(output)
        if planned not in ("true", "false"):
            errors.append(f"missing or invalid scope output: {output}")
        selected += planned == "true"
        result = needs.get(job, {}).get("result")
        if planned == "true" and result != "success":
            errors.append(f"required job {job}: {result or 'missing'}")
        elif result not in ("success", "skipped"):
            errors.append(f"job {job}: {result or 'missing'}")
    if not selected:
        errors.append("change-scope selected no validation jobs")
    return errors


def main() -> int:
    try:
        needs = json.loads(os.environ["CI_NEEDS"])
        if not isinstance(needs, dict):
            raise ValueError("CI_NEEDS must be an object")
        errors = check_results(needs)
    except (KeyError, ValueError, TypeError, AttributeError) as err:
        errors = [f"invalid CI needs data: {err}"]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("All validation jobs selected by change-scope succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
