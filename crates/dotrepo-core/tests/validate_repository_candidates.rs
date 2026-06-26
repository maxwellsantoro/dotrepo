use dotrepo_core::{validate_index_root, validate_repository, IndexFindingSeverity};
use std::fs;
use std::path::PathBuf;

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("dotrepo-validate-candidates-{label}-{unique}"));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

#[test]
fn validate_repository_checks_all_root_candidates() {
    let root = temp_dir("multi-root");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "native-canonical"
description = "Native canonical record"
"#,
    )
    .expect("native manifest written");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "broken-overlay"
description = "Missing overlay trust metadata"
"#,
    )
    .expect("overlay manifest written");

    let report = validate_repository(&root);
    assert!(!report.valid);
    assert_eq!(report.manifest_path.as_deref(), Some(".repo"));
    assert!(
        report
            .diagnostics
            .iter()
            .any(|diagnostic| diagnostic.manifest_path.as_deref() == Some("record.toml")),
        "overlay diagnostics should be attributed to record.toml"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_repository_ignores_descendant_record_candidates() {
    let root = temp_dir("descendant");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "native-canonical"
description = "Native canonical record"
"#,
    )
    .expect("native manifest written");

    let overlay_dir = root.join("index/repos/github.com/acme/widget");
    fs::create_dir_all(&overlay_dir).expect("overlay dir created");
    fs::write(
        overlay_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "broken-overlay"
description = "Missing overlay trust metadata"
"#,
    )
    .expect("overlay manifest written");

    let report = validate_repository(&root);
    assert!(report.valid, "descendant records belong to validate-index");
    assert_eq!(report.manifest_path.as_deref(), Some(".repo"));
    assert!(report.diagnostics.is_empty());

    let index_findings = validate_index_root(&root.join("index")).expect("index validation runs");
    assert!(
        index_findings
            .iter()
            .any(|finding| finding.severity == IndexFindingSeverity::Error),
        "validate-index should still catch invalid descendant records"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}
