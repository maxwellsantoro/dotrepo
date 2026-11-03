"""Offline metadata versus source-enriched discovery over one frozen candidate set."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import unicodedata
from pathlib import Path

import repodigest_discovery as discovery
from repodigest_acquire import canonical, sha
from repodigest_store import ROOT, Store, connect_writer, ingest

MODES = ("metadata", "repodigest")


def terms(query):
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError("query must be a string of at most 200 characters")
    return list(
        dict.fromkeys(
            w.lower()
            for w in re.findall(r"[^\W_]+", unicodedata.normalize("NFC", query))
            if w.lower() not in discovery.STOP_WORDS
        )
    )[:16]


def build(packet, output):
    """Reuse normal admission; unavailable source profiles keep a labeled metadata entry."""
    output.mkdir(parents=True, exist_ok=False)
    connect_writer(output / "source-store.sqlite").close()
    metadata_raw = (packet / "metadata.json").read_bytes()
    metadata = json.loads(metadata_raw)
    if len(metadata) != 100 or len({m["repository"] for m in metadata}) != 100:
        raise ValueError("expected the frozen 100 unique candidates")
    database = output / "paired.sqlite"
    db = sqlite3.connect(database)
    db.executescript("""
        CREATE TABLE catalog(repository TEXT PRIMARY KEY, digest TEXT NOT NULL, body BLOB NOT NULL);
        CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE VIRTUAL TABLE metadata_search USING fts5(identity,purpose,keywords,passages);
        CREATE VIRTUAL TABLE repodigest_search USING fts5(identity,purpose,keywords,passages);
    """)
    started = time.perf_counter()
    receipts = []
    for item in metadata:
        full = item["repository"].split("/", 1)[1]
        source = packet / "acquisition" / full.replace("/", "__")
        result = {"repository": item["repository"], "hasProfile": False}
        if (source / "snapshot.json").exists():
            try:
                result["admission"] = ingest(
                    source,
                    output / "source-store.sqlite",
                    output / "admissions" / full.replace("/", "__"),
                    ROOT / "target/debug/dotrepo",
                )
                result["hasProfile"] = True
            except (ValueError, OSError, KeyError) as exc:
                result["error"] = str(exc)
        else:
            result["error"] = "bounded-source-acquisition-unavailable"
        body = canonical({**item, "hasProfile": result["hasProfile"]})
        db.execute("INSERT INTO catalog VALUES(?,?,?)", (item["repository"], sha(body), body))
        keywords = " ".join([item.get("name") or "", *item["topics"], *item["languages"]])
        columns = (item["repository"], item.get("description") or "", keywords, "")
        db.execute("INSERT INTO metadata_search VALUES(?,?,?,?)", columns)
        if result["hasProfile"]:
            reader = Store(output / "source-store.sqlite")
            prof = reader.db.execute(
                "SELECT purpose,keywords,passages FROM discovery_profiles WHERE identity=?",
                (item["repository"],),
            ).fetchone()
            reader.close()
            enriched = (columns[0], columns[1] + "\n" + prof[0], keywords + " " + prof[1], prof[2])
        else:
            enriched = columns
        db.execute("INSERT INTO repodigest_search VALUES(?,?,?,?)", enriched)
        receipts.append(result)
    db.execute("INSERT INTO settings VALUES('metadataSha256',?)", (sha(metadata_raw),))
    db.commit()
    db.close()
    report = {
        "repositories": 100,
        "sourceProfiles": sum(r["hasProfile"] for r in receipts),
        "wallSeconds": time.perf_counter() - started,
        "metadataSha256": sha(metadata_raw),
        "receipts": receipts,
        "meaning": "Both indexes contain the same 100 metadata candidates. RepoDigest adds admitted source profile text where available; otherwise results explicitly remain metadata-only. No live GitHub search or consumer model is measured.",
    }
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


class Search:
    def __init__(self, output):
        self.db = sqlite3.connect(
            (output / "paired.sqlite").resolve().as_uri() + "?mode=ro", uri=True
        )
        self.db.execute("PRAGMA query_only=ON")
        self.source = Store(output / "source-store.sqlite")

    def close(self):
        self.source.close()
        self.db.close()

    def metadata(self, repo):
        row = self.db.execute(
            "SELECT digest,body FROM catalog WHERE repository=?", (repo,)
        ).fetchone()
        if not row or not isinstance(row[1], bytes) or sha(row[1]) != row[0]:
            raise ValueError("metadata object integrity failure")
        item = json.loads(row[1])
        if item["repository"] != repo:
            raise ValueError("metadata identity mismatch")
        return item

    def describe(self, repository, *, mode="repodigest"):
        if mode not in MODES:
            raise ValueError("unsupported mode")
        item = self.metadata(repository)
        result = {"metadata": {k: v for k, v in item.items() if k != "hasProfile"}}
        if mode == "repodigest":
            result["discoveryProfile"] = (
                self.source.profile(repository, item["revision"]) if item["hasProfile"] else None
            )
        return result

    def find(self, query, *, mode="repodigest", language=None, limit=10):
        if mode not in MODES or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("supported mode and limit 1..20 required")
        if language is not None and language not in discovery.LANGUAGES:
            raise ValueError("unsupported language")
        words = terms(query)
        if language is not None:
            words = [w for w in words if w != language.lower()]
        result = {
            "repositories": [],
            "mode": mode,
            "ranking": "lexical OR-prefix BM25; no suitability score",
            "meaning": "Discovery leads; claims and derived target identities are not tested capabilities. Coverage is partial. Use describe and retained source passages for verification.",
            "languageFilter": "exact membership in the same retained metadata language list in both arms",
            "moreCandidates": False,
            "refusedCandidates": 0,
        }
        if not words:
            return result
        # The table name is selected only from the closed MODES set.
        table = mode + "_search"
        rows = self.db.execute(
            f"SELECT identity FROM {table} WHERE {table} MATCH ? ORDER BY bm25({table},2,5,3,1),identity LIMIT 101",
            (" OR ".join('"' + w + '"*' for w in words),),
        )
        for n, row in enumerate(rows):
            if n == 100:
                result["moreCandidates"] = True
                break
            try:
                item = self.metadata(row[0])
                if language is not None and language not in item["languages"]:
                    continue
                if mode == "repodigest" and item["hasProfile"]:
                    profile = self.source.profile(item["repository"], item["revision"])
                    if "missingEvidence" in profile:
                        raise ValueError("source profile refused")
                    compact = discovery.compact(profile, profile["profileSha256"], words, {})
                    compact["knowledge"] = "source-profile"
                else:
                    text = " ".join(
                        [
                            item["repository"],
                            item.get("name") or "",
                            item.get("description") or "",
                            *item["topics"],
                            *item["languages"],
                        ]
                    )
                    compact = {
                        "repository": item["repository"],
                        "revision": item["revision"],
                        "recordSha256": item["recordSha256"],
                        "knowledge": "metadata-claim",
                        "purpose": (item.get("description") or "")[:160] or None,
                        "purposeTruncated": len(item.get("description") or "") > 160,
                        "languages": item["languages"][:4],
                        "topics": item["topics"][:6],
                        "relevance": {"matchedTerms": discovery.lexical_matches(words, text)},
                    }
                result["repositories"].append(compact)
                if len(canonical(result)) > discovery.MAX_RESPONSE - 256:
                    result["repositories"].pop()
                    result["moreCandidates"] = True
                    break
                if len(result["repositories"]) == limit:
                    for remaining in rows:
                        try:
                            extra = self.metadata(remaining[0])
                            if language is not None and language not in extra["languages"]:
                                continue
                            if (
                                mode == "repodigest"
                                and extra["hasProfile"]
                                and "missingEvidence"
                                in self.source.profile(extra["repository"], extra["revision"])
                            ):
                                raise ValueError("source profile refused")
                            result["moreCandidates"] = True
                            break
                        except (ValueError, KeyError, TypeError):
                            result["refusedCandidates"] += 1
                    break
            except (ValueError, KeyError, TypeError):
                result["refusedCandidates"] += 1
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "find", "describe"))
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, default="repodigest")
    parser.add_argument("--query", default="")
    parser.add_argument("--language", choices=discovery.LANGUAGES)
    parser.add_argument("--repository")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.operation == "build":
        if not args.packet:
            parser.error("build requires --packet")
        result = build(args.packet, args.index)
        result = {k: v for k, v in result.items() if k != "receipts"}
    else:
        reader = Search(args.index)
        try:
            result = (
                reader.describe(args.repository, mode=args.mode)
                if args.operation == "describe"
                else reader.find(
                    args.query, mode=args.mode, language=args.language, limit=args.limit
                )
            )
        finally:
            reader.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
