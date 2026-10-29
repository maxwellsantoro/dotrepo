use super::*;
use crate::import::{
    import_repository_with_options, score_import_fields, verify_import_plan, FieldConfidence,
    ImportMode, ImportOptions,
};
use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

const FIELD: &str = "repo.test_candidates.0";
const URL: &str = "https://github.com/keras-team/keras";
const TIME: &str = "2026-10-29T06:00:00Z";

struct Root(PathBuf);
impl Root {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "dotrepo-context-binding-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(path.join("keras/api")).unwrap();
        fs::create_dir_all(path.join("keras/src")).unwrap();
        let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("src/import/commands/context/python_recipe/testdata");
        for name in [
            "README.md",
            "CONTRIBUTING.md",
            "pyproject.toml",
            "requirements.txt",
            "requirements-common.txt",
        ] {
            fs::copy(source.join(name), path.join(name)).unwrap();
        }
        Self(path)
    }
    fn plan(&self) -> ImportPlan {
        import_repository_with_options(
            &self.0,
            ImportMode::Overlay,
            Some(URL),
            &ImportOptions {
                generated_at: Some(TIME.to_owned()),
                ..Default::default()
            },
        )
        .unwrap()
    }
}
impl Drop for Root {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

fn evidence(plan: &mut ImportPlan) -> &mut toml::map::Map<String, toml::Value> {
    plan.manifest
        .x
        .get_mut("dotrepo")
        .unwrap()
        .get_mut("field_evidence")
        .unwrap()
        .get_mut(FIELD)
        .unwrap()
        .as_table_mut()
        .unwrap()
}
fn bindings(plan: &mut ImportPlan) -> serde_json::Value {
    serde_json::from_str(evidence(plan)["sourceBindingsJson"].as_str().unwrap()).unwrap()
}
fn set_bindings(plan: &mut ImportPlan, bindings: &serde_json::Value) {
    evidence(plan).insert(
        "sourceBindingsJson".into(),
        toml::Value::String(bindings.to_string()),
    );
}
fn assert_failed(root: &Root, plan: &ImportPlan) {
    let checks = verify(&root.0, plan);
    assert_eq!(checks.len(), 1);
    assert_eq!(checks[0].field, FIELD);
    assert_eq!(
        checks[0].severity,
        VerificationSeverity::Failure,
        "{}",
        checks[0].message
    );
    let report = verify_import_plan(&root.0, plan, URL);
    assert!(!report.passed);
    assert!(!source_bindings_intact(&report, FIELD));
    let scores = score_import_fields(plan, &report);
    assert_eq!(
        scores
            .scores
            .iter()
            .find(|s| s.field == FIELD)
            .unwrap()
            .confidence,
        FieldConfidence::Unresolved
    );
}

#[test]
fn unmodified_real_keras_route_checks_integrity_only_and_stays_medium() {
    let root = Root::new();
    let mut plan = root.plan();
    let attached = bindings(&mut plan);
    assert_eq!(attached.as_array().unwrap().len(), 8);
    assert_eq!(
        attached
            .as_array()
            .unwrap()
            .iter()
            .map(|b| b["path"].as_str().unwrap())
            .collect::<BTreeSet<_>>()
            .len(),
        5
    );
    let checks = verify(&root.0, &plan);
    assert_eq!(checks.len(), 1);
    assert_eq!(checks[0].severity, VerificationSeverity::Pass);
    assert!(checks[0]
        .message
        .contains("completeness remains unresolved"));
    let report = verify_import_plan(&root.0, &plan, URL);
    assert!(report.passed && source_bindings_intact(&report, FIELD));
    let scores = score_import_fields(&plan, &report);
    assert_eq!(
        scores
            .scores
            .iter()
            .find(|s| s.field == FIELD)
            .unwrap()
            .confidence,
        FieldConfidence::MediumConfidencePresent
    );
}

#[test]
fn changed_deleted_or_nonregular_source_after_import_is_unresolved() {
    for kind in ["changed", "deleted", "directory", "oversize"] {
        let root = Root::new();
        let plan = root.plan();
        let path = root.0.join("requirements-common.txt");
        match kind {
            "changed" => fs::write(&path, "pytest\nnew-required-package\n").unwrap(),
            "deleted" => fs::remove_file(&path).unwrap(),
            "directory" => {
                fs::remove_file(&path).unwrap();
                fs::create_dir(&path).unwrap();
            }
            _ => fs::write(
                &path,
                vec![b'x'; super::super::read::MAX_INPUT_BYTES as usize + 1],
            )
            .unwrap(),
        }
        assert_failed(&root, &plan);
    }
}

#[test]
fn malformed_empty_or_excessive_attachment_is_unresolved() {
    for raw in [
        "not JSON".to_owned(),
        "[]".to_owned(),
        "{}".to_owned(),
        "null".to_owned(),
        " ".repeat(MAX_BINDINGS_JSON_BYTES + 1),
    ] {
        let root = Root::new();
        let mut plan = root.plan();
        evidence(&mut plan).insert("sourceBindingsJson".into(), toml::Value::String(raw));
        assert_failed(&root, &plan);
    }
    let root = Root::new();
    let mut plan = root.plan();
    let original = bindings(&mut plan)[0].clone();
    set_bindings(
        &mut plan,
        &serde_json::Value::Array(vec![original; MAX_BINDINGS + 1]),
    );
    assert_failed(&root, &plan);
    let mut plan = root.plan();
    evidence(&mut plan).insert("sourceBindingsJson".into(), toml::Value::Boolean(true));
    assert_failed(&root, &plan);
}

#[test]
fn invalid_row_shapes_paths_hashes_and_spans_are_unresolved() {
    let mutations = [
        ("path", serde_json::json!("../README.md")),
        ("path", serde_json::json!("/README.md")),
        ("path", serde_json::json!("C:\\README.md")),
        ("path", serde_json::json!("docs\\README.md")),
        ("path", serde_json::json!("./README.md")),
        ("path", serde_json::json!("README.md\n")),
        ("sha256", serde_json::json!("0".repeat(64))),
        ("sha256", serde_json::json!("g".repeat(64))),
        ("startLine", serde_json::json!(0)),
        ("startLine", serde_json::json!(-1)),
        ("startLine", serde_json::json!(true)),
        ("startLine", serde_json::json!(999999)),
        ("endLine", serde_json::json!(1)),
        ("endLine", serde_json::json!(999999)),
        ("endLine", serde_json::json!(1.5)),
    ];
    for (key, value) in mutations {
        let root = Root::new();
        let mut plan = root.plan();
        let mut rows = bindings(&mut plan);
        rows[0][key] = value;
        set_bindings(&mut plan, &rows);
        assert_failed(&root, &plan);
    }
    for kind in ["missing-key", "unknown-key", "duplicate"] {
        let root = Root::new();
        let mut plan = root.plan();
        let mut rows = bindings(&mut plan);
        match kind {
            "missing-key" => {
                rows[0].as_object_mut().unwrap().remove("endLine");
            }
            "unknown-key" => {
                rows[0]["extra"] = serde_json::json!("unsupported");
            }
            _ => {
                let row = rows[0].clone();
                rows.as_array_mut().unwrap().push(row);
            }
        }
        set_bindings(&mut plan, &rows);
        assert_failed(&root, &plan);
    }
}

#[test]
fn unrelated_valid_sources_do_not_establish_declared_sources() {
    let root = Root::new();
    let mut plan = root.plan();
    let rows = bindings(&mut plan);
    let unrelated = rows
        .as_array()
        .unwrap()
        .iter()
        .find(|row| row["path"] == "requirements.txt")
        .unwrap()
        .clone();
    set_bindings(&mut plan, &serde_json::json!([unrelated]));
    assert_failed(&root, &plan);
}

#[test]
fn tuple_source_and_time_changes_are_unresolved() {
    for kind in [
        "tuple",
        "context-source",
        "candidate-source",
        "assessment-source",
        "assessment-time",
        "generation-time",
        "missing-generation",
        "bad-value",
    ] {
        let root = Root::new();
        let mut plan = root.plan();
        match kind {
            "tuple" => plan.manifest.repo.test_candidates[0]
                .context
                .as_mut()
                .unwrap()
                .prerequisites
                .push("new unbound setup".into()),
            "context-source" => {
                plan.manifest.repo.test_candidates[0]
                    .context
                    .as_mut()
                    .unwrap()
                    .source = "README.md".into()
            }
            "candidate-source" => plan.manifest.repo.test_candidates[0].source = "README.md".into(),
            "assessment-source" => {
                evidence(&mut plan)
                    .insert("source".into(), toml::Value::String("README.md".into()));
            }
            "assessment-time" => {
                evidence(&mut plan).insert(
                    "checkedAt".into(),
                    toml::Value::String("2026-10-28T06:00:00Z".into()),
                );
            }
            "generation-time" => {
                plan.manifest.record.generated_at = Some("2026-10-28T06:00:00Z".into())
            }
            "missing-generation" => plan.manifest.record.generated_at = None,
            _ => {
                evidence(&mut plan).insert("valueJson".into(), toml::Value::String("{}".into()));
            }
        }
        assert_failed(&root, &plan);
    }
}

#[cfg(unix)]
#[test]
fn symlink_source_leaf_and_ancestor_are_refused_without_following() {
    use std::os::unix::fs::symlink;
    for kind in ["leaf", "ancestor"] {
        let root = Root::new();
        let mut plan = root.plan();
        if kind == "leaf" {
            fs::rename(
                root.0.join("requirements-common.txt"),
                root.0.join("saved.txt"),
            )
            .unwrap();
            symlink("saved.txt", root.0.join("requirements-common.txt")).unwrap();
        } else {
            fs::create_dir(root.0.join("real")).unwrap();
            fs::copy(
                root.0.join("requirements-common.txt"),
                root.0.join("real/requirements-common.txt"),
            )
            .unwrap();
            symlink("real", root.0.join("alias")).unwrap();
            let mut rows = bindings(&mut plan);
            let row = rows
                .as_array_mut()
                .unwrap()
                .iter_mut()
                .find(|row| row["path"] == "requirements-common.txt")
                .unwrap();
            row["path"] = serde_json::json!("alias/requirements-common.txt");
            set_bindings(&mut plan, &rows);
        }
        assert_failed(&root, &plan);
    }
}

#[test]
fn absent_attachment_and_missing_or_conflicting_checks_do_not_create_a_pass() {
    let root = Root::new();
    let mut plan = root.plan();
    let mut missing_check = verify_import_plan(&root.0, &plan, URL);
    missing_check
        .checks
        .retain(|check| check.check_id != format!("{CHECK_PREFIX}{FIELD}"));
    assert!(!source_bindings_intact(&missing_check, FIELD));
    assert_eq!(
        score_import_fields(&plan, &missing_check)
            .scores
            .iter()
            .find(|score| score.field == FIELD)
            .unwrap()
            .confidence,
        FieldConfidence::Unresolved
    );
    evidence(&mut plan).remove("sourceBindingsJson");
    assert!(verify(&root.0, &plan).is_empty());
    let mut report = verify_import_plan(&root.0, &plan, URL);
    assert!(!source_bindings_intact(&report, FIELD));
    assert!(!score_import_fields(&plan, &report)
        .scores
        .iter()
        .any(|score| score.field == FIELD));
    report.checks.push(VerificationCheck {
        check_id: format!("{CHECK_PREFIX}{FIELD}"),
        field: FIELD.into(),
        severity: VerificationSeverity::Pass,
        message: "control".into(),
    });
    assert!(source_bindings_intact(&report, FIELD));
    report.checks.push(VerificationCheck {
        check_id: format!("{CHECK_PREFIX}{FIELD}"),
        field: FIELD.into(),
        severity: VerificationSeverity::Failure,
        message: "control".into(),
    });
    assert!(!source_bindings_intact(&report, FIELD));
}
