#!/usr/bin/env -S uv run python
"""Keep live release and benchmark prose aligned with their owning sources."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

START = "<!-- dotrepo:release-status:start -->"
END = "<!-- dotrepo:release-status:end -->"


def versions(root: Path) -> tuple[str, str]:
    source = tomllib.loads((root / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    adoption = (root / "crates/dotrepo-core/src/adoption.rs").read_text()
    stable = re.search(r'pub const DEFAULT_CI_RELEASE_VERSION: &str = "([^"]+)";', adoption)
    if stable is None or re.fullmatch(r"\d+\.\d+\.\d+", stable[1]) is None:
        raise ValueError("maintainer CI must own an explicit stable release version")
    return stable[1], source


def release_block(root: Path) -> str:
    stable, source = versions(root)
    status = (
        "release candidate"
        if "-rc." in source
        else "prerelease"
        if "-" in source
        else "stable source"
    )
    return (
        f"{START}\nStable installs use `{stable}`; current source is `{source}` ({status}).\n"
        f"Use the matching tagged documentation for installed binaries.\n{END}"
    )


def check(root: Path, *, write: bool = False) -> list[str]:
    errors = []
    expected = release_block(root)
    for relative in ("docs/install.md", "docs/distribution.md"):
        path = root / relative
        text = path.read_text()
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
        matches = pattern.findall(text)
        if len(matches) != 1:
            errors.append(f"{relative}: requires one generated release-status block")
        elif matches[0] != expected:
            if write:
                text = pattern.sub(lambda _: expected, text)
                path.write_text(text)
            else:
                errors.append(
                    f"{relative}: release status is stale; run check_release_guidance.py --write"
                )
    stable, _ = versions(root)
    install = (root / "docs/install.md").read_text()
    pins = re.findall(
        r"^cargo install dotrepo(?:-cli|-mcp|-lsp)? --version (\S+) --locked$",
        install,
        re.MULTILINE,
    )
    if len(pins) != 3 or any(pin != stable for pin in pins):
        errors.append(
            "docs/install.md: stable installation commands disagree with the stable release owner"
        )
    # Internal agreement is insufficient: retain the publication evidence before
    # advancing defaults, and reject defaults left behind that verified release.
    compatibility = root / "docs/release-compatibility.md"
    if compatibility.is_file():
        references = re.findall(
            r"\(\.\./(index/telemetry/[^)]+/release-[^/()]+-verification\.json)\)",
            compatibility.read_text(),
        )
        if len(references) != 1:
            errors.append("release compatibility requires one stable publication receipt")
        else:
            try:
                receipt = json.loads((root / references[0]).read_text())
                if not (
                    receipt.get("version") == stable
                    and receipt.get("tag") == f"v{stable}"
                    and receipt.get("tagCommit") == receipt.get("releaseCommit")
                    and receipt.get("releaseCommit")
                    and receipt.get("postMergeCi", {}).get("conclusion") == "success"
                    and receipt.get("releaseWorkflow", {}).get("conclusion") == "success"
                    and all(
                        receipt.get("releaseWorkflow", {}).get("publicInstallJobs", {}).get(job)
                        == "success"
                        for job in (
                            "verify-public-installs (ubuntu-latest)",
                            "verify-public-installs (macos-latest)",
                        )
                    )
                ):
                    errors.append(
                        "stable default disagrees with verified publication/install receipt"
                    )
            except (OSError, ValueError):
                errors.append("stable publication receipt is missing or invalid")
    for relative in ("README.md", "docs/release-compatibility.md"):
        path = root / relative
        if path.is_file():
            release_tags = re.findall(r"releases/tag/v(\d+\.\d+\.\d+)", path.read_text())
            if not release_tags or release_tags[0] != stable:
                errors.append(
                    f"{relative}: primary stable release link disagrees with stable owner"
                )
    for manifest in sorted((root / "crates").glob("*/Cargo.toml")):
        package = tomllib.loads(manifest.read_text())["package"]
        if package.get("publish") is False:
            continue
        readme = package.get("readme")
        if readme != "README.md":
            errors.append(f"{manifest.relative_to(root)}: use a package-specific README.md")
            continue
        path = manifest.parent / readme
        if not path.is_file():
            errors.append(f"{path.relative_to(root)}: missing package README")
            continue
        content = path.read_text()
        for destination in re.findall(r"\]\(([^)]+)\)", content):
            if not destination.startswith(("https://", "#")):
                errors.append(
                    f"{path.relative_to(root)}: package link must be absolute: {destination}"
                )
        for pin in re.findall(r"cargo install \S+ --version (\S+) --locked", content):
            if pin != stable:
                errors.append(f"{path.relative_to(root)}: stale stable installation command")
    baseline = json.loads(
        (root / "scripts/fixtures/public_upstream_accuracy_baseline.json").read_text()
    )
    workload = json.loads((root / baseline["workload"]).read_text())
    assertions = workload["assertions"]
    expected_counts = f"with {len(assertions)} independently sourced assertions across {len({a['repository'] for a in assertions})} preselected repositories."
    path = root / "docs/public-factual-accuracy-benchmark.md"
    text = path.read_text()
    pattern = r"with \d+ independently sourced assertions across \d+ preselected repositories\."
    if re.findall(pattern, text) != [expected_counts]:
        if write and len(re.findall(pattern, text)) == 1:
            path.write_text(re.sub(pattern, expected_counts, text))
        else:
            errors.append(
                "docs/public-factual-accuracy-benchmark.md: recapture counts disagree with workload"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    errors = check(args.root, write=args.write)
    for error in errors:
        print(f"error: {error}")
    if not errors:
        print("release guidance and recapture counts match their sources")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
