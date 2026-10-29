"""Static independent review of three immutable native qualification leaves."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RESULTS = ROOT / "benchmarks/head-to-head/f05-offline-results-20261029"
PACKET = ROOT / "benchmarks/head-to-head/f05-offline-requalification-20261029"
ACCEPT = ROOT / "benchmarks/head-to-head/f05-offline-acceptance-20261029"
LEAF_HASHES = {
    "rust-02": "d48ccbd478ed8f58fb577428f067000ff460e11068b17fb34122ec5ff462869a",
    "typescript-02": "fbfd63eb670d4571bd68116aa48ba5fdf737e644d789a845741aeaffb60d62a8",
    "go-03": "84c64b53ff2e3e5a4cbdf76650ba9b6642c04f8ebeedb72c22d8134e77c1e027",
}
PLAN_HASH = "2d44b468d8954b42210cce44ae12c2571a835b8a89154d585a20f4cdbbce90e6"
BEFORE_HASH = "ebe024b00217a705ca8425dda1ab6ed01a86be4fc88b9a92fca589214cc27ff6"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(1024**2):
            digest.update(data)
    return digest.hexdigest()


def data_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text())


def good(receipt):
    assert receipt["exitCode"] == 0 and receipt["error"] is None


def receipt(folder, label):
    return load(folder / "logs" / label / "receipt.json")


def text(folder, label, stream="stdout"):
    return (folder / "logs" / label / (stream + ".txt")).read_text()


def main():
    assert sha(PACKET / "plan.v5.json") == PLAN_HASH
    assert sha(RESULTS / "BEFORE.v2.json") == BEFORE_HASH
    plan, before, acceptance = (
        load(PACKET / "plan.v5.json"),
        load(RESULTS / "BEFORE.v2.json"),
        load(ACCEPT / "acceptance.json"),
    )
    checked = []
    for path, digest in before["bindings"].items():
        assert sha(Path(path)) == digest, path
        checked.append({"path": path, "sha256": digest})
    for name, digest in plan["code"].items():
        assert sha(PACKET / name) == digest, name
        checked.append({"path": str(PACKET / name), "sha256": digest})
    for item in plan["frozenMetadata"]:
        assert sha(Path(item["path"])) == item["sha256"], item["path"]
    assert acceptance["planSha256"] == PLAN_HASH and acceptance["imageId"] == plan["imageId"]
    assert acceptance["paidCampaignAuthorized"] is False
    for item in load(ACCEPT / "FREEZE.json")["files"]:
        assert sha(ACCEPT / item["path"]) == item["sha256"]
    prior_image_path = next(
        Path(row["path"])
        for row in plan["frozenMetadata"]
        if row["path"].endswith("image-inspect/stdout.txt")
    )
    prior_image = load(prior_image_path)[0]
    results, archive_bindings = [], []
    previous_finish = None
    for row in before["attempts"]:
        task_id = row["task"]
        leaf, task = RESULTS / task_id, plan["tasks"][task_id]
        freeze_path = RESULTS / (task_id + "-FREEZE.json")
        assert sha(freeze_path) == LEAF_HASHES[task_id]
        freeze = load(freeze_path)
        assert freeze["beforeSha256"] == BEFORE_HASH
        assert {p.relative_to(leaf).as_posix() for p in leaf.rglob("*") if p.is_file()} == set(
            freeze["files"]
        )
        for name, digest in freeze["files"].items():
            assert sha(leaf / name) == digest, (task_id, name)
        receipt_count = 0
        for path in leaf.rglob("receipt.json"):
            r = load(path)
            assert sha(path.with_name("stdout.txt")) == r["stdoutSha256"]
            assert sha(path.with_name("stderr.txt")) == r["stderrSha256"]
            assert r["costUsd"] is None
            if path.relative_to(leaf).parts[0] == "raw":
                good(r)
            receipt_count += 1
        raw = leaf / "raw"
        result, outcome = load(raw / "result.json"), load(leaf / "outcome.json")
        assert outcome["driverResult"] == result
        assert outcome["attempts"] == 1 and outcome["retried"] is False
        outer = receipt(leaf, "driver-invocation")
        good(outer)
        assert outer["argv"] == row["argv"] and outcome["output"] == row["output"]
        started = datetime.fromisoformat(outer["startedAt"])
        if previous_finish is not None:
            assert started >= previous_finish
        previous_finish = datetime.fromisoformat(outcome["recordedAt"])
        binding = load(raw / "acceptance-binding.json")
        assert (
            binding["acceptanceSha256"] == sha(ACCEPT / "acceptance.json")
            and binding["planSha256"] == PLAN_HASH
        )
        for name, item in acceptance["cacheAudits"].items():
            assert sha(Path(item["path"])) == item["sha256"] == binding["auditHashes"][name]
        audit = load(Path(acceptance["cacheAudits"][task_id]["path"]))
        assert audit["state"] == "qualified-download-cache"
        for field in [
            "downloadOnly",
            "buildOutputsExcluded",
            "taskSourceExcluded",
            "credentialsExcluded",
            "protectedEvaluationAliasesExcluded",
        ]:
            assert audit[field] is True
        for item in audit["evidence"]:
            assert sha(ROOT / item["path"]) == item["sha256"]
        assert result["sourceRevision"] == task["revision"] == audit["revision"]
        assert result["imageId"] == plan["imageId"] == audit["imageDigest"]
        for kind in ["source", "cache"]:
            spec = task[kind]
            archive = Path(spec["archive"]["path"])
            assert (
                sha(archive)
                == spec["archive"]["sha256"]
                == result[kind + "ArchiveSha256"]
                == audit[kind + "ArchiveSha256"]
            )
            inventory_path = Path(spec["inventory"]["path"])
            assert sha(inventory_path) == spec["inventory"]["sha256"]
            inventory = load(inventory_path)["files"]
            provision = receipt(raw, kind + "-provision")
            good(provision)
            assert (
                provision["stdinBytes"] == archive.stat().st_size
                and provision["stdinSha256"] == spec["archive"]["sha256"]
            )
            prefix = "/workspace/repository" if kind == "source" else "/workspace/dependency-cache"
            check_data = "".join(
                digest + "  " + prefix + "/" + name + "\n" for name, digest in inventory.items()
            ).encode()
            initial = receipt(raw, "initial-" + kind + "-byte-check")
            good(initial)
            assert initial["stdinSha256"] == data_sha(check_data) and initial["stdinBytes"] == len(
                check_data
            )
            if kind == "source":
                after = receipt(raw, "tracked-source-after-tests")
                good(after)
                assert after["stdinSha256"] == data_sha(check_data)
            archive_bindings.append(
                {
                    "task": task_id,
                    "kind": kind,
                    "path": str(archive),
                    "bytes": archive.stat().st_size,
                    "sha256": spec["archive"]["sha256"],
                    "inventoryFiles": len(inventory),
                }
            )
        assert (
            sha(Path(task["cache"]["draftPreparation"]["path"]))
            == task["cache"]["draftPreparation"]["sha256"]
            == audit["draftPreparationSha256"]
        )
        image, container = (
            load(raw / "logs/image-inspect/stdout.txt")[0],
            load(raw / "logs/container-inspect/stdout.txt")[0],
        )
        assert image["Id"] == prior_image["Id"] == plan["imageId"] == container["Image"]
        assert image["RootFS"] == prior_image["RootFS"] and image["Config"] == prior_image["Config"]
        assert image["Os"] == "linux" and image["Architecture"] == "arm64"
        assert not image["Config"].get("Volumes") and not image["Config"].get("OnBuild")
        assert not container["Mounts"]
        host = container["HostConfig"]
        assert host["NetworkMode"] == "none" and set(container["NetworkSettings"]["Networks"]) == {
            "none"
        }
        assert not host["Privileged"] and host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"]
        assert "no-new-privileges" in host["SecurityOpt"]
        assert host["PidMode"] != "host" and host["IpcMode"] == host["CgroupnsMode"] == "private"
        assert (
            not host["Binds"]
            and not host["VolumesFrom"]
            and not host["Devices"]
            and not host["DeviceRequests"]
        )
        assert (
            host["Memory"] == host["MemorySwap"] == plan["resources"]["memoryBytes"] == 4 * 1024**3
        )
        assert host["NanoCpus"] == 3 * 10**9 and host["PidsLimit"] == 256
        for location, size in [("/workspace", "8g"), ("/tmp", "512m")]:
            assert set(host["Tmpfs"][location].split(",")) == {
                "rw",
                "exec",
                "nosuid",
                "nodev",
                "size=" + size,
                "uid=1000",
                "gid=1000",
                "mode=0700",
            }
        expected_env = dict(v.split("=", 1) for v in image["Config"]["Env"])
        expected_env.update(plan["environment"])
        assert dict(v.split("=", 1) for v in container["Config"]["Env"]) == expected_env
        assert (
            container["Config"]["User"] == "1000:1000"
            and container["Config"]["WorkingDir"] == "/workspace"
        )
        create = receipt(raw, "create")
        good(create)
        name = create["argv"][create["argv"].index("--name") + 1]
        assert name == outcome["ownedContainer"] and container["Name"] == "/" + name
        assert "--pull=never" in create["argv"] and "--network=none" in create["argv"]
        for number, expected in enumerate(task["offlineSetup"]):
            setup = receipt(raw, "offline-setup-" + str(number))
            good(setup)
            assert setup["argv"][-1] == "cd /workspace/repository; " + expected
        native = receipt(raw, "native-tests")
        good(native)
        assert native["argv"][-1] == "cd /workspace/repository; " + task["testCommand"]
        output, error = text(raw, "native-tests"), text(raw, "native-tests", "stderr")
        scope = {}
        if task_id == "rust-02":
            cases = re.findall(r"^test (\S+) \.\.\. (ok|FAILED)$", output, re.M)
            assert sorted(name for name, status in cases) == sorted(
                task["rustDefaultPolicy"]["expectedUnitCaseIds"]
            )
            assert len(cases) == 2 and all(status == "ok" for name, status in cases)
            summaries = re.findall(
                r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out",
                output,
                re.M,
            )
            assert summaries == [("ok", "2", "0", "0", "0", "0"), ("ok", "0", "0", "0", "0", "0")]
            assert len(re.findall(r"^\s*Running unittests src/lib\.rs\b", error, re.M)) == 1
            assert len(re.findall(r"^\s*Doc-tests sniffnet_packet_parser\s*$", error, re.M)) == 1
            assert not re.search(r"^\s*error(?:\[|:)", error, re.M)
            scope = {
                "unitCaseIds": cases,
                "docCases": 0,
                "phaseCoverageComplete": True,
                "defaultFeatureFlagChanged": False,
            }
        elif task_id == "typescript-02":
            report = load(raw / "logs/vitest-native-report/stdout.txt")
            suites = report["testResults"]
            assert (
                len(suites) == 1 and suites[0]["name"] == "/workspace/repository/" + task["suite"]
            )
            cases = suites[0]["assertionResults"]
            assert len(cases) == 2 and sorted(v["title"] for v in cases) == sorted(
                task["expectedTests"]
            )
            assert all(v["status"] == "passed" and not v["failureMessages"] for v in cases)
            assert report["numPassedTests"] == report["numTotalTests"] == 2
            assert (
                report["numFailedTests"] == report["numPendingTests"] == report["numTodoTests"] == 0
            )
            assert "npm run make-i18n && vitest run " + task["suite"] in output
            assert "node scripts/make-i18n-translations.cjs" in output
            assert text(raw, "tools-after-setup").splitlines()[0] == "11.12.1"
            assert "NPM_CONFIG_IGNORE_SCRIPTS" not in expected_env
            scope = {
                "suite": task["suite"],
                "caseTitles": sorted(v["title"] for v in cases),
                "npmVersion": "11.12.1",
                "nativeWrapperAndI18nObserved": True,
                "offlineInstallHooksDisabled": True,
                "onlineNpmCiEquivalenceEstablished": False,
            }
        else:
            listing_receipt = receipt(raw, "native-list")
            good(listing_receipt)
            assert listing_receipt["argv"][-1] == "cd /workspace/repository; " + task["listCommand"]
            listing = [json.loads(v) for v in text(raw, "native-list").splitlines()]
            events = [json.loads(v) for v in output.splitlines()]
            expected = {
                (r["Package"], line)
                for r in listing
                for line in r.get("Output", "").splitlines()
                if re.fullmatch(r"(?:Test|Example|Fuzz)\S+", line)
            }
            ran = {
                (r["Package"], r["Test"]) for r in events if r.get("Test") and r["Action"] == "run"
            }
            passed = {
                (r["Package"], r["Test"]) for r in events if r.get("Test") and r["Action"] == "pass"
            }
            top = {v for v in ran if "/" not in v[1]}
            packages = {r["Package"] for r in events}
            ended = {r["Package"] for r in events if not r.get("Test") and r["Action"] == "pass"}
            assert len(expected) == len(top) == 93 and top == expected and ran == passed
            assert packages == ended == set(task["expectedPackages"])
            assert not any(r["Action"] in ("skip", "fail") for r in events)
            scope = {
                "packages": sorted(packages),
                "topLevelTests": len(top),
                "nestedTestCases": len(ran) - len(top),
                "allRunCasesTerminalPass": True,
                "skipAtAnyDepth": False,
            }
        assert result["testExitCode"] == 0 and result["executionError"] is None
        assert (
            result["taskOutcomeObserved"] is True
            and result["testsPassed"] is True
            and result["trackedSourceIntact"] is True
        )
        assert (
            result["modelCalls"] == 0
            and result["indexConsulted"] is False
            and result["campaignExecuted"] is False
            and result["costUsd"] is None
        )
        assert (
            result["preflightSeconds"] >= 0
            and result["workElapsedSeconds"] < 1800
            and 0 <= result["cleanupSeconds"] < 60
        )
        assert (
            abs(
                result["totalMeasuredOperatorSeconds"]
                - (result["elapsedSeconds"] + result["metadataVerification"]["elapsedSeconds"])
            )
            < 1e-8
        )
        cleanup = receipt(raw, "cleanup")
        good(cleanup)
        assert cleanup["argv"] == ["docker", "rm", "-f", name]
        absent = receipt(leaf, "post-cleanup-owned-inspect")
        assert (
            absent["exitCode"] == 1
            and absent["error"] is None
            and "no such object: " + name
            in text(leaf, "post-cleanup-owned-inspect", "stderr").lower()
        )
        listing = receipt(leaf, "post-cleanup-owned-list")
        good(listing)
        assert not text(leaf, "post-cleanup-owned-list").strip()
        assert (
            result["cleanupAttempted"] is True
            and result["cleanupExitCode"] == 0
            and outcome["postCleanupContainerAbsent"] is True
        )
        all_native_receipts = list((raw / "logs").glob("*/receipt.json"))
        assert result["dockerCalls"] == len(all_native_receipts)
        results.append(
            {
                "task": task_id,
                "leafFreezeSha256": LEAF_HASHES[task_id],
                "verifiedReceiptCount": receipt_count,
                "sourceCacheImageAcceptanceBindings": True,
                "exactIsolationAndResources": True,
                "nativeScope": scope,
                "cleanupAndRetainedIndependentAbsence": True,
                "taskOutcomeQualified": True,
                "testsPassed": True,
                "preflightSeconds": result["preflightSeconds"],
                "nativeTestSeconds": native["elapsedSeconds"],
                "totalMeasuredOperatorSeconds": result["totalMeasuredOperatorSeconds"],
                "costUsd": None,
            }
        )
    print(
        json.dumps(
            {
                "state": "static-native-evidence-qualified-for-three-known-scopes",
                "reviewer": "/root/e1_establishment",
                "priorContext": "Prior F05 curator/runtime development context; separate from execution author, not a blind consumer or second independent gold curator.",
                "planSha256": PLAN_HASH,
                "beforeSha256": BEFORE_HASH,
                "taskResults": results,
                "archiveBindings": archive_bindings,
                "codeAndAcceptanceBindings": checked,
                "noNewDockerCalls": True,
                "noNewUpstreamExecution": True,
                "noNetworkOrProviderCalls": True,
                "consumerBenefitEstablished": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
