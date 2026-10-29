"""Host-uv checks of actual installed Linux binaries; never execute fixture commands."""

import json
import shlex
import tarfile
import tomllib

from linux_session import COMMIT, HERE, VERSION, command, container, digest, execute, stamp, write

CLI = "/work/install-dotrepo-cli/bin/dotrepo"
assert (HERE / "installation-complete.json").exists()
inspection = json.loads((HERE / "logs/container-inspect/stdout.txt").read_text())[0]
assert not inspection["Mounts"]
assert inspection["HostConfig"]["ReadonlyRootfs"]
assert inspection["HostConfig"]["CapDrop"] == ["ALL"]
assert not inspection["NetworkSettings"]["Networks"]
results = []


def checked(label, argv, *, data=None, success=True):
    result = execute(label, argv, data=data, timeout=30)
    assert (result[0] == 0) == success, (label, result)
    return result


def shell(label, script):
    return checked(label, ["/bin/sh", "-eu", "-c", script])


def imported(label, repo, force=False, success=True):
    return checked(
        label,
        [
            CLI,
            "--root",
            repo,
            "import",
            "--mode",
            "overlay",
            "--source",
            "https://github.com/example/safety-fixture",
            *(["--force"] if force else []),
        ],
        success=success,
    )


def without_nulls(value):
    if isinstance(value, dict):
        return {key: without_nulls(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [without_nulls(item) for item in value]
    return value


with tarfile.open(HERE / "controlled-source.tar") as archive:
    expectations = json.load(
        archive.extractfile("crates/dotrepo-core/tests/fixtures/import/expectations.json")
    )
    manifest = archive.extractfile("examples/native-minimal/.repo").read().decode()
names = {
    path.rsplit("/", 1)[-1]
    for path in json.loads((HERE.parent / "preparation.json").read_text())["controlledSourcePaths"]
    if "/import/" in path and not path.endswith("expectations.json")
}
rows = [row for row in expectations if row["fixture"] in names]
assert {row["fixture"] for row in rows} == names and len(rows) == 25
for row in rows:
    name = row["fixture"]
    repo = f"/work/cases/{name}"
    shell(
        "fixture-copy-" + name,
        f"mkdir -p /work/cases; cp -a /work/source/crates/dotrepo-core/tests/fixtures/import/{name} {repo}",
    )
    imported("fixture-import-" + name, repo)
    record = tomllib.loads(
        checked("fixture-record-" + name, ["cat", repo + "/record.toml"])[1].decode()
    )["repo"]
    assert record.get("build") == row.get("repo_build"), name
    assert record.get("test") == row.get("repo_test"), name
    for field in ("build_candidates", "test_candidates"):
        assert without_nulls(record.get(field, [])) == without_nulls(
            row.get("repo_" + field, [])
        ), name
    assert "build_context" not in record and "test_context" not in record
    results.append(
        {
            "fixture": name,
            "result": "passed",
            "build": record.get("build"),
            "test": record.get("test"),
        }
    )

for name in (
    "readme-escape",
    "readme-contained-link",
    "package-escape",
    "workflow-directory-escape",
    "oversized-readme",
    "directory-readme",
    "fifo-readme",
    "force-symlink",
    "force-hardlink",
):
    base = "/work/boundaries/" + name
    repo = base + "/repo"
    sentinel = base + "/outside"
    setup = f"mkdir -p {repo}; printf '# Fixture\\n\\nOrdinary contained input.\\n' >{repo}/README.md; printf '# External sentinel\\n\\nUnchanged.\\n' >{sentinel}; "
    if name.startswith("readme-"):
        if name == "readme-contained-link":
            sentinel = repo + "/inside.md"
            setup += f"printf '# Inside\\n' >{sentinel}; "
        setup += f"rm {repo}/README.md; ln -s {sentinel} {repo}/README.md"
    elif name == "package-escape":
        setup += f'printf \'%s\' \'{{"scripts":{{"test":"vitest run"}}}}\' >{sentinel}; ln -s {sentinel} {repo}/package.json'
    elif name == "workflow-directory-escape":
        setup += f"mkdir -p {repo}/.github {base}/outside-workflows; printf 'name: Test\\non: [push]\\njobs: {{}}\\n' >{base}/outside-workflows/test.yml; ln -s {base}/outside-workflows {repo}/.github/workflows"
    elif name == "oversized-readme":
        setup += f"truncate -s 2097153 {repo}/README.md"
    elif name in ("directory-readme", "fifo-readme"):
        setup += f"rm {repo}/README.md; {'mkdir' if name == 'directory-readme' else 'mkfifo'} {repo}/README.md"
    else:
        setup += f"ln {'-s ' if name == 'force-symlink' else ''}{sentinel} {repo}/record.toml"
    shell("boundary-setup-" + name, setup)
    before = checked("boundary-before-" + name, ["sha256sum", sentinel])[1].split()[0]
    result = imported(
        "boundary-import-" + name, repo, force=name.startswith("force-"), success=False
    )
    assert checked("boundary-after-" + name, ["sha256sum", sentinel])[1].split()[0] == before
    if not name.startswith("force-"):
        checked("boundary-no-record-" + name, ["test", "!", "-e", repo + "/record.toml"])
    results.append(
        {"fixture": name, "result": "passed", "exitCode": result[0], "sentinelUnchanged": True}
    )

native = 'schema="dotrepo/v0.1"\n[record]\nmode="native"\nstatus="draft"\n[repo]\nname="fixture"\ndescription="Fixture project"\n[compat.github]\ncodeowners="generate"\n'
for name in ("generate-parent", "generate-leaf", "generate-hardlink", "ci-parent", "init-dangling"):
    base = "/work/outputs/" + name
    repo, outside = base + "/checkout", base + "/outside"
    setup = f"mkdir -p {repo} {outside}; printf '%s' {shlex.quote(native)} >{repo}/.repo; printf 'EXTERNAL SENTINEL\\n' >{outside}/CODEOWNERS; "
    if name in ("generate-parent", "ci-parent"):
        setup += f"ln -s {outside} {repo}/.github"
    elif name in ("generate-leaf", "generate-hardlink"):
        setup += f"mkdir {repo}/.github; ln {'-s ' if name == 'generate-leaf' else ''}{outside}/CODEOWNERS {repo}/.github/CODEOWNERS"
    else:
        setup += f"rm {repo}/.repo; ln -s {outside}/missing {repo}/.repo"
    shell("output-setup-" + name, setup)
    before = checked("output-before-" + name, ["sha256sum", outside + "/CODEOWNERS"])[1].split()[0]
    args = (
        ["ci", "init"]
        if name == "ci-parent"
        else ["init"]
        if name == "init-dangling"
        else ["generate"]
    )
    result = checked("output-invoke-" + name, [CLI, "--root", repo, *args], success=False)
    assert result[0] == 1
    assert (
        checked("output-after-" + name, ["sha256sum", outside + "/CODEOWNERS"])[1].split()[0]
        == before
    )
    shell(
        "output-no-write-" + name,
        f"test ! -e {outside}/workflows; test ! -e {outside}/missing; test ! -e {repo}/README.md",
    )
    results.append(
        {"fixture": name, "result": "passed", "exitCode": result[0], "sentinelUnchanged": True}
    )

item = "/work/promotion/index/repos/github.com/example/sentinel"
shell(
    "promotion-setup",
    f"mkdir -p {item}; printf 'sentinel record' >{item}/record.toml; printf 'sentinel evidence' >{item}/evidence.md",
)
before = checked("promotion-before", ["sha256sum", item + "/record.toml", item + "/evidence.md"])[1]
checked(
    "promotion-reject-apply",
    [CLI, "promotion-report", "--index-root", "/work/promotion/index", "--apply"],
    success=False,
)
assert (
    checked("promotion-after", ["sha256sum", item + "/record.toml", item + "/evidence.md"])[1]
    == before
)
results.append({"fixture": "promotion-no-write", "result": "passed"})
assert len(results) == 40
write(
    HERE / "safety-results.json",
    {
        "checkedAt": stamp(),
        "version": VERSION,
        "sourceCommit": COMMIT,
        "results": results,
        "limit": "Controlled fixtures only; no fixture commands executed.",
    },
)

for package, binary in (
    ("dotrepo-cli", "dotrepo"),
    ("dotrepo-cli", "dotrepo-public-query"),
    ("dotrepo-mcp", "dotrepo-mcp"),
    ("dotrepo-lsp", "dotrepo-lsp"),
    ("dotrepo", "dotrepo"),
):
    path = f"/work/install-{package}/bin/{binary}"
    if package not in ("dotrepo-mcp", "dotrepo-lsp"):
        checked(f"help-{package}-{binary}", [path, "--help"])
    checked(f"binary-sha256-{package}-{binary}", ["sha256sum", path])
    header = bytes.fromhex(
        checked(f"elf-{package}-{binary}", ["od", "-An", "-tx1", "-N20", path])[1].decode()
    )
    assert header[:4] == b"\x7fELF" and header[4:6] == b"\x02\x01" and header[18:20] == b"\xb7\x00"
checked(
    "alias-validate",
    [
        "/work/install-dotrepo/bin/dotrepo",
        "--root",
        "/work/source/examples/native-minimal",
        "validate",
    ],
)

root = "/work/source/examples/native-minimal"
messages = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "linux-rc2-control", "version": "0"},
        },
    },
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
]
for number, name, extra in (
    (3, "validate", {}),
    (4, "query", {"path": "repo.name"}),
    (5, "trust", {}),
    (6, "import_preview", {"mode": "native"}),
    (7, "import_write", {"mode": "native"}),
):
    messages.append(
        {
            "jsonrpc": "2.0",
            "id": number,
            "method": "tools/call",
            "params": {"name": "dotrepo." + name, "arguments": {"root": root, **extra}},
        }
    )
