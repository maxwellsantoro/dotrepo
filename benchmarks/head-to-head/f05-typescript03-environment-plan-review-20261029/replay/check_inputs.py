"""Owned data-only source, lock-block, runtime-range and scope checks."""

import hashlib
import json
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def package_blocks(text):
    rows, section, current, block, document = [], None, None, [], 0
    first, doc = 0, 0
    for number, line in enumerate(text.splitlines(), 1):
        if line == "---":
            document += 1
        match = re.fullmatch(r"  (.+):", line) if section == "packages" else None
        if match or (line and not line.startswith(" ")):
            if current is not None:
                rows.append(
                    {
                        "id": current,
                        "document": doc,
                        "startLine": first,
                        "endLine": number - 1,
                        "text": "\n".join(block) + "\n",
                    }
                )
                current, block = None, []
        if line and not line.startswith(" "):
            section = line[:-1] if line.endswith(":") else None
        if match:
            current, first, doc = match[1].strip("'\""), number, document
        if current is not None:
            block.append(line)
    return rows


def version(text):
    return tuple(
        int(x) if x not in {"*", "x"} else 0 for x in (text.lstrip("v").split(".") + ["0", "0"])[:3]
    )


def accepts(range_text, candidate=(24, 22, 2)):
    """Only the comparator grammar occurring in this frozen lock; reject unknown."""
    for branch in range_text.split("||"):
        tokens = re.findall(r"(>=|<=|>|<|\^|~|=)?\s*(v?\d+(?:\.(?:\d+|\*|x)){0,2})", branch.strip())
        rendered = "".join((op or "") + val for op, val in tokens)
        if rendered != re.sub(r"\s", "", branch):
            raise ValueError("unsupported range: " + range_text)
        okay = True
        for op, val in tokens:
            low = version(val)
            if op == ">=":
                okay &= candidate >= low
            elif op == ">":
                okay &= candidate > low
            elif op == "<=":
                okay &= candidate <= low
            elif op == "<":
                okay &= candidate < low
            elif op == "^":
                okay &= low <= candidate < (low[0] + 1, 0, 0)
            elif op == "~":
                okay &= low <= candidate < (low[0], low[1] + 1, 0)
            else:
                parts = val.split(".")
                count = next(
                    (i for i, value in enumerate(parts) if value in {"*", "x"}), len(parts)
                )
                okay &= candidate[:count] == low[:count]
        if okay:
            return True
    return False


def main():
    acquisition = json.loads((HERE / "acquisition.json").read_bytes())
    inventory = json.loads((HERE / "inventory.json").read_bytes())["files"]
    archive_path = Path(acquisition["archivePath"])
    assert sha(archive_path.read_bytes()) == acquisition["archiveSha256"]
    observed = {}
    with tarfile.open(archive_path, "r:") as archive:
        for item in archive:
            assert item.isfile() and item.name not in observed
            body = archive.extractfile(item).read()
            observed[item.name] = sha(body)
        assert observed == inventory
        for path in (HERE / "sources").rglob("*"):
            if path.is_file():
                name = str(path.relative_to(HERE / "sources"))
                assert sha(path.read_bytes()) == inventory[name]
    assert len(observed) == 703
    package = json.loads((HERE / "sources/package.json").read_bytes())
    assert package["packageManager"] == "pnpm@12.11.2"
    assert package["scripts"]["test"] == "vitest"
    assert (
        package["scripts"]["test-e2e"]
        == "node scripts/build.js vue -f global -d && vitest --project e2e --project e2e-browser"
    )
    assert package["scripts"]["preinstall"] == "npx only-allow pnpm"
    assert package["scripts"]["postinstall"] == "simple-git-hooks"
    lock = (HERE / "sources/pnpm-lock.yaml").read_text()
    blocks = package_blocks(lock)
    requested = {
        "pnpm@12.11.2",
        "@pnpm/exe.linux-arm64@12.11.2",
        "vitest@4.1.11",
        "vite@8.3.4",
        "jsdom@30.0.1",
        "@vitest/browser-playwright@4.1.11",
        "@vitest/browser@4.1.11",
        "playwright@1.64.0",
        "playwright-core@1.64.0",
        "puppeteer@25.11.0",
        "puppeteer-core@25.11.0",
        "simple-git-hooks@2.14.0",
        "esbuild@0.28.2",
        "@swc/core@1.16.18",
    }
    requested.update(row["id"] for row in blocks if row["id"].startswith("@puppeteer/browsers@"))
    pins = []
    for name in sorted(requested):
        row = next(r for r in blocks if r["id"] == name)
        integrity = re.search(r"resolution: \{integrity: ([^}]+)\}", row["text"])
        assert integrity is not None
        node = re.search(r"engines: \{node: (?:'([^']+)'|\"([^\"]+)\"|([^,}]+))", row["text"])
        pins.append(
            {
                **row,
                "integrity": integrity[1],
                "nodeRange": next((x for x in node.groups() if x is not None), None)
                if node
                else None,
            }
        )
    assert not any(row["id"].startswith("only-allow@") for row in blocks)
    ranges = sorted(
        {
            next(x for x in match.groups() if x is not None)
            for match in re.finditer(r"engines: \{node: (?:'([^']+)'|\"([^\"]+)\"|([^,}]+))", lock)
        }
    )
    assert all(accepts(value) for value in ranges)
    assert accepts(package["engines"]["node"])
    # Owned comparator controls, unrelated to running task code.
    assert not accepts(">=25") and not accepts("^22.12") and accepts("^24.15")
    assert not accepts(">=20 <22 || >=25") and accepts(">=20 <22 || >=24")
    config = (HERE / "sources/vitest.config.ts").read_text()
    names = re.findall(r"name: '([^']+)'", config)
    assert names == ["unit", "unit-gc", "unit-jsdom", "e2e", "e2e-browser"]
    assert "execArgv: ['--expose-gc']" in config and "pool: 'forks'" in config
    assert "instances: [{ browser: 'chromium' }]" in config
    checks = {
        "state": "source-and-declared-constraint-data-checks-pass-not-environment-qualification",
        "sourceMembersVerified": 703,
        "retainedSourceFiles": sum(f.is_file() for f in (HERE / "sources").rglob("*")),
        "lockDocuments": lock.count("\n---\n") + 1,
        "packageManagerPinDocument": next(r["document"] for r in pins if r["id"] == "pnpm@12.11.2"),
        "packagePins": pins,
        "node24_22_2SatisfiesObservedNodeEngineRanges": ranges,
        "engineEvaluationLimit": "frozen simple comparator grammar only, no peer/OS/libc/ABI/package resolution proof",
        "onlyAllowPinnedInPackageLock": False,
        "fiveProjects": names,
        "nativeCollectionOccurred": False,
        "actualAdmission": False,
    }
    with (HERE / "checks.json").open("x") as out:
        json.dump(checks, out, sort_keys=True, indent=2)
        out.write("\n")
    print(
        json.dumps(
            {
                "sourceMembers": 703,
                "projects": names,
                "pins": len(pins),
                "nodeEngineRanges": len(ranges),
                "actualAdmission": False,
            }
        )
    )


if __name__ == "__main__":
    main()
