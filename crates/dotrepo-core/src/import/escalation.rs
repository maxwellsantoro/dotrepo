use super::adjudication::{AdjudicationTier, ImportEscalationOptions, TieredAdjudicationProviders};
use super::commands::load_first_existing_file;
use super::commands::sanitize_import_command;
use super::{
    apply_adjudication_response, apply_adjudication_results, build_adjudication_requests,
    is_actionable_security_url, parse_codeowners_metadata, parse_contributing_security,
    parse_issue_template_security, parse_readme_security, parse_security_import_metadata,
    push_unique, AdjudicationCandidate, AdjudicationModelConfidence, AdjudicationModelResponse,
    AdjudicationOutcome, AdjudicationRequest, AdjudicationResult, CommandCandidateSelection,
    CommandSourceTier, FieldConfidence, FieldScoreReport, ImportPlan, ImportedCommandProvenance,
    VerificationReport, IMPORT_README_CANDIDATES,
};
use dotrepo_schema::{BuildTestCandidate, Owners};
use std::collections::HashSet;
use std::path::Path;

const ESCALATION_TIERS: [CommandSourceTier; 6] = [
    CommandSourceTier::GitHubApi,
    CommandSourceTier::Manifest,
    CommandSourceTier::ContribDoc,
    CommandSourceTier::TaskScript,
    CommandSourceTier::Workflow,
    CommandSourceTier::EcosystemDefault,
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
    let is_command_field = request.field == "repo.build" || request.field == "repo.test";
    if request.field == "repo.test" {
        if let Some(source_paths) =
            conflicting_cross_ecosystem_test_sources_for_adjudication(&request.candidates)
        {
            if defer_conflicts_to_model {
                return AdjudicationResult {
                    field: request.field.clone(),
                    outcome: AdjudicationOutcome::Rejected {
                        model_value: String::new(),
                        reason: format!(
                            "conflicting test candidates from {} deferred to model adjudication",
                            source_paths.join(", ")
                        ),
                    },
                };
            }
            return apply_adjudication_response(
                &AdjudicationModelResponse {
                    field: request.field.clone(),
                    value: None,
                    confidence: AdjudicationModelConfidence::High,
                    reason: format!(
                        "conflicting test candidates from {}",
                        source_paths.join(", ")
                    ),
                    source: None,
                },
                request,
            );
        }
    }
    for tier in ESCALATION_TIERS {
        let tier_candidates: Vec<_> = request
            .candidates
            .iter()
            .filter(|candidate| candidate.source_tier == tier)
            .filter(|candidate| {
                if is_command_field {
                    sanitize_import_command(&candidate.value).is_some()
                } else {
                    !candidate.value.trim().is_empty()
                }
            })
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
                CommandSourceTier::GitHubApi
                | CommandSourceTier::Manifest
                | CommandSourceTier::ContribDoc
                | CommandSourceTier::TaskScript => FieldConfidence::HighConfidencePresent,
                CommandSourceTier::Workflow | CommandSourceTier::EcosystemDefault => {
                    FieldConfidence::MediumConfidencePresent
                }
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
        FieldConfidence::Suspect | FieldConfidence::Unresolved => AdjudicationModelConfidence::Low,
    }
}

fn conflicting_cross_ecosystem_test_sources_for_adjudication(
    candidates: &[AdjudicationCandidate],
) -> Option<Vec<String>> {
    let node = candidates.iter().find(|candidate| {
        candidate.source_tier == CommandSourceTier::Manifest
            && candidate.source_path == "package.json"
            && is_node_package_test_command(&candidate.value)
    })?;
    let python = candidates.iter().find(|candidate| {
        candidate.source_tier == CommandSourceTier::EcosystemDefault
            && matches!(
                candidate.source_path.as_str(),
                "pyproject.toml" | "setup.py" | "setup.cfg"
            )
            && is_python_test_command(&candidate.value)
            && candidate.value != node.value
    })?;

    let mut source_paths = Vec::new();
    push_unique(&mut source_paths, node.source_path.clone());
    push_unique(&mut source_paths, python.source_path.clone());
    Some(source_paths)
}

