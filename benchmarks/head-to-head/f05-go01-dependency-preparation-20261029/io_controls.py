"""Exercise byte transport with tiny owned uv emitters, never Docker/network."""

from pathlib import Path
import tempfile
import time

from boundaries import file_sha, require, sha, write
import process_io

HERE = Path(__file__).resolve().parent


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="io-synthetic-", dir=HERE) as temp:
        root = Path(temp)
        backend = process_io.DockerBackend()
        old_text, old_binary = process_io.TEXT_LIMIT, process_io.TRANSPORT_LIMIT
        process_io.TEXT_LIMIT = process_io.TRANSPORT_LIMIT = 16
        try:
            source = root / "source"
            source.write_bytes(b"fixture")
            samples = [
                (
                    "input",
                    "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())",
                    {"stdin_path": source},
                ),
                ("text", "import sys;sys.stdout.buffer.write(b'x'*100)", {}),
                ("stderr", "import sys;sys.stderr.buffer.write(b'x'*100)", {}),
                (
                    "binary",
                    "import sys;sys.stdout.buffer.write(b'x'*100)",
                    {"binary_path": root / "binary.tar"},
                ),
                ("timeout", "import time;time.sleep(10)", {}),
                ("missing-input", "pass", {"stdin_path": root / "absent"}),
                ("raw-bytes", "import sys;sys.stdout.buffer.write(bytes([255]))", {}),
            ]
            for name, script, kwargs in samples:
                result = backend.command(
                    root,
                    name,
                    ["uv", "run", "--offline", "--no-sync", "python", "-c", script],
                    deadline=time.monotonic() + (0.2 if name == "timeout" else 5),
                    **kwargs,
                )
                folder = root / "logs" / name
                require((folder / "receipt.json").is_file(), "lost command failure receipt")
                for role in ["stdout", "stderr"]:
                    require(
                        file_sha(folder / f"{role}.bin") == result[f"{role}Sha256"],
                        "lost raw byte binding",
                    )
                if name == "input":
                    require(
                        result["exitCode"] == 0
                        and result["error"] is None
                        and result["stdinSha256"] == sha(b"fixture")
                        and result["stdinBytes"] == 7,
                        "input transport",
                    )
                elif name == "raw-bytes":
                    require((folder / "stdout.bin").read_bytes() == b"\xff", "raw bytes normalized")
                else:
                    require(result["error"] is not None, "missing boundary refusal")
                if name == "binary":
                    require(
                        (root / "binary.tar").stat().st_size == 16 and result["binaryBytes"] == 16,
                        "binary cap",
                    )
                require(result["costUsd"] is None, "fabricated zero cost")
                results.append(
                    {
                        "case": name,
                        "error": result["error"],
                        "exitCode": result["exitCode"],
                        "rawBindingsChecked": True,
                        "passed": True,
                    }
                )
        finally:
            process_io.TEXT_LIMIT, process_io.TRANSPORT_LIMIT = old_text, old_binary
    write(
        HERE / "io-controls.json",
        {
            "controls": results,
            "passed": len(results),
            "workload": "tiny owned uv byte emitters only; synthetic caps lowered to16bytes",
            "DockerNetworkNativeTaskProviderCalls": 0,
            "actualPreparationOccurred": False,
        },
    )


if __name__ == "__main__":
    main()
