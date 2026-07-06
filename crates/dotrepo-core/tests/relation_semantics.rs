use dotrepo_core::{public_repository_relations, validate_manifest, PublicFreshness};
use dotrepo_schema::parse_manifest;
use std::fs;
use std::path::{Path, PathBuf};

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-relation-semantics-{label}-{}-{unique}",
        std::process::id()
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

fn record(identity: &str, relation_block: &str) -> String {
    let name = identity.rsplit('/').next().expect("name");
    format!(
        r#"schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "verified"
source = "https://{identity}"

[record.trust]
confidence = "high"
provenance = ["verified"]

[repo]
name = "{name}"
description = "Relation fixture for {name}."

{relation_block}
"#
    )
}

fn write_record(index: &Path, identity: &str, contents: &str) {
    let root = index.join("repos").join(identity);
    fs::create_dir_all(&root).expect("record root created");
    fs::write(root.join("record.toml"), contents).expect("record written");
    fs::write(root.join("evidence.md"), "# Evidence\n").expect("evidence written");
}

const TYPED_RELATIONS: &str = r#"[relations]
references = ["https://github.com/example/nova.git"]

[[relations.links]]
kind = "alternative"
target = "github.com/example/nova"
notes = "A substitutable implementation."
[relations.links.trust]
confidence = "high"
provenance = ["declared"]

[[relations.links]]
kind = "dependency"
target = "github.com/example/nova"
[relations.links.trust]
confidence = "medium"
provenance = ["imported"]

[[relations.links]]
kind = "predecessor"
target = "github.com/example/nova"
[relations.links.trust]
confidence = "high"
provenance = ["declared"]

[[relations.links]]
kind = "fork"
target = "github.com/example/nova"
[relations.links.trust]
confidence = "high"
provenance = ["declared"]

[[relations.links]]
kind = "related"
target = "github.com/example/nova"
[relations.links.trust]
confidence = "low"
provenance = ["inferred"]
"#;

#[test]
fn typed_relations_validate_and_traverse_with_semantic_inverses() {
    let index = temp_dir("traversal");
    write_record(
        &index,
        "github.com/example/orbit",
        &record("github.com/example/orbit", TYPED_RELATIONS),
    );
    write_record(
        &index,
        "github.com/example/nova",
        &record("github.com/example/nova", ""),
    );
    let freshness = PublicFreshness {
        generated_at: "2026-06-28T12:00:00Z".into(),
        snapshot_digest: "fixture".into(),
        stale_after: None,
    };

    let outgoing =
        public_repository_relations(&index, "github.com", "example", "orbit", freshness.clone())
            .expect("outgoing traversal succeeds");
    let outgoing_names = outgoing
        .references
        .iter()
        .map(|item| item.relationship.as_str())
        .collect::<Vec<_>>();
    assert_eq!(
        outgoing_names,
        [
            "alternative",
            "dependency",
            "fork",
            "predecessor",
            "reference",
            "related"
        ]
    );
    assert!(outgoing
        .references
        .iter()
        .all(|item| item.profile.is_some()));
    let dependency = outgoing
        .references
        .iter()
        .find(|item| item.relationship == "dependency")
        .expect("dependency relation");
    assert_eq!(
        dependency
            .trust
            .as_ref()
            .and_then(|trust| trust.confidence.as_deref()),
        Some("medium")
    );
    assert_eq!(
        dependency
            .trust
            .as_ref()
            .map(|trust| trust.provenance.clone()),
        Some(vec!["imported".to_string()])
    );

    let incoming = public_repository_relations(&index, "github.com", "example", "nova", freshness)
        .expect("incoming traversal succeeds");
    let incoming_names = incoming
        .references
        .iter()
        .map(|item| item.relationship.as_str())
        .collect::<Vec<_>>();
    assert_eq!(
        incoming_names,
        [
            "alternative",
            "depended_on_by",
            "forked_by",
            "referenced_by",
            "related",
            "successor"
        ]
    );

    fs::remove_dir_all(index).expect("temp dir removed");
}

#[test]
fn typed_relations_require_valid_identity_and_independent_trust() {
    let manifest = parse_manifest(&record(
        "github.com/example/orbit",
        r#"[[relations.links]]
kind = "dependency"
target = "../escape"
[relations.links.trust]
provenance = []
"#,
    ))
    .expect("manifest parses");
    let root = temp_dir("validation");

    let error = validate_manifest(&root, &manifest).expect_err("invalid relation rejected");
    let message = error.to_string();
    assert!(message.contains("relations.links[0].target"));
    assert!(message.contains("trust.confidence"));
    assert!(message.contains("trust.provenance"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn github_relation_identity_resolution_is_case_insensitive_across_filesystems() {
    let index = temp_dir("case-insensitive");
    write_record(
        &index,
        "github.com/example/Source",
        &record(
            "github.com/example/Source",
            r#"[[relations.links]]
kind = "related"
target = "github.com/example/target"
[relations.links.trust]
confidence = "high"
provenance = ["declared"]
"#,
        ),
    );
    write_record(
        &index,
        "github.com/example/Target",
        &record("github.com/example/Target", ""),
    );
    let freshness = PublicFreshness {
        generated_at: "2026-06-28T12:00:00Z".into(),
        snapshot_digest: "fixture".into(),
        stale_after: None,
    };

    let outgoing =
        public_repository_relations(&index, "github.com", "example", "Source", freshness.clone())
            .expect("case-insensitive outgoing traversal succeeds");
    let related = outgoing.references.first().expect("outgoing relation");
    assert!(related.error.is_none());
    assert!(related.profile.is_some());

    let incoming =
        public_repository_relations(&index, "github.com", "example", "Target", freshness)
            .expect("case-insensitive incoming traversal succeeds");
    assert_eq!(incoming.references.len(), 1);
    assert_eq!(incoming.references[0].direction, "incoming");
    assert_eq!(incoming.references[0].relationship, "related");

    fs::remove_dir_all(index).expect("temp dir removed");
}
