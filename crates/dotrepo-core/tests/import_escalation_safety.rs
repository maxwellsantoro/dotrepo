use dotrepo_core::{
    adjudicate_requests_deterministic, apply_adjudication_results,
    apply_adjudication_to_import_plan, build_adjudication_requests, import_repository,
    run_import_escalation, score_import_fields, verify_import_plan, AdjudicationCandidate,
    AdjudicationModelConfidence, AdjudicationModelResponse, AdjudicationOutcome,
    AdjudicationProvider, AdjudicationProviderResponse, AdjudicationRequest, AdjudicationResult,
    AdjudicationTier, CommandCandidateSelection, CommandSourceTier, FieldConfidence,
    ImportEscalationOptions, ImportMode, ImportedCommandProvenance, StubAdjudicationProvider,
    TieredAdjudicationProviders,
};
use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicUsize, Ordering};

fn workflow_fixture(name: &str, conflicting_tests: bool) -> PathBuf {
    let root = std::env::temp_dir().join(format!("dotrepo-escalation-safety-{name}"));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(root.join("README.md"), "# Example\n\nA project.\n").expect("readme");
    fs::write(
        root.join(".github/workflows/check.yml"),
        "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo test\n",
    )
    .expect("check workflow");
    let mut other = String::from(
        "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    );
    if conflicting_tests {
        other.push_str(
            "  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo test --workspace\n",
        );
    }
    fs::write(root.join(".github/workflows/verify.yml"), other).expect("verify workflow");
    root
}

fn selection_details(
    selection: &Option<CommandCandidateSelection>,
) -> Option<(String, String, CommandSourceTier, ImportedCommandProvenance)> {
    selection.as_ref().map(|selection| {
        (
            selection.command.clone(),
            selection.source_path.clone(),
            selection.source_tier,
            selection.provenance.clone(),
        )
    })
}

#[test]
fn wrong_field_model_response_preserves_known_test_command() {
    let root = workflow_fixture("wrong-field", false);
    let source = "https://github.com/example/wrong-field";
    let mut plan = import_repository(&root, ImportMode::Overlay, Some(source)).expect("import");
    let verification = verify_import_plan(&root, &plan, source);
    let mut scores = score_import_fields(&plan, &verification);
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("cargo test"));
    assert_eq!(build_adjudication_requests(&scores, &plan).len(), 1);
    let selected_test = selection_details(&plan.command_candidates.selected_test);

    let provider = StubAdjudicationProvider::new(
        AdjudicationTier::LocalPrimary,
        vec![AdjudicationProviderResponse {
            response: AdjudicationModelResponse {
                citations: Vec::new(),
                field: "repo.test".into(),
                value: Some("cargo build --workspace".into()),
                confidence: AdjudicationModelConfidence::High,
                reason: "incorrect field in provider response".into(),
                source: Some(".github/workflows/check.yml".into()),
            },
            tokens_used: Some(17),
        }],
    );
    let report = run_import_escalation(
        &root,
        &mut plan,
        &verification,
        &mut scores,
        &ImportEscalationOptions {
            max_adjudication_calls: 1,
            ..Default::default()
        },
        TieredAdjudicationProviders {
            local_primary: Some(&provider),
            local_second_opinion: None,
            api_escalation: None,
        },
    );

    assert_eq!(report.model_calls, 1);
    assert_eq!(report.model_resolved, 0);
    assert_eq!(report.tokens_used, Some(17));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("cargo test"));
    assert_eq!(
        selection_details(&plan.command_candidates.selected_test),
        selected_test
    );
    let test_score = scores
        .scores
        .iter()
        .find(|score| score.field == "repo.test")
        .unwrap();
    assert_eq!(test_score.value.as_deref(), Some("cargo test"));
    assert!(plan.manifest.repo.build.is_none());
    assert_eq!(plan.manifest.repo.build_candidates.len(), 2);
    assert!(verify_import_plan(&root, &plan, source).passed);
    assert!(!plan
        .evidence_text
        .as_deref()
        .unwrap_or_default()
        .contains("Set `repo.test` to `cargo build"));

    fs::remove_dir_all(root).expect("cleanup");
}