fn is_node_package_test_command(command: &str) -> bool {
    matches!(
        command.trim(),
        "npm test" | "pnpm test" | "yarn test" | "bun test"
    )
}

fn is_python_test_command(command: &str) -> bool {
    matches!(
        command.trim(),
        "python -m pytest" | "python -m unittest discover" | "tox" | "nox"
    )
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
                let source_tier = request
                    .candidates
                    .iter()
                    .find(|candidate| candidate.value == *value)
                    .map(|candidate| candidate.source_tier)
                    .unwrap_or(CommandSourceTier::Workflow);
                let provenance = if matches!(
                    source_tier,
                    CommandSourceTier::GitHubApi
                        | CommandSourceTier::Manifest
                        | CommandSourceTier::ContribDoc
                        | CommandSourceTier::TaskScript
                ) {
                    ImportedCommandProvenance::Imported
                } else {
                    ImportedCommandProvenance::Inferred
                };
                let selection = CommandCandidateSelection {
                    command: safe_value.clone(),
                    source_path: source_path.clone(),
                    source_tier,
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
                } else if result.field == "repo.name" {
                    plan.manifest.repo.name = safe_value;
                } else if result.field == "repo.description" {
                    plan.manifest.repo.description = safe_value;
                }
                if let Some(ref mut evidence) = plan.evidence_text {
                    evidence.push_str("\n- ");
                    evidence.push_str(&bullet);
                }
                note_trust_resolution(plan, &result.field, &source_path, escalation_label);
            }
            AdjudicationOutcome::Absent { reason } => {
                let preserved_candidates = distinct_command_candidates(&request.candidates);
                if result.field == "repo.build" {
                    plan.manifest.repo.build = None;
                    plan.command_candidates.selected_build = None;
                    plan.manifest.repo.build_candidates = preserved_candidates.clone();
                } else if result.field == "repo.test" {
                    plan.manifest.repo.test = None;
                    plan.command_candidates.selected_test = None;
                    plan.manifest.repo.test_candidates = preserved_candidates.clone();
                }
                if let Some(ref mut evidence) = plan.evidence_text {
                    evidence.push_str("\n- Left `");
                    evidence.push_str(&result.field);
                    evidence.push_str("` unset after ");
                    evidence.push_str(escalation_label);
                    evidence.push_str(" escalation: ");
                    evidence.push_str(reason);
                    evidence.push('.');
                    if preserved_candidates.len() > 1 {
                        evidence.push_str(" Preserved ");
                        evidence.push_str(&preserved_candidates.len().to_string());
                        evidence.push_str(" candidate command(s) in `");
                        evidence.push_str(&result.field);
                        evidence.push_str("_candidates` instead of discarding them.");
                    }
                }
            }
            AdjudicationOutcome::Rejected { .. } => {}
        }
    }
}

fn note_trust_resolution(
    plan: &mut ImportPlan,
    field: &str,
    source_path: &str,
    escalation_label: &str,
) {
    let Some(trust) = plan.manifest.record.trust.as_mut() else {
        return;
    };
    let mut notes = trust.notes.take().unwrap_or_default();
    remove_stale_unset_note(&mut notes, field);
    let resolution_note =
        format!("Resolved `{field}` from `{source_path}` after {escalation_label} escalation.");
    if notes.is_empty() {
        notes = resolution_note;
    } else if !notes.contains(&resolution_note) {
        notes.push(' ');
        notes.push_str(&resolution_note);
    }
    trust.notes = Some(notes);
}

fn remove_stale_unset_note(notes: &mut String, field: &str) {
    let marker = format!("Left `{field}` unset because");
    let Some(start) = notes.find(&marker) else {
        return;
    };
    let after_marker = start + marker.len();
    let end = notes[after_marker..]
        .find(". ")
        .map(|idx| after_marker + idx + 2)
        .or_else(|| {
            notes[after_marker..]
                .rfind('.')
                .map(|idx| after_marker + idx + 1)
        })
        .unwrap_or(notes.len());
    notes.replace_range(start..end, "");
    *notes = notes.split_whitespace().collect::<Vec<_>>().join(" ");
}

