"""Read selected frozen package members as data; never extract or execute packages."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
CACHE = Path("/private/tmp/dotrepo-go01-dependency-download-cache-20261029-1/cache.tar")


def read_selected(package_index, names):
    declaration = json.loads((HERE / "identities.json").read_text())
    row = declaration["packages"][package_index]
    with tarfile.open(CACHE, "r:") as outer:
        member = outer.getmember(row["cachePath"])
        assert member.isfile() and member.size == row["tarballBytes"] <= 33554432
        compressed = outer.extractfile(member).read(member.size + 1)
    assert hashlib.sha256(compressed).hexdigest() == row["tarballSha256"]
    result = {}
    seen = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(compressed), mode="r:gz") as package:
        for number, member in enumerate(package):
            assert number < 10000
            parts = member.name.split("/")
            assert not member.name.startswith("/") and all(x not in ("", ".", "..") for x in parts)
            assert "\\" not in member.name and ":" not in member.name
            assert member.name not in seen
            seen.add(member.name)
            assert member.isfile() or member.isdir()
            total += member.size
            assert total <= 33554432 and member.size <= 2097152
            if member.name in names:
                assert member.isfile()
                data = package.extractfile(member).read(member.size + 1)
                assert len(data) == member.size
                result[member.name] = {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "text": data.decode("utf-8"),
                }
    assert set(result) == set(names)
    return {
        "packageLockPath": row["lockPath"],
        "version": row["version"],
        "tarballSha256": row["tarballSha256"],
        "members": result,
        "executionOccurred": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_index", type=int, choices=range(3))
    parser.add_argument("output")
    parser.add_argument("members", nargs="+")
    args = parser.parse_args()
    output = HERE / args.output
    assert output.parent == HERE
    with output.open("x") as stream:
        json.dump(read_selected(args.package_index, args.members), stream, indent=2, sort_keys=True)
        stream.write("\n")
