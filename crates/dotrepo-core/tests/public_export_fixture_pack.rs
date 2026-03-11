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
    files.into_iter()
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
}
