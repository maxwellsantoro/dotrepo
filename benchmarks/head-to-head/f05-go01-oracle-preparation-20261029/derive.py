"""Derive source-only evidence from the existing frozen archive; execute no Go."""

import hashlib
import json
from pathlib import Path
import re
import tarfile

from oracle import COMMAND, REVISION, SOURCE

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "f05-go01-requalification-proposal-20261029"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, value):
    with (HERE / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    freeze = json.loads((PRIOR / "freeze.json").read_text())
    for entry in freeze["files"]:
        assert sha((PRIOR / entry["path"]).read_bytes()) == entry["sha256"]
    integrity = json.loads((PRIOR / "source-integrity.json").read_text())
    archive = Path(integrity["sourceArchive"]["path"])
    assert sha(archive.read_bytes()) == SOURCE
    lexical = json.loads((PRIOR / "static-test-inventory.json").read_text())
    files = {row["path"]: row for row in lexical["files"]}
    sites = lexical["skipSites"]
    by_path = {}
    for site in sites:
        by_path.setdefault(site["path"], []).append(site)
    evidence, helper_sites, raw_sources = [], [], {}
    with tarfile.open(archive) as tar:
        for member in tar:
            path = member.name
            if not path.startswith("tsc/") or not path.endswith(".go") or "/testdata/" in path:
                continue
            if path.endswith("_test.go") and path not in by_path:
                continue
            raw = tar.extractfile(member).read()
            lines = raw.decode().splitlines()
            if path in by_path:
                assert sha(raw) == files[path]["sha256"]
                raw_sources[path] = raw
                for site in by_path[path]:
                    line = site["line"]
                    assert lines[line - 1].strip() == site["text"]
                    start, end = max(1, line - 4), min(len(lines), line + 2)
                    evidence.append(
                        {
                            **site,
                            "sourceSha256": sha(raw),
                            "startLine": start,
                            "endLine": end,
                            "excerpt": "\n".join(lines[start - 1 : end]),
                            "disposition": "not an executable allowlist; exact native identity/condition may remain unresolved",
                        }
                    )
            elif not path.endswith("_test.go"):
                for number, line in enumerate(lines, 1):
                    if re.search(r"\.Skip(?:Now|f)?\(", line):
                        start, end = max(1, number - 8), min(len(lines), number + 3)
                        helper_sites.append(
                            {
                                "path": path,
                                "line": number,
                                "text": line.strip(),
                                "sourceSha256": sha(raw),
                                "startLine": start,
                                "endLine": end,
                                "excerpt": "\n".join(lines[start - 1 : end]),
                                "disposition": "unresolved dynamic identity or missing setup; no pattern exclusion allowed",
                            }
                        )
                        raw_sources[path] = raw
    assert len(evidence) == len(sites) == 469
    assert len(helper_sites) == 11
    candidates = json.loads((PRIOR / "known-disabled-candidates.json").read_text())["cases"]
    exclusions = []

    def entry(path, test, line, reason, message, condition):
        raw = raw_sources[path]
        source_lines = raw.decode().splitlines()
        return {
            "package": "github.com/microsoft/TypeScript/" + path.rsplit("/", 1)[0],
            "test": test,
            "reason": reason,
            "outputReason": message,
            "condition": condition,
            "conditionSatisfied": True,
            "sourcePath": path,
            "sourceSha256": sha(raw),
            "line": line,
            "startLine": max(1, line - 2),
            "endLine": line + 2,
            "excerpt": "\n".join(source_lines[max(0, line - 3) : line + 2]),
            "behaviorExercised": False,
        }

    for case in candidates:
        path, line = case["upstreamPath"], case["line"]
        raw = raw_sources[path]
        assert sha(raw) == case["sourceSha256"]
        assert (
            raw.decode().splitlines()[line - 1].strip() == 't.Skip("Known failing fourslash test")'
        )
        prefix = raw.decode().splitlines()[: line - 1]
        assert re.search(
            r"func " + re.escape(case["test"]) + r"\(t \*testing.T\) \{\s*$", "\n".join(prefix)
        )
        exclusions.append(
            entry(
                path,
                case["test"],
                line,
                case["sourceReason"],
                case["sourceReason"],
                "Immediate unconditional source-authored default skip",
            )
        )
    exclusions.append(
        entry(
            "tsc/internal/fourslash/tests/autoImportPackageRootPathTypeModule_test.go",
            "TestAutoImportPackageRootPathTypeModule",
            11,
            "Source-authored unconditional bare skip",
            None,
            "Immediate unconditional source-authored default skip",
        )
    )
    exclusions.append(
        entry(
            "tsc/internal/lsp/replay_test.go",
            "TestReplay",
            45,
            "no replay file specified",
            "no replay file specified",
            "Frozen default wrapper supplies no -replay argument; source flag defaults to empty",
        )
    )
    exclusions.append(
        entry(
            "tsc/internal/project/ata/ata_test.go",
            "TestATA/deduplicate_from_local_@types_packages",
            518,
            "Todo - implement removing local @types from include list",
            "Todo - implement removing local @types from include list",
            "Immediate unconditional skip in this exact literal TestATA subtest; spaces become underscores in Go identity",
        )
    )
    assert len(exclusions) == 380
    binding = {
        "revision": REVISION,
        "sourceArchiveSha256": SOURCE,
        "imageId": "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092",
        "environmentSha256": "UNRESOLVED_FUTURE_FROZEN_ENVIRONMENT",
        "command": COMMAND,
        "scope": "repository-default",
    }
    write(
        "policy-proposal.json",
        {
            "state": "proposal-unaccepted",
            "synthetic": False,
            "binding": binding,
            "acceptanceSha256": None,
            "acceptedAt": None,
            "exclusions": exclusions,
            "unresolved": [
                "Exact future native collection and environment binding",
                "Dynamic compiler output/options, fuzz seed identities and platform/capability/helper conditions",
                "Independent policy review and coordinator acceptance; no observed future failure may enlarge this list automatically",
            ],
        },
    )
    write(
        "collection-required.json",
        {
            "state": "missing-native-collection",
            "synthetic": False,
            "binding": binding,
            "packages": {},
            "exitCode": None,
            "error": None,
            "completedAt": None,
            "frozenAt": None,
            "rawEventsSha256": None,
            "packageInventorySha256": None,
            "receiptSha256": None,
            "note": "No native case/package counts collected; static lexical inventory is not a substitute",
        },
    )
    write(
        "skip-source-ledger.json",
        {
            "revision": REVISION,
            "sourceArchiveSha256": SOURCE,
            "lexicalTestFileSites": evidence,
            "nonTestHelperSites": helper_sites,
            "lexicalCompletenessLimitation": "Direct literal Skip/Skipf/SkipNow calls only; not Go analysis or dynamic runtime identity collection. Benchmarks/build-tag alternatives/helper definitions are not assumed active.",
        },
    )
    write(
        "source-bindings.json",
        {
            "proposalFreezeSha256": sha((PRIOR / "freeze.json").read_bytes()),
            "proposalBindings": freeze["files"],
            "sourceArchive": integrity["sourceArchive"],
            "sourceArchiveRehashed": True,
            "testFileSkipSitesBound": len(evidence),
            "additionalNonTestHelperSkipSitesBound": len(helper_sites),
            "proposedExactExclusions": len(exclusions),
            "nativeCollectionOccurred": False,
            "networkDockerProviderOrUpstreamExecutionCalls": 0,
        },
    )


if __name__ == "__main__":
    main()
