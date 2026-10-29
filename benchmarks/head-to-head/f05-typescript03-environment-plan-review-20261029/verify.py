"""Inert source/lock verification only. No JS, packages, downloads or workloads."""

import base64
import hashlib
import json
from pathlib import Path
import re
import tarfile

import yaml

HERE = Path(__file__).resolve().parent
SUBJECT = Path("/tmp/dotrepo-f05-typescript03-environment-plan-20261029")
REPO = Path("/Users/maxwell/projects/agent/dotrepo")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(p):
    return json.loads(p.read_bytes())


def version(v):
    return tuple(
        int(n) if n not in ("x", "*") else 0 for n in (v.lstrip("v").split(".") + ["0", "0"])[:3]
    )


def witness(text):
    actual = (24, 22, 2)
    for arm in text.split("||"):
        tokens = re.findall(r"(>=|<=|>|<|\^|~|=)?\s*(v?\d+(?:\.(?:\d+|x|\*)){0,2})", arm)
        assert "".join((o or "") + v for o, v in tokens) == re.sub(r"\s", "", arm), text
        good = True
        for op, v in tokens:
            low = version(v)
            if op == ">=":
                okay = actual >= low
            elif op == ">":
                okay = actual > low
            elif op == "<=":
                okay = actual <= low
            elif op == "<":
                okay = actual < low
            elif op == "^":
                high = (
                    (low[0] + 1, 0, 0)
                    if low[0]
                    else ((0, low[1] + 1, 0) if low[1] else (0, 0, low[2] + 1))
                )
                okay = low <= actual < high
            elif op == "~":
                okay = low <= actual < (low[0], low[1] + 1, 0)
            else:
                parts = v.lstrip("v").split(".")
                count = next((i for i, n in enumerate(parts) if n in ("x", "*")), len(parts))
                okay = actual[:count] == low[:count]
            good &= okay
        if good:
            return arm.strip()
    raise AssertionError("Node candidate violates source range: " + text)