#[test]
fn plan_application_rejects_mispaired_results_and_ungrounded_values() {
    let root = workflow_fixture("direct-results", false);
    let source = "https://github.com/example/direct-results";
    let plan = import_repository(&root, ImportMode::Overlay, Some(source)).expect("import");
    let verification = verify_import_plan(&root, &plan, source);
    let scores = score_import_fields(&plan, &verification);
    let requests = build_adjudication_requests(&scores, &plan);
    assert_eq!(requests.len(), 1);
    assert_eq!(requests[0].field, "repo.build");

    let results = [
        AdjudicationResult {
            field: "repo.test".into(),
            outcome: AdjudicationOutcome::Resolved {
                value: requests[0].candidates[0].value.clone(),
                confidence: FieldConfidence::MediumConfidencePresent,
                reason: "forged result field".into(),
            },
        },
        AdjudicationResult {
            field: "repo.test".into(),
            outcome: AdjudicationOutcome::Absent {
                reason: "forged abstention field".into(),
            },
        },
        AdjudicationResult {
            field: "repo.build".into(),
            outcome: AdjudicationOutcome::Resolved {
                value: "cargo build --all-features".into(),
                confidence: FieldConfidence::MediumConfidencePresent,
                reason: "forged result value".into(),
            },
        },
    ];

    for result in results {
        let mut changed = plan.clone();
        apply_adjudication_to_import_plan(&mut changed, &requests, &[result], "test");
        assert_eq!(
            serde_json::to_value(&changed.manifest).unwrap(),
            serde_json::to_value(&plan.manifest).unwrap()
        );
        assert_eq!(changed.evidence_text, plan.evidence_text);
        assert_eq!(
            selection_details(&changed.command_candidates.selected_build),
            selection_details(&plan.command_candidates.selected_build)
        );
        assert_eq!(
            selection_details(&changed.command_candidates.selected_test),
            selection_details(&plan.command_candidates.selected_test)
        );
    }

    fs::remove_dir_all(root).expect("cleanup");
}

#[test]
fn score_application_does_not_overwrite_an_already_resolved_field() {
    let root = workflow_fixture("known-score", false);
    let source = "https://github.com/example/known-score";
    let plan = import_repository(&root, ImportMode::Overlay, Some(source)).expect("import");
    let verification = verify_import_plan(&root, &plan, source);
    let mut scores = score_import_fields(&plan, &verification);
    let test = scores
        .scores
        .iter()
        .find(|score| score.field == "repo.test")
        .unwrap()
        .clone();

    apply_adjudication_results(
        &mut scores,
        &[AdjudicationResult {
            field: "repo.test".into(),
            outcome: AdjudicationOutcome::Resolved {
                value: "cargo build".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                reason: "forged result for a field without a request".into(),
            },
        }],
    );

    let after = scores
        .scores
        .iter()
        .find(|score| score.field == "repo.test")
        .unwrap();
    assert_eq!(after.value, test.value);
    assert_eq!(after.confidence, test.confidence);
    assert_eq!(after.source, test.source);
    assert_eq!(after.reason, test.reason);
    fs::remove_dir_all(root).expect("cleanup");
}

