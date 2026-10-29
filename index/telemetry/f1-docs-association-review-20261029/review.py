"""Independent read-only record, retained-source and publication receipt review."""

import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import tomllib
from urllib.parse import urljoin

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUTHOR = ROOT / "index/telemetry/f1-docs-association-20261029"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = [dict(attrs).get("href"), ""]

    def handle_data(self, text):
        if self.current is not None:
            self.current[1] += text

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append(self.current)
            self.current = None


def changes(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [
            item
            for key in sorted(a.keys() | b.keys())
            for item in changes(a.get(key), b.get(key), f"{path}.{key}".strip("."))
        ]
    return [] if a == b else [path]


def main():
    freeze_counts = {}
    for packet in [AUTHOR, AUTHOR / "publication-assessment-boundary"]:
        freeze = json.loads((packet / "FREEZE.json").read_text())
        for row in freeze["files"]:
            path = packet / row["path"]
            assert path.stat().st_size == row["bytes"] and sha(path) == row["sha256"]
        freeze_counts[packet.name] = len(freeze["files"])
    results = []
    cases = [("realm/SwiftLint", "swiftlint", "root"), ("minio/minio", "minio", "getting_started")]
    for repo, short, key in cases:
        identity = "github.com/" + repo
        before = AUTHOR / "before" / identity
        after = AUTHOR / "after" / identity
        live = ROOT / "index/repos" / identity
        for name in ["record.toml", "evidence.md"]:
            assert (live / name).read_bytes() == (after / name).read_bytes()
        a = tomllib.loads((before / "record.toml").read_text())
        b = tomllib.loads((after / "record.toml").read_text())
        field = "docs." + key
        allowed = {
            "record.status",
            "record.trust.confidence",
            "record.trust.provenance",
            "record.trust.notes",
            field,
        }
        delta = changes(a, b)
        assert all(
            path in allowed or path.startswith("x.dotrepo.field_evidence." + field + ".")
            for path in delta
        ), delta
        assert a["record"]["generated_at"] == b["record"]["generated_at"]
        assert a["record"]["status"] == "verified" and b["record"]["status"] == "imported"
        assert b["record"]["trust"]["confidence"] == "medium"
        assert b["record"]["trust"]["provenance"] == ["imported"]
        assert (
            (after / "evidence.md").read_bytes().startswith((before / "evidence.md").read_bytes())
        )
        assert "withdraws the whole-record verified claim" in (after / "evidence.md").read_text()
        metadata = b["x"]["dotrepo"]["field_evidence"][field]
        assert json.loads(metadata["valueJson"]) == b["docs"][key]
        assert metadata["checkedAt"] != b["record"]["generated_at"]
        request = json.loads((AUTHOR / "requests" / (short + "-readme.json")).read_text())
        raw = base64.b64decode(request["response"]["structuredContent"]["content"])
        source = AUTHOR / "sources" / identity / "README.md"
        assert raw == source.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert blob == request["response"]["structuredContent"]["sha"]
        assert request["args"]["ref"] == metadata["sourceRevision"]
        assert hashlib.sha256(raw).hexdigest() == metadata["sourceSha256"]
        public = json.loads(
            (
                AUTHOR
                / "publication-assessment-boundary/exported-profiles"
                / identity
                / "profile.json"
            ).read_text()
        )
        public_key = "gettingStarted" if key == "getting_started" else key
        assert public["docs"][public_key] == b["docs"][key]
        assert public["record"]["generatedAt"] == b["record"]["generated_at"]
        assert field not in public["fieldEvidence"]
        results.append(
            {
                "identity": identity,
                "field": field,
                "newValue": b["docs"][key],
                "liveRecordSha256": sha(live / "record.toml"),
                "liveEvidenceSha256": sha(live / "evidence.md"),
                "changedSemanticPaths": delta,
                "datesAndUninspectedFactsPreserved": True,
                "oldEvidenceExactPrefix": True,
                "wholeRecordAuthorityWithdrawn": True,
                "exactValueAndSourceBindingsMatch": True,
                "correctedFactPublishedWithoutNewAssessment": True,
            }
        )
    directory = Anchors()
    directory.feed((AUTHOR / "targets/swiftlint-rule-directory.html").read_text())
    nav = [
        link for link in directory.links if link[0] == "index.html" and "SwiftLintCore" in link[1]
    ]
    assert len(nav) >= 2
    assert (
        urljoin("https://realm.github.io/SwiftLint/rule-directory.html", nav[0][0])
        == results[0]["newValue"]
    )
    index = Anchors()
    index.feed((AUTHOR / "targets/swiftlint-documentation-index.html").read_text())
    assert any(link[0] == "https://github.com/realm/SwiftLint" for link in index.links)
    for name in ["swiftlint-rule-directory", "swiftlint-documentation-index"]:
        request = json.loads((AUTHOR / "requests" / (name + ".json")).read_text())
        assert request["status"] == 200 and request["finalUrl"] == request["url"]
        assert sha(AUTHOR / request["bodyPath"]) == request["bodySha256"]
    source_contract = ROOT / "crates/dotrepo-core/src/public/evidence.rs"
    assert (
        source_contract.read_bytes()
        == (AUTHOR / "publication-assessment-boundary/public-evidence.rs.txt").read_bytes()
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "reviewer": "/root/e1_establishment; separate from record author, prior project context disclosed",
                "frozenFilesChecked": freeze_counts,
                "records": results,
                "swiftLintRootNavigation": nav,
                "publicationContractSha256": sha(source_contract),
                "noNetworkCargoUpstreamExecution": True,
                "limits": "Static source/receipt review, not a new exporter invocation or parser-repair qualification. Mutable documentation version parity is unresolved.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
