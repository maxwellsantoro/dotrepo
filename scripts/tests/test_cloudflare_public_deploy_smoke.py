import importlib.util
import hashlib
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "smoke_cloudflare_public_deploy.py"
SPEC = importlib.util.spec_from_file_location("smoke_cloudflare_public_deploy", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(smoke)


def write_reviewed_export(root: Path, *, snapshot_digest: str = "abc123") -> None:
    (root / "v0" / "repos").mkdir(parents=True)
    (root / "v0" / "snapshots").mkdir(parents=True)
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
    snapshot_log = {
        "apiVersion": "v0",
        "snapshotCount": 1,
        "entries": [
            {
                "snapshotId": snapshot_digest[:12],
                "snapshotDigest": snapshot_digest,
                "generatedAt": "2026-03-10T18:30:00Z",
                "repositoryCount": 1,
                "fileCount": 1,
            }
        ],
    }
    stats = {
        "apiVersion": "v0",
        "latest": snapshot_log["entries"][0],
        "snapshotCount": 1,
        "history": snapshot_log["entries"],
        "deltas": [],
    }
    (root / "v0" / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (root / "v0" / "files.json").write_text(json.dumps(files, indent=2) + "\n")
    (root / "v0" / "repos" / "index.json").write_text(
        json.dumps(inventory, indent=2) + "\n"
    )
    (root / "v0" / "snapshots" / "log.json").write_text(
        json.dumps(snapshot_log, indent=2) + "\n"
    )
    (root / "v0" / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")


def test_load_reviewed_public_state_reads_deploy_coherence_inputs(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_reviewed_export(public_root)

    reviewed = smoke.load_reviewed_public_state(public_root)

    assert reviewed["meta"]["snapshotDigest"] == "abc123"
    assert reviewed["files"]["freshness"]["snapshotDigest"] == "abc123"
    assert reviewed["inventory"]["repositoryCount"] == 1
    assert reviewed["log"]["entries"][0]["snapshotDigest"] == "abc123"
    assert reviewed["stats"]["latest"]["snapshotDigest"] == "abc123"


def test_deploy_coherence_mismatches_reports_exact_live_drift(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_reviewed_export(public_root)
    reviewed = smoke.load_reviewed_public_state(public_root)
    live = {
        "meta": {**reviewed["meta"], "snapshotDigest": "old"},
        "files": reviewed["files"],
        "inventory": {**reviewed["inventory"], "repositoryCount": 0},
        "log": reviewed["log"],
        "stats": {**reviewed["stats"], "snapshotCount": 0},
    }

    assert smoke.deploy_coherence_mismatches(reviewed, live) == [
        "v0/meta.json",
        "v0/repos/index.json",
        "v0/stats.json",
    ]


def test_deploy_coherence_mismatches_passes_for_reviewed_export(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_reviewed_export(public_root)
    reviewed = smoke.load_reviewed_public_state(public_root)

    assert smoke.deploy_coherence_mismatches(reviewed, reviewed) == []


def manifest_entry(path: str, body: bytes) -> dict:
    return {
        "path": path,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def test_select_manifest_coherence_entries_prioritizes_public_contract_paths() -> None:
    files = {
        "files": [
            manifest_entry("query-input/github.com/example/orbit.json", b"private"),
            manifest_entry("v0/repos/github.com/example/orbit/profile.json", b"profile"),
            manifest_entry("v0/repos/index.json", b"inventory"),
            manifest_entry("v0/meta.json", b"meta"),
            manifest_entry("v0/files.json", b"files"),
            manifest_entry("v0/repos/github.com/example/orbit/trust.json", b"trust"),
            manifest_entry("v0/repos/github.com/example/other/profile.json", b"other"),
        ]
    }
    identity = {"host": "github.com", "owner": "example", "repo": "orbit"}

    selected = smoke.select_manifest_coherence_entries(files, identity, 5)

    assert [entry["path"] for entry in selected] == [
        "v0/meta.json",
        "v0/files.json",
        "v0/repos/index.json",
        "v0/repos/github.com/example/orbit/profile.json",
        "v0/repos/github.com/example/orbit/trust.json",
    ]


def test_select_manifest_coherence_entries_spreads_remaining_public_files() -> None:
    files = {
        "files": [
            manifest_entry("v0/meta.json", b"meta"),
            manifest_entry("v0/files.json", b"files"),
            manifest_entry("v0/repos/index.json", b"inventory"),
            manifest_entry("query-input/github.com/example/orbit.json", b"private"),
            manifest_entry("v0/repos/github.com/example/one/profile.json", b"one"),
            manifest_entry("v0/repos/github.com/example/two/profile.json", b"two"),
            manifest_entry("v0/repos/github.com/example/three/profile.json", b"three"),
        ]
    }
    identity = {"host": "github.com", "owner": "example", "repo": "missing"}

    selected = smoke.select_manifest_coherence_entries(files, identity, 5)

    assert [entry["path"] for entry in selected] == [
        "v0/meta.json",
        "v0/files.json",
        "v0/repos/index.json",
        "v0/repos/github.com/example/one/profile.json",
        "v0/repos/github.com/example/two/profile.json",
    ]


def test_live_manifest_entry_mismatches_reports_hash_and_size_drift(
    monkeypatch,
) -> None:
    bodies = {
        "https://example.test/v0/meta.json?_smoke=cache": b"meta",
        "https://example.test/v0/files.json?_smoke=cache": b"wrong",
    }

    def fake_get_bytes(url: str) -> bytes:
        return bodies[url]

    monkeypatch.setattr(smoke, "http_get_bytes", fake_get_bytes)
    entries = [
        manifest_entry("v0/meta.json", b"meta"),
        manifest_entry("v0/files.json", b"files"),
    ]

    assert smoke.live_manifest_entry_mismatches(
        "https://example.test", "", entries, "cache"
    ) == ["v0/files.json"]
