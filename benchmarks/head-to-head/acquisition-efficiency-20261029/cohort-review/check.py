"""Independent inert-record reconstruction; no acquisition or source execution."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib
from urllib.parse import urlsplit

ROOT = Path("/Users/maxwell/projects/agent/dotrepo")
SUBJECT = Path("/tmp/dotrepo-acquisition100-cohort-20261029")
BASE = "9fe76b4d08e44db3b4563281b82054674101dacc"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    frozen = json.loads((SUBJECT / "FREEZE.json").read_bytes())
    for name, b in frozen["artifactBindings"].items():
        raw = (SUBJECT / name).read_bytes()
        assert len(raw) == b["bytes"] and digest(raw) == b["sha256"], name
    inputs = json.loads((SUBJECT / "inputs.json").read_bytes())
    cohort = json.loads((SUBJECT / "cohort.json").read_bytes())
    assert inputs["seed"] == cohort["seed"] == "dotrepo-acquisition100-20261029-v1"
    assert inputs["selectionMethodReadmeSha256"] == digest((SUBJECT / "README.md").read_bytes())
    assert cohort["selectionMethodReadmeSha256"] == inputs["selectionMethodReadmeSha256"]
    assert cohort["indexInputBindingSha256"] == digest((SUBJECT / "inputs.json").read_bytes())
    subprocess.run(
        ["git", "diff", "--exit-code", BASE, "--", "index/repos/github.com"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    exclusions = defaultdict(list)
    for binding in inputs["exclusionSources"]:
        raw = (ROOT / binding["path"]).read_bytes()
        assert len(raw) == binding["bytes"] and digest(raw) == binding["sha256"]
        for task in json.loads(raw)["tasks"]:
            identity = task["repository"].lower()
            if binding["path"] not in exclusions[identity]:
                exclusions[identity].append(binding["path"])
    for identity in [
        "github.com/docker/compose",
        "github.com/keras-team/keras",
        "github.com/zellij-org/zellij",
    ]:
        exclusions[identity].append("explicit exposed development exclusion")
    assert dict(exclusions) == inputs["excludedIdentityUnion"]
    paths = sorted(
        p
        for p in (ROOT / "index/repos/github.com").glob("*/*/record.toml")
        if p.is_file() and not p.is_symlink()
    )
    identities = Counter("/".join(p.parts[-4:-1]).lower() for p in paths)
    assert not any(n > 1 for n in identities.values())
    bound = {x["recordPath"]: x for x in inputs["records"]}
    assert len(bound) == len(inputs["records"]) == len(paths) == inputs["recordCount"] == 615
    assert set(bound) == {str(p.relative_to(ROOT)) for p in paths}
    primary_counts, reasons = Counter(), Counter()
    pools = defaultdict(list)
    source_schemes = Counter()
    for path in paths:
        relative = str(path.relative_to(ROOT))
        b = bound[relative]
        raw = path.read_bytes()
        assert len(raw) == b["bytes"] and digest(raw) == b["sha256"], relative
        data = tomllib.loads(raw.decode())
        identity = "/".join(path.parts[-4:-1]).lower()
        languages = data["repo"].get("languages", [])
        primary = languages[0] if languages else None
        revision = data.get("x", {}).get("github", {}).get("head_sha")
        source = data["record"].get("source")
        parsed = urlsplit(source)
        assert parsed.hostname == "github.com" and not parsed.username and not parsed.password
        assert not parsed.query and not parsed.fragment and parsed.port is None
        source_identity = "/".join(["github.com", *parsed.path.strip("/").split("/")]).lower()
        assert source_identity == identity
        assert isinstance(revision, str) and re.fullmatch("[0-9a-f]{40}", revision)
        assert b["identity"] == identity and b["recordedPrimaryLanguage"] == primary
        assert b["recordedRevision"] == revision and b["recordSource"] == source
        primary_counts[str(primary)] += 1
        source_schemes[parsed.scheme] += 1
        group = {
            "Rust": "Rust",
            "Python": "Python",
            "JavaScript": "JS-TS",
            "TypeScript": "JS-TS",
            "Go": "Go",
        }.get(primary)
        # This cohort's two ineligible groups are disjoint: every indexed
        # exclusion has a declared sampled primary language.
        reason = (
            "frozen-or-development-exclusion"
            if identity in exclusions
            else "primary-language-outside-declared-groups"
            if group is None
            else None
        )
        if reason:
            assert b["eligible"] is False and b["selected"] is False and b["reason"] == reason
            reasons[reason] += 1
        else:
            rank = digest((inputs["seed"] + "\0" + group + "\0" + identity).encode())
            assert b["eligible"] is True and b["group"] == group and b["rankSha256"] == rank
            pools[group].append((rank, identity, b))
    assert dict(primary_counts) == inputs["primaryLanguageCounts"]
    assert dict(reasons) == inputs["ineligibilityCounts"]
    assert (
        {g: len(v) for g, v in pools.items()}
        == inputs["eligiblePoolCounts"]
        == cohort["eligiblePoolCounts"]
        == frozen["eligiblePools"]
    )
    expected = []
    for group in ["Rust", "Python", "JS-TS", "Go"]:
        for within, (rank, identity, b) in enumerate(sorted(pools[group])[:25], 1):
            expected.append((group, within, rank, identity, b))
    assert cohort["groupsInOutputOrder"] == ["Rust", "Python", "JS-TS", "Go"]
    assert (
        cohort["quotaPerGroup"] == 25
        and cohort["requestedTotal"]
        == cohort["selectedCount"]
        == len(cohort["opportunities"])
        == 100
    )
    assert len({x["identity"] for x in cohort["opportunities"]}) == 100
    for number, (actual, (group, within, rank, identity, b)) in enumerate(
        zip(cohort["opportunities"], expected, strict=True), 1
    ):
        assert actual["opportunityId"] == f"acq100-{number:03}"
        assert (
            actual["identity"],
            actual["group"],
            actual["withinGroupRank"],
            actual["rankSha256"],
        ) == (identity, group, within, rank)
        assert actual["repositoryUrl"].lower() == "https://" + identity
        assert actual["recordPath"] == b["recordPath"] and actual["recordSha256"] == b["sha256"]
        assert (
            actual["revision"] == b["recordedRevision"]
            and actual["recordedPrimaryLanguage"] == b["recordedPrimaryLanguage"]
        )
        assert (
            actual["recordedRevisionIsFreshInspection"] is False
            and actual["eventualFailureReplacementAllowed"] is False
        )
    selected = {row[3] for row in expected}
    assert all(b["selected"] == (b["identity"] in selected) for b in bound.values())
    assert not selected.intersection(exclusions)
    assert (
        not cohort["selectionUsesAcquisitionOutcomeOrFieldQuality"]
        and not cohort["recordedRevisionsFreshlyResolved"]
    )
    assert cohort["noReplacementOfMissingOrFailedSources"] is True
    assert not cohort["comparisonResultsExist"] and not cohort["experimentRunAuthorized"]
    assert (
        cohort["upstreamSourceRequests"]
        == cohort["providerCalls"]
        == cohort["nativeWorkloadsExecuted"]
        == 0
    )
    return {
        "state": "independent-cohort-data-audit-passed",
        "findings": [],
        "subjectFreezeSha256": digest((SUBJECT / "FREEZE.json").read_bytes()),
        "cohortSha256": digest((SUBJECT / "cohort.json").read_bytes()),
        "inputRecordsHashTomlIdentityRevisionLanguageRechecked": 615,
        "allInputRecordsUnchangedFromBase": BASE,
        "sourceSchemes": dict(source_schemes),
        "duplicateCanonicalIdentities": 0,
        "exclusionUnion": len(exclusions),
        "indexedExclusions": sum(i in exclusions for i in identities),
        "ineligibleReasons": dict(reasons),
        "eligiblePools": {g: len(v) for g, v in pools.items()},
        "selected": 100,
        "selectedByGroup": dict(Counter(x["group"] for x in cohort["opportunities"])),
        "all100RankingOrderAndRevisionBindingsMatch": True,
        "notFreshHoldoutOrConsumerEvidence": True,
        "experimentRunAuthorized": False,
        "reviewerContext": "Known E1/F05 source curator and tree-reuse implementation author; did not select this cohort. No upstream source bodies, acquisition results or field-quality outputs consulted for the audit.",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