/// Deduplicates candidate commands by value, preserving first-seen order,
/// and tags each with a best-effort ecosystem label. Used to populate
/// `repo.build_candidates`/`repo.test_candidates` when no single command
/// could be honestly chosen as primary (see `Repo::build_candidates`'s
/// doc comment and RFC 0020).
fn distinct_command_candidates(candidates: &[AdjudicationCandidate]) -> Vec<BuildTestCandidate> {
    let mut seen = HashSet::new();
    let mut result = Vec::new();
    for candidate in candidates {
        let Some(command) = sanitize_import_command(&candidate.value) else {
            continue;
        };
        if !seen.insert(command.clone()) {
            continue;
        }
        result.push(BuildTestCandidate {
            command,
            ecosystem: ecosystem_for_source_path(&candidate.source_path),
            source: candidate.source_path.clone(),
        });
    }
    result
}

/// Best-effort ecosystem label for a known manifest/build-file path, used
/// only to make preserved build/test candidates easier for a human or agent
/// to tell apart at a glance. Returns `None` for unrecognized paths (e.g.
/// arbitrary CI workflow files) rather than guessing.
fn ecosystem_for_source_path(source_path: &str) -> Option<String> {
    let file_name = Path::new(source_path)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(source_path);
    let label = match file_name {
        "Cargo.toml" => "Rust",
        "package.json" => "Node.js",
        "pyproject.toml" | "setup.py" | "setup.cfg" => "Python",
        "go.mod" => "Go",
        "pom.xml" => "Java (Maven)",
        "build.gradle" | "build.gradle.kts" => "Java/Kotlin (Gradle)",
        "composer.json" => "PHP",
        "mix.exs" => "Elixir",
        "rebar.config" => "Erlang",
        "Rakefile" | "rakefile" => "Ruby",
        "CMakePresets.json" => "C/C++ (CMake)",
        _ if file_name.ends_with(".csproj") => ".NET",
        _ => return None,
    };
    Some(label.to_string())
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
    let mut suspect = Vec::new();
    let mut unresolved = Vec::new();
    for score in &field_scores.scores {
        match score.confidence {
            FieldConfidence::HighConfidencePresent => {
                high_confidence_present.push(score.field.clone())
            }
            FieldConfidence::MediumConfidencePresent => {
                medium_confidence_present.push(score.field.clone())
            }
            FieldConfidence::Suspect => suspect.push(score.field.clone()),
            FieldConfidence::HighConfidenceAbsent => {
                high_confidence_absent.push(score.field.clone())
            }
            FieldConfidence::Unresolved => unresolved.push(score.field.clone()),
        }
    }
    field_scores.summary.high_confidence_present = high_confidence_present;
    field_scores.summary.medium_confidence_present = medium_confidence_present;
    field_scores.summary.high_confidence_absent = high_confidence_absent;
    field_scores.summary.suspect = suspect;
    field_scores.summary.unresolved = unresolved;
    field_scores.summary.eligible_for_auto_publish = field_scores.summary.unresolved.is_empty()
        && field_scores.summary.medium_confidence_present.is_empty();
    field_scores.summary.eligible_for_auto_publish &= field_scores.summary.suspect.is_empty();
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
            let is_low_confidence =
                provider_response.response.confidence == AdjudicationModelConfidence::Low;
            // A `Rejected` outcome (model proposed a value outside the
            // candidate set) has always escalated when low-confidence. An
            // `Absent` outcome (model explicitly declined to answer) did
            // not: any confidence level was previously treated as a final,
            // accepted "honest unknown", so a cheap tier's uncertain guess
            // at genuine ambiguity could never get a second opinion from a
            // stronger model. A *confident* Absent (e.g. correctly
            // identifying a polyglot repository with no single valid
            // answer) still terminates immediately here -- only a
            // low-confidence Absent now continues up the tier ladder, the
            // same as a low-confidence Rejected already did.
            let accepted = !(matches!(result.outcome, AdjudicationOutcome::Rejected { .. })
                || is_low_confidence
                    && matches!(result.outcome, AdjudicationOutcome::Absent { .. }));
            last_result = Some(result);
            if accepted {
                resolved = true;
                break;
            }
            if !is_low_confidence {
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