payload = b"".join(json.dumps(message).encode() + b"\n" for message in messages)
(HERE / "mcp-requests.jsonl").write_bytes(payload)
raw = checked("mcp-stdio", ["/work/install-dotrepo-mcp/bin/dotrepo-mcp"], data=payload)[1]
responses = {row["id"]: row for row in map(json.loads, raw.splitlines())}
assert len(responses) == 7
assert responses[1]["result"]["serverInfo"]["version"] == VERSION
assert responses[1]["result"]["protocolVersion"] == "2025-11-25"
assert any(tool["name"] == "dotrepo.validate" for tool in responses[2]["result"]["tools"])
assert responses[3]["result"]["structuredContent"]["valid"] is True
assert responses[3]["result"]["structuredContent"]["diagnostics"] == []
assert responses[4]["result"]["structuredContent"]["value"] == "orbit"
assert responses[5]["result"]["structuredContent"]["selection"]["reason"] == "only_matching_record"
assert responses[6]["result"]["structuredContent"]["record"]["status"] == "draft"
assert responses[7]["result"]["isError"] is True
assert "already exists" in responses[7]["result"]["structuredContent"]["error"]

uri = "file://" + root + "/.repo"
lsp = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "processId": None,
            "capabilities": {},
            "clientInfo": {"name": "linux-rc2-control", "version": "0"},
        },
    },
    {"jsonrpc": "2.0", "method": "initialized", "params": {}},
    {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {
            "textDocument": {"uri": uri, "languageId": "toml", "version": 1, "text": manifest}
        },
    },
    {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
    {"jsonrpc": "2.0", "method": "exit", "params": {}},
]
payload = b""
for message in lsp:
    body = json.dumps(message).encode()
    payload += f"Content-Length: {len(body)}\r\n\r\n".encode() + body
