"""One authorized serialized offline attempt per frozen task; never retry/repair."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from control import HERE, checked, command, write


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            value.update(raw)
    return value.hexdigest()


def main():
    freeze = json.loads((HERE / "BEFORE.v2.json").read_text())
    for path, digest in freeze["bindings"].items():
        assert sha(Path(path)) == digest, path
    for row in freeze["attempts"]:
        task = row["task"]
        folder = HERE / task
        folder.mkdir()
        output = Path(row["output"])
        assert not output.exists()
        call = command(
            folder,
            "driver-invocation",
            row["argv"],
            timeout=1920,
        )
        outcome = {
            "task": task,
            "output": str(output),
            "invocationExitCode": call["exitCode"],
            "invocationError": call["error"],
            "attempts": 1,
            "retried": False,
            "costUsd": None,
            "indexConsulted": False,
            "modelCalls": 0,
        }
        if output.exists():
            shutil.copytree(output, folder / "raw")
            if (output / "result.json").exists():
                outcome["driverResult"] = json.loads((output / "result.json").read_text())
            name = None
            create = output / "logs/create/receipt.json"
            if create.exists():
                argv = json.loads(create.read_text())["argv"]
                name = argv[argv.index("--name") + 1]
            if name:
                inspect = command(folder, "post-cleanup-owned-inspect", ["docker", "inspect", name])
                listing = checked(
                    folder,
                    "post-cleanup-owned-list",
                    [
                        "docker",
                        "ps",
                        "-a",
                        "--filter",
                        "name=" + name,
                        "--format",
                        "{{.Names}} {{.Status}}",
                    ],
                )
                outcome["ownedContainer"] = name
                outcome["postCleanupInspectExitCode"] = inspect["exitCode"]
                outcome["postCleanupContainerAbsent"] = (
                    inspect["exitCode"] != 0 and not listing["stdout"].strip()
                )
            else:
                outcome["postCleanupContainerAbsent"] = None
                outcome["containerCheckExclusion"] = (
                    "No create receipt; no owned container identity available."
                )
        else:
            outcome["driverResult"] = None
            outcome["attemptOutputExclusion"] = (
                "Driver refused before accepted-attempt output; invocation failure retained."
            )
        outcome["recordedAt"] = datetime.now(timezone.utc).isoformat()
        write(folder / "outcome.json", outcome)


if __name__ == "__main__":
    main()
