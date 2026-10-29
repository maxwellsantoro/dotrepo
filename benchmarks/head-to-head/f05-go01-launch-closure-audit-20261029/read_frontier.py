"""Bounded second source frontier, inert local archive/package bytes only."""

from pathlib import Path
import base64
import hashlib
import io
import json
import tarfile

OUTPUT = Path(__file__).resolve().parent
source = Path("/tmp/dotrepo-f05-qualification-20261029-tranche-1/go-01-full/runtime-source.tar")
cache = Path("/private/tmp/dotrepo-go01-dependency-download-cache-20261029-1/cache.tar")
lock = json.loads((OUTPUT / "repository-source/package-lock.json").read_bytes())["packages"]
rows = []


def save(t, name, area, container):
    p = OUTPUT / area / name
    if p.exists():
        return
    m = t.getmember(name)
    assert m.isfile() and m.size <= 2 * 1024**2
    b = t.extractfile(m).read()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b)
    rows.append(
        {
            "path": name,
            "area": area,
            "container": str(container),
            "sha256": hashlib.sha256(b).hexdigest(),
            "bytes": len(b),
        }
    )


with tarfile.open(source, "r:") as t:
    for n in [
        "tools/scripts/gen/generatedFile.mts",
        "tools/scripts/tsc/schema.ts",
        "tools/scripts/tsc/generate-options.ts",
        "tools/scripts/tsc/options.ts",
    ]:
        save(t, n, "repository-source", source)
extra = {
    "hereby": [
        "package/dist/cli.js",
        "package/dist/cli/loadHerebyfile.js",
        "package/dist/cli/parseArgs.js",
        "package/dist/cli/runner.js",
        "package/dist/cli/utils.js",
        "package/dist/cli/style.js",
        "package/dist/index.js",
    ],
    "@vscode/vsce-sign": ["package/src/target.js", "package/src/permissions.js"],
    "dprint": ["package/install.cjs", "package/bin.cjs"],
    "esbuild": [],
}
with tarfile.open(cache, "r:") as t:
    for pkg, names in extra.items():
        integ = lock["node_modules/" + pkg]["integrity"]
        d = base64.b64decode(integ.split("-", 1)[1])
        h = d.hex()
        path = "npm-cache/_cacache/content-v2/sha512/" + h[:2] + "/" + h[2:4] + "/" + h[4:]
        m = t.getmember(path)
        b = t.extractfile(m).read()
        assert hashlib.sha512(b).digest() == d
        with tarfile.open(fileobj=io.BytesIO(b), mode="r:gz") as p:
            for n in names:
                save(p, n, "npm-source/" + pkg, str(cache) + "::" + path)
(OUTPUT / "frontier-sources.json").write_text(
    json.dumps(
        {
            "sources": rows,
            "scope": "Selected local static import and launcher/hook frontier; no package execution",
        },
        indent=2,
    )
    + "\n"
)
print(json.dumps({"files": len(rows), "bytes": sum(x["bytes"] for x in rows)}))
