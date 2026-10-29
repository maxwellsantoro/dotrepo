"""Prospective source-free interpreter metadata probe; stdlib only, no task imports."""

import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import sysconfig


def main():
    binary = Path(sys.executable)
    value = {
        "schema": "owned-python-interpreter-probe-v1",
        "version": list(sys.version_info),
        "versionText": sys.version,
        "executable": str(binary),
        "executableSha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "baseExecutable": getattr(sys, "_base_executable", None),
        "prefix": sys.prefix,
        "basePrefix": sys.base_prefix,
        "platform": sys.platform,
        "platformTag": sysconfig.get_platform(),
        "soabi": sysconfig.get_config_var("SOABI"),
        "openssl": ssl.OPENSSL_VERSION,
        "isolated": sys.flags.isolated,
        "noSite": sys.flags.no_site,
        "sysPath": sys.path,
        "configurationEnvironment": {
            k: os.environ.get(k) for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PYTHON")
        },
        "targetImportsPerformed": False,
    }
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()
