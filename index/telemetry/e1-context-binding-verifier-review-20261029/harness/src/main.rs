//! Independent local-fixture API controls; never execute fixture commands.
use dotrepo_core::{
    import_repository_with_options, score_import_fields, verify_import_plan, ImportMode,
    ImportOptions, ImportPlan, VerificationReport,
};
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

const FIELD: &str = "repo.test_candidates.0";
const URL: &str = "https://github.com/keras-team/keras";

struct Fixture(PathBuf);
impl Fixture {
    fn new(base: &Path) -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let path = base.join(format!(
            "fixture-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(path.join("keras/api")).unwrap();
        fs::create_dir_all(path.join("keras/src")).unwrap();
        let source = Path::new(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(4)
            .unwrap()
            .join("crates/dotrepo-core/src/import/commands/context/python_recipe/testdata");
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
                generated_at: Some("2026-10-29T06:00:00Z".into()),
                ..Default::default()
            },
        )
        .unwrap()
    }
}
impl Drop for Fixture {
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
fn rows(plan: &mut ImportPlan) -> Value {
    serde_json::from_str(evidence(plan)["sourceBindingsJson"].as_str().unwrap()).unwrap()
}
fn replace(plan: &mut ImportPlan, value: Value) {
    evidence(plan).insert(
        "sourceBindingsJson".into(),
        toml::Value::String(value.to_string()),
    );
}
fn confidence(plan: &ImportPlan, report: &VerificationReport) -> String {
    score_import_fields(plan, report)
        .scores
        .iter()
        .find(|s| s.field == FIELD)
        .map(|s| format!("{:?}", s.confidence))
        .unwrap_or_else(|| "absent".into())
}
fn observe(root: &Fixture, plan: &ImportPlan) -> Value {
    let report = verify_import_plan(&root.0, plan, URL);
    json!({"verificationPassed": report.passed, "confidence": confidence(plan, &report),
        "checks": report.checks.iter().filter(|c| c.field == FIELD).map(|c| json!({"checkId":c.check_id,"field":c.field,"severity":format!("{:?}",c.severity),"message":c.message})).collect::<Vec<_>>()})
}

fn main() {
    let arguments = std::env::args().skip(1).collect::<Vec<_>>();
    assert_eq!(
        arguments.len(),
        2,
        "arguments: owned-scratch-directory fresh-result.json"
    );
    let base = Path::new(&arguments[0]);
    fs::create_dir(base).unwrap();
    let mut results = Vec::new();
    for case in [
        "baseline-repeated-path-spans",
        "confidence-spoof-stays-medium",
        "semantic-incompleteness-stays-medium",
        "crlf-byte-change",
        "invalid-utf8",
        "directory-source",
        "missing-source",
        "oversized-source",
        "path-parent",
        "path-empty-component",
        "path-control",
        "path-colon",
        "hash-uppercase",
        "range-zero",
        "range-past-end",
        "span-duplicate",
        "attachment-empty",
        "attachment-nonstring",
        "attachment-too-many",
        "attachment-too-large",
        "command-source-unbound",
        "context-source-unbound",
        "tuple-changed",
        "checked-time-changed",
        "missing-generation",
        "absence-preserves-no-score",
    ] {
        let root = Fixture::new(base);
        let mut plan = root.plan();
        let mut bindings = rows(&mut plan);
        match case {
            "baseline-repeated-path-spans" => assert!(bindings.as_array().unwrap().len() > 5),
            "confidence-spoof-stays-medium" => {
                evidence(&mut plan).insert("confidence".into(), toml::Value::String("high".into()));
            }
            "semantic-incompleteness-stays-medium" => {
                plan.manifest.repo.test_candidates[0].context.as_mut().unwrap().prerequisites.push("Synthetic unsupported semantic claim; integrity must not establish completeness".into());
                let value = serde_json::to_string(&plan.manifest.repo.test_candidates[0]).unwrap();
                evidence(&mut plan).insert("valueJson".into(), toml::Value::String(value));
            }
            "crlf-byte-change" => {
                let path = root.0.join("requirements-common.txt");
                let text = fs::read_to_string(&path).unwrap();
                fs::write(path, text.replace('\n', "\r\n")).unwrap();
            }
            "invalid-utf8" => {
                fs::write(root.0.join("requirements-common.txt"), [255, 254]).unwrap()
            }
            "directory-source" => {
                let path = root.0.join("requirements-common.txt");
                fs::remove_file(&path).unwrap();
                fs::create_dir(path).unwrap();
            }
            "missing-source" => fs::remove_file(root.0.join("requirements-common.txt")).unwrap(),
            "oversized-source" => fs::write(
                root.0.join("requirements-common.txt"),
                vec![b'x'; 2 * 1024 * 1024 + 1],
            )
            .unwrap(),
            "path-parent" => {
                bindings[0]["path"] = json!("../README.md");
                replace(&mut plan, bindings);
            }
            "path-empty-component" => {
                bindings[0]["path"] = json!("docs//README.md");
                replace(&mut plan, bindings);
            }
            "path-control" => {
                bindings[0]["path"] = json!("README.md\u{0000}");
                replace(&mut plan, bindings);
            }
            "path-colon" => {
                bindings[0]["path"] = json!("C:README.md");
                replace(&mut plan, bindings);
            }
            "hash-uppercase" => {
                bindings[0]["sha256"] =
                    json!(bindings[0]["sha256"].as_str().unwrap().to_uppercase());
                replace(&mut plan, bindings);
            }
            "range-zero" => {
                bindings[0]["startLine"] = json!(0);
                replace(&mut plan, bindings);
            }
            "range-past-end" => {
                bindings[0]["endLine"] = json!(999999);
                replace(&mut plan, bindings);
            }
            "span-duplicate" => {
                let duplicate = bindings[0].clone();
                bindings.as_array_mut().unwrap().push(duplicate);
                replace(&mut plan, bindings);
            }
            "attachment-empty" => replace(&mut plan, json!([])),
            "attachment-nonstring" => {
                evidence(&mut plan).insert("sourceBindingsJson".into(), toml::Value::Integer(1));
            }
            "attachment-too-many" => {
                replace(&mut plan, Value::Array(vec![bindings[0].clone(); 129]))
            }
            "attachment-too-large" => {
                evidence(&mut plan).insert(
                    "sourceBindingsJson".into(),
                    toml::Value::String(" ".repeat(128 * 1024 + 1)),
                );
            }
            "command-source-unbound" => {
                plan.manifest.repo.test_candidates[0].source = "unbound.txt".into();
                let value = serde_json::to_string(&plan.manifest.repo.test_candidates[0]).unwrap();
                evidence(&mut plan).insert("valueJson".into(), toml::Value::String(value));
            }
            "context-source-unbound" => {
                plan.manifest.repo.test_candidates[0]
                    .context
                    .as_mut()
                    .unwrap()
                    .source = "unbound.txt".into();
                let value = serde_json::to_string(&plan.manifest.repo.test_candidates[0]).unwrap();
                evidence(&mut plan).insert("valueJson".into(), toml::Value::String(value));
                evidence(&mut plan)
                    .insert("source".into(), toml::Value::String("unbound.txt".into()));
            }
            "tuple-changed" => {
                plan.manifest.repo.test_candidates[0].command = "pytest narrowed".into();
            }
            "checked-time-changed" => {
                evidence(&mut plan).insert(
                    "checkedAt".into(),
                    toml::Value::String("2026-10-28T06:00:00Z".into()),
                );
            }
            "missing-generation" => plan.manifest.record.generated_at = None,
            "absence-preserves-no-score" => {
                evidence(&mut plan).remove("sourceBindingsJson");
            }
            _ => unreachable!(),
        }
        let observed = observe(&root, &plan);
        let expected = if case.ends_with("medium") || case == "baseline-repeated-path-spans" {
            "MediumConfidencePresent"
        } else if case == "absence-preserves-no-score" {
            "absent"
        } else {
            "Unresolved"
        };
        assert_eq!(observed["confidence"], expected, "{case}: {observed}");
        results.push(json!({"case": case, "observed": observed, "passed": true}));
    }
    let root = Fixture::new(base);
    let mut plan = root.plan();
    let old_report = verify_import_plan(&root.0, &plan, URL);
    evidence(&mut plan).insert(
        "sourceBindingsJson".into(),
        toml::Value::String("not JSON".into()),
    );
    let stale = confidence(&plan, &old_report);
    let fresh = observe(&root, &plan);
    assert_eq!(stale, "MediumConfidencePresent");
    assert_eq!(fresh["confidence"], "Unresolved");
    results.push(json!({"case":"stale-report-caller-precondition", "staleConfidence":stale, "fresh":fresh, "classification":"documented API limitation, not canonical-flow defect", "passed":true}));
    drop(root);
    assert!(fs::read_dir(base).unwrap().next().is_none());
    fs::remove_dir(base).unwrap();
    let output = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&arguments[1])
        .unwrap();
    serde_json::to_writer_pretty(output, &json!({"independentControls":results,"upstreamExecution":false,"highConfidenceOrCompletenessClaim":false})).unwrap();
}
