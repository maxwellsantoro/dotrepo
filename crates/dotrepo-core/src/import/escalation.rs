use super::adjudication::{AdjudicationTier, ImportEscalationOptions, TieredAdjudicationProviders};
use super::commands::load_first_existing_file;
use super::commands::sanitize_import_command;
use super::{
    apply_adjudication_response, apply_adjudication_results, build_adjudication_requests,
    is_actionable_security_url, parse_codeowners_metadata, parse_contributing_security,
    parse_issue_template_security, parse_readme_security, parse_security_import_metadata,
    push_unique, AdjudicationModelConfidence, AdjudicationModelResponse, AdjudicationOutcome,
    AdjudicationRequest, AdjudicationResult, CommandCandidateSelection, CommandSourceTier,
    FieldConfidence, FieldScoreReport, ImportPlan, ImportedCommandProvenance, VerificationReport,
    IMPORT_README_CANDIDATES,
};
use dotrepo_schema::Owners;
use std::collections::HashSet;
use std::path::Path;

const ESCALATION_TIERS: [CommandSourceTier; 4] = [
    CommandSourceTier::Manifest,
    CommandSourceTier::ContribDoc,
    CommandSourceTier::TaskScript,
    CommandSourceTier::Workflow,
];

const DEEPEN_SECURITY_PATHS: &[&str] = &[
    ".github/SECURITY.md",
    "SECURITY.md",
    "docs/SECURITY.md",
    "docs/security.md",
    ".github/CONTRIBUTING.md",
    "CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/security.md",
    ".github/ISSUE_TEMPLATE/SECURITY.md",
    ".github/ISSUE_TEMPLATE/security.yml",
];

const DEEPEN_CODEOWNERS_PATHS: &[&str] = &[".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"];

#[derive(Debug, Clone, Default, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportEscalationReport {
    pub deterministic_requests: usize,
    pub deterministic_resolved: usize,
    pub security_owners_deepened: usize,
    pub model_calls: usize,
    pub model_resolved: usize,
    pub tokens_used: u64,
    pub remaining_unresolved: usize,
    pub adjudication_tiers_used: Vec<AdjudicationTier>,
}

/// Walk the command-source hierarchy to resolve unresolved build/test fields
/// without model spend.
pub fn adjudicate_requests_deterministic(
    requests: &[AdjudicationRequest],
) -> Vec<AdjudicationResult> {
    adjudicate_requests_deterministic_with_policy(requests, false)
}

pub fn adjudicate_requests_deterministic_with_policy(
    requests: &[AdjudicationRequest],
    defer_conflicts_to_model: bool,
) -> Vec<AdjudicationResult> {
    requests
        .iter()
        .map(|request| adjudicate_request_deterministic(request, defer_conflicts_to_model))
        .collect()
}

fn adjudicate_request_deterministic(
    request: &AdjudicationRequest,
    defer_conflicts_to_model: bool,
) -> AdjudicationResult {
    for tier in ESCALATION_TIERS {
        let tier_candidates: Vec<_> = request
            .candidates
            .iter()
            .filter(|candidate| candidate.source_tier == tier)
            .filter(|candidate| sanitize_import_command(&candidate.value).is_some())
            .collect();
        if tier_candidates.is_empty() {
            continue;
        }

        let unique_values: HashSet<&str> = tier_candidates
            .iter()
            .map(|candidate| candidate.value.as_str())
            .collect();
        if unique_values.len() == 1 {
            let winner = tier_candidates[0];
            let confidence = match tier {
                CommandSourceTier::Manifest
                | CommandSourceTier::ContribDoc
                | CommandSourceTier::TaskScript => FieldConfidence::HighConfidencePresent,
                CommandSourceTier::Workflow => FieldConfidence::MediumConfidencePresent,
            };
            return apply_adjudication_response(
                &AdjudicationModelResponse {
                    field: request.field.clone(),
                    value: Some(winner.value.clone()),
                    confidence: adjudication_model_confidence(confidence),
                    reason: format!(
                        "deterministic tier {:?} produced a unique candidate from {}",
                        tier, winner.source_path
                    ),
                    source: Some(winner.source_path.clone()),
                },
                request,
            );
        }
    }

    if defer_conflicts_to_model {
        return AdjudicationResult {
            field: request.field.clone(),
            outcome: AdjudicationOutcome::Rejected {
                model_value: String::new(),
                reason: "conflicting candidates deferred to model adjudication".into(),
            },
        };
    }

    apply_adjudication_response(
        &AdjudicationModelResponse {
            field: request.field.clone(),
            value: None,
            confidence: AdjudicationModelConfidence::High,
            reason: "no unique build/test candidate after deterministic tier walk".into(),
            source: None,
        },
        request,
    )
}

