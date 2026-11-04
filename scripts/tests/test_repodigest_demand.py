"""Pinned follow-up, retained coverage, negative controls and advertised limits."""

import json
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures/repodigest"
sys.path.insert(0, str(ROOT / "scripts"))
import repodigest_store as store  # noqa: E402
from repodigest_acquire import acquire, canonical  # noqa: E402
from repodigest_demand import follow_up, plan  # noqa: E402
from repodigest_service import registry  # noqa: E402

PACKET = FIXTURES / "repodigest-multirepo-service-20261029"
SOURCE = PACKET / "acquisition-001/mitsuhiko__minijinja"
SNAPSHOT = json.loads((SOURCE / "snapshot.json").read_text())
REPO, REV = SNAPSHOT["repository"], SNAPSHOT["revision"]
RETAINED = PACKET / "consumer-004-minijinja-source-only/source-responses/mitsuhiko/minijinja"


class HTTP:
    def __init__(self, *, wrong=False):
        self.events = []
        self.wrong = wrong

    def get(self, url, limit=1048576):
        self.events.append({"url": url})
        if "/commits/" in url:
            return (SOURCE / "commit.json").read_bytes()
        path = url.split(REV + "/", 1)[1]
        raw = (RETAINED / path).read_bytes()
        return b"corrupt" if self.wrong else raw


def test_bounded_follow_up_closes_manifest_and_preserves_old_evidence(tmp_path):
    http = HTTP()
    snapshot, report = follow_up(
        SOURCE, tmp_path / "follow", http, component="minijinja", revision=REV
    )
    assert report["fetchedFiles"] == ["minijinja/Cargo.toml", "scripts/use-msrv-lock.sh"]
    assert len(http.events) == 2 and len(report["reusedFiles"]) == 36
    assert snapshot["checkedAt"] == SNAPSHOT["checkedAt"]
    assert snapshot["files"].items() >= SNAPSHOT["files"].items()
    checked, _, contents = store.validate_snapshot(tmp_path / "follow")
    assert checked == snapshot and "1.70" in contents["minijinja/Cargo.toml"]
    repeat_http = HTTP()
    repeated, repeat = follow_up(
        tmp_path / "follow", tmp_path / "again", repeat_http, component="minijinja", revision=REV
    )
    assert repeat["state"] == "cached" and repeated == snapshot and not repeat_http.events
    refreshed = acquire(
        REPO, tmp_path / "refresh", HTTP(), previous=tmp_path / "follow", revision=REV
    )
    assert refreshed["files"] == snapshot["files"]
    assert refreshed["demandFocus"] == snapshot["demandFocus"]


def test_enrichment_updates_compiled_record_without_promoting_recipe(tmp_path, monkeypatch):
    db = tmp_path / "store.sqlite"
    cli = ROOT / "target/debug/dotrepo"
    store.ingest(SOURCE, db, tmp_path / "before-admission", cli)
    reader = store.Store(db)
    before = reader.lookup(REPO, REV, component="minijinja")
    reader.close()
    assert before["nextInspection"]["files"][0] == {
        "path": "minijinja/Cargo.toml",
        "reason": "component-manifest",
        "inspection": "not-inspected",
    }
    follow_up(SOURCE, tmp_path / "follow", HTTP(), component="minijinja", revision=REV)
    store.ingest(tmp_path / "follow", db, tmp_path / "after-admission", cli)
    reader = store.Store(db)
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda *a: (_ for _ in ()).throw(AssertionError("lookup read raw sources")),
    )
    result = reader.lookup(REPO, REV, component="minijinja", include_leads=True)
    assert result["componentManifestInspected"] is True
    assert result["facts"]["minijinja/Cargo.toml"]["declarations"]["rust-version"] == "1.70"
    assert "component-manifest-not-inspected" not in result["missingEvidence"]
    assert result["instruction"] is None and result["authorized"] == "not-granted"
    assert any(
        p["path"] == "scripts/use-msrv-lock.sh" and "Cargo.lock.msrv" in p["excerpt"]
        for p in result["sourceLeads"]
    )
    assert result["recordSha256"] != before["recordSha256"]
    assert reader.db.execute("SELECT COUNT(*) FROM records").fetchone()[0] > 53
    reader.close()


