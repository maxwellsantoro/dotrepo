"""Discovery relevance, evidence boundaries, scoped filters, refresh and batch serving."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures/repodigest"
sys.path.insert(0, str(ROOT / "scripts"))
import repodigest_discovery as discovery  # noqa: E402
import repodigest_store as store  # noqa: E402
from repodigest_acquire import canonical, sha  # noqa: E402
from repodigest_service import registry  # noqa: E402

STAMP = "2026-10-29T12:00:00+00:00"


def compile_profile(contents, name="parser", revision="a" * 40):
    snapshot = {
        "repository": "github.com/example/" + name,
        "revision": revision,
        "tree": "b" * 40,
        "checkedAt": STAMP,
    }
    return discovery.build(snapshot, {p: {} for p in contents}, contents)


def admit_profile(db, contents, name="parser", revision="a" * 40):
    profile, body = compile_profile(contents, name, revision)
    digest = sha(body)
    repo = profile["repository"]
    root = {
        "repository": repo,
        "revision": revision,
        "tree": profile["tree"],
        "checkedAt": STAMP,
        "component": {"path": "."},
        "policySha256": store.policy_id(),
        "discoveryProfileSha256": digest,
    }
    record = canonical(root)
    with db:
        db.execute("INSERT OR IGNORE INTO objects VALUES(?,?)", (digest, body))
        db.execute("INSERT OR IGNORE INTO records VALUES(?,?)", (sha(record), record))
        db.execute(
            "INSERT OR REPLACE INTO versions VALUES(?,?,?,?)", (repo, revision, ".", sha(record))
        )
        db.execute(
            "INSERT OR REPLACE INTO current VALUES(?,?,?,?,?)",
            (repo, revision, profile["tree"], STAMP, "c" * 64),
        )
        discovery.write(db, profile)
    return profile


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "index.sqlite"
    db = store.connect_writer(path)
    admit_profile(
        db,
        {
            "pyproject.toml": '[project]\nname="parser"\ndescription="Read configuration files in Python"\nkeywords=["configuration", "parser"]\nrequires-python=">=3.10"\ndependencies=[]\n',
            "README.md": "# Parser\n\nA library for parsing configuration files. Offline operation has not been verified.\n",
        },
    )
    admit_profile(
        db,
        {
            "package.json": json.dumps(
                {
                    "name": "network",
                    "description": "Send network requests from a command-line client",
                    "bin": "cli.js",
                }
            )
        },
        "network",
    )
    db.close()
    return path


def test_compact_find_keeps_claims_unknowns_and_scoped_evidence(database, monkeypatch):
    reader = store.Store(database)
    monkeypatch.setattr(Path, "read_bytes", lambda *a: pytest.fail("serving read raw evidence"))
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: pytest.fail("serving launched process")
    )
    result = reader.find("configuration parser compatibility", language="Python")
    assert len(result["repositories"]) == 1
    item = result["repositories"][0]
    assert item["repository"] == "github.com/example/parser"
    assert "compatibility" in item["relevance"]["unmatchedQueryTerms"]
    assert item["languages"] == ["Python"]
    assert item["relevance"]["sourcePaths"][0] == "pyproject.toml"
    assert "execution remain unknown" in result["meaning"]
    assert len(canonical(result)) <= discovery.MAX_RESPONSE
    profile = reader.describe(item["repository"])["discoveryProfile"]
    assert "tested-runtime-compatibility" in profile["unknowns"]
    assert profile["components"][0]["dependencies"]["directDeclared"] == 0
    assert profile["components"][0]["runtimeRequirement"] == ">=3.10"
    assert profile["authorized"] == "not-granted" and not profile["executionEstablished"]
    assert "not been verified" in profile["publisherPassages"][0]["text"]
    assert profile["components"][0]["source"]["sha256"]
    reader.close()


def test_filters_require_same_component_and_unknown_is_not_negative(database):
    db = store.connect_writer(database)
    admit_profile(
        db,
        {
            "pyproject.toml": '[project]\nname="mixed"\ndescription="Configuration tooling"\n',
            "cli/package.json": '{"bin":"cli.js"}',
        },
        "mixed",
    )
    db.close()
    reader = store.Store(database)
    assert reader.find("configuration", language="Python", kind="cli")["repositories"] == []
    result = reader.find("", language="JavaScript", kind="cli", interface="command-line")
    assert {r["repository"] for r in result["repositories"]} == {
        "github.com/example/mixed",
        "github.com/example/network",
    }
    assert "unknown/default interfaces may be excluded" in result["scope"]
    reader.close()


@pytest.mark.parametrize(
    "name,description,query",
    [
        ("foo_bar", "Analysis toolkit", "bar"),
        ("coffee", "Café analysis toolkit", "cafe"),
        ("coffee", "Café analysis toolkit", "Cafe\u0301"),
        ("unicode", "東京 analysis toolkit", "東京"),
    ],
)
def test_fts_unicode_and_separator_matches_are_not_integrity_failures(
    tmp_path, name, description, query
):
    path = tmp_path / "unicode.sqlite"
    db = store.connect_writer(path)
    admit_profile(db, {"package.json": json.dumps({"description": description})}, name)
    db.close()
    reader = store.Store(path)
    result = reader.find(query)
    assert result["refusedCandidates"] == 0
    assert len(result["repositories"]) == 1
    assert not result["repositories"][0]["relevance"]["unmatchedQueryTerms"]
    reader.close()


def test_refresh_removes_old_discovery_and_preserves_historical_objects(database):
    db = store.connect_writer(database)
    old = db.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    admit_profile(
        db,
        {"pyproject.toml": '[project]\nname="parser"\ndescription="Render diagrams"\n'},
        revision="d" * 40,
    )
    assert db.execute("SELECT COUNT(*) FROM objects").fetchone()[0] > old
    db.close()
    reader = store.Store(database)
    assert reader.find("configuration")["repositories"] == []
    assert reader.find("diagrams")["repositories"][0]["revision"] == "d" * 40
    reader.close()


def test_corrupted_profile_and_policy_changes_refuse_without_fallback(database):
    db = store.connect_writer(database)
    db.execute("DROP TRIGGER objects_no_update")
    with db:
        db.execute("UPDATE objects SET body='{}'")
    db.close()
    reader = store.Store(database)
    result = reader.find("configuration")
    assert result["repositories"] == [] and result["refusedCandidates"] == 1
    assert result["missingEvidence"]
    reader.close()


def test_policy_change_and_legacy_database_are_explicit(database, tmp_path):
    reader = store.Store(database)
    reader.policy = "changed"
    assert reader.find("configuration")["missingEvidence"]
    reader.close()
    import sqlite3

    old = tmp_path / "old.sqlite"
    sqlite3.connect(old).close()
    reader = store.Store(old)
    assert reader.find("configuration")["missingEvidence"] == ["discovery-re-admission-required"]
    reader.close()


def test_batch_limits_and_literal_query(database):
    db = store.connect_writer(database)
    for n in range(25):
        admit_profile(
            db,
            {
                "package.json": json.dumps(
                    {
                        "name": f"config-{n}",
                        "description": "Configuration conversion library",
                        "main": "index.js",
                    }
                )
            },
            f"config-{n}",
        )
    db.close()
    reader = store.Store(database)
    result = reader.find('configuration " OR *; DROP TABLE records', limit=20)
    assert 2 < len(result["repositories"]) <= 20
    assert len(canonical(result)) <= discovery.MAX_RESPONSE
    assert result["moreCandidates"]
    assert reader.db.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 27
    reader.close()


@pytest.mark.parametrize(
    "options",
    [
        {"limit": 21},
        {"limit": True},
        {"language": "French"},
        {"kind": "maintained"},
        {"interface": 1},
        {"query": "x" * 201},
    ],
)
def test_disclosed_argument_limits(database, options):
    reader = store.Store(database)
    with pytest.raises(ValueError):
        reader.find(**({"query": "config"} | options))
    schema = registry(reader)["dotrepo.decision.find"][0]["inputSchema"]["properties"]
    assert schema["limit"]["maximum"] == 20
    assert schema["language"]["enum"] == list(discovery.LANGUAGES)
    reader.close()


def test_dynamic_absent_and_malformed_metadata_remain_unknown():
    profile, _ = compile_profile(
        {
            "pyproject.toml": '[project]\nname="x"\ndynamic=["dependencies"]\n',
            "bad/package.json": "[]",
            "Cargo.toml": '[package]\nname="x"\nrust-version={workspace=true}\n[lib]\n',
            "go.mod": "module example.org/x\ngo 1.23\n",
        }
    )
    assert profile["coverage"]["unreadableManifests"] == ["bad/package.json"]
    parts = {p["language"]: p for p in profile["components"]}
    assert parts["Python"]["dependencies"]["directDeclared"] is None
    assert parts["Rust"]["runtimeRequirement"] is None
    assert parts["Rust"]["interfaces"] == ["library"]
    assert parts["Go"]["runtimeRequirement"] == "1.23"
    assert parts["Go"]["dependencies"] is None
    assert not parts["Python"]["kinds"]


def test_actual_admission_and_mcp_batch(tmp_path):
    source = FIXTURES / "repodigest-multirepo-service-20261029/acquisition-001/python-attrs__cattrs"
    db = tmp_path / "real.sqlite"
    store.ingest(source, db, tmp_path / "admission", ROOT / "target/debug/dotrepo")
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "dotrepo.decision.find",
                "arguments": {"query": "serialization", "language": "Python"},
            },
        },
    ]
    done = subprocess.run(
        [
            "uv",
            "run",
            "--offline",
            "--no-sync",
            "python",
            str(ROOT / "scripts/repodigest_service.py"),
            "--database",
            str(db),
        ],
        input="".join(json.dumps(m) + "\n" for m in messages),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert done.returncode == 0, done.stderr
    reply = json.loads(done.stdout.splitlines()[1])
    result = json.loads(reply["result"]["content"][0]["text"])
    item = result["repositories"][0]
    assert item["repository"] == "github.com/python-attrs/cattrs"
    assert "pyproject.toml" in item["relevance"]["sourcePaths"]
    assert item["languages"] == ["Python"]


def test_conventional_cargo_targets_are_derived_from_inspected_bodies():
    profile, _ = compile_profile(
        {
            "crate/Cargo.toml": '[package]\nname="x"\nedition="2021"\n',
            "crate/src/lib.rs": "pub fn hello() {}\n",
            "crate/src/main.rs": "fn main() {}\n",
        }
    )
    part = profile["components"][0]
    assert part["interfaces"] == ["library"]
    assert part["targetEvidence"][0]["value"] == "binary"
    assert part["targetEvidence"][0]["knowledge"] == "derived"
    assert all(e["knowledge"] == "derived" for e in part["interfaceEvidence"])
    assert part["interfaceEvidence"][0]["sources"][1]["path"] == "crate/src/lib.rs"
    assert not profile["executionEstablished"]
    # A tree entry without its inspected file body is insufficient evidence.
    snapshot = {
        "repository": "github.com/example/x",
        "revision": "a" * 40,
        "tree": "b" * 40,
        "checkedAt": STAMP,
    }
    absent, _ = discovery.build(
        snapshot, {"src/lib.rs": {}}, {"Cargo.toml": '[package]\nname="x"\n'}
    )
    assert not absent["components"][0]["interfaces"]


@pytest.mark.parametrize(
    "manifest",
    [
        '[package]\nname="x"\nautolib=false\nautobins=false\n',
        '[package]\nname="x"\n[[example]]\nname="demo"\n',
        '[package]\nname="x"\nedition={workspace=true}\n',
        "[workspace]\nmembers=[]\n",
    ],
)
def test_disabled_legacy_or_unresolved_target_conventions_remain_unknown(manifest):
    profile, _ = compile_profile({"Cargo.toml": manifest, "src/lib.rs": "", "src/main.rs": ""})
    assert not profile["components"][0]["interfaces"]


def test_declared_targets_keep_their_distinct_evidence_label():
    profile, _ = compile_profile(
        {"Cargo.toml": '[package]\nname="x"\n[lib]\npath="other.rs"\n', "src/lib.rs": ""}
    )
    evidence = profile["components"][0]["interfaceEvidence"]
    assert len(evidence) == 1 and evidence[0]["knowledge"] == "declared"
    assert evidence[0]["selector"] == "[lib]"


def test_cargo_binaries_do_not_establish_a_command_line_interface():
    for declaration in ("", '[[bin]]\nname="gui"\n'):
        profile, _ = compile_profile(
            {
                "Cargo.toml": '[package]\nname="gui"\nedition="2021"\n' + declaration,
                "src/main.rs": "fn main() { launch_gui(); }\n",
            }
        )
        part = profile["components"][0]
        assert not part["interfaces"] and "cli" not in part["kinds"]
        assert part["targetEvidence"][0]["value"] == "binary"


def test_unchanged_admission_verifies_profile_and_repairs_search(tmp_path, monkeypatch):
    source = FIXTURES / "repodigest-multirepo-service-20261029/acquisition-001/python-attrs__cattrs"
    path = tmp_path / "real.sqlite"
    cli = ROOT / "target/debug/dotrepo"
    store.ingest(source, path, tmp_path / "admission", cli)
    monkeypatch.setattr(store, "export_profiles", lambda *a: pytest.fail("redundant export"))
    db = store.connect_writer(path)
    with db:
        db.execute("DELETE FROM discovery_profiles")
        db.execute("DELETE FROM discovery_facets")
    result = store.ingest(source, path, tmp_path / "unchanged", cli)
    assert result["state"] == "unchanged" and result["discoveryCache"]
    reader = store.Store(path)
    assert len(reader.find("serialization", language="Python")["repositories"]) == 1
    profile_id = reader.find("serialization")["repositories"][0]["profileSha256"]
    reader.close()
    db.execute("DROP TRIGGER objects_no_update")
    with db:
        db.execute("UPDATE objects SET body=? WHERE digest=?", (b"{}", profile_id))
    db.close()
    with pytest.raises(ValueError, match="discovery profile integrity failure"):
        store.ingest(source, path, tmp_path / "corrupt", cli)
