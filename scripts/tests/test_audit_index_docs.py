import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "audit_index_docs", Path(__file__).resolve().parents[1] / "audit_index_docs.py"
)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)
audit_cross_record_targets = audit.audit_cross_record_targets
audit_docs = audit.audit_docs
identity_supported = audit.identity_supported


def test_identity_signals_use_url_components_and_allow_custom_homepage():
    assert identity_supported("https://docs.astral.sh/uv/guide", "github.com/astral-sh/uv", "")
    assert not identity_supported(
        "https://uvicorn.example/?project=uv", "github.com/astral-sh/uv", ""
    )
    assert not identity_supported(
        "https://trio.readthedocs.io/", "github.com/astral-sh/uv", "https://docs.astral.sh/uv"
    )
    assert identity_supported(
        "https://unrelated.example/manual", "github.com/owner/project", "https://unrelated.example/"
    )
    assert not identity_supported(
        "https://github.com/other/docs",
        "github.com/owner/project",
        "https://github.com/owner/project",
    )
    assert not identity_supported("https://[bad", "github.com/owner/project", "")


def test_every_docs_field_requires_specific_matching_evidence():
    url = "https://project.example/docs"
    document = {
        "docs": {field: url for field in ("root", "getting_started", "api", "architecture")}
    }
    findings = audit_docs(document, "github.com/owner/project", "Imported docs from README.md.")
    assert {finding["field"] for finding in findings} == {
        "docs.root",
        "docs.getting_started",
        "docs.api",
        "docs.architecture",
    }
    assert all("missing-or-mismatched-field-evidence" in finding["signals"] for finding in findings)
    assert all("missing-specific-evidence-note" in finding["signals"] for finding in findings)
    document["docs"] = {"root": url}
    metadata = {
        "valueJson": json.dumps(url),
        "source": "README.md",
        "reason": "Explicit documentation link at README.md:8",
        "method": "extracted",
        "checkedAt": "2026-09-21T00:00:00Z",
    }
    document["record"] = {"generated_at": "2026-09-21T00:00:00Z"}
    document["x"] = {"dotrepo": {"field_evidence": {"docs.root": metadata}}}
    assert (
        audit_docs(
            document, "github.com/owner/project", f"Imported docs.root as `{url}` from README.md:8."
        )
        == []
    )
    metadata["valueJson"] = json.dumps("https://other.example/")
    assert (
        "missing-or-mismatched-field-evidence"
        in audit_docs(document, "github.com/owner/project", "")[0]["signals"]
    )


def test_cross_record_match_is_an_audit_signal_not_a_rejection():
    records = [
        {
            "identity": "github.com/astral-sh/uv",
            "homepageUrl": "https://docs.astral.sh/uv",
            "docsUrls": {"root": "https://trio.readthedocs.io/"},
            "docsAuditFindings": [],
        },
        {
            "identity": "github.com/python-trio/trio",
            "homepageUrl": "https://trio.readthedocs.io",
            "docsUrls": {},
            "docsAuditFindings": [],
        },
    ]
    audit_cross_record_targets(records)
    assert records[0]["docsUrls"]["root"] == "https://trio.readthedocs.io/"
    assert records[0]["docsAuditFindings"][0]["relatedIdentities"] == [
        "github.com/python-trio/trio"
    ]
    assert records[1]["docsAuditFindings"] == []
