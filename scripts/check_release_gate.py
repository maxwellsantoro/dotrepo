#!/usr/bin/env python3

import argparse
import html
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_BASE_PATH = "/"


def rfc3339_now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rfc3339_plus_hours(value: str, hours: int) -> str:
    timestamp = parse_rfc3339_utc(value, field="generatedAt") + timedelta(hours=hours)
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_rfc3339_utc(value: str, *, field: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"{field} must be a valid RFC3339 timestamp, got: {value}") from exc
    if timestamp.tzinfo is None:
        raise SystemExit(f"{field} must include a timezone offset, got: {value}")
    return timestamp.astimezone(timezone.utc)


def parse_args() -> argparse.Namespace:
    default_generated_at = rfc3339_now_utc()
    default_stale_after = rfc3339_plus_hours(default_generated_at, 24)
    parser = argparse.ArgumentParser(
        description="Run the release-surface gate for dotrepo."
    )
    parser.add_argument(
        "--output-root",
        default="release-gate",
        help="Directory where generated gate artifacts will be written (default: release-gate)",
    )
    parser.add_argument(
        "--base-path",
        default=DEFAULT_BASE_PATH,
        help=f"Hosted base path used for public export links (default: {DEFAULT_BASE_PATH})",
    )
    parser.add_argument(
        "--generated-at",
        default=default_generated_at,
        help=f"generatedAt timestamp for the public export (default: {default_generated_at})",
    )
    parser.add_argument(
        "--stale-after",
        default=default_stale_after,
        help=f"staleAfter timestamp for the public export (default: {default_stale_after})",
    )
    parser.add_argument(
        "--skip-vsix",
        action="store_true",
        help="Skip npm install and VSIX packaging",
    )
    parser.add_argument(
        "--skip-release-bundle",
        action="store_true",
        help="Skip release-binary packaging and install-smoke checks",
    )
    return parser.parse_args()


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"+ {shlex.join(cmd)}", flush=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    subprocess.run(cmd, cwd=cwd, check=True, env=merged_env)


def capture(cmd: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def host_target(repo_root: Path) -> str:
    rustc_info = capture(["rustc", "-vV"], cwd=repo_root)
    for line in rustc_info.splitlines():
        if line.startswith("host: "):
            return line.removeprefix("host: ").strip()
    raise SystemExit("could not detect host target from rustc -vV")


def workspace_version(repo_root: Path) -> str:
    with (repo_root / "Cargo.toml").open("rb") as handle:
        document = tomllib.load(handle)
    return document["workspace"]["package"]["version"]


def extension_version(repo_root: Path) -> str:
    package_json = repo_root / "editors" / "vscode" / "package.json"
    data = json.loads(package_json.read_text())
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit(f"missing VS Code extension version in {package_json}")
    return version


def ensure_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"expected file was not created: {path}")


