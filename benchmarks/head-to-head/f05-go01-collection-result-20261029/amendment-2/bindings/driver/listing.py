"""Bounded Go listing interpretation; raw native output remains the evidence."""

import json
import re

PREFIX = "github.com/microsoft/TypeScript/tsc"
CWD = "/workspace/repository/tsc"
REQUIRED = tuple(
    PREFIX + "/internal/" + name
    for name in ["parser", "lsp", "jsnum", "fswatch", "fourslash/tests"]
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("non-JSON numeric constant: " + value)


DECODER = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=invalid_constant)


def objects(raw):
    text = raw.decode("utf-8", errors="strict")
    result, position = [], 0
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        if position == len(text):
            break
        value, position = DECODER.raw_decode(text, position)
        require(isinstance(value, dict), "JSON item is not an object")
        result.append(value)
    require(bool(result), "empty JSON listing")
    return result


def environment(raw, expected):
    values = objects(raw)
    require(len(values) == 1 and values[0] == expected, "Go environment mismatch")
    return values[0]


def packages(raw, source_files=None):
    result = {}
    for row in objects(raw):
        name, directory = row.get("ImportPath"), row.get("Dir")
        require(
            isinstance(name, str) and (name == PREFIX or name.startswith(PREFIX + "/")),
            "package outside module",
        )
        require(name not in result, "duplicate package")
        require(
            all(part not in ("", ".", "..") for part in name.split("/"))
            and not any(c.isspace() or c in "\\:" for c in name),
            "invalid package identity",
        )
        require(
            isinstance(directory, str) and (directory == CWD or directory.startswith(CWD + "/")),
            "package outside checkout",
        )
        require(
            directory == CWD + name.removeprefix(PREFIX),
            "package directory differs from ImportPath",
        )
        require(
            not any(part in ("", ".", "..") for part in directory[1:].split("/")),
            "invalid package directory",
        )
        require(
            not row.get("Error") and not row.get("DepsErrors") and not row.get("Incomplete"),
            "incomplete/error package",
        )
        module = row.get("Module")
        require(
            isinstance(module, dict)
            and module.get("Path") == PREFIX
            and module.get("Dir") == CWD
            and not module.get("Replace"),
            "module identity mismatch",
        )
        selected = set()
        for field in ["GoFiles", "CgoFiles", "TestGoFiles", "XTestGoFiles"]:
            value = row.get(field, [])
            require(
                isinstance(value, list)
                and all(
                    isinstance(item, str)
                    and item not in ("", ".", "..")
                    and item.endswith(".go")
                    and not any(c in "/\\:" or ord(c) < 32 or ord(c) == 127 for c in item)
                    for item in value
                )
                and len(value) == len(set(value))
                and not selected.intersection(value),
                "invalid selected file list",
            )
            selected.update(value)
            if source_files is not None:
                require(
                    all(
                        directory.removeprefix("/workspace/repository/") + "/" + item
                        in source_files
                        for item in value
                    ),
                    "selected Go file absent from validated source inventory",
                )
        require(bool(selected), "package has no selected Go source")
        result[name] = row
    require(set(REQUIRED) <= set(result), "missing required package observation")
    return result


def collection(raw, inventory):
    rows = objects(raw)
    output, started, terminal = {name: [] for name in inventory}, set(), {}
    diagnostics = []
    for row in rows:
        action, name = row.get("Action"), row.get("Package")
        require(not row.get("Test"), "unexpected test-body/subtest event during listing")
        if action == "build-output":
            require(isinstance(row.get("Output"), str), "malformed build diagnostic")
            diagnostics.append(row)
            continue
        require(name in inventory, "event package missing from inventory")
        require(
            action in {"start", "output", "pass", "skip"}, "unexpected/failing collection event"
        )
        require(name not in terminal, "event after package terminal")
        if action == "start":
            require(name not in started, "duplicate package start")
            started.add(name)
        elif action == "output":
            require(
                name in started and isinstance(row.get("Output"), str), "malformed package output"
            )
            output[name].append(row["Output"])
        else:
            require(name in started, "terminal without package start")
            terminal[name] = action
    require(set(terminal) == set(inventory), "missing package terminal/listing")
    cases, benchmarks = {}, {}
    for name, parts in output.items():
        identifiers = [
            line
            for line in "".join(parts).splitlines()
            if re.fullmatch(r"(?:Test|Example|Fuzz|Benchmark)\w*", line)
        ]
        require(len(identifiers) == len(set(identifiers)), "duplicate top-level identifier")
        tests = sorted(value for value in identifiers if not value.startswith("Benchmark"))
        benchmarks[name] = sorted(value for value in identifiers if value.startswith("Benchmark"))
        if terminal[name] == "skip":
            require(
                not inventory[name].get("TestGoFiles")
                and not inventory[name].get("XTestGoFiles")
                and not identifiers
                and "[no test files]" in "".join(parts),
                "unexpected skipped package",
            )
        cases[name] = {
            "identifiers": tests,
            "terminal": terminal[name],
            "selectedTestFiles": inventory[name].get("TestGoFiles", []),
            "selectedExternalTestFiles": inventory[name].get("XTestGoFiles", []),
        }
    require(any(row["identifiers"] for row in cases.values()), "empty top-level case listing")
    require(
        all(cases[name]["identifiers"] for name in REQUIRED),
        "missing known test-package case observations",
    )
    return {
        "packages": cases,
        "benchmarks": benchmarks,
        "buildDiagnostics": diagnostics,
        "scope": "top-level listing only; no test bodies/subtests/fuzz-seed identities inferred",
    }
