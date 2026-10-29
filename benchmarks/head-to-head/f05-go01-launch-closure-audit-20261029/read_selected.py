"""Read retained archive bytes only, without extraction or upstream imports."""

from pathlib import Path
import base64
import hashlib
import io
import json
import tarfile

OUT = Path(__file__).resolve().parent
ROOT = Path("/Users/maxwell/projects/agent/dotrepo")
IMAGE = Path("/tmp/dotrepo-f05-common-image-audit-9slpmcbi/filesystem-export.tar")
SOURCE = Path("/tmp/dotrepo-f05-qualification-20261029-tranche-1/go-01-full/runtime-source.tar")
CACHE = Path("/private/tmp/dotrepo-go01-dependency-download-cache-20261029-1/cache.tar")
rows = []


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def retain(tar, name, area, archive):
    m = tar.getmember(name)
    assert m.isfile() and 0 <= m.size <= 2 * 1024**2
    raw = tar.extractfile(m).read(m.size + 1)
    assert len(raw) == m.size
    p = OUT / area / name
    p.parent.mkdir(parents=True, exist_ok=True)
    assert not p.exists()
    p.write_bytes(raw)
    rows.append(
        {
            "path": name,
            "container": str(archive),
            "area": area,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
    return raw


image_names = [
    "node_modules/@npmcli/config/lib/set-envs.js",
    "node_modules/@npmcli/config/lib/env-replace.js",
    "node_modules/@npmcli/config/lib/definitions/index.js",
    "node_modules/@npmcli/config/lib/definitions/definitions.js",
    "node_modules/@npmcli/config/package.json",
    "node_modules/libnpmexec/package.json",
    "node_modules/libnpmexec/lib/file-exists.js",
    "node_modules/@npmcli/run-script/package.json",
    "node_modules/@npmcli/run-script/lib/package-envs.js",
    "node_modules/@npmcli/promise-spawn/package.json",
    "node_modules/@npmcli/promise-spawn/lib/index.js",
    "lib/utils/resolve-allow-scripts.js",
    "lib/commands/ci.js",
]
with tarfile.open(IMAGE, "r:") as tar:
    for name in image_names:
        retain(tar, "usr/local/lib/node_modules/npm/" + name, "image-source", IMAGE)
assert sha(SOURCE) == "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f"
local = [
    "Herebyfile.mjs",
    "tools/scripts/gen/utils.mts",
    "tools/scripts/lsp/fetchModel.mts",
    "tools/scripts/tsc/generate-encoder.ts",
    "tools/scripts/tsc/generate-enums.ts",
    "tools/scripts/tsc/generate-go-ast.ts",
    "tools/scripts/tsc/generate-ts-ast.ts",
    "tsc/internal/stringutil/_scripts/generate-unicode-data.mts",
    "package.json",
    "package-lock.json",
]
with tarfile.open(SOURCE, "r:") as tar:
    for name in local:
        retain(tar, name, "repository-source", SOURCE)
lock = json.loads((OUT / "repository-source/package-lock.json").read_bytes())["packages"]
assert sha(CACHE) == "583fad501fa7b1a1a6d85ab8fe4b890786e39c1e016f785d6d3fb9d060383284"
packages = ["hereby", "tinyexec", "@vscode/vsce-sign", "dprint", "esbuild"]
selected = {}
sri = []
with tarfile.open(CACHE, "r:") as cache:
    for name in packages:
        entry = lock["node_modules/" + name]
        integrity = entry["integrity"]
        algorithm, checksum = integrity.split("-", 1)
        assert algorithm == "sha512"
        dig = base64.b64decode(checksum)
        hexvalue = dig.hex()
        blob = (
            "npm-cache/_cacache/content-v2/sha512/"
            + hexvalue[:2]
            + "/"
            + hexvalue[2:4]
            + "/"
            + hexvalue[4:]
        )
        m = cache.getmember(blob)
        assert m.isfile() and m.size <= 4 * 1024**2
        raw = cache.extractfile(m).read()
        assert hashlib.sha512(raw).digest() == dig
        selected[name] = (raw, blob)
        sri.append(
            {
                "name": name,
                "version": entry["version"],
                "integrity": integrity,
                "blobPath": blob,
                "compressedBytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as package:
            retain(
                package,
                "package/package.json",
                "npm-source/" + name,
                CACHE.as_posix() + "::" + blob,
            )
            names = [v.name for v in package.getmembers() if v.isfile() and v.size < 2 * 1024**2]
            (OUT / ("package-files-" + name.replace("/", "_") + ".json")).write_text(
                json.dumps(names, indent=2) + "\n"
            )
            wanted = {
                "hereby": [
                    "package/bin/hereby.js",
                    "package/dist/cli/index.js",
                    "package/dist/cli/reexec.js",
                    "package/dist/cli/find.js",
                    "package/dist/cli/load.js",
                    "package/dist/runner.js",
                ],
                "tinyexec": ["package/dist/main.mjs"],
                "@vscode/vsce-sign": ["package/src/main.js", "package/src/postinstall.js"],
                "dprint": ["package/install.js", "package/bin.js"],
                "esbuild": ["package/install.js", "package/bin/esbuild", "package/lib/main.js"],
            }[name]
            for path in wanted:
                if path in names:
                    retain(package, path, "npm-source/" + name, CACHE.as_posix() + "::" + blob)
(OUT / "additional-sources.json").write_text(
    json.dumps(
        {
            "sources": rows,
            "sriVerifiedPackages": sri,
            "scriptScope": "Inert archive reads only; no package imports/install or native actions",
        },
        indent=2,
    )
    + "\n"
)
print(
    json.dumps(
        {
            "retainedFiles": len(rows),
            "retainedBytes": sum(r["bytes"] for r in rows),
            "packages": [(r["name"], r["version"]) for r in sri],
        }
    )
)