fn adjudication_model_confidence(confidence: FieldConfidence) -> AdjudicationModelConfidence {
    match confidence {
        FieldConfidence::HighConfidencePresent | FieldConfidence::HighConfidenceAbsent => {
            AdjudicationModelConfidence::High
        }
        FieldConfidence::MediumConfidencePresent => AdjudicationModelConfidence::Medium,
        FieldConfidence::Unresolved => AdjudicationModelConfidence::Low,
    }
}

pub fn apply_adjudication_to_import_plan(
    plan: &mut ImportPlan,
    requests: &[AdjudicationRequest],
    results: &[AdjudicationResult],
    escalation_label: &str,
) {
    for (request, result) in requests.iter().zip(results.iter()) {
        match &result.outcome {
            AdjudicationOutcome::Resolved { value, .. } => {
                let is_command_field = result.field == "repo.build" || result.field == "repo.test";
                let safe_value = if is_command_field {
                    match sanitize_import_command(value) {
                        Some(command) => command,
                        None => {
                            if result.field == "repo.build" {
                                plan.manifest.repo.build = None;
                                plan.command_candidates.selected_build = None;
                            } else if result.field == "repo.test" {
                                plan.manifest.repo.test = None;
                                plan.command_candidates.selected_test = None;
                            }
                            if let Some(ref mut evidence) = plan.evidence_text {
                                evidence.push_str("\n- Left `");
                                evidence.push_str(&result.field);
                                evidence.push_str("` unset after ");
                                evidence.push_str(escalation_label);
                                evidence.push_str(
                                    " escalation: candidate command was unsafe shell-like.",
                                );
                                evidence.push('.');
                            }
                            continue;
                        }
                    }
                } else {
                    value.clone()
                };
                let source_path = request
                    .candidates
                    .iter()
                    .find(|candidate| candidate.value == *value)
                    .map(|candidate| candidate.source_path.clone())
                    .unwrap_or_else(|| "adjudicated".into());
                let provenance = request
                    .candidates
                    .iter()
                    .find(|candidate| candidate.value == *value)
                    .map(|candidate| {
                        if matches!(
                            candidate.source_tier,
                            CommandSourceTier::Manifest
                                | CommandSourceTier::ContribDoc
                                | CommandSourceTier::TaskScript
                        ) {
                            ImportedCommandProvenance::Imported
                        } else {
                            ImportedCommandProvenance::Inferred
                        }
                    })
                    .unwrap_or(ImportedCommandProvenance::Inferred);
                let selection = CommandCandidateSelection {
                    command: safe_value.clone(),
                    source_path: source_path.clone(),
                    provenance,
                };
                let bullet = format!(
                    "Set `{}` to `{}` from `{}` after {} escalation.",
                    result.field, safe_value, source_path, escalation_label
                );
                if result.field == "repo.build" {
                    plan.manifest.repo.build = Some(safe_value);
                    plan.command_candidates.selected_build = Some(selection);
                } else if result.field == "repo.test" {
                    plan.manifest.repo.test = Some(safe_value);
                    plan.command_candidates.selected_test = Some(selection);
                }
                if let Some(ref mut evidence) = plan.evidence_text {
                    evidence.push_str("\n- ");
                    evidence.push_str(&bullet);
                }
            }
            AdjudicationOutcome::Absent { reason } => {
                if result.field == "repo.build" {
                    plan.manifest.repo.build = None;
                    plan.command_candidates.selected_build = None;
                } else if result.field == "repo.test" {
                    plan.manifest.repo.test = None;
                    plan.command_candidates.selected_test = None;
                }
                if let Some(ref mut evidence) = plan.evidence_text {
                    evidence.push_str("\n- Left `");
                    evidence.push_str(&result.field);
                    evidence.push_str("` unset after ");
                    evidence.push_str(escalation_label);
                    evidence.push_str(" escalation: ");
                    evidence.push_str(reason);
                    evidence.push('.');
                }
            }
            AdjudicationOutcome::Rejected { .. } => {}
        }
    }
}

fn deepen_security_owners_deterministic(
    root: &Path,
    plan: &mut ImportPlan,
    field_scores: &mut FieldScoreReport,
) -> usize {
    let mut deepened = 0;

    if deepen_security_contact(root, plan, field_scores) {
        deepened += 1;
    }
    if deepen_owners_team(root, plan, field_scores) {
        deepened += 1;
    }

    deepened
}

