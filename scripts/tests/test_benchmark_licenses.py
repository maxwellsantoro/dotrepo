from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_benchmark_licenses import check  # noqa: E402


def test_retained_captures_and_exact_revision_notices_keep_their_bindings():
    report = check()
    assert not report["byteErrors"]
    assert report["sourceFiles"] >= 530
    assert report["licenseNoticeFiles"] >= 45
    assert report["redistributionHolds"]
