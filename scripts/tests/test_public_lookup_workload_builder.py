import importlib.util
import json
from pathlib import Path
from typing import Optional


SCRIPT = Path(__file__).resolve().parents[1] / "build_public_lookup_workload.py"
SPEC = importlib.util.spec_from_file_location("build_public_lookup_workload", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(builder)


def write_export_profile(
    root: Path,
    owner: str,
    repo: str,
    *,
    has_build: bool = False,
    has_test: bool = False,
    has_docs: bool = False,
    has_security: bool = False,
    has_team: bool = False,
    maintainers: Optional[list[str]] = None,
    has_license: bool = False,
    languages: Optional[list[str]] = None,
) -> None:
    repo_dir = root / "v0" / "repos" / "github.com" / owner / repo
    repo_dir.mkdir(parents=True)
    profile = {
        "identity": {
            "host": "github.com",
            "owner": owner,
            "repo": repo,
        },
        "completeness": {
            "hasBuild": has_build,
            "hasTest": has_test,
            "hasDocs": has_docs,
            "hasSecurityContact": has_security,
            "hasOwnershipSignal": has_team or bool(maintainers),
            "hasLicense": has_license,
        },
        "ownership": {
            "maintainers": maintainers or [],
            **({"team": f"@{owner}/{repo}"} if has_team else {}),
            **({"securityContact": "security@example.com"} if has_security else {}),
        },
        "languages": languages or [],
        "topics": [],
    }
    (repo_dir / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")


def write_inventory(root: Path, repos: list[tuple[str, str]]) -> None:
    inventory_dir = root / "v0" / "repos"
    inventory_dir.mkdir(parents=True, exist_ok=True)
    inventory = {
        "apiVersion": "v0",
        "repositoryCount": len(repos),
        "repositories": [
            {
                "identity": {
                    "host": "github.com",
                    "owner": owner,
                    "repo": repo,
                }
            }
            for owner, repo in repos
        ],
    }
    (inventory_dir / "index.json").write_text(json.dumps(inventory, indent=2) + "\n")


def test_build_workload_uses_profile_completeness(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_inventory(public_root, [("example", "beta"), ("example", "alpha")])
    write_export_profile(
        public_root,
        "example",
        "alpha",
        has_build=True,
        has_test=True,
        has_docs=True,
        has_security=True,
        has_team=True,
        has_license=True,
        languages=["Rust"],
    )
    write_export_profile(public_root, "example", "beta")

    workload = builder.build_workload(public_root)

    assert workload["schema"] == "dotrepo-public-lookup-workload/v0"
    assert [task["repository"] for task in workload["tasks"]] == [
        "github.com/example/alpha",
        "github.com/example/beta",
    ]
    assert workload["tasks"][0]["fields"] == [
        "repo.description",
        "repo.homepage",
        "repo.license",
        "repo.build",
        "repo.test",
        "docs.root",
        "owners.security_contact",
        "owners.team",
        "repo.languages",
    ]
    assert workload["tasks"][1]["fields"] == ["repo.description", "repo.homepage"]


def test_build_workload_honors_limit(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_inventory(public_root, [("example", "alpha"), ("example", "beta")])
    write_export_profile(public_root, "example", "alpha")
    write_export_profile(public_root, "example", "beta")

    workload = builder.build_workload(public_root, limit=1)

    assert len(workload["tasks"]) == 1
    assert workload["tasks"][0]["repository"] == "github.com/example/alpha"


def test_build_workload_uses_maintainers_when_team_is_absent(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_inventory(public_root, [("example", "alpha")])
    write_export_profile(
        public_root,
        "example",
        "alpha",
        maintainers=["@example/maintainer"],
    )

    workload = builder.build_workload(public_root)

    assert "owners.maintainers" in workload["tasks"][0]["fields"]
    assert "owners.team" not in workload["tasks"][0]["fields"]