(HERE / "lsp-requests.bin").write_bytes(payload)
raw = checked("lsp-stdio", ["/work/install-dotrepo-lsp/bin/dotrepo-lsp"], data=payload)[1]
responses = []
while raw:
    header, raw = raw.split(b"\r\n\r\n", 1)
    length = int(header.split(b":", 1)[1].strip())
    responses.append(json.loads(raw[:length]))
    raw = raw[length:]
initial = next(row for row in responses if row.get("id") == 1)
assert initial["result"]["serverInfo"] == {"name": "dotrepo-lsp", "version": VERSION}
diagnostics = next(
    row for row in responses if row.get("method") == "textDocument/publishDiagnostics"
)
assert diagnostics["params"]["uri"] == uri
assert all(row.get("severity", 1) > 3 for row in diagnostics["params"]["diagnostics"])
assert any(row.get("id") == 2 and row.get("result") is None for row in responses)
write(
    HERE / "controls-complete.json",
    {
        "completedAt": stamp(),
        "version": VERSION,
        "sourceCommit": COMMIT,
        "safetyChecks": len(results),
        "nativeElfArm64Binaries": 5,
        "mcpResponses": 7,
        "lspInitializeDiagnosticsShutdown": "passed",
        "networkDisconnected": True,
        "scriptSha256": digest(__import__("pathlib").Path(__file__)),
    },
)
assert command("cleanup", ["docker", "rm", "--force", "--volumes", container()])[0] == 0
print(
    "40 safety checks, 5 ARM64 ELF checks, 3 CLI help checks, alias validate, MCP and LSP passed; ephemeral container removed."
)