#[test]
fn duplicate_values_use_grounded_provenance_from_strongest_source() {
    let root = workflow_fixture("grounded-provenance", false);
    let source = "https://github.com/example/grounded-provenance";
    let mut plan = import_repository(&root, ImportMode::Overlay, Some(source)).expect("import");
    let requests = [AdjudicationRequest {
        field: "repo.build".into(),
        candidates: vec![
            AdjudicationCandidate {
                context_evidence: None,
                value: "cargo build".into(),
                source_path: ".github/workflows/verify.yml".into(),
                source_tier: CommandSourceTier::Workflow,
            },
            AdjudicationCandidate {
                context_evidence: None,
                value: "cargo build".into(),
                source_path: "Cargo.toml".into(),
                source_tier: CommandSourceTier::Manifest,
            },
        ],
    }];
    let results = adjudicate_requests_deterministic(&requests);
    apply_adjudication_to_import_plan(&mut plan, &requests, &results, "deterministic");

    let selection = plan
        .command_candidates
        .selected_build
        .as_ref()
        .expect("selected build");
    assert_eq!(selection.command, "cargo build");
    assert_eq!(selection.source_path, "Cargo.toml");
    assert_eq!(selection.source_tier, CommandSourceTier::Manifest);
    assert_eq!(selection.provenance, ImportedCommandProvenance::Imported);
    assert!(plan
        .evidence_text
        .as_deref()
        .unwrap_or_default()
        .contains("Set `repo.build` to `cargo build` from `Cargo.toml`"));
    fs::remove_dir_all(root).expect("cleanup");
}

struct FailingProvider {
    tier: AdjudicationTier,
    attempts: AtomicUsize,
}

impl FailingProvider {
    fn new(tier: AdjudicationTier) -> Self {
        Self {
            tier,
            attempts: AtomicUsize::new(0),
        }
    }
}

impl AdjudicationProvider for FailingProvider {
    fn tier(&self) -> AdjudicationTier {
        self.tier
    }

    fn adjudicate(
        &self,
        _request: &AdjudicationRequest,
    ) -> anyhow::Result<AdjudicationProviderResponse> {
        self.attempts.fetch_add(1, Ordering::SeqCst);
        anyhow::bail!("simulated provider timeout")
    }
}

#[test]
fn failed_attempts_share_the_cap_across_tiers_and_fields() {
    for budget in [0, 1, 2, 4] {
        let root = workflow_fixture(&format!("failed-budget-{budget}"), true);
        let source = "https://github.com/example/failed-budget";
        let mut plan = import_repository(&root, ImportMode::Overlay, Some(source)).expect("import");
        let verification = verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);
        assert_eq!(build_adjudication_requests(&scores, &plan).len(), 2);
        let primary = FailingProvider::new(AdjudicationTier::LocalPrimary);
        let second = FailingProvider::new(AdjudicationTier::LocalSecondOpinion);
        let api = FailingProvider::new(AdjudicationTier::ApiEscalation);

        let report = run_import_escalation(
            &root,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions {
                max_adjudication_calls: budget,
                enable_second_opinion: true,
                enable_api_escalation: true,
            },
            TieredAdjudicationProviders {
                local_primary: Some(&primary),
                local_second_opinion: Some(&second),
                api_escalation: Some(&api),
            },
        );

        let actual_attempts = primary.attempts.load(Ordering::SeqCst)
            + second.attempts.load(Ordering::SeqCst)
            + api.attempts.load(Ordering::SeqCst);
        assert_eq!(actual_attempts, budget);
        assert_eq!(report.model_calls, actual_attempts);
        assert_eq!(report.model_resolved, 0);
        assert_eq!(report.tokens_used, (budget == 0).then_some(0));
        assert_eq!(report.tokens_used_known_subtotal, 0);
        assert_eq!(report.unknown_token_usage_calls, budget);
        assert_eq!(report.token_usage_complete, budget == 0);
        for provider in [&primary, &second, &api] {
            assert_eq!(
                report.adjudication_tiers_used.contains(&provider.tier),
                provider.attempts.load(Ordering::SeqCst) > 0
            );
        }
        assert!(plan.manifest.repo.build.is_none());
        assert!(plan.manifest.repo.test.is_none());
        assert_eq!(plan.manifest.repo.build_candidates.len(), 2);
        assert_eq!(plan.manifest.repo.test_candidates.len(), 2);
        assert!(scores.summary.unresolved.is_empty());
        assert!(verify_import_plan(&root, &plan, source).passed);
        fs::remove_dir_all(root).expect("cleanup");
    }
}

