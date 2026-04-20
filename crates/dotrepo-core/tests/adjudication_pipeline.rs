use dotrepo_core::{
    apply_adjudication_response, apply_adjudication_results, build_adjudication_requests,
    import_repository, score_import_fields, verify_import_plan, AdjudicationCandidate,
    AdjudicationModelConfidence, AdjudicationModelResponse, AdjudicationOutcome,
    AdjudicationRequest, CommandSourceTier, FieldConfidence, ImportMode,
};
use std::fs;

fn temp_dir(name: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("dotrepo-adjudication-test-{}", name));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("temp dir created");
    dir
}

#[test]
fn build_requests_only_includes_unresolved_build_test() {
    let root = temp_dir("adj-unresolved");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Conflict\n\nConflicting workflows.\n",
    )
    .expect("README");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
    ).expect("ci.yml");
    fs::write(
        root.join(".github/workflows/release.yml"),
        "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    ).expect("release.yml");

    let source = "https://github.com/example/conflict";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let requests = build_adjudication_requests(&report, &plan);
    assert!(!requests.is_empty(), "should have unresolved fields");

    for req in &requests {
        assert!(
            req.field == "repo.build" || req.field == "repo.test",
            "request should only be for build/test, got: {}",
            req.field
        );
        assert!(
            !req.candidates.is_empty(),
            "request should have candidates for {}",
            req.field
        );
    }

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn build_requests_empty_when_no_unresolved() {
    let root = temp_dir("adj-no-unresolved");
    fs::write(
        root.join("README.md"),
        "# AutoPub\n\nA well-documented project.\n",
    )
    .expect("README");
    fs::write(
        root.join("Cargo.toml"),
        "[package]\nname = \"autopub\"\nversion = \"0.1.0\"\n",
    )
    .expect("Cargo.toml");

    let source = "https://github.com/example/autopub";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let requests = build_adjudication_requests(&report, &plan);
    assert!(requests.is_empty(), "no unresolved fields, no requests");

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn post_check_accepts_valid_candidate() {
    let request = AdjudicationRequest {
        field: "repo.build".into(),
        candidates: vec![
            AdjudicationCandidate {
                value: "cargo build --workspace".into(),
                source_path: ".github/workflows/ci.yml".into(),
                source_tier: CommandSourceTier::Workflow,
            },
            AdjudicationCandidate {
                value: "cargo build".into(),
                source_path: ".github/workflows/release.yml".into(),
                source_tier: CommandSourceTier::Workflow,
            },
        ],
    };

    let response = AdjudicationModelResponse {
        field: "repo.build".into(),
        value: Some("cargo build --workspace".into()),
        confidence: AdjudicationModelConfidence::Medium,
        reason: "CI workflow runs workspace build as primary".into(),
        source: Some(".github/workflows/ci.yml".into()),
    };

    let result = apply_adjudication_response(&response, &request);
    match result.outcome {
        AdjudicationOutcome::Resolved {
            value,
            confidence,
            reason,
        } => {
            assert_eq!(value, "cargo build --workspace");
            assert_eq!(confidence, FieldConfidence::MediumConfidencePresent);
            assert!(reason.contains("CI workflow"));
        }
        other => panic!("expected Resolved, got {:?}", other),
    }
}

#[test]
fn post_check_rejects_out_of_candidate_value() {
    let request = AdjudicationRequest {
        field: "repo.test".into(),
        candidates: vec![AdjudicationCandidate {
            value: "cargo test".into(),
            source_path: "Cargo.toml".into(),
            source_tier: CommandSourceTier::Manifest,
        }],
    };

    let response = AdjudicationModelResponse {
        field: "repo.test".into(),
        value: Some("cargo test --all-features --release".into()),
        confidence: AdjudicationModelConfidence::Medium,
        reason: "hallucinated command".into(),
        source: None,
    };

    let result = apply_adjudication_response(&response, &request);
    match result.outcome {
        AdjudicationOutcome::Rejected { model_value, .. } => {
            assert_eq!(model_value, "cargo test --all-features --release");
        }
        other => panic!("expected Rejected, got {:?}", other),
    }
}

#[test]
fn post_check_maps_null_to_absent() {
    let request = AdjudicationRequest {
        field: "repo.build".into(),
        candidates: vec![AdjudicationCandidate {
            value: "make build".into(),
            source_path: "Makefile".into(),
            source_tier: CommandSourceTier::TaskScript,
        }],
    };

    let response = AdjudicationModelResponse {
        field: "repo.build".into(),
        value: None,
        confidence: AdjudicationModelConfidence::High,
        reason: "candidates test different sub-crates".into(),
        source: None,
    };

    let result = apply_adjudication_response(&response, &request);
    match result.outcome {
        AdjudicationOutcome::Absent { reason } => {
            assert!(reason.contains("sub-crates"));
        }
        other => panic!("expected Absent, got {:?}", other),
    }
}

#[test]
fn apply_results_updates_scores_and_summary() {
    let root = temp_dir("adj-apply");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Conflict\n\nConflicting workflows.\n",
    )
    .expect("README");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n      - run: cargo test --workspace\n",
    ).expect("ci.yml");
    fs::write(
        root.join(".github/workflows/release.yml"),
        "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n      - run: cargo test\n",
    ).expect("release.yml");

    let source = "https://github.com/example/adjapply";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let mut report = score_import_fields(&plan, &verification);

    assert!(
        !report.summary.unresolved.is_empty(),
        "should start with unresolved fields"
    );

    let requests = build_adjudication_requests(&report, &plan);
    let results: Vec<_> = requests
        .iter()
        .map(|req| {
            let first_value = req.candidates.first().unwrap().value.clone();
            apply_adjudication_response(
                &AdjudicationModelResponse {
                    field: req.field.clone(),
                    value: Some(first_value),
                    confidence: AdjudicationModelConfidence::Medium,
                    reason: "selected first candidate".into(),
                    source: None,
                },
                req,
            )
        })
        .collect();

    apply_adjudication_results(&mut report, &results);

    assert!(
        report.summary.unresolved.is_empty(),
        "unresolved should be empty after adjudication: {:?}",
        report.summary.unresolved
    );

    let build_score = report
        .scores
        .iter()
        .find(|s| s.field == "repo.build")
        .unwrap();
    assert_eq!(
        build_score.confidence,
        FieldConfidence::MediumConfidencePresent
    );

    fs::remove_dir_all(&root).expect("cleanup");
}
