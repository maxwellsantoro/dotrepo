"""Frozen snapshot of agent_runtime.limited_process for this qualification packet."""

import os
import selectors
import subprocess
import tempfile
import time


def limited_process(argv, *, data=b"", timeout, output_limit):
    """Bound host capture even when an untrusted container writes indefinitely."""
    host_env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    with tempfile.TemporaryFile() as incoming:
        incoming.write(data)
        incoming.seek(0)
        process = subprocess.Popen(
            argv, stdin=incoming, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=host_env
        )
        selector = selectors.DefaultSelector()
        streams = {process.stdout: bytearray(), process.stderr: bytearray()}
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        deadline, error = time.monotonic() + timeout, None
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    error = "timeout"
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    available = output_limit - sum(map(len, streams.values()))
                    streams[key.fileobj].extend(chunk[:available])
                    if len(chunk) > available:
                        error = "output-limit"
                        break
                if error:
                    break
        finally:
            if error:
                process.kill()
            process.wait(timeout=max(1, deadline - time.monotonic()))
            selector.close()
            for stream in streams:
                stream.close()
        return {
            "stdout": bytes(streams[process.stdout]).decode(errors="replace"),
            "stderr": bytes(streams[process.stderr]).decode(errors="replace"),
            "exitCode": process.returncode,
            "error": error,
        }
