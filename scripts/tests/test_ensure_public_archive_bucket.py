import subprocess
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

import ensure_public_archive_bucket as provision  # noqa: E402


@pytest.mark.parametrize("exists", [True, False])
def test_create_only_after_successful_exact_name_listing(
    tmp_path: Path, monkeypatch, exists: bool
) -> None:
    calls = []
    present = exists

    def run(command, **kwargs):
        nonlocal present
        calls.append(command)
        assert kwargs["check"] is True
        if command[4] == "create":
            present = True
            assert command[5] == "dotrepo-archive"
            assert "--update-config=false" in command
            return subprocess.CompletedProcess(command, 0, "created", "")
        text = "Listing buckets...\nname: other-archive\ncreation_date: 2026-10-06\n"
        if present:
            text += "name: dotrepo-archive\ncreation_date: 2026-10-06\n"
        return subprocess.CompletedProcess(command, 0, text, "")

    monkeypatch.setattr(provision.subprocess, "run", run)
    assert provision.ensure_bucket("dotrepo-archive", tmp_path) == {
        "bucket": "dotrepo-archive",
        "created": not exists,
    }
    assert sum(command[4] == "create" for command in calls) == int(not exists)


def test_failed_listing_never_becomes_an_empty_account(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def failed(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command, stderr="authentication failed")

    monkeypatch.setattr(provision.subprocess, "run", failed)
    with pytest.raises(subprocess.CalledProcessError):
        provision.ensure_bucket("dotrepo-archive", tmp_path)
    assert len(calls) == 1
    assert calls[0][4] == "list"


def test_listing_format_changes_fail_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        provision.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "unexpected output", ""),
    )
    with pytest.raises(ValueError, match="unsupported output"):
        provision.ensure_bucket("dotrepo-archive", tmp_path)