#[test]
fn failed_primary_attempt_counts_before_a_successful_second_opinion() {
    let root = workflow_fixture("failed-then-success", false);
    let source = "https://github.com/example/failed-then-success";
    let mut plan = import_repository(&root, ImportMode::Overlay, Some(source)).expect("import");
    let verification = verify_import_plan(&root, &plan, source);
    let mut scores = score_import_fields(&plan, &verification);
    let primary = FailingProvider::new(AdjudicationTier::LocalPrimary);
    let second = StubAdjudicationProvider::new(
        AdjudicationTier::LocalSecondOpinion,
        vec![AdjudicationProviderResponse {
            response: AdjudicationModelResponse {
                citations: Vec::new(),
                field: "repo.build".into(),
                value: Some("cargo build --workspace".into()),
                confidence: AdjudicationModelConfidence::High,
                reason: "grounded second opinion".into(),
                source: Some(".github/workflows/check.yml".into()),
            },
            tokens_used: Some(23),
        }],
    );

    let report = run_import_escalation(
        &root,
        &mut plan,
        &verification,
        &mut scores,
        &ImportEscalationOptions {
            max_adjudication_calls: 2,
            enable_second_opinion: true,
            enable_api_escalation: false,
        },
        TieredAdjudicationProviders {
            local_primary: Some(&primary),
            local_second_opinion: Some(&second),
            api_escalation: None,
        },
    );

    assert_eq!(primary.attempts.load(Ordering::SeqCst), 1);
    assert_eq!(report.model_calls, 2);
    assert_eq!(report.model_resolved, 1);
    assert_eq!(report.tokens_used, None);
    assert_eq!(report.tokens_used_known_subtotal, 23);
    assert_eq!(report.unknown_token_usage_calls, 1);
    assert!(!report.token_usage_complete);
    assert!(report
        .adjudication_tiers_used
        .contains(&AdjudicationTier::LocalPrimary));
    assert!(report
        .adjudication_tiers_used
        .contains(&AdjudicationTier::LocalSecondOpinion));
    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("cargo build --workspace")
    );
    fs::remove_dir_all(root).expect("cleanup");
}

#[test]
fn mixed_native_usage_preserves_subtotal_and_unknown_attempts() {
    for budget in [0, 1, 2, 3] {
        let root = workflow_fixture(&format!("mixed-usage-{budget}"), false);
        let source = "https://github.com/example/mixed-usage";
        let mut plan = import_repository(&root, ImportMode::Overlay, Some(source)).unwrap();
        let verification = verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);
        let provider = |tier, tokens_used| {
            StubAdjudicationProvider::new(
                tier,
                vec![AdjudicationProviderResponse {
                    response: AdjudicationModelResponse {
                        field: "repo.build".into(),
                        value: None,
                        confidence: AdjudicationModelConfidence::Low,
                        reason: "owned low-confidence abstention".into(),
                        source: None,
                        citations: Vec::new(),
                    },
                    tokens_used,
                }],
            )
        };
        let primary = provider(AdjudicationTier::LocalPrimary, Some(120));
        let second = provider(AdjudicationTier::LocalSecondOpinion, None);
        let api = provider(AdjudicationTier::ApiEscalation, Some(0));
        let report = run_import_escalation(
            &root,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions {
                max_adjudication_calls: budget,
                enable_second_opinion: true,
                enable_api_escalation: true,
            },
            TieredAdjudicationProviders {
                local_primary: Some(&primary),
                local_second_opinion: Some(&second),
                api_escalation: Some(&api),
            },
        );
        assert_eq!(report.model_calls, budget);
        assert_eq!(
            report.tokens_used_known_subtotal,
            if budget > 0 { 120 } else { 0 }
        );
        assert_eq!(report.unknown_token_usage_calls, usize::from(budget >= 2));
        assert_eq!(report.token_usage_complete, budget < 2);
        assert_eq!(
            report.tokens_used,
            match budget {
                0 => Some(0),
                1 => Some(120),
                _ => None,
            }
        );
        let wire = serde_json::to_value(&report).unwrap();
        assert_eq!(wire["tokenUsageComplete"], budget < 2);
        assert_eq!(wire["tokensUsed"].is_null(), budget >= 2);
        fs::remove_dir_all(root).unwrap();
    }
}
