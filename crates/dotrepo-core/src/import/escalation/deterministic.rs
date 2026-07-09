use super::super::commands::load_first_existing_file;
use super::super::commands::sanitize_import_command;
use super::super::{
    apply_adjudication_response, is_actionable_security_url, parse_codeowners_metadata,
    parse_contributing_security, parse_issue_template_security, parse_readme_security,
    parse_security_import_metadata, push_unique, AdjudicationCandidate,
    AdjudicationModelConfidence, AdjudicationModelResponse, AdjudicationOutcome,
    AdjudicationRequest, AdjudicationResult, CommandCandidateSelection, CommandSourceTier,
    FieldConfidence, FieldScoreReport, ImportPlan, ImportedCommandProvenance,
    IMPORT_README_CANDIDATES,
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

pub(crate) fn deepen_security_owners_deterministic(
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
