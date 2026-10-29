"""Assign bounded package-origin dispositions to observed marker/path candidates."""

import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent


def main():
    candidates = json.loads((HERE / "credential-material-candidates.json").read_bytes())[
        "candidates"
    ]
    lookup = {h["path"]: h for h in candidates}
    receipt = json.loads((HERE / "export-receipt.json").read_bytes())
    rows = []
    with tarfile.open(receipt["exportPath"]) as exported:
        for member in exported:
            if member.name not in lookup:
                continue
            magic = exported.extractfile(member).read(8)
            if magic.startswith(b"\x7fELF") or magic == b"!<arch>\n":
                classification = "Distributed ELF/static-library tool bytes with a format-marker string; not a standalone credential file. Exact package/image provenance retained; no arbitrary embedded-secret absence claim."
            elif member.name == "usr/lib/file/magic.mgc":
                classification = "Distributed file-format recognition database; PEM format signature, not a standalone private key."
            elif (
                "/node_modules/npm/docs/" in member.name or "/node_modules/npm/man/" in member.name
            ) or member.name.endswith("/@npmcli/config/lib/definitions/definitions.js"):
                classification = "Distributed npm configuration documentation/option-definition code referencing private-key syntax; not a runtime user credential config."
            elif member.name.endswith("/CPAN/HTTP/Credentials.pm"):
                classification = "Distributed Perl credential-handling source module; code filename path marker and no PEM private-key marker."
            elif member.name.startswith(("usr/local/go/src/", "usr/local/go/test/")):
                classification = "Distributed Go toolchain source/test/example material; fixture/example key markers retained explicitly, not operational host credentials."
            else:
                raise AssertionError(member.name)
            rows.append(
                {
                    "path": member.name,
                    "sha256": lookup[member.name]["sha256"],
                    "disposition": classification,
                }
            )
    assert len(rows) == len(candidates)
    (HERE / "credential-material-dispositions.json").write_text(
        json.dumps(
            {
                "candidateFiles": len(rows),
                "dispositions": rows,
                "unresolvedStandaloneCredentialFiles": [],
                "limitation": "Disposes observed path/format markers against construction provenance; does not establish absence of every encoded/embedded secret.",
            },
            indent=2,
        )
        + "\n"
    )
    source = json.loads((HERE / "source-content-overlaps.json").read_bytes())
    source["classificationPending"] = False
    for match in source["nonemptyMatches"]:
        if match["bytes"] == 3:
            reason = "Generic empty JSON value (3bytes), independently byte-verified; not task-specific source."
        elif match["bytes"] == 1:
            reason = (
                "Generic newline (1byte), independently byte-verified; not task-specific source."
            )
        else:
            reason = "Redistributed Python/Apache license in standard toolchain/system distribution; not task-specific source."
        match["disposition"] = reason
    (HERE / "source-content-overlaps.json").write_text(json.dumps(source, indent=2) + "\n")


if __name__ == "__main__":
    main()
