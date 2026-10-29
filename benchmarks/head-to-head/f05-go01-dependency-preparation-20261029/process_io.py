"""Bounded host Docker-client byte transport; container workloads stay external."""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import selectors
import subprocess
import time

from boundaries import TRANSPORT_LIMIT, file_sha, require, write

TEXT_LIMIT = 2 * 1024**2


class DockerBackend:
    def command(self, folder, label, argv, *, deadline, stdin_path=None, binary_path=None):
        output = folder / "logs" / label
        output.mkdir(parents=True)
        stamp, start = datetime.now(timezone.utc).isoformat(), time.monotonic()
        incoming, binary = None, None
        digest, sent, received, error, process = hashlib.sha256(), 0, 0, None, None
        captured = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            incoming = Path(stdin_path).open("rb") if stdin_path else None
            binary = Path(binary_path).open("xb") if binary_path else None
            require(time.monotonic() < deadline, "attempt deadline exhausted before subprocess")
            process = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE if incoming else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={key: os.environ[key] for key in ("HOME", "PATH") if key in os.environ},
            )
            selector = selectors.DefaultSelector()
            for stream, role in [(process.stdout, "stdout"), (process.stderr, "stderr")]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, role)
            if incoming:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            pending = b""
            try:
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        error = "attempt deadline exhausted"
                        break
                    for key, _ in selector.select(min(remaining, 0.1)):
                        role = key.data
                        if role == "stdin":
                            if not pending:
                                pending = incoming.read(65536)
                            if not pending:
                                selector.unregister(key.fileobj)
                                key.fileobj.close()
                                continue
                            try:
                                amount = os.write(key.fd, pending)
                            except BrokenPipeError:
                                error = "source input pipe closed early"
                                break
                            digest.update(pending[:amount])
                            sent += amount
                            pending = pending[amount:]
                            continue
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        if role == "stdout" and binary:
                            available = TRANSPORT_LIMIT - received
                            binary.write(chunk[:available])
                            received += min(len(chunk), available)
                            if len(chunk) > available:
                                error = "binary archive transport limit"
                                break
                        else:
                            available = TEXT_LIMIT - sum(len(value) for value in captured.values())
                            captured[role].extend(chunk[:available])
                            if len(chunk) > available:
                                error = "combined text trace limit"
                                break
                    if error:
                        break
            finally:
                if error and process.poll() is None:
                    process.kill()
                process.wait(timeout=max(1, deadline - time.monotonic()))
                selector.close()
                for stream in [process.stdout, process.stderr, process.stdin]:
                    if stream and not stream.closed:
                        stream.close()
        except Exception as failure:
            error = f"{type(failure).__name__}: {failure}"
            if process and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        finally:
            if incoming:
                incoming.close()
            if binary:
                binary.close()
            for role, raw in captured.items():
                (output / f"{role}.bin").write_bytes(raw)
            receipt = {
                "argv": argv,
                "startedAt": stamp,
                "elapsedSeconds": time.monotonic() - start,
                "exitCode": process.returncode if process else None,
                "error": error,
                "stdinBytes": sent,
                "stdinSha256": digest.hexdigest(),
                "stdoutSha256": file_sha(output / "stdout.bin"),
                "stderrSha256": file_sha(output / "stderr.bin"),
                "binaryPath": str(binary_path) if binary_path else None,
                "binaryBytes": received if binary_path else None,
                "binarySha256": file_sha(binary_path)
                if binary_path and Path(binary_path).is_file()
                else None,
                "costUsd": None,
                "costExclusions": [
                    "No metered host/container/download dollar receipt; no provider calls."
                ],
            }
            write(output / "receipt.json", receipt)
        return {
            **receipt,
            "stdout": captured["stdout"].decode(errors="replace"),
            "stderr": captured["stderr"].decode(errors="replace"),
        }
