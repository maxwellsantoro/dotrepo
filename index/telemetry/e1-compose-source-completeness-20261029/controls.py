"""Owned portable data-verifier controls; never execute inspected upstream code."""

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("compose_integration_verify", HERE / "verify.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    reports = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-e1-compose-integration-controls-") as folder:
        root = Path(folder).resolve()
        copy = root / "relocated"
        shutil.copytree(HERE, copy, ignore=shutil.ignore_patterns("__pycache__"))
        original_open = Path.open

        def local_only(path, *args, **kwargs):
            assert path.resolve().is_relative_to(copy), "unexpected external read: " + str(path)
            return original_open(path, *args, **kwargs)

        Path.open = local_only
        try:
            local = v.verify_evidence(copy)
        finally:
            Path.open = original_open
        assert (
            local["fullSourceArchiveVerifiedThisRun"] is False
            and local["externalArtifactsNotVerifiedThisRun"] == 9
        )
        reports.append({"case": "relocated-local-only-no-external-reads", "result": local})
        if args.archive is not None:
            full = v.verify_evidence(copy, args.archive)
            assert full["fullSourceMembersVerifiedThisRun"] == 956
            assert full["externalArtifactsNotVerifiedThisRun"] == 8
            reports.append({"case": "explicit-external-archive", "result": full})
        else:
            reports.append(
                {"case": "explicit-external-archive", "state": "not-requested-not-verified"}
            )

        def rejects(name, target, supplied_archive=None):
            try:
                v.verify_evidence(target, supplied_archive)
            except (ValueError, FileNotFoundError) as exc:
                reports.append({"case": name, "rejected": True, "error": str(exc)})
            else:
                raise AssertionError(name + " accepted")

        rejects("explicit-missing-archive-no-fallback", copy, root / "absent.tar")
        broken = root / "broken.tar"
        broken.write_bytes(b"owned non-archive data")
        rejects("explicit-malformed-archive", copy, broken)
        heads = json.loads((copy / "membership/headers.json").read_bytes())
        chosen = copy / "membership/headers" / heads["headers"][0]["path"]
        before = chosen.read_bytes()
        chosen.write_bytes(before + b"\n")
        rejects("changed-retained-header", copy)
        chosen.write_bytes(before)
        chosen.unlink()
        rejects("missing-retained-header", copy)
        chosen.write_bytes(before)
        route = copy / "membership/routing/Makefile"
        before = route.read_bytes()
        route.write_bytes(before + b"\n")
        rejects("changed-route-source", copy)
        route.write_bytes(before)
        manifest_path = copy / "integration.json"
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        changed = deepcopy(manifest)
        changed["packets"]["membership"]["omittedPaths"].append("headers.json")
        changed["packets"]["membership"]["copiedPaths"].remove("headers.json")
        manifest_path.write_text(json.dumps(changed))
        rejects("hidden-header-omission", copy)
        manifest_path.write_bytes(raw)
        external = copy / "acquisition/source.tar"
        external.write_bytes(b"not permitted in repository wrapper")
        rejects("archive-silently-contained", copy)
        external.unlink()
        assert v.verify_evidence(copy) == local
    result = {
        "state": "portable-data-controls-pass",
        "count": len(reports),
        "executedControls": len(reports) - (args.archive is None),
        "externalArchiveControlPerformed": args.archive is not None,
        "cases": reports,
        "newNetworkDaemonProviderActions": 0,
        "upstreamExecuted": False,
        "completeApplicableInstructionEstablished": False,
        "confidencePromotion": False,
        "heldOutQualification": False,
        "consumerBenefit": False,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
