//! Import escalation ladder: deterministic deepen, command-tier walk, model tiers.
//!
//! Split for maintainability:
//! - [`deterministic`] — command-tier resolution and security/owners deepen
//! - [`model_ladder`] — progressive model adjudication tiers
//! - [`report`] — report type and field-score summary recompute

mod deterministic;
mod model_ladder;
mod report;

pub use deterministic::{
    adjudicate_requests_deterministic, adjudicate_requests_deterministic_with_policy,
    apply_adjudication_to_import_plan,
};
pub use report::ImportEscalationReport;

use deterministic::deepen_security_owners_deterministic;
use model_ladder::run_model_escalation;
use report::recompute_field_score_summary;

use super::adjudication::{AdjudicationTier, ImportEscalationOptions, TieredAdjudicationProviders};
use super::commands::sanitize_import_command;
use super::{
    apply_adjudication_results, build_adjudication_requests, AdjudicationOutcome, FieldScoreReport,
    ImportPlan, VerificationReport,
};
use std::path::Path;

/// Run the import escalation ladder: deterministic deepen, build/test walk, then
/// optional model tiers when providers and caps are configured.
pub fn run_import_escalation(
    root: &Path,
    plan: &mut ImportPlan,
    _verification: &VerificationReport,
    field_scores: &mut FieldScoreReport,
    options: &ImportEscalationOptions,
    providers: TieredAdjudicationProviders<'_>,
) -> ImportEscalationReport {
    let mut report = ImportEscalationReport {
        security_owners_deepened: deepen_security_owners_deterministic(root, plan, field_scores),
        ..ImportEscalationReport::default()
    };
    if report.security_owners_deepened > 0 {
        recompute_field_score_summary(field_scores);
        if !report
            .adjudication_tiers_used
            .contains(&AdjudicationTier::Deterministic)
        {
            report
                .adjudication_tiers_used
                .push(AdjudicationTier::Deterministic);
        }
    }

    let defer_conflicts_to_model = options.max_adjudication_calls > 0
        && (providers.local_primary.is_some()
            || providers.local_second_opinion.is_some()
            || providers.api_escalation.is_some());

    let requests = build_adjudication_requests(field_scores, plan);
    if !requests.is_empty() {
        let results =
            adjudicate_requests_deterministic_with_policy(&requests, defer_conflicts_to_model);
        report.deterministic_requests = requests.len();
        report.deterministic_resolved = results
            .iter()
            .filter(|result| !matches!(result.outcome, AdjudicationOutcome::Rejected { .. }))
            .count();

        apply_adjudication_results(field_scores, &results);
        apply_adjudication_to_import_plan(plan, &requests, &results, "deterministic");
        recompute_field_score_summary(field_scores);
        if !report
            .adjudication_tiers_used
            .contains(&AdjudicationTier::Deterministic)
        {
            report
                .adjudication_tiers_used
                .push(AdjudicationTier::Deterministic);
        }
    }

    run_model_escalation(plan, field_scores, options, providers, &mut report);

    if field_scores.summary.unresolved.is_empty() {
        return report;
    }

    let remaining_requests = build_adjudication_requests(field_scores, plan);
    if remaining_requests.is_empty() {
        return report;
    }

    let fallback_results =
        adjudicate_requests_deterministic_with_policy(&remaining_requests, false);
    let fallback_resolved = fallback_results
        .iter()
        .filter(|result| !matches!(result.outcome, AdjudicationOutcome::Rejected { .. }))
        .count();
    if fallback_resolved > 0 {
        apply_adjudication_results(field_scores, &fallback_results);
        apply_adjudication_to_import_plan(
            plan,
            &remaining_requests,
            &fallback_results,
            "deterministic",
        );
        recompute_field_score_summary(field_scores);
        report.deterministic_resolved += fallback_resolved;
    }
    report.remaining_unresolved = field_scores.summary.unresolved.len();

    // Defense-in-depth: any code path that set build/test must have been sanitized,
    // but force-unset here if an unsafe value is present, and record in evidence.
    sanitize_plan_command_fields(plan, "escalation");

    report
}

