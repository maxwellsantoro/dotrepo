"""Portable retained-data checks; external full source is opt-in, never executed."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import sys
import tarfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def require(value, reason):
    if not value:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(root, relative):
    parts = Path(relative).parts
    require(
        parts and not Path(relative).is_absolute() and all(p not in {".", ".."} for p in parts),
        "unsafe retained path",
    )
    current = root
    for part in parts:
        current = current / part
        require(not current.is_symlink(), "retained symlink")
    require(stat.S_ISREG(current.lstat().st_mode), "nonregular retained artifact")
    return current.read_bytes()


def module(root, name):
    path = root / "membership" / (name + ".py")
    spec = importlib.util.spec_from_file_location("compose_retained_" + name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def verify_evidence(root, archive=None):
    root = Path(root).resolve()
    manifest = json.loads(read(root, "integration.json"))
    copied = 0
    omitted = []
    for label, packet in manifest["packets"].items():
        freeze_raw = read(root, label + "/FREEZE.json")
        require(digest(freeze_raw) == packet["freezeSha256"], "original freeze changed")
        freeze = json.loads(freeze_raw)
        expected = {"FREEZE.json", *freeze["artifacts"]}
        require(
            set(packet["copiedPaths"]) | set(packet["omittedPaths"]) == expected
            and not set(packet["copiedPaths"]) & set(packet["omittedPaths"]),
            "copy/omission partition",
        )
        for name, binding in freeze["artifacts"].items():
            relative = label + "/" + name
            if name in packet["omittedPaths"]:
                require(
                    label == "acquisition"
                    and (
                        name in {"source.tar", "source.tar.gz"} or name.startswith("objects.git/")
                    ),
                    "unexpected omitted evidence",
                )
                require(not (root / relative).exists(), "external artifact silently included")
                omitted.append(relative)
                continue
            raw = read(root, relative)
            expected_sha = binding if isinstance(binding, str) else binding["sha256"]
            require(digest(raw) == expected_sha, "copied bytes changed: " + relative)
            if isinstance(binding, dict):
                require(len(raw) == binding["bytes"], "copied length changed")
            copied += 1
    require(
        set(omitted) == {r["relativePath"] for r in manifest["externalArtifacts"]}
        and len(omitted) == 9,
        "external omission manifest",
    )
    acquisition = json.loads(read(root, "acquisition/FREEZE.json"))
    for row in manifest["externalArtifacts"]:
        require(
            row["included"] is False and row["relativePath"].startswith("acquisition/"),
            "external artifact disposition",
        )
        require(
            {k: row[k] for k in ["bytes", "sha256"]}
            == acquisition["artifacts"][row["relativePath"].removeprefix("acquisition/")],
            "external binding drift",
        )
    inventory = json.loads(read(root, "membership/acquisition-inventory.json"))
    require(
        read(root, "membership/acquisition-inventory.json")
        == read(root, "acquisition/inventory.json"),
        "inventory copy drift",
    )
    headers = json.loads(read(root, "membership/headers.json"))
    parser = module(root, "inspect_headers")
    selection = module(root, "membership")
    require(len(headers["headers"]) == 407, "header population")
    for row in headers["headers"]:
        raw = read(root, "membership/headers/" + row["path"])
        require(
            digest(raw) == row["headerSha256"] and len(raw) == row["headerBytes"], "header bytes"
        )
        prefix, package, comments = parser.header(raw)
        require(prefix == raw and package == row["package"], "header reparse")
        require(
            re.findall(r"^//go:build (.+)$", comments, re.M) == row["goBuild"]
            and re.findall(r"^// \+build (.+)$", comments, re.M) == row["plusBuild"],
            "constraint metadata",
        )
        require(
            inventory["entries"][row["path"]]["sha256"] == row["sourceSha256"]
            and inventory["entries"][row["path"]]["gitOid"] == row["gitBlobSha1"],
            "header/source metadata binding",
        )
    for row in headers["routing"]:
        raw = read(root, "membership/routing/" + row["path"])
        require(digest(raw) == inventory["entries"][row["path"]]["sha256"], "routing bytes")
    observed = json.loads(read(root, "membership/membership.json"))
    policy = json.loads(read(root, "membership/membership-policy.json"))
    module_path = re.match(r"module ([^\s]+)", read(root, "membership/routing/go.mod").decode())[1]
    expected = observed["representativeContext"]["packages"]
    for arch in observed["architectureLabelsCompared"]:
        require(
            selection.calculate(
                headers["headers"], inventory, arch, module_path, policy["excludedUnitDirectories"]
            )
            == expected,
            "membership rederivation",
        )
    counts = observed["representativeContext"]["counts"]
    require(
        counts
        == {
            "sourceGoDirectories": 39,
            "mainModuleDirectories": 38,
            "prospectiveSelectedDirectories": 37,
            "intendedUnitTestPackages": 27,
            "omittedIntendedUnitTestPackages": 0,
        },
        "conditional counts",
    )
    require(
        sum(len(r["intendedE2eTag"]["test"]) for r in expected if r["intendedUnitDirectory"])
        == 117,
        "conditional unit file count",
    )
    require(
        observed["completeTupleAccepted"] is False
        and observed["nativeCollectionOccurred"] is False,
        "unearned acceptance",
    )
    assessment = json.loads(read(root, "membership/assessment.json"))
    require(
        assessment["tupleDisposition"]["completeApplicableInstructionEstablished"] is False
        and assessment["automaticHighPromotion"] is False,
        "assessment qualification drift",
    )
    full_source = False
    if archive is not None:
        archive = Path(archive)
        expected_archive = next(
            r
            for r in manifest["externalArtifacts"]
            if r["relativePath"] == "acquisition/source.tar"
        )
        require(
            archive.is_file() and not archive.is_symlink(), "explicit archive missing/nonregular"
        )
        require(archive.stat().st_size == expected_archive["bytes"], "external archive length")
        require(digest(archive.read_bytes()) == expected_archive["sha256"], "external archive hash")
        seen = set()
        with tarfile.open(archive, "r:") as source:
            for member in source:
                require(
                    member.name not in seen and member.name in inventory["entries"],
                    "external member identity",
                )
                seen.add(member.name)
                row = inventory["entries"][member.name]
                if member.issym():
                    require(row["mode"] == "120000", "external link mode")
                    raw = member.linkname.encode()
                else:
                    require(
                        member.isfile() and row["mode"] in {"100644", "100755"},
                        "external member type",
                    )
                    require(member.mode & 0o777 == int(row["mode"][-3:], 8), "external member mode")
                    raw = source.extractfile(member).read()
                require(
                    len(raw) == row["bytes"] and digest(raw) == row["sha256"],
                    "external body binding",
                )
                require(
                    hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                    == row["gitOid"],
                    "external Git blob identity",
                )
                if member.name.endswith(".go"):
                    require(
                        raw.startswith(read(root, "membership/headers/" + member.name)),
                        "external header prefix",
                    )
        require(seen == set(inventory["entries"]), "external source missing members")
        full_source = True
    return {
        "state": "retained-data-and-conditional-membership-verified",
        "mode": "explicit-archive" if full_source else "local-only",
        "copiedArtifactsVerified": copied,
        "copiedFreezesVerified": len(manifest["packets"]),
        "headersVerified": 407,
        "conditionalMembershipRederived": True,
        "fullSourceArchiveVerifiedThisRun": full_source,
        "fullSourceMembersVerifiedThisRun": 956 if full_source else 0,
        "externalArtifactsVerifiedThisRun": 1 if full_source else 0,
        "externalArtifactsNotVerifiedThisRun": 8 if full_source else 9,
        "bareGitObjectsVerifiedThisRun": False,
        "gzipVerifiedThisRun": False,
        "completeApplicableInstructionEstablished": False,
        "confidencePromotion": False,
        "heldOutQualification": False,
        "consumerBenefit": False,
        "upstreamExecuted": False,
    }


def verify_wrapper(root):
    freeze = json.loads(read(root, "FREEZE.json"))
    for name, b in freeze["artifacts"].items():
        raw = read(root, name)
        require(
            digest(raw) == b["sha256"] and len(raw) == b["bytes"],
            "integration wrapper artifact changed: " + name,
        )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path)
    args = p.parse_args()
    verify_wrapper(HERE)
    print(json.dumps(verify_evidence(HERE, args.archive), indent=2))


if __name__ == "__main__":
    main()
