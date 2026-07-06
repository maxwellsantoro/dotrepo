"""Seed a self-contained offline scenario into the replay cache so the full
pipeline (Http -> arms -> scoring -> report) runs with no network. One repo,
crafted so the dotrepo arm is CORRECT on most fields but CONFIDENTLY WRONG on
license -- proving the four-way scorer flags the exact failure mode dotrepo's
trust model exists to prevent."""

import hashlib
import json
import os
from urllib.parse import quote

import yaml

from bench.arms.github_arm import DOC_PATHS

CACHE = "results/fixtures"
os.makedirs(CACHE, exist_ok=True)
for name in os.listdir(CACHE):
    if name.endswith(".json"):
        os.unlink(os.path.join(CACHE, name))

seeded_urls = set()


def put(url, status, text):
    seeded_urls.add(url)
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    json.dump(
        {"url": url, "status": status, "text": text}, open(os.path.join(CACHE, f"{h}.json"), "w")
    )


REPO = "github.com/acme/widget"
OWNER, REPOSITORY = "acme", "widget"

# --- GitHub REST metadata (truthful) ---
put(
    f"https://api.github.com/repos/{OWNER}/{REPOSITORY}",
    200,
    json.dumps(
        {
            "description": "A fast widget toolkit for the terminal",
            "language": "Rust",
            "homepage": "https://widget.example",
            "archived": False,
            "default_branch": "main",
            "license": {"spdx_id": "Apache-2.0"},
        }
    ),
)

# --- README with a real build + test block and an MSRV line ---
put(
    f"https://raw.githubusercontent.com/{OWNER}/{REPOSITORY}/main/README.md",
    200,
    """# widget

## Building
```bash
cargo build --release
```

## Testing
```bash
cargo test --all
```

widget requires Rust 1.74 or newer (MSRV 1.74).
""",
)

# --- SECURITY.md with a contact ---
put(
    f"https://raw.githubusercontent.com/{OWNER}/{REPOSITORY}/main/SECURITY.md",
    200,
    "Please report vulnerabilities privately to security@widget.example.",
)

# CONTRIBUTING absent
put(f"https://raw.githubusercontent.com/{OWNER}/{REPOSITORY}/main/CONTRIBUTING.md", 404, "")

# Freeze every conventional-source probe. Replay mode fails closed on a cache
# miss, so the offline self-test cannot silently touch the network when the
# baseline's source discovery expands.
for candidate_paths in DOC_PATHS.values():
    for candidate_path in candidate_paths:
        url = f"https://raw.githubusercontent.com/{OWNER}/{REPOSITORY}/main/{candidate_path}"
        if url not in seeded_urls:
            put(url, 404, "")

# --- dotrepo batch/query envelope ---
# Correct on description/language/build/test/security; ABSTAINS on homepage;
# CONFIDENTLY WRONG on license (says MIT @ high). This is the scenario that
# separates "accurate index" from "confidently wrong index".
paths = [
    "repo.description",
    "repo.license",
    "repo.language",
    "repo.homepage",
    "repo.archived",
    "repo.build",
    "repo.test",
    "owners.security_contact",
    "repo.toolchain.min",
]


def result(path, value, conf, prov="native-record"):
    return {"path": path, "value": value, "confidence": conf, "provenance": prov}


env = {
    "repo": REPO,
    "results": [
        result("repo.description", "A fast widget toolkit for the terminal", "high"),
        result("repo.license", "MIT", "high"),  # WRONG, asserted high
        result("repo.language", "Rust", "high"),
        result("repo.homepage", None, None),  # abstain
        result("repo.archived", "active", "high"),
        result("repo.build", "cargo build --release", "high"),
        result("repo.test", "cargo test --all", "high"),
        result("owners.security_contact", "security@widget.example", "high"),
        result("repo.toolchain.min", "1.74", "medium"),
    ],
}
q = "&".join([f"repo={quote(REPO)}"] + [f"path={quote(p)}" for p in paths])
put(f"https://dotrepo.org/v0/batch/query?{q}", 200, json.dumps(env))

# --- gold for this scenario ---
gold = {
    "repos": {
        REPO: {
            "description": "widget toolkit",
            "license": "Apache-2.0",
            "language": "Rust",
            "homepage": "https://widget.example",
            "archived": "active",
            "build": "cargo build",
            "test": "cargo test",
            "security_contact": "security@widget.example",
            "min_toolchain": "1.74",
        }
    }
}

yaml.safe_dump(gold, open("gold.fixture.yaml", "w"), sort_keys=False)
print("seeded", len(os.listdir(CACHE)), "fixtures + gold.fixture.yaml")
