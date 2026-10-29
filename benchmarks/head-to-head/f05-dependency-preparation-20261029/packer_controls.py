"""Data-only counterexamples for this packet's regular download-cache packer."""

import importlib.util
import io
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bounded_preparation", HERE / "prepare.v3.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample(path, entries):
    with module.tarfile.open(path, mode="w") as archive:
        for name, kind, raw in entries:
            info = module.tarfile.TarInfo(name)
            info.mode, info.size = 0o600, len(raw)
            if kind == "symlink":
                info.type, info.linkname, info.size = module.tarfile.SYMTYPE, raw.decode(), 0
            elif kind == "hardlink":
                info.type, info.linkname, info.size = module.tarfile.LNKTYPE, raw.decode(), 0
            archive.addfile(info, io.BytesIO(raw) if info.isfile() else None)


def main():
    rejected = []
    with tempfile.TemporaryDirectory(
        prefix="packer-controls-", dir="/tmp/dotrepo-f05-dependency-preparation-20261029"
    ) as root:
        root = Path(root)
        good = ("cargo/registry/cache/source.crate", "regular", b"dependency-bytes")
        sample(root / "valid.tar", [good])
        files, expanded, exclusions = module.normalize(
            root / "valid.tar", root / "out.tar", ["cargo/registry"], 1
        )
        assert list(files) == [good[0]] and expanded == len(good[2]) and not exclusions
        for label, entries in {
            "outside-root": [("repository/Cargo.toml", "regular", b"task")],
            "absolute-path": [("/cargo/registry/escape", "regular", b"task")],
            "parent-path": [("cargo/registry/../escape", "regular", b"task")],
            "duplicate-file": [good, good],
            "symlink": [("cargo/registry/link", "symlink", b"source.crate")],
            "hardlink": [("cargo/registry/link", "hardlink", b"cargo/registry/cache/source.crate")],
        }.items():
            source, target = root / (label + ".tar"), root / (label + "-out.tar")
            sample(source, entries)
            try:
                module.normalize(source, target, ["cargo/registry"], 1)
            except AssertionError:
                rejected.append(label)
            else:
                raise AssertionError(f"accepted {label}")
        module.LIMIT = 5
        sample(root / "large.tar", [good])
        try:
            module.normalize(root / "large.tar", root / "large-out.tar", ["cargo/registry"], 1)
        except AssertionError:
            rejected.append("expanded-byte-limit")
        else:
            raise AssertionError("accepted excessive expanded bytes")
    print(
        json.dumps(
            {
                "positiveControls": 1,
                "rejectedCounterexamples": rejected,
                "state": "passed",
                "limits": "Synthetic packer boundary checks only; no member-content audit, source execution or dependency completeness claim.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