fn sanitize_plan_command_fields(plan: &mut ImportPlan, context: &str) {
    let mut changed = false;
    if let Some(cmd) = &plan.manifest.repo.build {
        if sanitize_import_command(cmd).is_none() {
            plan.manifest.repo.build = None;
            plan.command_candidates.selected_build = None;
            if let Some(ref mut ev) = plan.evidence_text {
                ev.push_str(&format!(
                    "\n- Left `repo.build` unset during {}: contained unsafe shell-like characters.",
                    context
                ));
            }
            changed = true;
        }
    }
    if let Some(cmd) = &plan.manifest.repo.test {
        if sanitize_import_command(cmd).is_none() {
            plan.manifest.repo.test = None;
            plan.command_candidates.selected_test = None;
            if let Some(ref mut ev) = plan.evidence_text {
                ev.push_str(&format!(
                    "\n- Left `repo.test` unset during {}: contained unsafe shell-like characters.",
                    context
                ));
            }
            changed = true;
        }
    }
    if changed {
        // Ensure downstream verification sees the corrected state
    }
}

/// Whether an autonomous crawl may write back overlay artifacts.
///
/// This gate is intentionally looser than `FieldScoreSummary::eligible_for_auto_publish`:
/// writeback may persist honestly partial overlays when deterministic verification passes,
/// even when field scoring still has unresolved entries. Auto-publish to `verified` requires
/// full field resolution instead.
pub fn autonomous_writeback_eligible(verification: &VerificationReport) -> bool {
    verification.passed
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::import::{
        import_repository, score_import_fields, AdjudicationCandidate, AdjudicationModelConfidence,
        AdjudicationModelResponse, AdjudicationOutcome, AdjudicationProviderResponse,
        AdjudicationRequest, CommandSourceTier, FieldConfidence, ImportEscalationOptions,
        ImportMode, StubAdjudicationProvider, TieredAdjudicationProviders,
    };
    use std::fs;

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("dotrepo-escalation-{name}"));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("temp dir created");
        dir
    }

    #[test]
    fn deterministic_escalation_keeps_node_python_test_conflict_absent() {
        let results = adjudicate_requests_deterministic(&[AdjudicationRequest {
            field: "repo.test".into(),
            candidates: vec![
                AdjudicationCandidate {
                    value: "npm test".into(),
                    source_path: "package.json".into(),
                    source_tier: CommandSourceTier::Manifest,
                },
                AdjudicationCandidate {
                    value: "tox".into(),
                    source_path: "pyproject.toml".into(),
                    source_tier: CommandSourceTier::EcosystemDefault,
                },
            ],
        }]);

        assert_eq!(results.len(), 1);
        assert!(matches!(
            results[0].outcome,
            AdjudicationOutcome::Absent { .. }
        ));
    }

    #[test]
    fn deterministic_escalation_marks_conflicts_absent_without_model_spend() {
        let root = temp_dir("workflow-conflict");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
        fs::write(
            root.join("README.md"),
            "# Conflict\n\nConflicting workflows.\n",
        )
        .expect("readme");
        fs::write(
            root.join(".github/workflows/check.yml"),
            "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
        )
        .expect("check");
        fs::write(
            root.join(".github/workflows/verify.yml"),
            "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
        )
        .expect("verify");

        let source = "https://github.com/example/conflict";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);
        assert!(!scores.summary.unresolved.is_empty());

        let report = run_import_escalation(
            &root,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions::default(),
            TieredAdjudicationProviders {
                local_primary: None,
                local_second_opinion: None,
                api_escalation: None,
            },
        );
        assert!(report.deterministic_requests > 0);
        assert!(scores.summary.unresolved.is_empty());
        assert!(plan.manifest.repo.build.is_none());
        assert_eq!(report.model_calls, 0);
        assert!(autonomous_writeback_eligible(&verification));

        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn writeback_gate_can_pass_while_auto_publish_remains_blocked() {
        let root = temp_dir("writeback-vs-auto-publish");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
        fs::write(
            root.join("README.md"),
            "# Conflict\n\nConflicting workflows.\n",
        )
        .expect("readme");
        fs::write(
            root.join(".github/workflows/check.yml"),
            "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
        )
        .expect("check");
        fs::write(
            root.join(".github/workflows/verify.yml"),
            "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
        )
        .expect("verify");

        let source = "https://github.com/example/writeback-vs-auto-publish";
        let plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let scores = score_import_fields(&plan, &verification);

        assert!(autonomous_writeback_eligible(&verification));
        assert!(!scores.summary.unresolved.is_empty());
        assert!(!scores.summary.eligible_for_auto_publish);

        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn deepen_finds_security_contact_in_readme_section() {
        let root = temp_dir("readme-security");
        fs::write(
            root.join("README.md"),
            "# Demo\n\nA project.\n\n## Security\n\nReport issues to security@example.com.\n",
        )
        .expect("readme");

        let source = "https://github.com/example/readme-security";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);

        let report = run_import_escalation(
            &root,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions::default(),
            TieredAdjudicationProviders {
                local_primary: None,
                local_second_opinion: None,
                api_escalation: None,
            },
        );

        assert_eq!(report.security_owners_deepened, 1);
        assert_eq!(
            plan.manifest
                .owners
                .as_ref()
                .and_then(|owners| owners.security_contact.as_deref()),
            Some("security@example.com")
        );

        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn model_escalation_resolves_remaining_fields_under_cap() {
        let root = temp_dir("model-escalation");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
        fs::write(
            root.join("README.md"),
            "# Conflict\n\nConflicting workflows.\n",
        )
        .expect("readme");
        fs::write(
            root.join(".github/workflows/check.yml"),
            "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo test --workspace\n",
        )
        .expect("check");
        fs::write(
            root.join(".github/workflows/verify.yml"),
            "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo test\n",
        )
        .expect("verify");

        let source = "https://github.com/example/model-escalation";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);

        let provider = StubAdjudicationProvider::new(
            AdjudicationTier::LocalPrimary,
            vec![
                AdjudicationProviderResponse {
                    response: AdjudicationModelResponse {
                        field: "repo.build".into(),
                        value: Some("cargo build --workspace".into()),
                        confidence: AdjudicationModelConfidence::Medium,
                        reason: "Check workflow is primary".into(),
                        source: Some(".github/workflows/check.yml".into()),
                    },
                    tokens_used: 120,
                },
                AdjudicationProviderResponse {
                    response: AdjudicationModelResponse {
                        field: "repo.test".into(),
                        value: Some("cargo test --workspace".into()),
                        confidence: AdjudicationModelConfidence::Medium,
                        reason: "Check workflow is primary".into(),
                        source: Some(".github/workflows/check.yml".into()),
                    },
                    tokens_used: 95,
                },
            ],
        );

        let report = run_import_escalation(
            &root,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions {
                max_adjudication_calls: 2,
                enable_second_opinion: false,
                enable_api_escalation: false,
            },
            TieredAdjudicationProviders {
                local_primary: Some(&provider),
                local_second_opinion: None,
                api_escalation: None,
            },
        );

        assert_eq!(report.model_calls, 2);
        assert_eq!(report.tokens_used, 215);
        assert_eq!(report.model_resolved, 2);
        assert!(scores.summary.unresolved.is_empty());
        assert_eq!(
            plan.manifest.repo.build.as_deref(),
            Some("cargo build --workspace")
        );

        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn low_confidence_abstention_escalates_to_second_opinion() {
        // Reproduces the shape of the intended fix: a cheap primary tier
        // that is *uncertain* (not confidently correct) should get a second
        // opinion before its "no answer" is accepted as final, the same way
        // a low-confidence wrong-value guess already escalates.
        let root = temp_dir("low-confidence-escalation");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
        fs::write(
            root.join("README.md"),
            "# Conflict\n\nConflicting workflows.\n",
        )
        .expect("readme");
        fs::write(
            root.join(".github/workflows/check.yml"),
            "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
        )
        .expect("check");
        fs::write(
            root.join(".github/workflows/verify.yml"),
            "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
        )
        .expect("verify");

        let source = "https://github.com/example/low-confidence-escalation";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);

        let primary = StubAdjudicationProvider::new(
            AdjudicationTier::LocalPrimary,
            vec![AdjudicationProviderResponse {
                response: AdjudicationModelResponse {
                    field: "repo.build".into(),
                    value: None,
                    confidence: AdjudicationModelConfidence::Low,
                    reason: "Not sure which workflow is primary".into(),
                    source: None,
                },
                tokens_used: 80,
            }],
        );
        let second_opinion = StubAdjudicationProvider::new(
            AdjudicationTier::LocalSecondOpinion,
            vec![AdjudicationProviderResponse {
                response: AdjudicationModelResponse {
                    field: "repo.build".into(),
                    value: Some("cargo build --workspace".into()),
                    confidence: AdjudicationModelConfidence::High,
                    reason: "Check workflow lists --workspace, matching a monorepo build".into(),
                    source: Some(".github/workflows/check.yml".into()),
                },
                tokens_used: 140,
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
                local_second_opinion: Some(&second_opinion),
                api_escalation: None,
            },
        );

        assert_eq!(report.model_calls, 2);
        assert_eq!(report.tokens_used, 220);
        assert_eq!(report.model_resolved, 1);
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
    fn confident_abstention_does_not_escalate_to_second_opinion() {
        // A confident "no single answer is honest" (e.g. a genuinely
        // polyglot repository) must remain terminal -- escalating this to a
        // stronger model would waste a call re-litigating a correct
        // abstention rather than genuine model uncertainty. Reproduces the
        // real astral-sh/ruff and oven-sh/bun cases observed in production.
        let root = temp_dir("confident-abstention");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
        fs::write(
            root.join("README.md"),
            "# Conflict\n\nConflicting workflows.\n",
        )
        .expect("readme");
        fs::write(
            root.join(".github/workflows/check.yml"),
            "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
        )
        .expect("check");
        fs::write(
            root.join(".github/workflows/verify.yml"),
            "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
        )
        .expect("verify");

        let source = "https://github.com/example/confident-abstention";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);

        let primary = StubAdjudicationProvider::new(
            AdjudicationTier::LocalPrimary,
            vec![AdjudicationProviderResponse {
                response: AdjudicationModelResponse {
                    field: "repo.build".into(),
                    value: None,
                    confidence: AdjudicationModelConfidence::High,
                    reason: "Distinct mutually exclusive build targets; no single honest answer"
                        .into(),
                    source: None,
                },
                tokens_used: 80,
            }],
        );
        let second_opinion = StubAdjudicationProvider::new(
            AdjudicationTier::LocalSecondOpinion,
            vec![AdjudicationProviderResponse {
                response: AdjudicationModelResponse {
                    field: "repo.build".into(),
                    value: Some("cargo build --workspace".into()),
                    confidence: AdjudicationModelConfidence::High,
                    reason: "Should never be called".into(),
                    source: None,
                },
                tokens_used: 140,
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
                local_second_opinion: Some(&second_opinion),
                api_escalation: None,
            },
        );

        assert_eq!(report.model_calls, 1);
        assert_eq!(report.tokens_used, 80);
        assert!(!report
            .adjudication_tiers_used
            .contains(&AdjudicationTier::LocalSecondOpinion));
        assert_eq!(plan.manifest.repo.build, None);
        // Even though no single command could be honestly chosen, the
        // concrete candidates are preserved rather than silently discarded.
        let candidates = &plan.manifest.repo.build_candidates;
        assert_eq!(candidates.len(), 2);
        assert!(candidates
            .iter()
            .any(|c| c.command == "cargo build --workspace"));
        assert!(candidates.iter().any(|c| c.command == "cargo build"));

        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn declared_script_avoids_polyglot_default_escalation() {
        // A declared package script is stronger evidence than the conventional
        // command merely implied by Cargo.toml, so this needs no model call.
        let root = temp_dir("polyglot-ecosystem-labels");
        fs::write(
            root.join("README.md"),
            "# Polyglot\n\nRust and Node.js in one repo.\n",
        )
        .expect("readme");
        fs::write(
            root.join("Cargo.toml"),
            "[package]\nname = \"polyglot\"\nversion = \"0.1.0\"\n",
        )
        .expect("Cargo.toml");
        fs::write(
            root.join("package.json"),
            "{\"name\": \"polyglot\", \"scripts\": {\"build\": \"tsc\"}}",
        )
        .expect("package.json");

        let source = "https://github.com/example/polyglot-ecosystem-labels";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);

        let primary = StubAdjudicationProvider::new(
            AdjudicationTier::LocalPrimary,
            vec![AdjudicationProviderResponse {
                response: AdjudicationModelResponse {
                    field: "repo.build".into(),
                    value: None,
                    confidence: AdjudicationModelConfidence::High,
                    reason: "Distinct, mutually exclusive ecosystems (Rust vs Node.js)".into(),
                    source: None,
                },
                tokens_used: 90,
            }],
        );

        let report = run_import_escalation(
            &root,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions {
                max_adjudication_calls: 1,
                enable_second_opinion: false,
                enable_api_escalation: false,
            },
            TieredAdjudicationProviders {
                local_primary: Some(&primary),
                local_second_opinion: None,
                api_escalation: None,
            },
        );

        assert_eq!(report.model_calls, 0);
        assert_eq!(plan.manifest.repo.build.as_deref(), Some("npm run build"));
        assert!(plan.manifest.repo.build_candidates.is_empty());

        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn escalation_does_not_apply_unsafe_task_script_test_command() {
        let root = temp_dir("unsafe-makefile-test");
        fs::write(root.join("README.md"), "# Docker CLI\n\nThe Docker CLI.\n").expect("readme");
        fs::write(
            root.join("Makefile"),
            ".PHONY: unit\n\
             unit:\n\
             \tgotestsum -- $${TESTDIRS:-$(shell go list ./... | grep -vE '/vendor/')} $(TESTFLAGS)\n",
        )
        .expect("makefile");

        let source = "https://github.com/docker/cli";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        let verification = crate::import::verify_import_plan(&root, &plan, source);
        let mut scores = score_import_fields(&plan, &verification);

        let report = run_import_escalation(
            &root,
            &mut plan,
            &verification,
            &mut scores,
            &ImportEscalationOptions::default(),
            TieredAdjudicationProviders {
                local_primary: None,
                local_second_opinion: None,
                api_escalation: None,
            },
        );

        assert_eq!(report.model_calls, 0);
        assert!(plan.manifest.repo.test.is_none());
        assert!(!scores.summary.unresolved.contains(&"repo.test".to_string()));
        crate::validate_manifest(&root, &plan.manifest).expect("manifest validates");

        fs::remove_dir_all(root).expect("cleanup");
    }

    #[test]
    fn escalation_rejects_unsafe_value_returned_by_adjudication_provider() {
        // Even if a provider returns an unsafe command in a Resolved outcome
        // (defense in depth), apply_adjudication_to_import_plan must reject it.
        let root = temp_dir("unsafe-adjudicated-test");
        fs::write(root.join("README.md"), "# Example\n\nA project.\n").expect("readme");

        let source = "https://github.com/example/unsafe-adj";
        let mut plan =
            import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
        // Seed a request that looks like it had a (hypothetically unsafe-in-list) candidate
        // so we can directly exercise the Resolved+unsafe branch.
        plan.command_candidates
            .candidates
            .push(crate::import::CommandCandidateSummary {
                source_path: "Makefile".into(),
                source_tier: CommandSourceTier::Workflow,
                build: None,
                test: Some("go test ./... || true".into()),
            });

        let requests = vec![crate::import::AdjudicationRequest {
            field: "repo.test".into(),
            candidates: vec![crate::import::AdjudicationCandidate {
                value: "go test ./... || true".into(),
                source_path: "Makefile".into(),
                source_tier: CommandSourceTier::Workflow,
            }],
        }];
        let results = vec![crate::import::AdjudicationResult {
            field: "repo.test".into(),
            outcome: crate::import::AdjudicationOutcome::Resolved {
                value: "go test ./... || true".into(),
                confidence: FieldConfidence::MediumConfidencePresent,
                reason: "erroneous provider response".into(),
            },
        }];

        // Before apply, test should be absent.
        assert!(plan.manifest.repo.test.is_none());

        apply_adjudication_to_import_plan(&mut plan, &requests, &results, "test");

        // Must have been rejected and unset (with evidence note).
        assert!(plan.manifest.repo.test.is_none());
        assert!(plan.command_candidates.selected_test.is_none());
        let evidence = plan.evidence_text.as_deref().unwrap_or("");
        assert!(
            evidence.contains("Left `repo.test` unset") && evidence.contains("unsafe"),
            "expected rejection note in evidence, got: {}",
            evidence
        );

        crate::validate_manifest(&root, &plan.manifest)
            .expect("manifest validates after rejection");

        fs::remove_dir_all(root).expect("cleanup");
    }
}
