#!/usr/bin/env -S uv run python
"""Lead releases with user changes, package choice and explicit release channels."""

import argparse
import re
from pathlib import Path
from urllib.parse import urljoin

from check_release_guidance import versions
from check_release_version import SEMVER


def render(root: Path, version: str) -> str:
    if SEMVER.fullmatch(version) is None:
        raise ValueError("release version must be SemVer")
    stable, _ = versions(root)
    preview = "-" in version
    channel = (
        f"**Preview release.** For production use stable **{stable}**. Install this preview only when you need its version-specific behavior."
        if preview
        else f"**Stable release {version}.** Use the pinned installation below for production."
    )
    changelog = (root / "CHANGELOG.md").read_text()
    sections = re.split(r"(?m)^## ", changelog)
    selected = next(
        (section for section in sections[1:] if section.splitlines()[0].split()[0] == version),
        None,
    )
    if selected is None:
        selected = next(section for section in sections[1:] if section.startswith("Unreleased\n"))
    changes = selected.split("\n", 1)[1].strip()
    # Release bodies are rendered outside the repository's Markdown context.
    changes = re.sub(
        r"\]\(([^)]+)\)",
        lambda match: "]("
        + (
            match[1]
            if match[1].startswith(("https://", "http://", "#"))
            else urljoin("https://github.com/maxwellsantoro/dotrepo/blob/main/", match[1])
        )
        + ")",
        changes,
    )
    return f"""{channel}

### What changed

{changes}

### Install the tool you need

- `dotrepo-cli` supplies the `dotrepo` command and `dotrepo-public-query`.
- `dotrepo-mcp` connects an MCP client over stdio.
- `dotrepo-lsp` provides editor diagnostics and completion for `.repo` files.

```bash
cargo install dotrepo-cli --version {version} --locked
cargo install dotrepo-mcp --version {version} --locked
cargo install dotrepo-lsp --version {version} --locked
```

Install only the packages you need. Platform bundles and the VS Code extension
are attached below. Verify downloads against their matching checksum files.
The MCP Registry may show a higher prerelease as latest; choose your version explicitly.

[Installation and release channels](https://github.com/maxwellsantoro/dotrepo/blob/main/docs/install.md)
· [Version-specific behavior and limits](https://github.com/maxwellsantoro/dotrepo/blob/main/docs/release-compatibility.md)
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(render(args.root, args.version))


if __name__ == "__main__":
    main()
