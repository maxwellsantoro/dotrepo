"""Offline credential-material markers: report paths/hashes, never secret values."""

import hashlib
import json
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")
PATH_MARKER = re.compile(
    r"(^|/)(?:id_rsa|id_dsa|id_ed25519|client_secrets\.json|credentials[^/]*|[^/]*\.(?:key|p12|pfx)|[^/]*private[^/]*\.pem)$",
    re.I,
)


def main():
    receipt = json.loads((HERE / "export-receipt.json").read_bytes())
    hits = []
    with tarfile.open(receipt["exportPath"], mode="r:") as archive:
        for member in archive:
            if not member.isfile():
                continue
            hasher = hashlib.sha256()
            matched = 0
            tail = b""
            stream = archive.extractfile(member)
            while raw := stream.read(1024**2):
                hasher.update(raw)
                joined = tail + raw
                matched += len(PRIVATE_KEY.findall(joined))
                tail = joined[-80:]
            if matched or PATH_MARKER.search(member.name):
                toolchain = member.name.startswith(("usr/local/go/src/", "usr/local/go/test/"))
                hits.append(
                    {
                        "path": member.name,
                        "sha256": hasher.hexdigest(),
                        "bytes": member.size,
                        "privateKeyMarkersObserved": matched,
                        "pathMarker": bool(PATH_MARKER.search(member.name)),
                        "disposition": "Go toolchain distributed source/test data or documentation, inherited through selected tool image; fixture/example key material, not observed host/user injected credentials. Presence is explicit; no universal credential-absence claim."
                        if toolchain
                        else "Requires individual review; marker/path alone does not establish operational credential.",
                    }
                )
    print(
        json.dumps(
            {
                "method": "PEM private-key begin markers and explicit credential-material filename patterns, streaming all regular bytes; no key values emitted. Marker count may double-count across chunk boundaries; path/hash presence is authoritative.",
                "exportSha256": receipt["exportSha256"],
                "candidates": hits,
                "candidateFiles": len(hits),
                "unclassified": [
                    x["path"] for x in hits if x["disposition"].startswith("Requires")
                ],
                "limitations": [
                    "Packaged public test/example keys can match; markers do not prove an operational credential.",
                    "No general secret detector or arbitrary encoding/substring absence proof.",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