def main():
    assert (
        digest((SUBJECT / "FREEZE.json").read_bytes())
        == "cb9945829c3ba3d942e4bcf0b117bbb99c902d12faf12818b2a68cbd96c289df"
    )
    frozen = read(SUBJECT / "FREEZE.json")
    for name, row in frozen["artifacts"].items():
        p = SUBJECT / name
        assert p.is_file() and not p.is_symlink()
        assert p.stat().st_size == row["bytes"] and digest(p.read_bytes()) == row["sha256"], name
    plan = read(SUBJECT / "plan.json")
    binding = read(SUBJECT / "source-bindings.json")
    path = Path(plan["sourceArchive"]["path"])
    assert digest(path.read_bytes()) == plan["sourceArchive"]["sha256"] == binding["archiveSha256"]
    inventory = read(SUBJECT / "inventory.json")["files"]
    observed = {}
    with tarfile.open(path, "r:") as archive:
        for member in archive:
            assert member.isfile() and member.name not in observed
            observed[member.name] = digest(archive.extractfile(member).read())
    assert observed == inventory and len(observed) == 703
    for row in binding["sources"] + binding["ownerInputs"]:
        raw = (SUBJECT / row["snapshot"]).read_bytes()
        assert len(raw) == row["bytes"] and digest(raw) == row["sha256"]
        if row in binding["sources"]:
            assert row["sha256"] == inventory[row["path"]]
    for span in read(SUBJECT / "source-spans.json"):
        raw = (SUBJECT / "sources" / span["path"]).read_bytes()
        excerpt = "".join(
            raw.decode().splitlines(keepends=True)[span["startLine"] - 1 : span["endLine"]]
        )
        assert excerpt == span["text"] and digest(excerpt.encode()) == span["passageSha256"]
        assert digest(raw) == span["wholeFileSha256"]
    lock = (SUBJECT / "sources/pnpm-lock.yaml").read_text()
    docs = list(yaml.safe_load_all(lock))
    assert len(docs) == 2
    assert docs[0]["importers"]["."]["packageManagerDependencies"]["pnpm"] == {
        "specifier": "12.11.2",
        "version": "12.11.2",
    }
    assert "catalogs" in docs[1] and "devDependencies" in docs[1]["importers"]["."]
    pins = read(SUBJECT / "tool-pins.json")
    assert len(pins["pins"]) == 15
    for row in pins["pins"]:
        source = docs[row["document"] - 1]["packages"][row["id"]]
        assert row["integrity"] == source["resolution"]["integrity"]
        assert row["text"] == "".join(
            lock.splitlines(keepends=True)[row["startLine"] - 1 : row["endLine"]]
        )
        alg, encoded = row["integrity"].split("-", 1)
        assert alg == "sha512" and len(base64.b64decode(encoded, validate=True)) == 64
    platform = docs[0]["packages"]["@pnpm/exe.linux-arm64@12.11.2"]
    assert (
        platform["cpu"] == ["arm64"]
        and platform["os"] == ["linux"]
        and platform["libc"] == ["glibc"]
    )
    assert "@pnpm/exe.linux-arm64@12.11.2" in docs[0]["snapshots"]
    nodeRanges = sorted(
        {
            str(package["engines"]["node"])
            for doc in docs
            for package in doc["packages"].values()
            if "engines" in package and "node" in package["engines"]
        }
    )
    assert len(nodeRanges) == 91
    witnesses = {s: witness(s) for s in nodeRanges}
    package = read(SUBJECT / "sources/package.json")
    assert witness(package["engines"]["node"])
    assert package["packageManager"] == "pnpm@12.11.2" and package["scripts"]["test"] == "vitest"
    assert (
        package["scripts"]["test-e2e"]
        == "node scripts/build.js vue -f global -d && vitest --project e2e --project e2e-browser"
    )
    assert (
        package["scripts"]["preinstall"] == "npx only-allow pnpm"
        and package["scripts"]["postinstall"] == "simple-git-hooks"
    )
    assert "only-allow" not in package["devDependencies"]
    assert not any(name.startswith("only-allow@") for doc in docs for name in doc["packages"])
    config = (SUBJECT / "sources/vitest.config.ts").read_text()
    assert re.findall(r"name: '([^']+)'", config) == [
        "unit",
        "unit-gc",
        "unit-jsdom",
        "e2e",
        "e2e-browser",
    ]
    assert "pool: 'forks'" in config and "execArgv: ['--expose-gc']" in config
    assert "provider: playwright()" in config and "instances: [{ browser: 'chromium' }]" in config
    assert (SUBJECT / "sources/.node-version").read_text().strip() == "lts/*"
    workspace = yaml.safe_load((SUBJECT / "sources/pnpm-workspace.yaml").read_bytes())
    assert sorted(workspace["allowBuilds"]) == [
        "@parcel/watcher",
        "@swc/core",
        "esbuild",
        "puppeteer",
        "simple-git-hooks",
        "unrs-resolver",
    ]
    assert workspace["minimumReleaseAge"] == 1440 and workspace["trustPolicy"] == "no-downgrade"
    assert workspace["minimumReleaseAgeExclude"] == ["vitest@4.1.11"]
    image = read(SUBJECT / "image-tool-bindings.json")
    files = read(REPO / image["inventoryPath"])["files"]
    assert digest((REPO / image["inventoryPath"]).read_bytes()) == image["inventorySha256"]
    for name, row in image["selectedEntries"].items():
        assert files.get(name) == row, name
    assert not any("pnpm" in name and name.endswith("/package.json") for name in files)
    contract = read(SUBJECT / "preparation-contract.json")
    for flag in [
        "actualAdmission",
        "cacheQualified",
        "campaignAdmitted",
        "executionAuthorized",
        "nativeCollectionOccurred",
        "oracleQualified",
        "taskOutcomeObserved",
    ]:
        assert contract[flag] is False
    assert contract["scope"]["fullTarget"] == [
        "unit",
        "unit-gc",
        "unit-jsdom",
        "e2e",
        "e2e-browser",
    ]
    assert contract["scope"]["narrowingAllowed"] is False
    result = {
        "state": "independent-inert-source-and-lock-verification-pass",
        "subjectFreezeSha256": digest((SUBJECT / "FREEZE.json").read_bytes()),
        "contractSha256": digest((SUBJECT / "preparation-contract.json").read_bytes()),
        "authorArtifacts": len(frozen["artifacts"]),
        "archiveMembers": len(observed),
        "retainedSourceFiles": len(binding["sources"]),
        "retainedOwnerInputs": len(binding["ownerInputs"]),
        "lockDocuments": len(docs),
        "pinsVerified": len(pins["pins"]),
        "node24_22_2RangeWitnesses": witnesses,
        "yamlParserVersion": yaml.__version__,
        "platformSRI": platform["resolution"]["integrity"],
        "pnpmSRI": docs[0]["packages"]["pnpm@12.11.2"]["resolution"]["integrity"],
        "noNewAcquisitionOrExecution": True,
        "actualAdmission": False,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