fn deepen_security_contact(
    root: &Path,
    plan: &mut ImportPlan,
    field_scores: &mut FieldScoreReport,
) -> bool {
    let current = plan
        .manifest
        .owners
        .as_ref()
        .and_then(|owners| owners.security_contact.as_deref());
    let needs_deepen = current.is_none() || current == Some("unknown");
    if !needs_deepen {
        return false;
    }

    let mut discovered: Option<(String, String)> = None;

    if let Ok(Some(readme)) = load_first_existing_file(root, IMPORT_README_CANDIDATES) {
        if let Some(contact) = parse_readme_security(&readme.contents) {
            discovered = Some((contact, readme.path));
        }
    }

    if discovered.is_none() {
        for candidate in DEEPEN_SECURITY_PATHS {
            let path = root.join(candidate);
            if !path.is_file() {
                continue;
            }
            let contents = match std::fs::read_to_string(&path) {
                Ok(contents) => contents,
                Err(_) => continue,
            };
            let contact = if candidate.contains("ISSUE_TEMPLATE") {
                parse_issue_template_security(&contents)
            } else if candidate.contains("CONTRIBUTING") {
                parse_contributing_security(&contents)
            } else {
                parse_security_import_metadata(&contents).contact
            };
            if let Some(contact) = contact {
                discovered = Some((contact, (*candidate).to_string()));
                break;
            }
        }
    }

    let Some((contact, source_path)) = discovered else {
        return false;
    };

    let owners = plan.manifest.owners.get_or_insert_with(|| Owners {
        maintainers: Vec::new(),
        team: None,
        security_contact: None,
    });
    owners.security_contact = Some(contact.clone());
    push_unique(&mut plan.imported_sources, source_path.clone());

    if let Some(score) = field_scores
        .scores
        .iter_mut()
        .find(|score| score.field == "owners.security_contact")
    {
        if contact == "unknown" {
            score.confidence = FieldConfidence::HighConfidenceAbsent;
            score.value = Some(contact);
            score.reason = "explicitly unknown after deterministic deepen".into();
        } else if contact.contains('@') {
            score.confidence = FieldConfidence::HighConfidencePresent;
            score.value = Some(contact);
            score.source = Some(source_path.clone());
            score.reason = "direct email or mailing list after deterministic deepen".into();
        } else if is_actionable_security_url(&contact) {
            score.confidence = FieldConfidence::HighConfidencePresent;
            score.value = Some(contact);
            score.source = Some(source_path.clone());
            score.reason = "actionable security reporting URL after deterministic deepen".into();
        } else {
            score.confidence = FieldConfidence::MediumConfidencePresent;
            score.value = Some(contact);
            score.source = Some(source_path.clone());
            score.reason = "policy URL or non-email contact after deterministic deepen".into();
        }
    }

    if let Some(ref mut evidence) = plan.evidence_text {
        evidence.push_str("\n- Deepened `owners.security_contact` from `");
        evidence.push_str(&source_path);
        evidence.push_str("` during deterministic escalation.");
    }

    true
}

fn deepen_owners_team(
    root: &Path,
    plan: &mut ImportPlan,
    field_scores: &mut FieldScoreReport,
) -> bool {
    if plan
        .manifest
        .owners
        .as_ref()
        .and_then(|owners| owners.team.as_deref())
        .is_some()
    {
        return false;
    }

    let mut metadata = None;
    let mut source_path = None;
    for candidate in DEEPEN_CODEOWNERS_PATHS {
        let path = root.join(candidate);
        if !path.is_file() {
            continue;
        }
        let contents = match std::fs::read_to_string(&path) {
            Ok(contents) => contents,
            Err(_) => continue,
        };
        metadata = Some(parse_codeowners_metadata(&contents));
        source_path = Some((*candidate).to_string());
        break;
    }

    let Some(metadata) = metadata else {
        return false;
    };
    let Some(team) = metadata.team else {
        return false;
    };

    let owners = plan.manifest.owners.get_or_insert_with(|| Owners {
        maintainers: metadata.owners.clone(),
        team: None,
        security_contact: None,
    });
    if owners.maintainers.is_empty() {
        owners.maintainers = metadata.owners.clone();
    }
    owners.team = Some(team.clone());
    if let Some(path) = source_path.as_ref() {
        push_unique(&mut plan.imported_sources, path.clone());
    }

    if let Some(score) = field_scores
        .scores
        .iter_mut()
        .find(|score| score.field == "owners.team")
    {
        score.confidence = FieldConfidence::HighConfidencePresent;
        score.value = Some(team);
        score.source = source_path;
        score.reason = "clear CODEOWNERS team after deterministic deepen".into();
    }

    if let Some(ref mut evidence) = plan.evidence_text {
        evidence.push_str(
            "\n- Deepened `owners.team` from CODEOWNERS during deterministic escalation.",
        );
    }

    true
}

