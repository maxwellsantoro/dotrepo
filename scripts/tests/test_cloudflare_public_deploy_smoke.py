import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "smoke_cloudflare_public_deploy.py"
SPEC = importlib.util.spec_from_file_location("smoke_cloudflare_public_deploy", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(smoke)


def write_reviewed_export(root: Path, *, snapshot_digest: str = "abc123") -> None:
    (root / "v0" / "repos").mkdir(parents=True)
    meta = {
        "apiVersion": "v0",
        "generatedAt": "2026-03-10T18:30:00Z",
        "snapshotDigest": snapshot_digest,
        "staleAfter": "2026-03-11T18:30:00Z",
    }
    files = {
        "apiVersion": "v0",
        "freshness": {
            "generatedAt": "2026-03-10T18:30:00Z",
            "snapshotDigest": snapshot_digest,
            "staleAfter": "2026-03-11T18:30:00Z",
        },
        "fileCount": 1,
        "files": [{"path": "v0/meta.json", "bytes": 100, "sha256": "aaa"}],
    }
    inventory = {
        "apiVersion": "v0",
        "freshness": files["freshness"],
        "repositoryCount": 1,
        "repositories": [
            {
                "identity": {
                    "host": "github.com",
                    "owner": "example",
                    "repo": "orbit",
                    "source": "https://github.com/example/orbit",
                },
                "links": {
                    "queryTemplate": "/v0/repos/github.com/example/orbit/query?path={dot_path}"
                },
            }
        ],
    }
    (root / "v0" / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (root / "v0" / "files.json").write_text(json.dumps(files, indent=2) + "\n")
    (root / "v0" / "repos" / "index.json").write_text(
        json.dumps(inventory, indent=2) + "\n"
    )


def test_load_reviewed_public_state_reads_deploy_coherence_inputs(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_reviewed_export(public_root)

    reviewed = smoke.load_reviewed_public_state(public_root)

    assert reviewed["meta"]["snapshotDigest"] == "abc123"
    assert reviewed["files"]["freshness"]["snapshotDigest"] == "abc123"
    assert reviewed["inventory"]["repositoryCount"] == 1


def test_deploy_coherence_mismatches_reports_exact_live_drift(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_reviewed_export(public_root)
    reviewed = smoke.load_reviewed_public_state(public_root)
    live = {
        "meta": {**reviewed["meta"], "snapshotDigest": "old"},
        "files": reviewed["files"],
        "inventory": {**reviewed["inventory"], "repositoryCount": 0},
    }

    assert smoke.deploy_coherence_mismatches(reviewed, live) == [
        "v0/meta.json",
        "v0/repos/index.json",
    ]


def test_deploy_coherence_mismatches_passes_for_reviewed_export(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_reviewed_export(public_root)
    reviewed = smoke.load_reviewed_public_state(public_root)

    assert smoke.deploy_coherence_mismatches(reviewed, reviewed) == []

