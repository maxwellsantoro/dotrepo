from pathlib import Path
import hashlib
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_benchmark_licenses import check, check_capture_bytes  # noqa: E402


def test_retained_captures_and_exact_revision_notices_keep_their_bindings():
    report = check()
    assert not report["byteErrors"]
    assert report["sourceFiles"] == 530
    assert report["sourceFilesPresent"] == 422
    assert report["sourceFilesQuarantined"] == 108
    assert report["licenseNoticeFiles"] == 46
    assert not report["redistributionHolds"]
    assert len(report["historicalRedistributionHolds"]) == 3


def test_quarantine_cannot_hide_missing_sources_or_reintroduce_held_bytes(tmp_path):
    body = b"retained source"
    record = {"path": "source.txt", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    captures = [{"files": [record]}]
    assert check_capture_bytes(tmp_path, captures, {})[0] == ["source.txt"]
    assert not check_capture_bytes(tmp_path, captures, {"files": [record]})[0]
    (tmp_path / "source.txt").write_bytes(body)
    assert not check_capture_bytes(tmp_path, captures, {})[0]
    assert check_capture_bytes(tmp_path, captures, {"files": [record]})[0] == [
        "quarantined-source-reintroduced:source.txt"
    ]
    wrong = {**record, "sha256": "0" * 64}
    assert (
        "quarantine-record-mismatch:source.txt"
        in check_capture_bytes(tmp_path, captures, {"files": [wrong]})[0]
    )
