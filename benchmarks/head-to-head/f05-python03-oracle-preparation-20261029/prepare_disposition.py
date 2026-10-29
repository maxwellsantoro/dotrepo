"""Trusted source-data preparation only; never imports or executes upstream code."""

import hashlib
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(name, value):
    with (HERE / name).open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main():
    scan = json.loads((HERE / "source-scan.json").read_text())
    archive = Path(scan["sourceArchivePath"])
    assert digest(archive.read_bytes()) == scan["sourceArchiveSha256"]
    with tarfile.open(archive, "r:") as tar:
        files = {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}
    spans = []
    for path, start, end, purpose in [
        ("setup.py", 113, 116, "Primary package and its shipped child packages."),
        (
            "CONTRIBUTING.md",
            75,
            85,
            "Documented test routes; direct download file is an alternative developer test, not full task coverage.",
        ),
        (
            "Makefile",
            32,
            53,
            "Full test target plus lint versus explicitly narrower offline target.",
        ),
        ("tox.ini", 1, 14, "Default tox excludes product/download test files."),
        (
            "devscripts/run_tests.sh",
            3,
            22,
            "Core/download partition and default full test command.",
        ),
        (
            ".github/workflows/ci.yml",
            407,
            418,
            "Nose/PyNose dependency choice; versions not locked here.",
        ),
        (
            ".github/workflows/ci.yml",
            461,
            468,
            "CI download failure tolerance does not certify task completion.",
        ),
        (
            "test/test_YoutubeDL.py",
            15,
            34,
            "Product tests import selected package plus extractors and postprocessors.",
        ),
        ("test/test_postprocessors.py", 11, 17, "Product suite reaches postprocessor package."),
        ("test/helper.py", 27, 39, "Committed defaults and optional local parameter merge."),
        (
            "test/helper.py",
            106,
            109,
            "Download cases are sourced dynamically from extractor definitions.",
        ),
        (
            "test/test_download.py",
            100,
            128,
            "Source-declared extractor and test-definition skip branches.",
        ),
        (
            "test/test_download.py",
            163,
            188,
            "Dynamic network-exhaustion return can look like a passing test.",
        ),
        (
            "test/test_download.py",
            278,
            294,
            "Dynamic test identities depend on generated extractor definitions/order.",
        ),
        ("test/test_socks.py", 24, 76, "Four optional proxy-config early-return cases."),
        (
            "test/test_socks.py",
            79,
            114,
            "Three source-default SOCKS stand-in cases; not observed proxy behavior.",
        ),
        (
            "test/test_downloader_external.py",
            74,
            76,
            "External downloader availability conditional skip.",
        ),
        ("test/test_downloader_external.py", 234, 245, "FFmpeg availability conditional skip."),
    ]:
        data = files[path]
        spans.append(
            {
                "path": path,
                "sha256": digest(data),
                "startLine": start,
                "endLine": end,
                "excerpt": "".join(data.decode().splitlines(keepends=True)[start - 1 : end]),
                "purpose": purpose,
            }
        )
    write("source-spans.json", spans)
    locators = [
        "AGENTS.md",
        "benchmarks/head-to-head/f05-agent-tasks-20261029/requests/python-03.md",
        "benchmarks/head-to-head/f05-agent-tasks-20261029/curator/gold/python-03.json",
        "benchmarks/head-to-head/f05-agent-tasks-20261029/curator/oracles/python-03.json",
        "benchmarks/head-to-head/f05-qualification-next8-20261029/python-03/acquisition.json",
        "benchmarks/head-to-head/f05-qualification-next8-20261029/python-03/inventory.json",
        "benchmarks/head-to-head/f05-qualification-next8-20261029/independent-scope-review/dispositions.json",
        "benchmarks/head-to-head/f05-qualification-next8-20261029/independent-challenge-review/coordinator-decision-receipt.json",
    ]
    write(
        "input-bindings.json",
        {
            p: {"sha256": digest((ROOT / p).read_bytes()), "bytes": (ROOT / p).stat().st_size}
            for p in locators
        },
    )


if __name__ == "__main__":
    main()
