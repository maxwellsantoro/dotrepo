import hashlib
import io
import sys
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_task_command_sources as audit  # noqa: E402


def retained_record(root: Path, *, value: str | None = "make all", sha: str = "a" * 40):
    path = root / "repos/github.com/example/project/record.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "[repo]\n"
        + (f'build = "{value}"\n' if value else "")
        + "[x.github]\n"
        + f'head_sha = "{sha}"\n'
        + '[x.dotrepo.field_evidence."repo.build"]\nsource = "Makefile"\n'
    )
    return path


def test_audit_records_actual_case_and_hash_without_mutating_index(tmp_path, monkeypatch):
    path = retained_record(tmp_path / "index")
    original = path.read_bytes()
    body = b"all: setup\n\ttouch built\n"
    requests = []
    imports = []

    def fetch(request, timeout):
        requests.append(request.full_url)
        if request.full_url.endswith("/makefile"):
            return io.BytesIO(body)
        raise HTTPError(request.full_url, 404, "missing", {}, io.BytesIO(b"missing"))

    def reimport(command, **kwargs):
        imports.append(command)
        root = Path(command[2])
        assert (root / "makefile").read_bytes() == body
        (root / "record.toml").write_text('[repo]\nbuild = "make all"\n')

    monkeypatch.setattr(audit, "urlopen", fetch)
    monkeypatch.setattr(audit.subprocess, "run", reimport)
    output = tmp_path / "receipt"
    result = audit.audit_record(path, Path("/test/dotrepo"), output)
    assert "error" not in result
    assert result["sources"][0]["sha256"] == hashlib.sha256(body).hexdigest()
    assert result["fields"][0]["inspectedSource"] == "makefile"
    assert result["fields"][0]["disposition"] == "unchanged"
    assert path.read_bytes() == original
    assert imports[0][0] == "/test/dotrepo"
    assert imports[0][3:6] == ["import", "--mode", "overlay"]
    assert all("a" * 40 in url for url in requests)


def test_audit_requires_pinned_revision(tmp_path, monkeypatch):
    path = retained_record(tmp_path, sha="main")
    monkeypatch.setattr(
        audit, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError())
    )
    result = audit.audit_record(path, Path("/test/dotrepo"), tmp_path / "receipt")
    assert result["error"] == "audit requires a pinned GitHub revision"
