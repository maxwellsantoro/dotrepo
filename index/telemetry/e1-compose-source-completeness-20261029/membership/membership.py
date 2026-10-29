"""Finite source-header selection, not native go list, compilation or test discovery."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
# Filename suffix classification only; the report parameterizes architecture.
# No present header uses GOARCH/architecture-feature/release/compiler/CGO tags.
GOOS = set(
    "aix android darwin dragonfly freebsd hurd illumos ios js linux nacl netbsd openbsd plan9 solaris wasip1 windows zos".split()
)
GOARCH = set(
    "386 amd64 amd64p32 arm arm64 arm64be armbe loong64 mips mips64 mips64le mips64p32 mips64p32le mipsle ppc ppc64 ppc64le riscv riscv64 s390 s390x sparc sparc64 wasm".split()
)


class Expression:
    def __init__(self, value):
        self.tokens = re.findall(r"[A-Za-z0-9_.]+|&&|\|\||[!()]", value)
        if "".join(self.tokens) != re.sub(r"\s", "", value):
            raise ValueError("unsupported constraint characters")
        self.position = 0
        self.tags = set()

    def pop(self, expected=None):
        if self.position >= len(self.tokens):
            raise ValueError("incomplete expression")
        value = self.tokens[self.position]
        if expected is not None and value != expected:
            raise ValueError("unexpected expression token")
        self.position += 1
        return value

    def atom(self, tags):
        value = self.pop()
        if value == "!":
            return not self.atom(tags)
        if value == "(":
            result = self.disjunction(tags)
            self.pop(")")
            return result
        if re.fullmatch(r"[A-Za-z0-9_.]+", value) is None:
            raise ValueError("invalid constraint atom")
        self.tags.add(value)
        return value in tags

    def conjunction(self, tags):
        result = self.atom(tags)
        while self.position < len(self.tokens) and self.tokens[self.position] == "&&":
            self.pop("&&")
            right = self.atom(tags)
            result = result and right
        return result

    def disjunction(self, tags):
        result = self.conjunction(tags)
        while self.position < len(self.tokens) and self.tokens[self.position] == "||":
            self.pop("||")
            right = self.conjunction(tags)
            result = result or right
        return result

    def evaluate(self, tags):
        result = self.disjunction(tags)
        if self.position != len(self.tokens):
            raise ValueError("trailing constraint token")
        return result


def legacy(lines, tags):
    return all(
        any(
            all(
                (term[1:] not in tags) if term.startswith("!") else (term in tags)
                for term in option.split(",")
            )
            for option in line.split()
        )
        for line in lines
    )


def filename_matches(path, goos, arch):
    name = PurePosixPath(path).name
    if name.startswith((".", "_")) or not name.endswith(".go"):
        return False
    name = name[:-3]
    if name.endswith("_test"):
        name = name[:-5]
    pieces = name.split("_")
    if len(pieces) >= 3 and pieces[-2] in GOOS and pieces[-1] in GOARCH:
        return pieces[-2] == goos and pieces[-1] == arch
    if len(pieces) >= 2 and pieces[-1] in GOOS:
        return pieces[-1] == goos
    if len(pieces) >= 2 and pieces[-1] in GOARCH:
        return pieces[-1] == arch
    return True


def selected(row, tags, arch):
    if not filename_matches(row["path"], "linux", arch):
        return False
    if len(row["goBuild"]) > 1:
        raise ValueError("multiple go:build constraints")
    if row["goBuild"]:
        return Expression(row["goBuild"][0]).evaluate(tags)
    return legacy(row["plusBuild"], tags)


def main_module(path, modules):
    parts = PurePosixPath(path).parts[:-1]
    if any(part.startswith((".", "_")) or part in {"testdata", "vendor"} for part in parts):
        return False
    return not any(
        str(PurePosixPath(*parts[:n]) / "go.mod") in modules for n in range(1, len(parts) + 1)
    )


def calculate(headers, inventory, arch, module_path, excluded_units):
    modules = {name for name in inventory["entries"] if name.rsplit("/", 1)[-1] == "go.mod"}
    base_tags = {"linux", "unix", arch, "cgo", "gc"} | {"go1." + str(n) for n in range(1, 27)}
    result = {}
    for row in headers:
        path = row["path"]
        directory = str(PurePosixPath(path).parent)
        record = result.setdefault(
            directory,
            {
                "directory": directory,
                "mainModuleWalkIncluded": main_module(path, modules),
                "untagged": {"production": [], "test": []},
                "intendedE2eTag": {"production": [], "test": []},
                "sourcePackages": set(),
            },
        )
        record["sourcePackages"].add(row["package"])
        kind = "test" if path.endswith("_test.go") else "production"
        for label, tags in [("untagged", base_tags), ("intendedE2eTag", base_tags | {"e2e"})]:
            if selected(row, tags, arch):
                record[label][kind].append(path)
    for directory, record in result.items():
        record["sourcePackages"] = sorted(record["sourcePackages"])
        # Go list may load packages with only selected test files; this is not
        # a proof that loading/typechecking/import resolution succeeds.
        enumerable = record["mainModuleWalkIncluded"] and any(record["untagged"].values())
        import_path = module_path + ("/" + directory if directory != "." else "")
        record["importPath"] = import_path
        record["sourceEligibleForUntaggedEnumeration"] = enumerable
        record["excludedByLiteralE2eSubstring"] = "e2e" in import_path
        record["selectedByProspectiveRelay"] = enumerable and "e2e" not in import_path
        record["intendedUnitDirectory"] = record["mainModuleWalkIncluded"] and not any(
            directory == excluded or directory.startswith(excluded + "/")
            for excluded in excluded_units
        )
        record["hasIntendedSelectedTests"] = record["intendedUnitDirectory"] and bool(
            record["intendedE2eTag"]["test"]
        )
        record["unitTestPackageOmittedBySourceSelection"] = (
            record["hasIntendedSelectedTests"] and not record["selectedByProspectiveRelay"]
        )
    return list(result.values())


def main():
    head = json.loads((HERE / "headers.json").read_bytes())
    inventory = json.loads((HERE / "acquisition-inventory.json").read_bytes())
    policy = json.loads((HERE / "membership-policy.json").read_bytes())
    module_match = re.match(r"module ([^\s]+)", (HERE / "routing/go.mod").read_text())
    if module_match is None:
        raise ValueError("unsupported module declaration")
    module_path = module_match[1]
    tokens = set()
    for row in head["headers"]:
        for expression in row["goBuild"]:
            node = Expression(expression)
            node.evaluate(set())
            tokens.update(node.tags)
    contexts = []
    # All filename architecture labels are parameterized. No observed source
    # uses one, so these contexts are equivalent for this source population.
    for arch in sorted(GOARCH):
        packages = calculate(
            head["headers"], inventory, arch, module_path, policy["excludedUnitDirectories"]
        )
        contexts.append(
            {
                "GOOS": "linux",
                "GOARCH": arch,
                "CGO_ENABLED": "1",
                "toolchain": "source-intended Go1.26.10 gc; release tags through go1.26",
                "enumeratorBuildTags": [],
                "testBuildTags": ["e2e"],
                "effectiveChildContextObserved": False,
                "packages": packages,
                "counts": {
                    "sourceGoDirectories": len(packages),
                    "mainModuleDirectories": sum(r["mainModuleWalkIncluded"] for r in packages),
                    "prospectiveSelectedDirectories": sum(
                        r["selectedByProspectiveRelay"] for r in packages
                    ),
                    "intendedUnitTestPackages": sum(
                        r["hasIntendedSelectedTests"] for r in packages
                    ),
                    "omittedIntendedUnitTestPackages": sum(
                        r["unitTestPackageOmittedBySourceSelection"] for r in packages
                    ),
                },
            }
        )
    assert all(r["packages"] == contexts[0]["packages"] for r in contexts)
    compact = {
        "state": "conditional-source-membership-established-not-native-package-inventory",
        "headersSha256": hashlib.sha256((HERE / "headers.json").read_bytes()).hexdigest(),
        "constraintTokensObserved": sorted(tokens),
        "architectureVariationInThisSource": False,
        "architectureLabelsCompared": [r["GOARCH"] for r in contexts],
        "architectureLabelsAreFilenameGrammarNotClaimedSupportedImagePlatforms": True,
        "representativeContext": contexts[0],
        "conditions": [
            "Linux Go selection, CGO1, gc compiler, source-intended Go1.26.10; no extra GOFLAGS or custom tags",
            "TAGS command substitution supplies no extra enumeration arguments; its actual behavior is not observed",
            "go list loads/completes the selected source packages; imports/typechecking/acquisition not established here",
            "test command receives source-intended e2e build tag; no effective argv/environment observed",
            "default unchanged Make/Bake/Dockerfile and clean exact source tree; relay separate module/e2e separate lane",
        ],
        "completeTupleAccepted": False,
        "nativeCollectionOccurred": False,
    }
    with (HERE / "membership.json").open("x") as stream:
        json.dump(compact, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"counts": contexts[0]["counts"], "constraintTokens": sorted(tokens)}))


if __name__ == "__main__":
    main()
