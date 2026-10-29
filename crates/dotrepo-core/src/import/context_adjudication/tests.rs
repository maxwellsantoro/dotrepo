use super::*;
use crate::import::{
    import_repository_with_options, score_import_fields, verify_import_plan,
    AdjudicationModelConfidence, AdjudicationProvider, AdjudicationProviderResponse,
    AdjudicationTier, ImportEscalationOptions, ImportMode, ImportOptions,
    TieredAdjudicationProviders,
};
use dotrepo_schema::{BuildTestCandidate, ExecutionContext, ExecutionScope};
use std::fs;
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Mutex,
};

struct Root(PathBuf);
impl Root {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "dotrepo-context-adjudication-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&path).unwrap();
        fs::write(path.join("README.md"), "# Example\n\nExample repository.\n").unwrap();
        fs::write(
            path.join("CONTRIBUTING.md"),
            "Prerequisites: Rust 1.90.\nRun cargo test at the root.\n",
        )
        .unwrap();
        Self(path)
    }
    fn plan(&self) -> ImportPlan {
        let mut plan = import_repository_with_options(
            &self.0,
            ImportMode::Overlay,
            Some("https://github.com/example/synthetic-context"),
            &ImportOptions {
                generated_at: Some("2026-10-29T00:00:00Z".into()),
                ..Default::default()
            },
        )
        .unwrap();
        plan.imported_sources.push("CONTRIBUTING.md".into());
        plan.manifest.repo.test_candidates = vec![BuildTestCandidate {
            command: "cargo test".into(),
            ecosystem: Some("Rust".into()),
            source: "CONTRIBUTING.md".into(),
            context: Some(ExecutionContext {
                command: "cargo test".into(),
                working_directory: ".".into(),
                scope: ExecutionScope::Repository,
                component: None,
                prerequisites: vec!["Rust 1.90".into()],
                source: "CONTRIBUTING.md".into(),
            }),
        }];
        plan
    }
}
impl Drop for Root {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn response(request: &AdjudicationRequest) -> AdjudicationModelResponse {
    let candidate = &request.candidates[0];
    AdjudicationModelResponse {
        field: request.field.clone(),
        value: Some(candidate.value.clone()),
        source: Some(candidate.source_path.clone()),
        confidence: AdjudicationModelConfidence::High,
        reason: "synthetic source selection".into(),
        citations: candidate
            .context_evidence
            .as_ref()
            .unwrap()
            .sources
            .iter()
            .map(|source| source.citation_id.clone())
            .collect(),
    }
}
fn attach(plan: &mut ImportPlan, raw: &str) {
    let candidate = &plan.manifest.repo.test_candidates[0];
    let value = toml::Value::Table(toml::map::Map::from_iter([
        (
            "valueJson".into(),
            serde_json::to_string(candidate).unwrap().into(),
        ),
        ("source".into(), "CONTRIBUTING.md".into()),
        (
            "checkedAt".into(),
            plan.manifest.record.generated_at.clone().unwrap().into(),
        ),
        ("sourceBindingsJson".into(), raw.into()),
    ]));
    plan.manifest.x.insert(
        "dotrepo".into(),
        toml::Value::Table(toml::map::Map::from_iter([(
            "field_evidence".into(),
            toml::Value::Table(toml::map::Map::from_iter([(
                "repo.test_candidates.0".into(),
                value,
            )])),
        )])),
    );
}
fn is_resolved(result: AdjudicationResult) -> bool {
    matches!(
        result.outcome,
        AdjudicationOutcome::Resolved {
            confidence: FieldConfidence::MediumConfidencePresent,
            ..
        }
    )
}

#[test]
fn context_request_retains_exact_tuple_bytes_and_explicit_unknowns() {
    let root = Root::new();
    let plan = root.plan();
    let request = requests(&root.0, &plan).remove(0);
    let evidence = request.candidates[0].context_evidence.as_ref().unwrap();
    assert_eq!(
        evidence.tuple_json,
        serde_json::to_string(&plan.manifest.repo.test_candidates[0]).unwrap()
    );
    assert_eq!(
        evidence.sources[0].body.as_bytes(),
        fs::read(root.0.join("CONTRIBUTING.md")).unwrap()
    );
    assert_eq!(
        evidence.sources[0].whole_file_sha256,
        digest(&evidence.sources[0].body)
    );
    assert!(evidence.source_revision.is_none());
    assert!(evidence.revision_state.contains("unknown"));
    assert!(evidence
        .limitations
        .iter()
        .any(|text| text.contains("does not prove absent")));
    assert!(is_resolved(apply(&response(&request), &request)));
}

#[test]
fn tuple_and_citation_mutations_are_rejected_and_abstention_is_not_absence() {
    let root = Root::new();
    let request = requests(&root.0, &root.plan()).remove(0);
    for pointer in [
        "/command",
        "/context/command",
        "/context/working_directory",
        "/context/scope",
        "/context/prerequisites",
    ] {
        let mut answer = response(&request);
        let mut tuple: serde_json::Value =
            serde_json::from_str(answer.value.as_ref().unwrap()).unwrap();
        *tuple.pointer_mut(pointer).unwrap() = serde_json::json!("mutated");
        answer.value = Some(tuple.to_string());
        assert!(!is_resolved(apply(&answer, &request)), "{pointer}");
    }
    let mut low = response(&request);
    low.confidence = AdjudicationModelConfidence::Low;
    assert!(!is_resolved(apply(&low, &request)));
    for mode in 0..4 {
        let mut answer = response(&request);
        match mode {
            0 => answer.citations.clear(),
            1 => answer.citations.push(answer.citations[0].clone()),
            2 => answer.citations[0] = "invented".into(),
            _ => answer.source = Some("other.md".into()),
        };
        assert!(!is_resolved(apply(&answer, &request)));
    }
    let mut answer = response(&request);
    answer.value = None;
    answer.source = None;
    answer.citations.clear();
    assert!(matches!(
        apply(&answer, &request).outcome,
        AdjudicationOutcome::Rejected { .. }
    ));
}

#[test]
fn missing_malformed_changed_and_oversized_sources_disclose_and_refuse_selection() {
    let root = Root::new();
    let mut plan = root.plan();
    for raw in [
        "[]",
        "not JSON",
        r#"[{"path":"../outside","sha256":"bad","startLine":1,"endLine":2}]"#,
        r#"[{"path":"CONTRIBUTING.md","sha256":"","startLine":1,"endLine":2}]"#,
    ] {
        attach(&mut plan, raw);
        let request = requests(&root.0, &plan).remove(0);
        assert!(!request.candidates[0]
            .context_evidence
            .as_ref()
            .unwrap()
            .omissions
            .is_empty());
        assert!(!is_resolved(apply(&response(&request), &request)));
    }
    let raw = serde_json::json!([{"path":"CONTRIBUTING.md","sha256":digest("old source\n"),"startLine":1,"endLine":1}]).to_string();
    attach(&mut plan, &raw);
    assert!(!is_resolved(apply(
        &response(&requests(&root.0, &plan)[0]),
        &requests(&root.0, &plan)[0]
    )));
    let plan = root.plan();
    fs::remove_file(root.0.join("CONTRIBUTING.md")).unwrap();
    let request = requests(&root.0, &plan).remove(0);
    assert!(!is_resolved(apply(&response(&request), &request)));
    fs::write(
        root.0.join("CONTRIBUTING.md"),
        "x".repeat(MAX_BODY_BYTES + 1),
    )
    .unwrap();
    let request = requests(&root.0, &plan).remove(0);
    assert!(!is_resolved(apply(&response(&request), &request)));
    fs::write(
        root.0.join("CONTRIBUTING.md"),
        "x".repeat(2 * 1024 * 1024 + 1),
    )
    .unwrap();
    let request = requests(&root.0, &plan).remove(0);
    assert!(!is_resolved(apply(&response(&request), &request)));
}

#[cfg(unix)]
#[test]
fn source_reader_rejects_leaf_and_ancestor_symlinks() {
    let root = Root::new();
    let mut plan = root.plan();
    fs::rename(root.0.join("CONTRIBUTING.md"), root.0.join("real.md")).unwrap();
    std::os::unix::fs::symlink("real.md", root.0.join("CONTRIBUTING.md")).unwrap();
    let request = requests(&root.0, &plan).remove(0);
    assert!(!is_resolved(apply(&response(&request), &request)));
    fs::create_dir(root.0.join("real")).unwrap();
    fs::write(root.0.join("real/source.md"), "source\n").unwrap();
    std::os::unix::fs::symlink("real", root.0.join("linked")).unwrap();
    let candidate = &mut plan.manifest.repo.test_candidates[0];
    candidate.source = "linked/source.md".into();
    candidate.context.as_mut().unwrap().source = candidate.source.clone();
    plan.imported_sources.push("linked/source.md".into());
    let request = requests(&root.0, &plan).remove(0);
    assert!(!is_resolved(apply(&response(&request), &request)));
}

#[test]
fn evidence_mutation_and_retained_source_caps_are_checked() {
    let root = Root::new();
    let plan = root.plan();
    let mut request = requests(&root.0, &plan).remove(0);
    request.candidates[0]
        .context_evidence
        .as_mut()
        .unwrap()
        .sources[0]
        .body
        .push_str("mutated");
    assert!(!is_resolved(apply(&response(&request), &request)));
    let mut plan = root.plan();
    plan.manifest.repo.test_candidates =
        vec![plan.manifest.repo.test_candidates[0].clone(); MAX_REQUESTS + 2];
    assert_eq!(requests(&root.0, &plan).len(), MAX_REQUESTS);
}

struct RecordingProvider {
    seen: Mutex<Vec<AdjudicationRequest>>,
}
impl AdjudicationProvider for RecordingProvider {
    fn tier(&self) -> AdjudicationTier {
        AdjudicationTier::LocalPrimary
    }
    fn adjudicate(
        &self,
        request: &AdjudicationRequest,
    ) -> anyhow::Result<AdjudicationProviderResponse> {
        self.seen.lock().unwrap().push(request.clone());
        Ok(AdjudicationProviderResponse {
            response: response(request),
            tokens_used: Some(7),
        })
    }
}
#[test]
fn actual_ladder_transports_context_under_budget_without_scalar_or_conflict_promotion() {
    for budget in [0, 1, 2] {
        let root = Root::new();
        let mut plan = root.plan();
        let mut component = plan.manifest.repo.test_candidates[0].clone();
        let context = component.context.as_mut().unwrap();
        context.scope = ExecutionScope::Component;
        context.component = Some("engine".into());
        context.working_directory = "engine".into();
        plan.manifest.repo.test_candidates.push(component);
        let original = plan.manifest.repo.test_candidates.clone();
        let original_scalar = plan.manifest.repo.test.clone();
        let original_status = plan.manifest.record.status.clone();
        let verification = verify_import_plan(
            &root.0,
            &plan,
            "https://github.com/example/synthetic-context",
        );
        let mut scores = score_import_fields(&plan, &verification);
        let provider = RecordingProvider {
            seen: Mutex::new(Vec::new()),
        };
        let report = crate::import::run_import_escalation(
            &root.0,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions {
                max_adjudication_calls: budget,
                ..Default::default()
            },
            TieredAdjudicationProviders {
                local_primary: Some(&provider),
                local_second_opinion: None,
                api_escalation: None,
            },
        );
        assert_eq!(report.model_calls, budget);
        assert_eq!(report.tokens_used, Some(budget as u64 * 7));
        assert_eq!(plan.manifest.repo.test_candidates, original);
        assert_eq!(plan.manifest.repo.test, original_scalar);
        assert_eq!(plan.manifest.record.status, original_status);
        assert_eq!(provider.seen.lock().unwrap().len(), budget);
        assert!(scores
            .scores
            .iter()
            .filter(|score| is_context_field(&score.field))
            .all(
                |score| score.confidence != FieldConfidence::HighConfidencePresent
                    && score.confidence != FieldConfidence::HighConfidenceAbsent
            ));
    }
}

#[test]
fn real_known_keras_candidate_reaches_source_bound_request_without_new_extraction() {
    let root = Root::new();
    fs::create_dir_all(root.0.join("keras/api")).unwrap();
    fs::create_dir_all(root.0.join("keras/src")).unwrap();
    let fixtures = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src/import/commands/context/python_recipe/testdata");
    for name in [
        "README.md",
        "CONTRIBUTING.md",
        "pyproject.toml",
        "requirements.txt",
        "requirements-common.txt",
    ] {
        fs::copy(fixtures.join(name), root.0.join(name)).unwrap();
    }
    let plan = import_repository_with_options(
        &root.0,
        ImportMode::Overlay,
        Some("https://github.com/keras-team/keras"),
        &ImportOptions {
            generated_at: Some("2026-10-29T00:00:00Z".into()),
            ..Default::default()
        },
    )
    .unwrap();
    let request = requests(&root.0, &plan).remove(0);
    let evidence = request.candidates[0].context_evidence.as_ref().unwrap();
    assert!(evidence.omissions.is_empty(), "{:?}", evidence.omissions);
    assert!(evidence.sources.len() > 3);
    eprintln!(
        "KNOWN DEVELOPMENT REQUEST {}",
        serde_json::to_string(&request).unwrap()
    );
    assert!(evidence
        .sources
        .iter()
        .any(|source| source.path == "requirements-common.txt"));
    assert!(is_resolved(apply(&response(&request), &request)));
    // Existing scalar extraction is independent; this read-only request does not promote it.
    assert_eq!(request.field, "repo.test_candidates.0");
}

#[test]
fn scalar_serialization_omits_context_and_old_responses_default_citations() {
    let candidate = AdjudicationCandidate {
        value: "cargo test".into(),
        source_path: "Cargo.toml".into(),
        source_tier: CommandSourceTier::Manifest,
        context_evidence: None,
    };
    let serialized = serde_json::to_value(&candidate).unwrap();
    assert!(serialized.get("contextEvidence").is_none());
    let answer:AdjudicationModelResponse=serde_json::from_value(serde_json::json!({"field":"repo.test","value":"cargo test","source":"Cargo.toml","confidence":"high","reason":"old"})).unwrap();
    assert!(answer.citations.is_empty());
}

#[test]
fn repeated_bound_file_spans_preserve_exact_bytes_and_reject_time_span_mutation() {
    let root = Root::new();
    let mut plan = root.plan();
    let source = fs::read_to_string(root.0.join("CONTRIBUTING.md")).unwrap();
    let raw = serde_json::json!([
        {"path":"CONTRIBUTING.md","sha256":digest(&source),"startLine":1,"endLine":1},
        {"path":"CONTRIBUTING.md","sha256":digest(&source),"startLine":2,"endLine":2}
    ])
    .to_string();
    attach(&mut plan, &raw);
    let request = requests(&root.0, &plan).remove(0);
    let evidence = request.candidates[0].context_evidence.as_ref().unwrap();
    assert_eq!(evidence.sources.len(), 2);
    assert_eq!(
        evidence.sources[0].body.to_owned() + &evidence.sources[1].body,
        source
    );
    assert!(is_resolved(apply(&response(&request), &request)));
    let mut changed = request.clone();
    changed.candidates[0]
        .context_evidence
        .as_mut()
        .unwrap()
        .generated_at = Some("2026-11-01T00:00:00Z".into());
    assert!(!is_resolved(apply(&response(&changed), &changed)));
    attach(&mut plan, &raw.replace("\"endLine\":2", "\"endLine\":99"));
    let request = requests(&root.0, &plan).remove(0);
    assert!(!is_resolved(apply(&response(&request), &request)));
}

struct MutatingProvider {
    source: PathBuf,
}
impl AdjudicationProvider for MutatingProvider {
    fn tier(&self) -> AdjudicationTier {
        AdjudicationTier::LocalPrimary
    }
    fn adjudicate(
        &self,
        request: &AdjudicationRequest,
    ) -> anyhow::Result<AdjudicationProviderResponse> {
        let answer = response(request);
        fs::write(&self.source, "changed after request capture\n").unwrap();
        Ok(AdjudicationProviderResponse {
            response: answer,
            tokens_used: Some(11),
        })
    }
}
#[test]
fn ladder_rechecks_changed_sources_after_provider_and_retains_unresolved() {
    let root = Root::new();
    let mut plan = root.plan();
    let original = plan.manifest.repo.test_candidates.clone();
    let verification = verify_import_plan(
        &root.0,
        &plan,
        "https://github.com/example/synthetic-context",
    );
    let mut scores = score_import_fields(&plan, &verification);
    let provider = MutatingProvider {
        source: root.0.join("CONTRIBUTING.md"),
    };
    let report = crate::import::run_import_escalation(
        &root.0,
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
    assert_eq!(report.tokens_used, Some(11));
    assert_eq!(plan.manifest.repo.test_candidates, original);
    assert_eq!(
        scores
            .scores
            .iter()
            .find(|score| is_context_field(&score.field))
            .unwrap()
            .confidence,
        FieldConfidence::Unresolved
    );
}

struct ScalarsFirstProvider {
    seen: Mutex<Vec<String>>,
}
impl AdjudicationProvider for ScalarsFirstProvider {
    fn tier(&self) -> AdjudicationTier {
        AdjudicationTier::LocalPrimary
    }
    fn adjudicate(
        &self,
        request: &AdjudicationRequest,
    ) -> anyhow::Result<AdjudicationProviderResponse> {
        self.seen.lock().unwrap().push(request.field.clone());
        Ok(AdjudicationProviderResponse {
            response: AdjudicationModelResponse {
                field: request.field.clone(),
                value: Some(request.candidates[0].value.clone()),
                source: Some(request.candidates[0].source_path.clone()),
                confidence: AdjudicationModelConfidence::High,
                reason: "owned scalar-priority stub".into(),
                citations: vec![],
            },
            tokens_used: Some(13),
        })
    }
}
#[test]
fn many_large_contexts_share_call_cap_and_preserve_existing_scalar_priority() {
    let root = Root::new();
    let mut plan = root.plan();
    let mut bindings = Vec::new();
    for index in 0..16 {
        let path = if index == 0 {
            "CONTRIBUTING.md".to_owned()
        } else {
            format!("requirement-{index}.txt")
        };
        let body = "x".repeat(MAX_BODY_BYTES - 1) + "\n";
        fs::write(root.0.join(&path), &body).unwrap();
        bindings.push(
            serde_json::json!({"path":path,"sha256":digest(&body),"startLine":1,"endLine":1}),
        );
    }
    attach(&mut plan, &serde_json::to_string(&bindings).unwrap());
    plan.manifest.repo.test_candidates = vec![plan.manifest.repo.test_candidates[0].clone(); 32];
    let requests = requests(&root.0, &plan);
    assert_eq!(requests.len(), MAX_REQUESTS);
    for request in &requests {
        let evidence = request.candidates[0].context_evidence.as_ref().unwrap();
        assert!(
            evidence
                .sources
                .iter()
                .map(|source| source.body.len())
                .sum::<usize>()
                <= MAX_REQUEST_BODY_BYTES
        );
        assert!(serde_json::to_vec(request).unwrap().len() < 256 * 1024);
    }
    assert!(!requests[0].candidates[0]
        .context_evidence
        .as_ref()
        .unwrap()
        .omissions
        .is_empty());
    plan.command_candidates.candidates = vec![
        super::super::CommandCandidateSummary {
            source_path: ".github/workflows/a.yml".into(),
            source_tier: CommandSourceTier::Workflow,
            build: Some("cargo build".into()),
            test: None,
        },
        super::super::CommandCandidateSummary {
            source_path: ".github/workflows/b.yml".into(),
            source_tier: CommandSourceTier::Workflow,
            build: Some("cargo build --release".into()),
            test: None,
        },
    ];
    let verification = verify_import_plan(
        &root.0,
        &plan,
        "https://github.com/example/synthetic-context",
    );
    let mut scores = score_import_fields(&plan, &verification);
    let score = scores
        .scores
        .iter_mut()
        .find(|score| score.field == "repo.build")
        .unwrap();
    score.confidence = FieldConfidence::Unresolved;
    score.value = None;
    let provider = ScalarsFirstProvider {
        seen: Mutex::new(Vec::new()),
    };
    let report = crate::import::run_import_escalation(
        &root.0,
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
    assert_eq!(*provider.seen.lock().unwrap(), vec!["repo.build"]);
    assert_eq!(report.model_calls, 1);
    assert_eq!(report.tokens_used, Some(13));
    assert_eq!(plan.manifest.repo.build.as_deref(), Some("cargo build"));
    assert_eq!(plan.manifest.repo.test_candidates.len(), 32);
    assert_eq!(report.remaining_unresolved, scores.summary.unresolved.len());
}

#[test]
fn existing_higher_confidence_context_score_is_not_replaced() {
    let root = Root::new();
    let plan = root.plan();
    let request = requests(&root.0, &plan).remove(0);
    let verification = verify_import_plan(
        &root.0,
        &plan,
        "https://github.com/example/synthetic-context",
    );
    let mut scores = score_import_fields(&plan, &verification);
    scores.scores.push(super::super::FieldScore {
        field: request.field.clone(),
        confidence: FieldConfidence::HighConfidencePresent,
        value: Some(request.candidates[0].value.clone()),
        source: Some("protected".into()),
        reason: "preexisting; not created by adjudication".into(),
    });
    let answer = apply(&response(&request), &request);
    crate::import::apply_adjudication_results(&mut scores, &[answer]);
    let score = scores
        .scores
        .iter()
        .find(|score| score.field == request.field)
        .unwrap();
    assert_eq!(score.confidence, FieldConfidence::HighConfidencePresent);
    assert_eq!(score.source.as_deref(), Some("protected"));
}

#[test]
fn candidate_paths_cannot_exfiltrate_unadmitted_private_source_bytes() {
    let root = Root::new();
    let mut plan = root.plan();
    let secret = "PRIVATE UNINSPECTED BODY MUST NEVER ENTER ADJUDICATION";
    fs::write(root.0.join(".env"), secret).unwrap();
    let candidate = &mut plan.manifest.repo.test_candidates[0];
    candidate.source = ".env".into();
    candidate.context.as_mut().unwrap().source = ".env".into();
    let request = requests(&root.0, &plan).remove(0);
    let serialized = serde_json::to_string(&request).unwrap();
    assert!(!serialized.contains(secret));
    let evidence = request.candidates[0].context_evidence.as_ref().unwrap();
    assert!(evidence.sources.is_empty());
    assert!(evidence
        .omissions
        .iter()
        .any(|text| text.contains("not admitted")));
    assert!(!is_resolved(apply(&response(&request), &request)));
    assert!(!still_current(&root.0, &plan, &request));
}
