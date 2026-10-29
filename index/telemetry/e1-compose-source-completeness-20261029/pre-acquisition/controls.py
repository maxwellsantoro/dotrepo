"""Hash/reference and explicit abstract package-selection counterexamples only."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def main():
    bindings = json.loads((HERE / "source-bindings.json").read_bytes())
    for row in bindings["sources"]:
        raw = (HERE / row["snapshot"]).read_bytes()
        assert sha(raw) == row["sha256"] and len(raw) == row["bytes"]
        assert blob(raw) == row["gitBlobSha1"]
    for row in bindings["ownerInputs"]:
        raw = (HERE / row["snapshot"]).read_bytes()
        assert sha(raw) == row["sha256"] and len(raw) == row["bytes"]
    for row in bindings["spans"]:
        raw = (HERE / "sources" / row["path"]).read_bytes()
        passage = b"".join(raw.splitlines(keepends=True)[row["startLine"] - 1 : row["endLine"]])
        assert sha(raw) == row["wholeFileSha256"]
        assert sha(passage) == row["passageSha256"] and passage.decode() == row["text"]
    source = {r["path"]: (HERE / r["snapshot"]).read_text() for r in bindings["sources"]}
    assert "To run all of the unit tests, run:" in source["BUILDING.md"]
    assert "test: ## Run unit tests\n\t$(BUILDX_CMD) bake test" in source["Makefile"]
    assert (
        'target "test" {\n  inherits = ["_common"]\n  target = "test-coverage"'
        in source["docker-bake.hcl"]
    )
    command = next(r for r in source["Dockerfile"].splitlines() if "--format testname" in r)
    assert '-tags "$BUILD_TAGS"' in command
    assert "$(go list  $(TAGS) ./... | grep -vE 'e2e')" in command
    assert source["Dockerfile"].index("FROM build-base AS test") < source["Dockerfile"].index(
        command
    )
    assert "$(MAKE)" not in command  # Dockerfile body is not a Make recipe.
    tree_receipt = next(
        r for r in bindings["ownerInputs"] if r["path"].endswith("02-root-tree.json")
    )
    wrapper = json.loads((HERE / tree_receipt["snapshot"]).read_bytes())
    tree = json.loads(wrapper["result"]["structuredContent"]["content"])
    assert tree["truncated"] is False and len(tree["tree"]) == 27
    assert not any("/" in row["path"] for row in tree["tree"])
    entries = sorted(
        tree["tree"],
        key=lambda row: (row["path"] + ("/" if row["type"] == "tree" else "")).encode(),
    )
    payload = b"".join(
        row["mode"].lstrip("0").encode()
        + b" "
        + row["path"].encode()
        + b"\0"
        + bytes.fromhex(row["sha"])
        for row in entries
    )
    actual_tree = hashlib.sha1(b"tree " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
    assert actual_tree == tree["sha"] == "b10e2fc106b7ea146f5d31f56ca0386688275aa7"
    assert {"cmd", "pkg", "internal"} <= {
        row["path"] for row in tree["tree"] if row["type"] == "tree"
    }

    # These are finite abstract data fixtures, not parser/Go/shell execution,
    # native package inventories, or assertions about actual Compose packages.
    module = "github.com/docker/compose/v5/"
    examples = []
    for name, untagged, tagged, intended, expected_missing in [
        (
            "all-intended-packages-selected",
            {module + "pkg/unit", module + "pkg/e2e"},
            {module + "pkg/unit", module + "pkg/e2e"},
            {module + "pkg/unit"},
            set(),
        ),
        (
            "tag-only-unit-package-not-enumerated",
            {module + "pkg/unit"},
            {module + "pkg/unit", module + "pkg/taggedunit"},
            {module + "pkg/unit", module + "pkg/taggedunit"},
            {module + "pkg/taggedunit"},
        ),
        (
            "literal-e2e-substring-is-not-a-directory-classifier",
            {module + "pkg/type2enum"},
            {module + "pkg/type2enum"},
            {module + "pkg/type2enum"},
            {module + "pkg/type2enum"},
        ),
    ]:
        selected = {path for path in untagged if "e2e" not in path}
        missing = intended - selected
        assert missing == expected_missing
        examples.append(
            {
                "name": name,
                "untaggedPackageInventory": sorted(untagged),
                "taggedPackageInventory": sorted(tagged),
                "intendedUnits": sorted(intended),
                "selectedByLiteralSubstringFilter": sorted(selected),
                "missingIntended": sorted(missing),
                "actualComposePackageClaim": False,
            }
        )
    report = {
        "allPassed": True,
        "sourceFilesHashAndBlobMatched": len(bindings["sources"]),
        "ownerInputHashesMatched": len(bindings["ownerInputs"]),
        "passagesMatched": len(bindings["spans"]),
        "abstractCounterexamples": examples,
        "rootTreeIsCompleteAtOneLevelNotRecursive": True,
        "rootTreeSha1Reconstructed": actual_tree,
        "sourceOrShellOrGoExecuted": False,
        "upstreamOrNetworkActions": 0,
        "instructionQualified": False,
    }
    with (HERE / "controls.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"allPassed": True, "sources": len(bindings["sources"]), "examples": 3}))


if __name__ == "__main__":
    main()
