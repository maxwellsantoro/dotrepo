"""Generate unaccepted offline setup metadata; never daemon or package calls."""

import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
BASE = Path("/Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head")
prior = json.loads((BASE / "f05-go01-dependency-preparation-20261029/plan.json").read_text())
result = BASE / "f05-go01-dependency-download-result-20261029"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


versions = {
    "@vscode/vsce-sign": "2.1.0",
    "dprint": "0.57.4",
    "esbuild": "0.28.2",
    "@vscode/vsce-sign-linux-arm64": "2.0.6",
    "@dprint/linux-arm64-glibc": "0.57.4",
    "@esbuild/linux-arm64": "0.28.2",
    "@typescript/bundled-typescript": "7.0.2",
    "@typescript/typescript-linux-arm64": "7.0.2",
}
files = [
    "@vscode/vsce-sign/bin/vsce-sign",
    "@vscode/vsce-sign-linux-arm64/bin/vsce-sign",
    "@dprint/linux-arm64-glibc/dprint",
    "@esbuild/linux-arm64/bin/esbuild",
    ".bin/dprint",
    ".bin/esbuild",
]
observation = (
    'const fs=require("fs"),path=require("path"),crypto=require("crypto");const root="/workspace/repository/node_modules";const names='
    + json.dumps(versions)
    + ";const files="
    + json.dumps(files)
    + ';const versions={};for(const name of Object.keys(names)){try{versions[name]=JSON.parse(fs.readFileSync(path.join(root,name,"package.json"),"utf8")).version;}catch(e){versions[name]=null;}}const rows={};for(const name of files){try{const full=path.join(root,name),link=fs.lstatSync(full),resolved=fs.realpathSync(full),s=fs.statSync(full);rows[name]={isFile:s.isFile(),contained:resolved.startsWith(root+"/"),resolved,bytes:s.size,mode:s.mode&511,link:link.isSymbolicLink()?fs.readlinkSync(full):null,sha256:s.isFile()?crypto.createHash("sha256").update(fs.readFileSync(full)).digest("hex"):null};}catch(e){rows[name]=null;}}console.log(JSON.stringify({versions,files:rows}));'
)
env = {
    **prior["environment"],
    "NPM_CONFIG_IGNORE_SCRIPTS": "false",
    "NPM_CONFIG_OFFLINE": "true",
    "NPM_CONFIG_FOREGROUND_SCRIPTS": "true",
    "GOPROXY": "off",
    "GOSUMDB": "off",
}
bindings = {
    str(BASE / "f05-go01-dependency-preparation-20261029" / name): digest(
        BASE / "f05-go01-dependency-preparation-20261029" / name
    )
    for name in [
        "freeze.json",
        "plan.json",
        "prepare.py",
        "process_io.py",
        "boundaries.py",
        "protected-digests.json",
    ]
}
for sub in [
    "freeze.json",
    "evidence/dependency-cache-spec.json",
    "evidence/inventory.json",
    "evidence/provenance.json",
    "evidence/preparation.json",
    "evidence/trace.json",
    "evidence/result.json",
]:
    bindings[str(result / sub)] = digest(result / sub)
for sub in ["freeze.json", "identities.json", "assessment.json", "source-spans.json"]:
    f = BASE / "f05-go01-npm-hook-assessment-20261029" / sub
    bindings[str(f)] = digest(f)
original = BASE / "f05-go01-offline-setup-plan-20261029"
review = BASE / "f05-go01-offline-setup-review-20261029"
for artifact in [
    original / "freeze.json",
    original / "plan.json",
    review / "FREEZE.json",
    review / "counterexamples.json",
    review / "prior-inspect-representation.json",
    BASE / "f05-go01-dependency-download-review-20261029/FREEZE.json",
    HERE / "inspect-policy.json",
]:
    bindings[str(artifact)] = digest(artifact)
plan = {
    "identity": "go01-single-offline-normal-npm-setup-amendment-1",
    "state": "plan only; independent cache acceptance and separate one-attempt authorization required",
    "executionAuthorized": False,
    "cacheAdmissionSatisfied": False,
    "repository": prior["repository"],
    "revision": prior["revision"],
    "imageId": prior["imageId"],
    "sourceArchiveSha256": prior["source"]["archiveSha256"],
    "cache": {
        "path": "/private/tmp/dotrepo-go01-dependency-download-cache-20261029-1/cache.tar",
        "sha256": "583fad501fa7b1a1a6d85ab8fe4b890786e39c1e016f785d6d3fb9d060383284",
        "bytes": 366622720,
        "expandedBytes": 351962210,
    },
    "cacheInventoryPath": str(result / "evidence/inventory.json"),
    "cacheSpecSha256": digest(result / "evidence/dependency-cache-spec.json"),
    "publishedTaskPayloadsSha256": digest(HERE / "published-task-payloads.json"),
    "command": "cd /workspace/repository; npm ci --offline --foreground-scripts",
    "environment": env,
    "limits": prior["limits"],
    "toolProbe": prior["toolProbe"],
    "expectedToolLines": prior["expectedToolLines"],
    "npmConfigProbe": "cd /workspace/repository; npm config list --json",
    "packageObservation": "node -e " + shlex.quote(observation),
    "expectedHookMarkers": [
        "@vscode/vsce-sign@2.1.0 postinstall",
        "dprint@0.57.4 postinstall",
        "esbuild@0.28.2 postinstall",
    ],
    "expectedPackageVersions": versions,
    "requiredObservedFiles": files,
    "bindings": {
        **bindings,
        str(HERE / "published-task-payloads.json"): digest(HERE / "published-task-payloads.json"),
    },
    "scripts": {name: digest(HERE / name) for name in ["setup.py", "controls.py", "make_plan.py"]},
    "limitsOfEvidence": [
        "No daemon/package execution authorized by plan.",
        "Foreground hook logging is an explicit observation setting; no universal equivalence assertion.",
        "Normal npm lifecycle hooks may execute native esbuild --version/libc probes; proposed only in offline sandbox.",
        "Accepted cache receipt is a coordinator assertion bound to independent audit freeze; original draft falseflags remain unchanged.",
        "Setup outcome only; no Go helper compilation/install, native collection/test, Hereby task, provider/model or campaign admission.",
    ],
}
with (HERE / "plan.json").open("x") as f:
    json.dump(plan, f, indent=2, sort_keys=True)
    f.write("\n")
