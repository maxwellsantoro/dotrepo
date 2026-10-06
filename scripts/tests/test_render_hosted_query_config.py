import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from render_hosted_query_config import render_config  # noqa: E402

CONFIG = Path(__file__).resolve().parents[2] / "cloudflare/hosted-query/wrangler.jsonc"


def test_deployment_config_binds_the_upload_bucket_and_keeps_source_paths() -> None:
    config = render_config(CONFIG, "dotrepo-public-snapshot-archive", require_archive=True)
    assert config["r2_buckets"] == [
        {"binding": "SNAPSHOT_ARCHIVE", "bucket_name": "dotrepo-public-snapshot-archive"}
    ]
    assert Path(config["main"]) == CONFIG.parent / "src/index.mjs"
    assert Path(config["assets"]["directory"]) == CONFIG.parent / "public-snapshot"
    assert config["routes"] == json.loads(CONFIG.read_text())["routes"]


def test_public_deployment_refuses_an_unconfigured_archive() -> None:
    with pytest.raises(ValueError, match="required for public deployment"):
        render_config(CONFIG, "", require_archive=True)
    assert "r2_buckets" not in render_config(CONFIG, None)


@pytest.mark.parametrize("bucket", ["../archive", "Archive", "a", "-archive", "archive-", "x" * 64])
def test_invalid_bucket_names_are_refused(bucket: str) -> None:
    with pytest.raises(ValueError, match="valid R2 bucket"):
        render_config(CONFIG, bucket, require_archive=True)


def test_conflicting_or_unpaired_binding_is_refused(tmp_path: Path) -> None:
    config = json.loads(CONFIG.read_text())
    config["r2_buckets"] = [{"binding": "SNAPSHOT_ARCHIVE", "bucket_name": "existing-bucket"}]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="does not match"):
        render_config(path, "upload-bucket", require_archive=True)
    with pytest.raises(ValueError, match="matching upload bucket"):
        render_config(path, None)
    assert len(render_config(path, "existing-bucket")["r2_buckets"]) == 1
    config["r2_buckets"] *= 2
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="duplicate"):
        render_config(path, "existing-bucket", require_archive=True)
