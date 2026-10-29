"""Trusted Python-only constructor controls; no Go or upstream imports/execution."""

from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile

import build_input as builder

HERE = Path(__file__).resolve().parent


def refused(operation):
    try:
        operation()
    except (ValueError, KeyError, TypeError):
        return True
    raise AssertionError("invalid source data accepted")


def make_tar(path, entries):
    with tarfile.open(path, "w:") as archive:
        for name, data in entries:
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(data))


def main():
    package_path = builder.RESULT / "evidence/package-inventory.json"
    inventory = builder.load(builder.SOURCE_INVENTORY.read_bytes())["files"]
    packages = builder.load(package_path.read_bytes())
    selected = builder.validate_packages(packages, inventory)
    assert len(selected) == 4589
    checks = [{"case": "genuine104 selected membership validated4589 test files", "passed": True}]
    key = builder.PREFIX + "/internal/fourslash/tests"
    for name, mutate in [
        ("module", lambda rows: rows[key]["Module"].update(Path="other")),
        ("directory", lambda rows: rows[key].update(Dir="/workspace/other")),
        ("wrong identity", lambda rows: rows[key].update(ImportPath=builder.PREFIX + "/wrong")),
        ("error", lambda rows: rows[key].update(Error={"Err": "owned"})),
        ("incomplete", lambda rows: rows[key].update(Incomplete=True)),
        ("test traversal", lambda rows: rows[key].update(TestGoFiles=["../owned_test.go"])),
        ("missing test", lambda rows: rows[key].update(TestGoFiles=["missing_test.go"])),
        ("null test list", lambda rows: rows[key].update(TestGoFiles=None)),
        ("duplicate test", lambda rows: rows[key].update(TestGoFiles=rows[key]["TestGoFiles"] * 2)),
        (
            "cross field duplicate",
            lambda rows: rows[key].update(XTestGoFiles=rows[key]["TestGoFiles"]),
        ),
        (
            "no selected source",
            lambda rows: rows[key].update(GoFiles=[], CgoFiles=[], TestGoFiles=[], XTestGoFiles=[]),
        ),
        ("missing package", lambda rows: rows.pop(key)),
    ]:
        changed = deepcopy(packages)
        mutate(changed)
        checks.append(
            {
                "case": "reject " + name,
                "passed": refused(lambda: builder.validate_packages(changed, inventory)),
            }
        )
    checks.append(
        {
            "case": "reject duplicate JSON keys",
            "passed": refused(lambda: builder.load(b'{"x":1,"x":2}')),
        }
    )
    with tempfile.TemporaryDirectory(prefix=".constructor-controls-", dir=HERE) as temporary:
        temp = Path(temporary)
        name = "tsc/owned/owned_test.go"
        data = b"package owned\nfunc TestOwned(*T) {}\n"
        ignored = "tsc/owned/ignored_test.go"
        records = {name: builder.sha(data), ignored: builder.sha(b"ignored source")}
        selection = {name: {"field": "TestGoFiles"}}
        archive = temp / "owned.tar"
        make_tar(archive, [(name, data), (ignored, b"ignored source")])
        chosen, _, _ = builder.select_source(archive, records, selection)
        assert chosen == {name: data} and ignored not in chosen
        checks.append({"case": "unselected ignored source not embedded", "passed": True})
        whitespace = "tsc/owned/baseline with spaces.txt"
        whitespace_archive = temp / "whitespace.tar"
        make_tar(whitespace_archive, [(name, data), (whitespace, b"owned baseline")])
        chosen, _, _ = builder.select_source(
            whitespace_archive,
            {name: builder.sha(data), whitespace: builder.sha(b"owned baseline")},
            selection,
        )
        assert chosen == {name: data}
        checks.append(
            {
                "case": "unselected whitespace fixture paths remain valid archive data",
                "passed": True,
            }
        )
        for label, entries, actual_inventory, actual_selection in [
            (
                "changed bytes",
                [(name, b"changed"), (ignored, b"ignored source")],
                records,
                selection,
            ),
            ("missing selected", [(ignored, b"ignored source")], records, selection),
            (
                "unsafe member",
                [("../owned_test.go", data)],
                {"../owned_test.go": builder.sha(data)},
                {"../owned_test.go": {}},
            ),
            (
                "duplicate archive member",
                [(name, data), (name, data)],
                {name: builder.sha(data)},
                selection,
            ),
            ("nonutf8 selected", [(name, b"\xff")], {name: builder.sha(b"\xff")}, selection),
        ]:
            path = temp / (label.replace(" ", "-") + ".tar")
            make_tar(path, entries)
            checks.append(
                {
                    "case": "reject " + label,
                    "passed": refused(
                        lambda: builder.select_source(path, actual_inventory, actual_selection)
                    ),
                }
            )
        old_bound = builder.MAX_FILE
        try:
            builder.MAX_FILE = 8
            checks.append(
                {
                    "case": "selected per-file byte bound",
                    "passed": refused(lambda: builder.select_source(archive, records, selection)),
                }
            )
        finally:
            builder.MAX_FILE = old_bound
    output = HERE / "constructor-controls.json"
    with output.open("x") as stream:
        json.dump(
            {
                "state": "passed-python-data-controls",
                "passed": len(checks),
                "controls": checks,
                "GoHelperBuiltOrRun": False,
                "upstreamImportsOrExecution": False,
                "nativeCollectionOccurred": False,
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print(json.dumps({"passed": len(checks), "GoHelperBuiltOrRun": False}))


if __name__ == "__main__":
    main()
