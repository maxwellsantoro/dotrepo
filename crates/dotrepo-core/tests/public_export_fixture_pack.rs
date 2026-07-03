use dotrepo_core::{export_public_index_static, index_snapshot_digest, PublicFreshness};
use serde_json::Value;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("public-export")
}

fn fixture_index_root() -> PathBuf {
    fixture_root().join("fixture-index")
}

fn expected_root() -> PathBuf {
    fixture_root().join("expected").join("public")
}

fn sample_public_freshness() -> PublicFreshness {
    let index_root = fixture_index_root();
    PublicFreshness {
        generated_at: "2026-03-10T18:30:00Z".into(),
        snapshot_digest: index_snapshot_digest(&index_root).expect("snapshot digest"),
        stale_after: Some("2026-03-11T18:30:00Z".into()),
    }
}

fn collect_files(root: &Path, out: &mut Vec<PathBuf>) {
    if !root.is_dir() {
        return;
    }

    let mut entries = fs::read_dir(root)
        .expect("fixture directory is readable")
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .collect::<Vec<_>>();
    entries.sort();

    for path in entries {
        if path.is_dir() {
            collect_files(&path, out);
        } else {
            out.push(path);
        }
    }
}

fn read_tree(root: &Path) -> BTreeMap<String, String> {
    let mut files = Vec::new();
    collect_files(root, &mut files);
    files
        .into_iter()
        .map(|path| {
            (
                path.strip_prefix(root)
                    .expect("expected relative path")
                    .display()
                    .to_string(),
                fs::read_to_string(&path).expect("fixture file is readable"),
            )
        })
        .collect()
}

#[test]
fn public_export_fixture_pack_matches_checked_in_outputs() {
    let expected_root = expected_root();
    let generated = export_public_index_static(
        &fixture_index_root(),
        &expected_root,
        sample_public_freshness(),
    )
    .expect("public export succeeds")
    .into_iter()
    .map(|(path, contents)| {
        (
            path.strip_prefix(&expected_root)
                .expect("generated path stays under expected root")
                .display()
                .to_string(),
            contents,
        )
    })
    .collect::<BTreeMap<_, _>>();

    let expected = read_tree(&expected_root);
    assert_eq!(generated, expected, "public export fixture pack drifted");
}