def expect_single(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        rendered = ", ".join(str(path) for path in paths) or "<none>"
        raise SystemExit(f"expected exactly one {description}, found {rendered}")
    return paths[0]


def expected_homepage_snapshot_state(meta: dict, inventory: dict) -> dict:
    return {
        "apiVersion": meta.get("apiVersion"),
        "generatedAt": meta.get("generatedAt"),
        "snapshotDigest": meta.get("snapshotDigest"),
        "staleAfter": meta.get("staleAfter"),
        "repositoryCount": inventory.get("repositoryCount"),
    }


def extract_homepage_snapshot_state(document: str, source: str) -> dict:
    match = re.search(
        r'<script id="dotrepo-homepage-snapshot" type="application/json">(.+?)</script>',
        document,
        re.DOTALL,
    )
    if match is None:
        raise SystemExit(f"homepage snapshot state marker missing from {source}")
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"homepage snapshot state is invalid JSON in {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"homepage snapshot state is malformed in {source}: {payload!r}")
    return payload


def verify_homepage_snapshot_state(document: str, source: str, meta: dict, inventory: dict) -> None:
    expected = expected_homepage_snapshot_state(meta, inventory)
    actual = extract_homepage_snapshot_state(document, source)
    if actual != expected:
        raise SystemExit(
            f"homepage snapshot state mismatch in {source}: expected {expected}, got {actual}"
        )


def expected_freshness(meta: dict) -> dict:
    return {
        "generatedAt": meta.get("generatedAt"),
        "snapshotDigest": meta.get("snapshotDigest"),
        "staleAfter": meta.get("staleAfter"),
    }


def verify_freshness(payload: dict, meta: dict, source: str) -> None:
    freshness = payload.get("freshness")
    expected = expected_freshness(meta)
    if freshness != expected:
        raise SystemExit(
            f"freshness mismatch in {source}: expected {expected}, got {freshness}"
        )


def verify_inline_javascript_syntax(document: str, source: str) -> None:
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", document, re.IGNORECASE | re.DOTALL)
    for index, (attrs, body) in enumerate(scripts, start=1):
        if re.search(r'type\s*=\s*["\']application/json["\']', attrs, re.IGNORECASE):
            continue
        script_body = body.strip()
        if script_body == "":
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=True) as handle:
            handle.write(script_body)
            handle.flush()
            result = subprocess.run(
                ["node", "--check", handle.name],
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown parser error"
            raise SystemExit(
                f"inline script #{index} in {source} has invalid JavaScript syntax: {stderr}"
            )


def verify_public_meta(public_dir: Path, expected_base_path: str) -> None:
    meta_path = public_dir / "v0" / "meta.json"
    inventory_path = public_dir / "v0" / "repos" / "index.json"
    homepage_path = public_dir / "index.html"
    docs_path = public_dir / "docs" / "index.html"
    ensure_file(meta_path)
    ensure_file(inventory_path)
    ensure_file(homepage_path)
    ensure_file(docs_path)
    ensure_file(public_dir / ".nojekyll")

    meta = json.loads(meta_path.read_text())
    if not isinstance(meta.get("apiVersion"), str) or not meta["apiVersion"]:
        raise SystemExit(f"public export metadata is missing apiVersion: {meta_path}")
    if not isinstance(meta.get("snapshotDigest"), str) or not meta["snapshotDigest"]:
        raise SystemExit(f"public export metadata is missing snapshotDigest: {meta_path}")
    stale_after = meta.get("staleAfter")
    if not isinstance(stale_after, str) or not stale_after:
        raise SystemExit(f"public export metadata is missing staleAfter: {meta_path}")
    stale_after_utc = parse_rfc3339_utc(stale_after, field="staleAfter")
    if stale_after_utc <= datetime.now(timezone.utc):
        raise SystemExit(
            f"public export metadata staleAfter is already in the past: {meta_path} ({stale_after})"
        )

    inventory = json.loads(inventory_path.read_text())
    repositories = inventory.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise SystemExit(f"public export inventory is empty: {inventory_path}")
    homepage_document = homepage_path.read_text()
    verify_homepage_snapshot_state(homepage_document, str(homepage_path), meta, inventory)
    verify_inline_javascript_syntax(homepage_document, str(homepage_path))
    docs_document = docs_path.read_text()
    verify_inline_javascript_syntax(docs_document, str(docs_path))

    normalized_base = "/" if expected_base_path == "/" else expected_base_path.rstrip("/")
    docs_href = f'{normalized_base}/docs/' if normalized_base != "/" else "/docs/"
    if f'href="{docs_href}"' not in homepage_document:
        raise SystemExit(f"homepage does not link to first-party docs path {docs_href}")

    for repo in repositories:
        identity = repo.get("identity")
        links = repo.get("links")
        if not isinstance(identity, dict):
            raise SystemExit(f"public export inventory entry is missing identity: {repo}")
        if not isinstance(links, dict):
            raise SystemExit(f"public export inventory entry is missing links: {repo}")
        host = identity.get("host")
        owner = identity.get("owner")
        name = identity.get("repo")
        if not all(isinstance(value, str) and value for value in (host, owner, name)):
            raise SystemExit(f"public export inventory entry identity is malformed: {repo}")
        summary_link = links.get("self")
        trust_link = links.get("trust")
        query_template = links.get("queryTemplate")
        if not isinstance(summary_link, str) or not summary_link.startswith(normalized_base):
            raise SystemExit(f"summary link does not honor base path {normalized_base}: {summary_link}")
        if not isinstance(trust_link, str) or not trust_link.startswith(normalized_base):
            raise SystemExit(f"trust link does not honor base path {normalized_base}: {trust_link}")
        if not summary_link.endswith("/index.json"):
            raise SystemExit(f"summary link should point at the exported index.json file: {summary_link}")
        if not trust_link.endswith("/trust.json"):
            raise SystemExit(f"trust link should point at the exported trust.json file: {trust_link}")
        if not isinstance(query_template, str) or not query_template.startswith(normalized_base):
            raise SystemExit(
                f"query template does not honor base path {normalized_base}: {query_template}"
            )
        for link in (summary_link, trust_link):
            relative = link.removeprefix(normalized_base).lstrip("/")
            ensure_file(public_dir / relative)
            payload = json.loads((public_dir / relative).read_text())
            verify_freshness(payload, meta, str(public_dir / relative))
        query_input_path = public_dir / "query-input" / host / owner / f"{name}.json"
        ensure_file(query_input_path)
        verify_freshness(json.loads(query_input_path.read_text()), meta, str(query_input_path))


def verify_tar_contains_prefix(archive_path: Path, prefix: str) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
    if not any(name.startswith(prefix) for name in names):
        raise SystemExit(f"{archive_path} does not contain expected root prefix {prefix}")


def unused_addr() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
    return f"{host}:{port}"


def http_get_text(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()
    except urllib.error.URLError:
        return 0, ""


def normalize_base_path(base_path: str) -> str:
    if base_path == "/":
        return ""
    return base_path.rstrip("/")


def smoke_test_release_bundle(
    archive_path: Path,
    version: str,
    target: str,
    repo_root: Path,
    public_dir: Path,
    base_path: str,
    generated_at: str,
    stale_after: str,
) -> None:
    """Extract the release tarball and run the shipped binaries."""
    with tempfile.TemporaryDirectory(prefix="dotrepo-smoke-") as tmp:
        extract_dir = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(extract_dir)

        bin_dir = extract_dir / f"dotrepo-{version}-{target}" / "bin"
        if not bin_dir.is_dir():
            raise SystemExit(f"extracted bundle missing bin/ directory: {bin_dir}")

        for binary in ["dotrepo", "dotrepo-public-query", "dotrepo-lsp", "dotrepo-mcp"]:
            binary_path = bin_dir / binary
            if not binary_path.is_file():
                raise SystemExit(f"extracted bundle missing binary: {binary_path}")

            print(f"  smoke: {binary} --help", flush=True)
            result = subprocess.run(
                [str(binary_path), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise SystemExit(
                    f"{binary} --help failed (exit {result.returncode}): {result.stderr}"
                )

        example_root = repo_root / "examples" / "native-minimal"
        if example_root.is_dir():
            dotrepo_bin = str(bin_dir / "dotrepo")
            print("  smoke: dotrepo validate (from release binary)", flush=True)
            result = subprocess.run(
                [dotrepo_bin, "--root", str(example_root), "validate"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise SystemExit(
                    f"dotrepo validate failed (exit {result.returncode}): {result.stderr}"
                )

        server_addr = unused_addr()
        query_bin = str(bin_dir / "dotrepo-public-query")
        print("  smoke: dotrepo-public-query serves same-origin public tree", flush=True)
        server = subprocess.Popen(
            [
                query_bin,
                "--index-root",
                str(repo_root / "index"),
                "--public-root",
                str(public_dir),
                "--bind",
                server_addr,
                "--base-path",
                base_path,
                "--generated-at",
                generated_at,
                "--stale-after",
                stale_after,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.time() + 5
            healthz_url = f"http://{server_addr}/healthz"
            while time.time() < deadline:
                if server.poll() is not None:
                    stderr = server.stderr.read() if server.stderr else ""
                    raise SystemExit(
                        f"dotrepo-public-query exited early during smoke test: {stderr}"
                    )
                status, body = http_get_text(healthz_url)
                if status == 200 and body == "ok":
                    break
                time.sleep(0.05)
            else:
                raise SystemExit("dotrepo-public-query did not become ready during smoke test")

            base = normalize_base_path(base_path)
            inventory_url = f"http://{server_addr}{base}/v0/repos/index.json"
            status, body = http_get_text(inventory_url)
            if status != 200:
                raise SystemExit(
                    f"same-origin inventory smoke failed ({status}) for {inventory_url}: {body}"
                )
            inventory = json.loads(body)
            repositories = inventory.get("repositories")
            if not isinstance(repositories, list) or not repositories:
                raise SystemExit("same-origin inventory smoke found no repositories")
            meta_url = f"http://{server_addr}{base}/v0/meta.json"
            status, body = http_get_text(meta_url)
            if status != 200:
                raise SystemExit(
                    f"same-origin meta smoke failed ({status}) for {meta_url}: {body}"
                )
            meta = json.loads(body)
            homepage_url = f"http://{server_addr}{base or '/'}"
            status, body = http_get_text(homepage_url)
            if status != 200:
                raise SystemExit(
                    f"same-origin homepage smoke failed ({status}) for {homepage_url}: {body}"
                )
            verify_homepage_snapshot_state(body, homepage_url, meta, inventory)
            docs_url = f"http://{server_addr}{base}/docs/"
            status, body = http_get_text(docs_url)
            if status != 200:
                raise SystemExit(
                    f"same-origin docs smoke failed ({status}) for {docs_url}: {body}"
                )
            first_repo = repositories[0]
            summary_url = f"http://{server_addr}{first_repo['links']['self']}"
            status, body = http_get_text(summary_url)
            if status != 200:
                raise SystemExit(
                    f"same-origin summary smoke failed ({status}) for {summary_url}: {body}"
                )
            verify_freshness(json.loads(body), meta, summary_url)
            trust_url = f"http://{server_addr}{first_repo['links']['trust']}"
            status, body = http_get_text(trust_url)
            if status != 200:
                raise SystemExit(
                    f"same-origin trust smoke failed ({status}) for {trust_url}: {body}"
                )
            verify_freshness(json.loads(body), meta, trust_url)
            query_template = repositories[0]["links"]["queryTemplate"]
            if not isinstance(query_template, str):
                raise SystemExit("same-origin inventory smoke found no queryTemplate")
            query_url = f"http://{server_addr}{query_template.replace('{dot_path}', 'repo.description')}"
            status, body = http_get_text(query_url)
            if status != 200:
                raise SystemExit(
                    f"same-origin queryTemplate smoke failed ({status}) for {query_url}: {body}"
                )
            query_response = json.loads(body)
            if query_response.get("path") != "repo.description":
                raise SystemExit("same-origin queryTemplate smoke returned unexpected path")
            links = query_response.get("links", {})
            self_link = links.get("self")
            if not isinstance(self_link, str) or not self_link.startswith(base):
                raise SystemExit(
                    f"same-origin queryTemplate smoke returned unexpected self link: {self_link}"
                )
        finally:
            server.kill()
            server.wait(timeout=5)


def smoke_test_cloudflare_worker(worker_dir: Path, base_path: str) -> None:
    server_addr = unused_addr()
    host, port = server_addr.split(":")
    print("  smoke: Cloudflare Worker serves same-origin public tree", flush=True)
    server = subprocess.Popen(
        [
            "npx",
            "wrangler",
            "dev",
            "--config",
            "wrangler.jsonc",
            "--ip",
            host,
            "--port",
            port,
        ],
        cwd=worker_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 20
        healthz_url = f"http://{server_addr}/healthz"
        while time.time() < deadline:
            if server.poll() is not None:
                stderr = server.stderr.read() if server.stderr else ""
                raise SystemExit(
                    f"Cloudflare Worker exited early during smoke test: {stderr}"
                )
            status, body = http_get_text(healthz_url)
            if status == 200 and body == "ok":
                break
            time.sleep(0.1)
        else:
            raise SystemExit("Cloudflare Worker did not become ready during smoke test")

        base = normalize_base_path(base_path)
        inventory_url = f"http://{server_addr}{base}/v0/repos/index.json"
        status, body = http_get_text(inventory_url)
        if status != 200:
            raise SystemExit(
                f"Cloudflare Worker inventory smoke failed ({status}) for {inventory_url}: {body}"
            )
        inventory = json.loads(body)
        repositories = inventory.get("repositories")
        if not isinstance(repositories, list) or not repositories:
            raise SystemExit("Cloudflare Worker inventory smoke found no repositories")
        meta_url = f"http://{server_addr}{base}/v0/meta.json"
        status, body = http_get_text(meta_url)
        if status != 200:
            raise SystemExit(
                f"Cloudflare Worker meta smoke failed ({status}) for {meta_url}: {body}"
            )
        meta = json.loads(body)
        homepage_url = f"http://{server_addr}{base or '/'}"
        status, body = http_get_text(homepage_url)
        if status != 200:
            raise SystemExit(
                f"Cloudflare Worker homepage smoke failed ({status}) for {homepage_url}: {body}"
            )
        verify_homepage_snapshot_state(body, homepage_url, meta, inventory)
        docs_url = f"http://{server_addr}{base}/docs/"
        status, body = http_get_text(docs_url)
        if status != 200:
            raise SystemExit(
                f"Cloudflare Worker docs smoke failed ({status}) for {docs_url}: {body}"
            )
        first_repo = repositories[0]
        summary_url = f"http://{server_addr}{first_repo['links']['self']}"
        status, body = http_get_text(summary_url)
        if status != 200:
            raise SystemExit(
                f"Cloudflare Worker summary smoke failed ({status}) for {summary_url}: {body}"
            )
        verify_freshness(json.loads(body), meta, summary_url)
        trust_url = f"http://{server_addr}{first_repo['links']['trust']}"
        status, body = http_get_text(trust_url)
        if status != 200:
            raise SystemExit(
                f"Cloudflare Worker trust smoke failed ({status}) for {trust_url}: {body}"
            )
        verify_freshness(json.loads(body), meta, trust_url)
        query_template = repositories[0]["links"]["queryTemplate"]
        if not isinstance(query_template, str):
            raise SystemExit("Cloudflare Worker inventory smoke found no queryTemplate")
        query_url = f"http://{server_addr}{query_template.replace('{dot_path}', 'repo.description')}"
        status, body = http_get_text(query_url)
        if status != 200:
            raise SystemExit(
                f"Cloudflare Worker queryTemplate smoke failed ({status}) for {query_url}: {body}"
            )
        query_response = json.loads(body)
        if query_response.get("path") != "repo.description":
            raise SystemExit("Cloudflare Worker queryTemplate smoke returned unexpected path")
        links = query_response.get("links", {})
        self_link = links.get("self")
        if not isinstance(self_link, str) or not self_link.startswith(base):
            raise SystemExit(
                f"Cloudflare Worker queryTemplate smoke returned unexpected self link: {self_link}"
            )
    finally:
        server.kill()
        server.wait(timeout=5)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_root = (repo_root / args.output_root).resolve()
    public_dir = output_root / "public"
    public_bundle_dir = output_root / "public-bundle"
    release_bundle_dir = output_root / "release-bundle"
    vsix_dir = output_root / "vsix"
    worker_dir = repo_root / "cloudflare" / "hosted-query"
    worker_snapshot_dir = worker_dir / "public-snapshot"

    if output_root.exists():
        shutil.rmtree(output_root)
    public_bundle_dir.mkdir(parents=True, exist_ok=True)
    release_bundle_dir.mkdir(parents=True, exist_ok=True)
    vsix_dir.mkdir(parents=True, exist_ok=True)

    run(["cargo", "run", "-p", "dotrepo-cli", "--", "validate-index"], cwd=repo_root)
    run(
        [
            "cargo",
            "test",
            "-p",
            "dotrepo-core",
            "--test",
            "public_export_fixture_pack",
            "--test",
            "public_query_fixture_pack",
            "--test",
            "public_error_fixture_pack",
            "--test",
            "public_freshness_semantics",
            "--test",
            "public_contract_compatibility",
        ],
        cwd=repo_root,
    )
    run(
        [
            "cargo",
            "run",
            "-p",
            "dotrepo-cli",
            "--",
            "public",
            "export",
            "--index-root",
            "index",
            "--out-dir",
            str(public_dir),
            "--base-path",
            args.base_path,
            "--generated-at",
            args.generated_at,
            "--stale-after",
            args.stale_after,
        ],
        cwd=repo_root,
    )
    run(
        ["python3", "scripts/render_public_pages_landing.py", "--input", str(public_dir)],
        cwd=repo_root,
    )
    run(
        [
            "python3",
            "scripts/sync_cloudflare_public_snapshot.py",
            "--input",
            str(public_dir),
            "--output",
            str(worker_snapshot_dir),
        ],
        cwd=repo_root,
    )
    run(
        [
            "python3",
            "scripts/package_public_export.py",
            "--input",
            str(public_dir),
            "--output-dir",
            str(public_bundle_dir),
        ],
        cwd=repo_root,
    )
    run(["npm", "ci"], cwd=worker_dir)
    run(["npm", "test"], cwd=worker_dir)
    run(["npm", "run", "deploy:dry-run"], cwd=worker_dir)

    release_bundle = None
    release_checksum = None
    target = None
    version = workspace_version(repo_root)
    if not args.skip_release_bundle:
        run(
            [
                "cargo",
                "build",
                "--release",
                "-p",
                "dotrepo-cli",
                "--bins",
                "-p",
                "dotrepo-lsp",
                "-p",
                "dotrepo-mcp",
            ],
            cwd=repo_root,
        )
        target = host_target(repo_root)
        run(
            [
                "python3",
                "scripts/package_release_binaries.py",
                "--bin-dir",
                "target/release",
                "--output-dir",
                str(release_bundle_dir),
                "--target",
                target,
            ],
            cwd=repo_root,
        )

    vsix_path = None
    if not args.skip_vsix:
        run(["npm", "ci"], cwd=repo_root / "editors" / "vscode")
        run(["npm", "run", "build"], cwd=repo_root / "editors" / "vscode")
        extension_version_value = extension_version(repo_root)
        vsix_path = vsix_dir / f"dotrepo-vscode-v{extension_version_value}.vsix"
        run(
            [
                "npm",
                "run",
                "package:vsix",
                "--",
                "--output",
                str(vsix_path),
            ],
            cwd=repo_root / "editors" / "vscode",
        )

    verify_public_meta(public_dir, args.base_path)

    public_bundle = expect_single(sorted(public_bundle_dir.glob("*.tar.gz")), "public export bundle")
    verify_tar_contains_prefix(public_bundle, public_bundle.stem.removesuffix(".tar"))

    if not args.skip_release_bundle:
        release_bundle = expect_single(
            sorted(release_bundle_dir.glob("*.tar.gz")), "release binary bundle"
        )
        release_checksum = release_bundle_dir / f"dotrepo-{version}-{target}.sha256"
        ensure_file(release_checksum)
        verify_tar_contains_prefix(release_bundle, f"dotrepo-{version}-{target}/")

    if vsix_path is not None:
        ensure_file(vsix_path)

    print("")
    if release_bundle is not None and target is not None:
        print("release install smoke test")
        smoke_test_release_bundle(
            release_bundle,
            version,
            target,
            repo_root,
            public_dir,
            args.base_path,
            args.generated_at,
            args.stale_after,
        )
        print("  all release binaries passed smoke test")
    smoke_test_cloudflare_worker(worker_dir, args.base_path)
    print("  Cloudflare Worker smoke test passed")

    print("")
    print("release gate artifacts")
    print(f"  public tree: {public_dir}")
    print(f"  public bundle: {public_bundle}")
    if release_bundle is not None:
        print(f"  release bundle: {release_bundle}")
    if vsix_path is not None:
        print(f"  vsix: {vsix_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
