"""Experimental compiled RepoDigest store. Admission does work; serving reads records."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import observed_recipe
import repodigest_discovery as discovery
from repodigest_acquire import canonical, identity, sha
from repodigest_demand import plan as inspection_plan

ROOT = Path(__file__).resolve().parents[1]
CONSUMER_PATH = ROOT / "examples/external-consumer/lookup_before_scrape.py"
_spec = importlib.util.spec_from_file_location("repodigest_public_consumer", CONSUMER_PATH)
consumer = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = consumer
_spec.loader.exec_module(consumer)
MAX_RECORD = 32768
MAX_DETAILS = 65536
MAX_FIND_LIMIT = 20
MAX_DESCRIBE_LIMIT = 50
MAX_QUERY_LENGTH = 200


@lru_cache(maxsize=1)
def policy_id():
    return sha(
        canonical(
            {
                "format": "repodigest-compiled-experimental/1",
                "compiler": sha(Path(__file__).read_bytes()),
                "discoveryCompiler": sha(Path(discovery.__file__).read_bytes()),
                "acquisition": sha((ROOT / "scripts/repodigest_acquire.py").read_bytes()),
                "demandAcquisition": sha((ROOT / "scripts/repodigest_demand.py").read_bytes()),
                "retainedSourceReuse": sha((ROOT / "scripts/repodigest_reuse.py").read_bytes()),
                "sourceCache": sha((ROOT / "scripts/repodigest_source_cache.py").read_bytes()),
                "sourceTools": sha((ROOT / "scripts/repodigest_source_tools.py").read_bytes()),
                "cachedTools": sha((ROOT / "scripts/repodigest_cached_tools.py").read_bytes()),
                "sourceConsumer": sha(CONSUMER_PATH.read_bytes()),
                "observedVerifier": sha(Path(observed_recipe.__file__).read_bytes()),
                "observedCache": sha((ROOT / "scripts/repodigest_observed_cache.py").read_bytes()),
            }
        )
    )


def relative(path):
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or "\\" in path
        or any(ord(c) < 32 or ord(c) == 127 for c in path)
        or any(x in {"", ".", ".."} for x in path.split("/"))
    ):
        raise ValueError("unsafe repository path")
    return path


def stamp():
    return datetime.now(timezone.utc).isoformat()


def validate_snapshot(path):
    raw = (path / "snapshot.json").read_bytes()
    snapshot = observed_recipe.decode(raw)
    repo = identity(snapshot["repository"])
    if repo != snapshot["repository"] or not re.fullmatch("[0-9a-f]{40}", snapshot["revision"]):
        raise ValueError("invalid source identity")
    tree_raw = (path / "tree.json").read_bytes()
    tree = observed_recipe.decode(tree_raw)
    commit = observed_recipe.decode((path / "commit.json").read_bytes())
    if (
        sha(tree_raw) != snapshot["treeSha256"]
        or tree.get("truncated")
        or tree["sha"] != snapshot["tree"]
        or commit["sha"] != snapshot["revision"]
        or commit["commit"]["tree"]["sha"] != snapshot["tree"]
        or commit["html_url"].lower() != f"https://{repo}/commit/{snapshot['revision']}"
    ):
        raise ValueError("source frontier mismatch")
    blobs = {e["path"]: e for e in tree["tree"] if e["type"] == "blob"}
    if len(blobs) != sum(e["type"] == "blob" for e in tree["tree"]):
        raise ValueError("duplicate source tree path")
    contents = {}
    for name, binding in snapshot["files"].items():
        relative(name)
        file = path / "files" / name
        if not file.resolve().is_relative_to((path / "files").resolve()) or file.is_symlink():
            raise ValueError("source symlink refused")
        data = file.read_bytes()
        entry = blobs[name]
        import hashlib

        if (
            len(data) > 1048576
            or len(data) != binding["bytes"]
            or sha(data) != binding["sha256"]
            or entry.get("mode") not in {"100644", "100755"}
            or binding["gitBlob"] != entry["sha"]
            or hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            != entry["sha"]
        ):
            raise ValueError("source bytes changed:" + name)
        contents[name] = data.decode("utf-8")
    coverage = snapshot["coverage"]
    if (
        coverage["treeComplete"] is not True
        or coverage["trackedBlobs"] != len(blobs)
        or coverage["inspectedFiles"] != len(contents)
    ):
        raise ValueError("coverage mismatch")
    checked = datetime.fromisoformat(snapshot["checkedAt"])
    if checked.tzinfo is None or checked > datetime.now(timezone.utc):
        raise ValueError("invalid source check time")
    return snapshot, blobs, contents


def components(blobs, contents):
    found = {".": {"path": ".", "ecosystems": [], "manifests": [], "manifestInspected": True}}
    for name in sorted(blobs):
        base = name.rsplit("/", 1)[-1]
        if base not in {"Cargo.toml", "package.json", "pyproject.toml", "go.mod"}:
            continue
        path = name.rsplit("/", 1)[0] if "/" in name else "."
        if path.count("/") > 3:
            continue
        ecosystem = {
            "Cargo.toml": "Rust",
            "package.json": "JavaScript",
            "pyproject.toml": "Python",
            "go.mod": "Go",
        }[base]
        item = found.setdefault(
            path, {"path": path, "ecosystems": [], "manifests": [], "manifestInspected": True}
        )
        if ecosystem not in item["ecosystems"]:
            item["ecosystems"].append(ecosystem)
        item["manifests"].append(name)
        item["manifestInspected"] &= name in contents
    return found


def facts_for(component, contents):
    facts = {}
    prefix = "" if component == "." else component + "/"
    for name in ("package.json", "pyproject.toml", "Cargo.toml"):
        path = prefix + name
        if path not in contents:
            continue
        try:
            value = (
                json.loads(contents[path])
                if name.endswith("json")
                else tomllib.loads(contents[path])
            )
        except (ValueError, tomllib.TOMLDecodeError):
            facts[path] = {"parseState": "unreadable"}
            continue
        if name == "package.json":
            fields = {
                k: value[k]
                for k in (
                    "name",
                    "description",
                    "engines",
                    "packageManager",
                    "scripts",
                    "workspaces",
                )
                if k in value
            }
        elif name == "pyproject.toml":
            project = value.get("project", {})
            fields = {
                k: project[k] for k in ("name", "description", "requires-python") if k in project
            }
            fields["dependencyGroups"] = list(value.get("dependency-groups", {}))
            fields["optionalDependencies"] = list(project.get("optional-dependencies", {}))
            for key in ("tox", "pytest"):
                if key in value.get("tool", {}):
                    fields[key] = value["tool"][key]
        else:
            fields = {
                k: value["package"][k]
                for k in ("name", "rust-version", "edition")
                if k in value.get("package", {})
            }
            if "workspace" in value:
                fields["workspace"] = value["workspace"]
        facts[path] = {
            "sourceSha256": sha(contents[path].encode()),
            "declarations": fields,
            "meaning": "Publisher configuration declarations, not execution success or a complete procedure.",
        }
    return facts


def source_leads(component, snapshot, contents):
    prefix = "" if component == "." else component + "/"
    scored = []
    focus = snapshot.get("demandFocus", {})
    demanded = set(focus.get(component, []))
    if component == ".":
        demanded.update(path for paths in focus.values() for path in paths)
    for path, text in contents.items():
        if (
            component != "."
            and not path.startswith(prefix)
            and "/" in path
            and path not in demanded
        ):
            continue
        if not (
            path.lower().endswith((".md", ".rst"))
            or path.rsplit("/", 1)[-1].lower() in {"makefile", "justfile"}
            or (path in demanded and path.endswith((".sh", ".py")))
        ):
            continue
        lines = text.splitlines()
        hits = [
            n
            for n, line in enumerate(lines)
            if re.search(
                r"\b(test|tests|testing|pytest|tox|uv sync|just test|make test|MSRV)\b", line, re.I
            )
        ]
        if not hits:
            continue
        # Preserve adjacent context and explicit source bounds. Never promote excerpts to commands.
        start = max(0, hits[0] - 5)
        end = start
        used = 0
        for line in lines[start : start + 65]:
            cost = len(line.encode("utf-8")) + 1
            if used + cost > 8192:
                break
            used += cost
            end += 1
        if end == start:
            continue
        scored.append(
            (
                0 if path in demanded else 1 if "contribut" in path.lower() else 2,
                path,
                {
                    "path": path,
                    "sourceSha256": snapshot["files"][path]["sha256"],
                    "startLine": start + 1,
                    "endLine": end,
                    "totalLines": len(lines),
                    "excerpt": "\n".join(lines[start:end]),
                    "meaning": "Partial source passage. Read surrounding/linked material when needed; not qualified instructions.",
                },
            )
        )
    return [entry for _, _, entry in sorted(scored)[:5]]


def export_profiles(snapshot, contents, cli, archive):
    repo = snapshot["repository"]
    host, owner, name = repo.split("/")
    with tempfile.TemporaryDirectory(prefix="repodigest-import-") as temp:
        root = Path(temp)
        index = root / "index"
        stage = index / "repos" / host / owner / name
        stage.mkdir(parents=True)
        for path, text in contents.items():
            dest = stage / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        done = subprocess.run(
            [
                str(cli),
                "--root",
                str(stage),
                "import",
                "--mode",
                "overlay",
                "--source",
                "https://" + repo,
            ],
            capture_output=True,
            timeout=60,
        )
        (archive / "import.log").write_bytes(done.stdout + done.stderr)
        if done.returncode:
            raise ValueError("Rust importer rejected source; see retained log")
        record = stage / "record.toml"
        with record.open("a") as f:
            f.write("\n[x.github]\nhead_sha = " + json.dumps(snapshot["revision"]) + "\n")
        (archive / "record.toml").write_bytes(record.read_bytes())
        body = subprocess.check_output(
            [str(cli), "public", "profile", "--index-root", str(index), host, owner, name],
            timeout=60,
        )
        (archive / "profile.json").write_bytes(body)
        return json.loads(body)


SCHEMA = """
CREATE TABLE IF NOT EXISTS objects(digest TEXT PRIMARY KEY, body BLOB NOT NULL);
CREATE TRIGGER IF NOT EXISTS objects_no_update BEFORE UPDATE ON objects BEGIN SELECT RAISE(ABORT,'immutable object'); END;
CREATE TRIGGER IF NOT EXISTS objects_no_delete BEFORE DELETE ON objects BEGIN SELECT RAISE(ABORT,'immutable object'); END;
CREATE TABLE IF NOT EXISTS source_blobs(digest TEXT PRIMARY KEY, body BLOB NOT NULL);
CREATE TRIGGER IF NOT EXISTS source_blobs_no_update BEFORE UPDATE ON source_blobs BEGIN SELECT RAISE(ABORT,'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS source_blobs_no_delete BEFORE DELETE ON source_blobs BEGIN SELECT RAISE(ABORT,'immutable source'); END;
CREATE TABLE IF NOT EXISTS records(digest TEXT PRIMARY KEY, body BLOB NOT NULL);
CREATE TRIGGER IF NOT EXISTS records_no_update BEFORE UPDATE ON records BEGIN SELECT RAISE(ABORT,'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS records_no_delete BEFORE DELETE ON records BEGIN SELECT RAISE(ABORT,'immutable record'); END;
CREATE TABLE IF NOT EXISTS versions(identity TEXT,revision TEXT,component TEXT,digest TEXT REFERENCES records(digest),PRIMARY KEY(identity,revision,component));
CREATE TABLE IF NOT EXISTS current(identity TEXT PRIMARY KEY,revision TEXT,tree TEXT,checked_at TEXT,snapshot_digest TEXT);
CREATE TABLE IF NOT EXISTS admissions(digest TEXT PRIMARY KEY,body BLOB NOT NULL);
CREATE TRIGGER IF NOT EXISTS admissions_no_update BEFORE UPDATE ON admissions BEGIN SELECT RAISE(ABORT,'immutable admission'); END;
CREATE TRIGGER IF NOT EXISTS admissions_no_delete BEFORE DELETE ON admissions BEGIN SELECT RAISE(ABORT,'immutable admission'); END;
CREATE TABLE IF NOT EXISTS observations(digest TEXT PRIMARY KEY, identity TEXT, component TEXT, revision TEXT, purpose TEXT, policy TEXT, body BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS observations_target ON observations(identity,component,purpose,revision,policy);
CREATE TRIGGER IF NOT EXISTS observations_no_update BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT,'immutable observation'); END;
CREATE TRIGGER IF NOT EXISTS observations_no_delete BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT,'immutable observation'); END;
CREATE VIRTUAL TABLE IF NOT EXISTS discovery USING fts5(identity,description);
"""


def connect_writer(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA + discovery.SCHEMA)
    db.execute("PRAGMA foreign_keys=ON")
    return db


def ingest(snapshot_path, database, archive, cli):
    start = time.monotonic()
    snapshot, blobs, contents = validate_snapshot(snapshot_path)
    from repodigest_source_cache import prepare as prepare_sources, write as write_sources

    source_index, source_bodies = prepare_sources(snapshot, blobs, contents)
    frontier = sha(canonical(snapshot))
    code_policy = policy_id()
    db = connect_writer(database)
    previous = db.execute(
        "SELECT snapshot_digest FROM current WHERE identity=?", (snapshot["repository"],)
    ).fetchone()
    # Same exact source/coverage/check-time and same compiled policy: no parsing/export.
    if previous and previous[0] == frontier:
        row = db.execute(
            "SELECT r.digest,r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.revision=? AND v.component='.'",
            (snapshot["repository"], snapshot["revision"]),
        ).fetchone()
        if row and (not isinstance(row[1], bytes) or sha(row[1]) != row[0]):
            raise ValueError("existing source record corrupt")
        if row and json.loads(row[1])["policySha256"] == code_policy:
            record = json.loads(row[1])
            if (
                record["repository"],
                record["revision"],
                record["component"]["path"],
                record["tree"],
            ) != (snapshot["repository"], snapshot["revision"], ".", snapshot["tree"]):
                raise ValueError("existing source record binding mismatch")
            admission = db.execute(
                "SELECT body FROM admissions WHERE digest=?", (record["admissionSha256"],)
            ).fetchone()
            if (
                not admission
                or not isinstance(admission[0], bytes)
                or sha(admission[0]) != record["admissionSha256"]
            ):
                raise ValueError("existing source admission corrupt")
            if json.loads(admission[0]).get("sourceIndexSha256") != sha(source_index):
                raise ValueError("existing source inventory binding mismatch")
            compiler_matches = admission and json.loads(admission[0]).get("cliSha256") == sha(
                cli.read_bytes()
            )
        else:
            compiler_matches = False
        if compiler_matches:
            discovery_profile, discovery_id = discovery.read(
                db, code_policy, snapshot["repository"], snapshot["revision"], *row
            )
            if json.loads(admission[0]).get("discoveryProfileSha256") != discovery_id:
                raise ValueError("existing discovery admission binding mismatch")
            with db:
                write_sources(db, source_index, source_bodies)
                discovery.write(db, discovery_profile)
            db.close()
            return {
                "state": "unchanged",
                "repository": snapshot["repository"],
                "recordsWritten": 0,
                "sourceCache": "verified against retained snapshot",
                "discoveryCache": "verified; derived search indexes refreshed",
                "wallSeconds": time.monotonic() - start,
            }
    archive.mkdir(parents=True, exist_ok=False)
    profile = export_profiles(snapshot, contents, cli, archive)
    groups = components(blobs, contents)
    discovery_profile, discovery_body = discovery.build(snapshot, blobs, contents)
    discovery_id = sha(discovery_body)
    prior_files = {}
    if previous:
        row = db.execute(
            "SELECT r.body FROM versions v JOIN current c ON c.identity=v.identity AND c.revision=v.revision JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.component='.'",
            (snapshot["repository"],),
        ).fetchone()
        if row:
            previous_record = json.loads(row[0])
            details = db.execute(
                "SELECT body FROM objects WHERE digest=?", (previous_record["detailsSha256"],)
            ).fetchone()
            if (
                not details
                or not isinstance(details[0], bytes)
                or len(details[0]) > MAX_DETAILS
                or sha(details[0]) != previous_record["detailsSha256"]
            ):
                raise ValueError("previous compiled details corrupt")
            prior_files = observed_recipe.decode(details[0])["dependencies"]
    changed = sorted(
        p
        for p in set(prior_files) | set(snapshot["files"])
        if prior_files.get(p) != snapshot["files"].get(p, {}).get("sha256")
    )
    receipt = {
        "repository": snapshot["repository"],
        "revision": snapshot["revision"],
        "tree": snapshot["tree"],
        "snapshotSha256": frontier,
        "policySha256": code_policy,
        "cliSha256": sha(cli.read_bytes()),
        "profileSha256": sha(canonical(profile)),
        "sourceIndexSha256": sha(source_index),
        "discoveryProfileSha256": discovery_id,
        "changedInspectedFiles": changed,
        "checkedAt": snapshot["checkedAt"],
        "meaning": "Static source qualification only; no model calls or upstream code execution.",
    }
    receipt_id = sha(canonical(receipt))
    with db:
        write_sources(db, source_index, source_bodies)
        db.execute("INSERT OR IGNORE INTO objects VALUES(?,?)", (discovery_id, discovery_body))
        discovery.write(db, discovery_profile)
        for component, metadata in groups.items():
            selections = {}
            for purpose in ("build", "test"):
                result = consumer.interpret_http_response(
                    identity=snapshot["repository"], status_code=200, body=json.dumps(profile)
                )
                selection = consumer.select_instruction(
                    result,
                    purpose,
                    request={"scope": "repository", "workingDirectory": "."}
                    if component == "."
                    else {
                        "scope": "component",
                        "component": component,
                        "workingDirectory": component,
                    },
                )
                selections[purpose] = selection
            details = {
                "dependencies": {p: v["sha256"] for p, v in snapshot["files"].items()},
                "sourceLeads": source_leads(component, snapshot, contents),
            }
            details_body = canonical(details)
            if len(details_body) > MAX_DETAILS:
                raise ValueError("compiled details exceed budget")
            details_id = sha(details_body)
            db.execute("INSERT OR IGNORE INTO objects VALUES(?,?)", (details_id, details_body))
            record = {
                "repository": snapshot["repository"],
                "revision": snapshot["revision"],
                "tree": snapshot["tree"],
                "component": metadata,
                "knowledgeClass": "extracted-instruction",
                "policySha256": code_policy,
                "admissionSha256": receipt_id,
                "checkedAt": snapshot["checkedAt"],
                "detailsSha256": details_id,
                "discoveryProfileSha256": discovery_id,
                "coverage": snapshot["coverage"],
                "facts": facts_for(component, contents),
                "selections": selections,
                "inspectionHints": inspection_plan(component, blobs, contents)[:16],
            }
            body = canonical(record)
            if len(body) > MAX_RECORD:
                raise ValueError("compiled record exceeds budget")
            digest = sha(body)
            db.execute("INSERT OR IGNORE INTO records VALUES(?,?)", (digest, body))
            db.execute(
                "INSERT OR REPLACE INTO versions VALUES(?,?,?,?)",
                (snapshot["repository"], snapshot["revision"], component, digest),
            )
        db.execute("INSERT OR IGNORE INTO admissions VALUES(?,?)", (receipt_id, canonical(receipt)))
        db.execute(
            "INSERT OR REPLACE INTO current VALUES(?,?,?,?,?)",
            (
                snapshot["repository"],
                snapshot["revision"],
                snapshot["tree"],
                snapshot["checkedAt"],
                frontier,
            ),
        )
        db.execute("DELETE FROM discovery WHERE identity=?", (snapshot["repository"],))
        description = profile.get("repository", {}).get("description", "")
        db.execute(
            "INSERT INTO discovery(identity,description) VALUES(?,?)",
            (snapshot["repository"], description),
        )
    db.close()
    (archive / "admission.json").write_bytes(canonical(receipt) + b"\n")
    report = {
        "state": "admitted",
        "repository": snapshot["repository"],
        "revision": snapshot["revision"],
        "components": len(groups),
        "recordsWritten": len(groups),
        "changedInspectedFiles": changed,
        "wallSeconds": time.monotonic() - start,
        "policySha256": code_policy,
    }
    (archive / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


class Store:
    """One trusted local store connection. No raw evidence, network, subprocess or model in lookup."""

    def __init__(self, path):
        self.policy = policy_id()  # Bound once per process, never per request.
        self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        self.db.execute("PRAGMA query_only=ON")

    def close(self):
        self.db.close()

    def find(self, query, limit=10, *, language=None, kind=None, interface=None):
        return discovery.find(self, query, limit, language=language, kind=kind, interface=interface)

    def profile(self, repo, revision):
        row = self.db.execute(
            "SELECT r.digest,r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.revision=? AND v.component='.'",
            (repo, revision),
        ).fetchone()
        if not row:
            return {"missingEvidence": ["discovery-re-admission-required"]}
        try:
            profile, digest = discovery.read(self.db, self.policy, repo, revision, *row)
            return {"profileSha256": digest, **profile}
        except (ValueError, TypeError, KeyError) as exc:
            return {"missingEvidence": [str(exc)]}

    def describe(self, repo, offset=0, limit=30):
        repo = identity(repo)
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= MAX_DESCRIBE_LIMIT
        ):
            raise ValueError("invalid page")
        current = self.db.execute(
            "SELECT revision,tree,checked_at FROM current WHERE identity=?", (repo,)
        ).fetchone()
        if not current:
            return {
                "repository": repo,
                "state": "miss",
                "missingEvidence": ["repository-not-indexed"],
            }
        rows = self.db.execute(
            "SELECT component FROM versions WHERE identity=? AND revision=? ORDER BY component LIMIT ? OFFSET ?",
            (repo, current[0], limit + 1, offset),
        ).fetchall()
        return {
            "repository": repo,
            "indexedRevision": current[0],
            "tree": current[1],
            "checkedAt": current[2],
            "discoveryProfile": self.profile(repo, current[0]),
            "components": [r[0] for r in rows[:limit]],
            "nextOffset": offset + limit if len(rows) > limit else None,
        }

    def lookup(
        self,
        repo,
        revision,
        *,
        component=".",
        purpose="test",
        include_leads=False,
        opt_in=False,
        observed_request=None,
    ):
        repo = identity(repo)
        if (
            not isinstance(revision, str)
            or not re.fullmatch("[0-9a-f]{40}", revision)
            or purpose not in {"test", "build"}
        ):
            raise ValueError("exact revision and supported purpose required")
        if component != ".":
            relative(component)
        current = self.db.execute(
            "SELECT revision FROM current WHERE identity=?", (repo,)
        ).fetchone()
        out = {
            "repository": repo,
            "requestedRevision": revision,
            "component": component,
            "purpose": purpose,
            "instruction": None,
            "missingEvidence": [],
            "authorized": "not-granted",
        }
        if not current:
            out["missingEvidence"] = ["repository-not-indexed"]
            return out
        row = self.db.execute(
            "SELECT r.digest,r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.revision=? AND v.component=?",
            (repo, revision, component),
        ).fetchone()
        exact_revision = row is not None
        if row is None:
            row = self.db.execute(
                "SELECT r.digest,r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.revision=? AND v.component=?",
                (repo, current[0], component),
            ).fetchone()
        if row is None:
            out["missingEvidence"] = ["component-not-indexed"]
            return out
        digest, body = row
        if not isinstance(body, bytes) or len(body) > MAX_RECORD or sha(body) != digest:
            out["missingEvidence"] = ["compiled-record-integrity-failure"]
            return out
        record = observed_recipe.decode(body)
        expected_revision = revision if exact_revision else current[0]
        if (
            record["repository"] != repo
            or record["revision"] != expected_revision
            or record["component"]["path"] != component
        ):
            out["missingEvidence"] = ["compiled-record-key-mismatch"]
            return out
        if record["policySha256"] != self.policy:
            out["missingEvidence"] = ["admission-policy-changed-recompile-required"]
            return out
        out.update(
            {
                "recordSha256": digest,
                "indexedRevision": current[0],
                "recordedRevision": record["revision"],
                "coverage": record["coverage"],
                "facts": record["facts"],
                "componentManifestInspected": record["component"]["manifestInspected"],
                "evidenceAdmission": record["admissionSha256"],
                "sourceTree": record["tree"],
                "nextInspection": {
                    "meaning": "Heuristic file hints, not an exhaustive dependency or qualification checklist. Retained files may still require surrounding/linked context; partial passages are identified separately.",
                    "sourceRevision": record["revision"],
                    "files": record.get("inspectionHints", []),
                    "acquisition": "Separate operator follow-up acquisition; lookup performs no fetch or admission.",
                },
            }
        )
        checked = datetime.fromisoformat(record["checkedAt"])
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        if age < 0 or age > 30 * 86400:
            out["missingEvidence"].append("source-assessment-stale-or-future")
        if not exact_revision:
            out["missingEvidence"].append("revision-not-qualified")
        if record["component"]["manifestInspected"] is not True:
            out["missingEvidence"].append("component-manifest-not-inspected")
        selection = record["selections"][purpose]
        out["missingEvidence"] += selection["fallbackReasons"]
        if not out["missingEvidence"]:
            out["instruction"] = {
                "knowledgeClass": "extracted-instruction",
                **selection["instruction"],
                "execution": "unestablished",
                "environmentApplicability": "Not assessed beyond retained prerequisites.",
            }
        if include_leads is True:
            details = self.db.execute(
                "SELECT body FROM objects WHERE digest=?", (record["detailsSha256"],)
            ).fetchone()
            if (
                not details
                or not isinstance(details[0], bytes)
                or len(details[0]) > MAX_DETAILS
                or sha(details[0]) != record["detailsSha256"]
            ):
                out["missingEvidence"].append("compiled-detail-integrity-failure")
                out["instruction"] = None
                return out
            out["sourceLeads"] = observed_recipe.decode(details[0])["sourceLeads"]
        from repodigest_observed_cache import lookup as observed_lookup

        out.update(
            observed_lookup(
                self.db,
                self.policy,
                repo,
                revision,
                component,
                purpose,
                observed_request,
                include_leads=include_leads,
                opt_in=opt_in,
            )
        )
        out["missingEvidence"] = list(dict.fromkeys(out["missingEvidence"]))
        return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    ingest_parser = subs.add_parser("ingest")
    ingest_parser.add_argument("--snapshot", type=Path, required=True)
    ingest_parser.add_argument("--database", type=Path, required=True)
    ingest_parser.add_argument("--archive", type=Path, required=True)
    ingest_parser.add_argument("--cli", type=Path, default=ROOT / "target/debug/dotrepo")
    observed_parser = subs.add_parser("admit-observed")
    for name in ("capsule", "evidence-root", "database", "archive"):
        observed_parser.add_argument("--" + name, type=Path, required=True)
    observed_parser.add_argument("--trusted-capsule-sha256", required=True)
    lookup_parser = subs.add_parser("lookup")
    lookup_parser.add_argument("--database", type=Path, required=True)
    lookup_parser.add_argument("--repository", required=True)
    lookup_parser.add_argument("--revision", required=True)
    lookup_parser.add_argument("--component", default=".")
    lookup_parser.add_argument("--leads", action="store_true")
    args = parser.parse_args()
    if args.action == "ingest":
        result = ingest(args.snapshot, args.database, args.archive, args.cli.resolve())
    elif args.action == "admit-observed":
        from repodigest_observed_cache import admit

        result = admit(
            args.capsule,
            args.evidence_root,
            args.trusted_capsule_sha256,
            args.database,
            args.archive,
        )
    else:
        store = Store(args.database)
        try:
            result = store.lookup(
                args.repository, args.revision, component=args.component, include_leads=args.leads
            )
        finally:
            store.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