#[test]
fn public_export_fixture_pack_covers_plain_and_claim_aware_identities() {
    let expected_root = expected_root();
    let generated = export_public_index_static(
        &fixture_index_root(),
        &expected_root,
        sample_public_freshness(),
    )
    .expect("public export succeeds")
    .into_iter()
    .map(|(path, contents)| {
        (
            path.strip_prefix(&expected_root)
                .expect("generated path stays under expected root")
                .display()
                .to_string(),
            contents,
        )
    })
    .collect::<BTreeMap<_, _>>();

    let orbit = serde_json::from_str::<Value>(
        generated
            .get("v0/repos/github.com/example/orbit/index.json")
            .expect("orbit summary output"),
    )
    .expect("orbit summary parses");
    assert_eq!(
        orbit["repository"]["docsRoot"],
        Value::String("https://docs.example.com/orbit".into())
    );
    assert_eq!(
        orbit["repository"]["ownersTeam"],
        Value::String("@example/orbit-team".into())
    );
    assert!(
        orbit["selection"]["record"].get("claim").is_none(),
        "plain overlays should not expose claim context"
    );

    let nova = serde_json::from_str::<Value>(
        generated
            .get("v0/repos/github.com/example/nova/index.json")
            .expect("nova summary output"),
    )
    .expect("nova summary parses");
    assert_eq!(
        nova["selection"]["record"]["claim"]["handoff"],
        Value::String("pending_canonical".into())
    );
    assert_eq!(
        nova["selection"]["record"]["claim"]["state"],
        Value::String("accepted".into())
    );
    assert_eq!(
        nova["selection"]["record"]["claim"]["latestEvent"],
        Value::String(
            "repos/github.com/example/nova/claims/2026-03-10-maintainer-claim-01/events/0002-accepted.toml"
                .into()
        )
    );

    let inventory = serde_json::from_str::<Value>(
        generated
            .get("v0/repos/index.json")
            .expect("inventory output"),
    )
    .expect("inventory parses");
    assert_eq!(inventory["repositoryCount"], Value::from(2));
    let entries = inventory["repositories"]
        .as_array()
        .expect("inventory entries");
    assert!(entries.iter().any(|entry| {
        entry["identity"]["repo"] == Value::String("orbit".into())
            && entry["links"]["self"]
                == Value::String("/v0/repos/github.com/example/orbit/index.json".into())
    }));
    assert!(entries.iter().any(|entry| {
        entry["identity"]["repo"] == Value::String("nova".into())
            && entry["links"]["trust"]
                == Value::String("/v0/repos/github.com/example/nova/trust.json".into())
    }));

    let meta =
        serde_json::from_str::<Value>(generated.get("v0/meta.json").expect("metadata output"))
            .expect("metadata parses");
    assert_eq!(
        meta["validators"]["snapshot"],
        Value::String(format!(
            "sha256:{}",
            meta["snapshotDigest"].as_str().unwrap()
        ))
    );
    assert_eq!(
        meta["validators"]["etag"],
        Value::String(format!(
            "\"dotrepo-v0-{}\"",
            meta["snapshotDigest"].as_str().unwrap()
        ))
    );
    assert_eq!(
        meta["retention"]["edgeGuarantee"],
        Value::String("current_and_previous_snapshot".into())
    );
    assert_eq!(
        meta["retention"]["archiveGuarantee"],
        Value::String("all_published_snapshots_retrievable_from_archive".into())
    );
    assert_eq!(
        meta["paths"]["snapshotLog"],
        Value::String("/v0/snapshots/log.json".into())
    );

    let files = serde_json::from_str::<Value>(
        generated
            .get("v0/files.json")
            .expect("file manifest output"),
    )
    .expect("file manifest parses");
    assert_eq!(files["fileCount"], Value::from(11));
    let file_entries = files["files"].as_array().expect("file manifest entries");
    let snapshot_id = meta["snapshotId"].as_str().expect("snapshot id");
    assert!(file_entries.iter().any(|entry| {
        entry["path"]
            == Value::String(format!(
                "v0/snapshots/{snapshot_id}/repos/github.com/example/orbit/profile.json"
            ))
            && entry["sha256"]
                .as_str()
                .is_some_and(|digest| digest.len() == 64)
    }));
    assert!(file_entries.iter().any(|entry| {
        entry["path"]
            == Value::String(format!(
                "v0/snapshots/{snapshot_id}/repos/github.com/example/orbit/profile.json"
            ))
            && entry["bytes"].as_u64().is_some_and(|bytes| bytes > 0)
    }));
    assert!(file_entries.iter().any(|entry| {
        entry["path"]
            == Value::String(format!(
                "v0/snapshots/{snapshot_id}/repos/github.com/example/orbit/relations.json"
            ))
            && entry["bytes"].as_u64().is_some_and(|bytes| bytes > 0)
    }));

    let log = serde_json::from_str::<Value>(
        generated
            .get("v0/snapshots/log.json")
            .expect("snapshot log output"),
    )
    .expect("snapshot log parses");
    assert_eq!(log["apiVersion"], Value::String("v0".into()));
    assert_eq!(log["snapshotCount"], Value::from(1));
    assert_eq!(
        log["entries"][0]["snapshotId"],
        Value::String(snapshot_id.into())
    );
    assert_eq!(
        log["entries"][0]["snapshotDigest"],
        meta["snapshotDigest"].clone()
    );
    assert_eq!(log["entries"][0]["repositoryCount"], Value::from(2));
    assert_eq!(log["entries"][0]["fileCount"], Value::from(11));

    let orbit_query_input = serde_json::from_str::<Value>(
        generated
            .get("query-input/github.com/example/orbit.json")
            .expect("orbit query-input output"),
    )
    .expect("orbit query-input parses");
    assert_eq!(
        orbit_query_input["identity"]["repo"],
        Value::String("orbit".into())
    );
    assert_eq!(
        orbit_query_input["selection"]["manifest"]["repo"]["description"],
        Value::String("Reviewed orbital tooling metadata.".into())
    );
    let orbit_profile = serde_json::from_str::<Value>(
        generated
            .get("v0/repos/github.com/example/orbit/profile.json")
            .expect("orbit profile output"),
    )
    .expect("orbit profile parses");
    assert_eq!(
        orbit_profile["purpose"],
        Value::String("Reviewed orbital tooling metadata.".into())
    );
    assert_eq!(orbit_profile["completeness"]["hasDocs"], Value::Bool(true));
    assert_eq!(
        orbit_profile["trust"]["selectedStatus"],
        Value::String("reviewed".into())
    );

    let nova_query_input = serde_json::from_str::<Value>(
        generated
            .get("query-input/github.com/example/nova.json")
            .expect("nova query-input output"),
    )
    .expect("nova query-input parses");
    assert_eq!(
        nova_query_input["selection"]["record"]["claim"]["handoff"],
        Value::String("pending_canonical".into())
    );
}