@pytest.mark.parametrize(
    "component,revision", [("unknown", REV), ("minijinja", "0" * 40), ("../outside", REV)]
)
def test_invalid_demand_does_not_fetch(tmp_path, component, revision):
    http = HTTP()
    with pytest.raises(ValueError):
        follow_up(SOURCE, tmp_path / "follow", http, component=component, revision=revision)
    assert not http.events and not (tmp_path / "follow").exists()


def test_corrupt_follow_up_cannot_be_admitted(tmp_path):
    with pytest.raises(ValueError, match="pinned Git blob"):
        follow_up(
            SOURCE, tmp_path / "follow", HTTP(wrong=True), component="minijinja", revision=REV
        )
    assert not (tmp_path / "follow/snapshot.json").exists()


def test_plan_refuses_unsafe_operator_file_before_network(tmp_path):
    http = HTTP()
    with pytest.raises(ValueError):
        follow_up(
            SOURCE,
            tmp_path / "follow",
            http,
            component="minijinja",
            revision=REV,
            extra_paths=["../outside"],
        )
    assert not http.events
    _, blobs, contents = store.validate_snapshot(SOURCE)
    hints = plan("minijinja", blobs, contents)
    assert any(h["path"] == "scripts/use-msrv-lock.sh" for h in hints)


def test_schema_advertises_runtime_page_and_read_bounds():
    class Stub:
        def find(self):
            pass

        def list(self):
            pass

        def read(self):
            pass

    tools = registry(Stub(), sources=Stub())
    for name, maximum in (
        ("dotrepo.decision.find", 20),
        ("dotrepo.decision.describe", 50),
        ("source.list", 100),
    ):
        value = tools[name][0]["inputSchema"]["properties"]["limit"]
        assert value["minimum"] == 1 and value["maximum"] == maximum
    props = tools["source.list"][0]["inputSchema"]["properties"]
    assert props["offset"]["minimum"] == 0 and props["pattern"]["maxLength"] == 200
    assert "Full-path" in props["pattern"]["description"]
    assert "*typing*" in props["pattern"]["description"]
    read = tools["source.read"][0]["inputSchema"]["properties"]
    assert read["start"]["minimum"] == 1 and "start+119" in read["end"]["description"]
    assert "acquire" not in canonical([tool[0] for tool in tools.values()]).decode()


def test_follow_up_defers_ninth_file_and_rejects_oversized_body(tmp_path):
    raw = b"retained public context\n"
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    source = tmp_path / "empty"
    source.mkdir()
    paths = [f"context/{n}.md" for n in range(9)]
    tree = {
        "sha": "a" * 40,
        "truncated": False,
        "tree": [{"path": path, "type": "blob", "mode": "100644", "sha": blob} for path in paths],
    }
    tree_raw = canonical(tree)
    from repodigest_acquire import sha

    snapshot = {
        "repository": REPO,
        "revision": REV,
        "tree": "a" * 40,
        "treeSha256": sha(tree_raw),
        "checkedAt": SNAPSHOT["checkedAt"],
        "files": {},
        "coverage": {"treeComplete": True, "trackedBlobs": 9, "inspectedFiles": 0},
    }
    (source / "snapshot.json").write_bytes(canonical(snapshot))
    (source / "tree.json").write_bytes(tree_raw)
    (source / "commit.json").write_bytes(
        canonical(
            {
                "sha": REV,
                "commit": {"tree": {"sha": "a" * 40}},
                "html_url": f"https://{REPO}/commit/{REV}",
            }
        )
    )

    class FakeHTTP:
        def __init__(self, body):
            self.events = []
            self.body = body

        def get(self, *args):
            self.events.append({})
            return self.body

    http = FakeHTTP(raw)
    _, report = follow_up(
        source, tmp_path / "follow", http, component=".", revision=REV, extra_paths=paths
    )
    assert len(http.events) == 8 and report["deferredFiles"] == [paths[-1]]
    with pytest.raises(ValueError, match="byte budget"):
        follow_up(
            source,
            tmp_path / "oversized",
            FakeHTTP(b"x" * 262145),
            component=".",
            revision=REV,
            extra_paths=paths,
        )
    assert not (tmp_path / "oversized/snapshot.json").exists()