fn recompute_field_score_summary(field_scores: &mut FieldScoreReport) {
    let mut high_confidence_present = Vec::new();
    let mut medium_confidence_present = Vec::new();
    let mut high_confidence_absent = Vec::new();
    let mut unresolved = Vec::new();
    for score in &field_scores.scores {
        match score.confidence {
            FieldConfidence::HighConfidencePresent => {
                high_confidence_present.push(score.field.clone())
            }
            FieldConfidence::MediumConfidencePresent => {
                medium_confidence_present.push(score.field.clone())
            }
            FieldConfidence::HighConfidenceAbsent => {
                high_confidence_absent.push(score.field.clone())
            }
            FieldConfidence::Unresolved => unresolved.push(score.field.clone()),
        }
    }
    field_scores.summary.high_confidence_present = high_confidence_present;
    field_scores.summary.medium_confidence_present = medium_confidence_present;
    field_scores.summary.high_confidence_absent = high_confidence_absent;
    field_scores.summary.unresolved = unresolved;
    field_scores.summary.eligible_for_auto_publish = field_scores.summary.unresolved.is_empty()
        && field_scores.summary.medium_confidence_present.is_empty();
}

fn run_model_escalation(
    plan: &mut ImportPlan,
    field_scores: &mut FieldScoreReport,
    options: &ImportEscalationOptions,
    providers: TieredAdjudicationProviders<'_>,
    report: &mut ImportEscalationReport,
) {
    if options.max_adjudication_calls == 0 {
        return;
    }

    let requests = build_adjudication_requests(field_scores, plan);
    if requests.is_empty() {
        return;
    }

    let mut remaining_calls = options.max_adjudication_calls;
    let mut all_requests = Vec::new();
    let mut all_results = Vec::new();

    for request in requests {
        if remaining_calls == 0 {
            break;
        }

        let mut resolved = false;
        let mut tiers_to_try = vec![AdjudicationTier::LocalPrimary];
        if options.enable_second_opinion {
            tiers_to_try.push(AdjudicationTier::LocalSecondOpinion);
        }
        if options.enable_api_escalation {
            tiers_to_try.push(AdjudicationTier::ApiEscalation);
        }

        let mut last_result = None;
        for tier in tiers_to_try {
            if remaining_calls == 0 {
                break;
            }
            let Some(provider) = providers.provider_for_tier(tier) else {
                continue;
            };

            let provider_response = match provider.adjudicate(&request) {
                Ok(response) => response,
                Err(_) => continue,
            };
            remaining_calls -= 1;
            report.model_calls += 1;
            report.tokens_used += provider_response.tokens_used;
            if !report.adjudication_tiers_used.contains(&tier) {
                report.adjudication_tiers_used.push(tier);
            }

            let result = apply_adjudication_response(&provider_response.response, &request);
            let accepted = !matches!(result.outcome, AdjudicationOutcome::Rejected { .. });
            last_result = Some(result);
            if accepted {
                resolved = true;
                break;
            }
            if provider_response.response.confidence != AdjudicationModelConfidence::Low {
                break;
            }
        }

        if let Some(result) = last_result {
            if !matches!(result.outcome, AdjudicationOutcome::Rejected { .. }) {
                report.model_resolved += 1;
            }
            all_requests.push(request);
            all_results.push(result);
            if resolved {
                continue;
            }
        }
    }

    if !all_results.is_empty() {
        apply_adjudication_results(field_scores, &all_results);
        apply_adjudication_to_import_plan(plan, &all_requests, &all_results, "model");
        recompute_field_score_summary(field_scores);
    }
}

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
        import_repository, score_import_fields, AdjudicationModelConfidence,
        AdjudicationProviderResponse, ImportMode, StubAdjudicationProvider,
    };
    use std::fs;

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("dotrepo-escalation-{name}"));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("temp dir created");
        dir
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
            root.join(".github/workflows/ci.yml"),
            "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
        )
        .expect("ci");
        fs::write(
            root.join(".github/workflows/release.yml"),
            "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
        )
        .expect("release");

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
            root.join(".github/workflows/ci.yml"),
            "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
        )
        .expect("ci");
        fs::write(
            root.join(".github/workflows/release.yml"),
            "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
        )
        .expect("release");

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
            root.join(".github/workflows/ci.yml"),
            "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo test --workspace\n",
        )
        .expect("ci");
        fs::write(
            root.join(".github/workflows/release.yml"),
            "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo test\n",
        )
        .expect("release");

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
                        reason: "CI workflow is primary".into(),
                        source: Some(".github/workflows/ci.yml".into()),
                    },
                    tokens_used: 120,
                },
                AdjudicationProviderResponse {
                    response: AdjudicationModelResponse {
                        field: "repo.test".into(),
                        value: Some("cargo test --workspace".into()),
                        confidence: AdjudicationModelConfidence::Medium,
                        reason: "CI workflow is primary".into(),
                        source: Some(".github/workflows/ci.yml".into()),
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
