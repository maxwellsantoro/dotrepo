//! Field-resolution and reconciliation: scoring imported/inferred manifest
//! fields for confidence, building adjudication requests for unresolved
//! fields, and applying adjudication responses back into field scores.
use super::commands::sanitize_import_command;
use super::parsing::{is_actionable_security_url, is_quality_url};
use super::types::{
    AdjudicationCandidate, AdjudicationModelResponse, AdjudicationOutcome, AdjudicationRequest,
    AdjudicationResult, FieldConfidence, FieldScore, FieldScoreReport, FieldScoreSummary,
    ImportedCommandProvenance,
};
use super::{ImportPlan, VerificationReport};

pub fn score_import_fields(
    plan: &ImportPlan,
    verification: &VerificationReport,
) -> FieldScoreReport {
    let mut scores = Vec::new();

    // repo.name
    let name_has_readme_source = plan
        .imported_sources
        .iter()
        .any(|s| s.eq_ignore_ascii_case("readme.md"));
    scores.push(FieldScore {
        field: "repo.name".into(),
        confidence: if name_has_readme_source {
            FieldConfidence::HighConfidencePresent
        } else {
            FieldConfidence::MediumConfidencePresent
        },
        source: plan.imported_sources.first().cloned(),
        value: Some(plan.manifest.repo.name.clone()),
        reason: if name_has_readme_source {
            "extracted from README heading with post-cleaners".into()
        } else {
            "fell back to directory name or GitHub API".into()
        },
    });

    // repo.description
    scores.push(FieldScore {
        field: "repo.description".into(),
        confidence: if name_has_readme_source {
            FieldConfidence::HighConfidencePresent
        } else {
            FieldConfidence::MediumConfidencePresent
        },
        source: plan.imported_sources.first().cloned(),
        value: Some(plan.manifest.repo.description.clone()),
        reason: if name_has_readme_source {
            "extracted from README paragraph with post-cleaners".into()
        } else {
            "fell back to GitHub API or inferred".into()
        },
    });

    // repo.homepage
    if let Some(ref homepage) = plan.manifest.repo.homepage {
        scores.push(FieldScore {
            field: "repo.homepage".into(),
            confidence: if is_quality_url(homepage) {
                FieldConfidence::HighConfidencePresent
            } else {
                FieldConfidence::MediumConfidencePresent
            },
            source: None,
            value: Some(homepage.clone()),
            reason: "set and passes quality check".into(),
        });
    } else {
        scores.push(FieldScore {
            field: "repo.homepage".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no homepage detected".into(),
        });
    }

    // repo.build
    let build_unresolved = verification
        .unresolved_fields
        .contains(&"repo.build".to_string());
    let build_absent = verification
        .absent_fields
        .contains(&"repo.build".to_string());
    if let Some(ref build) = plan.manifest.repo.build {
        let is_manifest = plan
            .command_candidates
            .selected_build
            .as_ref()
            .map(|s| matches!(s.provenance, ImportedCommandProvenance::Imported))
            .unwrap_or(false);
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: if is_manifest {
                FieldConfidence::HighConfidencePresent
            } else {
                FieldConfidence::MediumConfidencePresent
            },
            source: plan
                .command_candidates
                .selected_build
                .as_ref()
                .map(|s| s.source_path.clone()),
            value: Some(build.clone()),
            reason: if is_manifest {
                "from manifest source".into()
            } else {
                "from workflow fallback".into()
            },
        });
    } else if build_unresolved {
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: FieldConfidence::Unresolved,
            source: None,
            value: None,
            reason: "conflicting candidates, no clear winner".into(),
        });
    } else if build_absent {
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no build command sources found".into(),
        });
    }

    // repo.test
    let test_unresolved = verification
        .unresolved_fields
        .contains(&"repo.test".to_string());
    let test_absent = verification
        .absent_fields
        .contains(&"repo.test".to_string());
    if let Some(ref test) = plan.manifest.repo.test {
        let is_manifest = plan
            .command_candidates
            .selected_test
            .as_ref()
            .map(|s| matches!(s.provenance, ImportedCommandProvenance::Imported))
            .unwrap_or(false);
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: if is_manifest {
                FieldConfidence::HighConfidencePresent
            } else {
                FieldConfidence::MediumConfidencePresent
            },
            source: plan
                .command_candidates
                .selected_test
                .as_ref()
                .map(|s| s.source_path.clone()),
            value: Some(test.clone()),
            reason: if is_manifest {
                "from manifest source".into()
            } else {
                "from workflow fallback".into()
            },
        });
    } else if test_unresolved {
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: FieldConfidence::Unresolved,
            source: None,
            value: None,
            reason: "conflicting candidates, no clear winner".into(),
        });
    } else if test_absent {
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no test command sources found".into(),
        });
    }

    // owners.security_contact
    let owners = plan.manifest.owners.as_ref();
    let security = owners.and_then(|o| o.security_contact.as_deref());
    if let Some(contact) = security {
        if contact == "unknown" {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::HighConfidenceAbsent,
                source: None,
                value: Some(contact.into()),
                reason: "explicitly unknown".into(),
            });
        } else if contact.contains('@') {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                source: plan.imported_sources.first().cloned(),
                value: Some(contact.into()),
                reason: "direct email or mailing list".into(),
            });
        } else if is_actionable_security_url(contact) {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                source: plan.imported_sources.first().cloned(),
                value: Some(contact.into()),
                reason: "actionable security reporting URL".into(),
            });
        } else {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::MediumConfidencePresent,
                source: plan.imported_sources.first().cloned(),
                value: Some(contact.into()),
                reason: "policy URL or non-email contact".into(),
            });
        }
    } else {
        scores.push(FieldScore {
            field: "owners.security_contact".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no SECURITY.md or security contact sources found".into(),
        });
    }

    // owners.team
    let team = owners.and_then(|o| o.team.as_deref());
    if let Some(team_val) = team {
        scores.push(FieldScore {
            field: "owners.team".into(),
            confidence: FieldConfidence::HighConfidencePresent,
            source: plan
                .imported_sources
                .iter()
                .find(|s| s.eq_ignore_ascii_case("codeowners"))
                .cloned(),
            value: Some(team_val.into()),
            reason: "clear CODEOWNERS team".into(),
        });
    } else {
        scores.push(FieldScore {
            field: "owners.team".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no single clear team in CODEOWNERS".into(),
        });
    }

    // docs.root
    if let Some(ref docs) = &plan.manifest.docs {
        if let Some(ref root) = docs.root {
            scores.push(FieldScore {
                field: "docs.root".into(),
                confidence: if is_quality_url(root) {
                    FieldConfidence::HighConfidencePresent
                } else {
                    FieldConfidence::MediumConfidencePresent
                },
                source: None,
                value: Some(root.clone()),
                reason: "docs URL present".into(),
            });
        } else {
            scores.push(FieldScore {
                field: "docs.root".into(),
                confidence: FieldConfidence::HighConfidenceAbsent,
                source: None,
                value: None,
                reason: "no docs site detected".into(),
            });
        }
    } else {
        scores.push(FieldScore {
            field: "docs.root".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no docs detected".into(),
        });
    }

    // docs.getting_started
    if let Some(ref docs) = &plan.manifest.docs {
        if let Some(ref gs) = docs.getting_started {
            scores.push(FieldScore {
                field: "docs.getting_started".into(),
                confidence: if is_quality_url(gs) {
                    FieldConfidence::HighConfidencePresent
                } else {
                    FieldConfidence::MediumConfidencePresent
                },
                source: None,
                value: Some(gs.clone()),
                reason: "getting started URL present".into(),
            });
        } else {
            scores.push(FieldScore {
                field: "docs.getting_started".into(),
                confidence: FieldConfidence::HighConfidenceAbsent,
                source: None,
                value: None,
                reason: "no getting started link detected".into(),
            });
        }
    } else {
        scores.push(FieldScore {
            field: "docs.getting_started".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no docs detected".into(),
        });
    }

    let high_confidence_present: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::HighConfidencePresent)
        .map(|s| s.field.clone())
        .collect();
    let medium_confidence_present: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::MediumConfidencePresent)
        .map(|s| s.field.clone())
        .collect();
    let high_confidence_absent: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::HighConfidenceAbsent)
        .map(|s| s.field.clone())
        .collect();
    let unresolved: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::Unresolved)
        .map(|s| s.field.clone())
        .collect();

    let eligible_for_auto_publish = unresolved.is_empty() && medium_confidence_present.is_empty();

    FieldScoreReport {
        scores,
        summary: FieldScoreSummary {
            high_confidence_present,
            medium_confidence_present,
            high_confidence_absent,
            unresolved,
            eligible_for_auto_publish,
        },
    }
}

pub fn build_adjudication_requests(
    report: &FieldScoreReport,
    plan: &ImportPlan,
) -> Vec<AdjudicationRequest> {
    let unresolved_fields: Vec<&str> = report
        .scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::Unresolved)
        .map(|s| s.field.as_str())
        .collect();

    if unresolved_fields.is_empty() {
        return Vec::new();
    }

    let mut requests = Vec::new();

    for field in &unresolved_fields {
        let is_build = *field == "repo.build";
        let is_test = *field == "repo.test";

        if !is_build && !is_test {
            continue;
        }

        let mut candidates = Vec::new();
        for candidate in &plan.command_candidates.candidates {
            let value = if is_build {
                candidate.build.as_ref()
            } else {
                candidate.test.as_ref()
            };
            if let Some(value) = value.filter(|command| sanitize_import_command(command).is_some())
            {
                candidates.push(AdjudicationCandidate {
                    value: value.clone(),
                    source_path: candidate.source_path.clone(),
                    source_tier: candidate.source_tier,
                });
            }
        }

        if !candidates.is_empty() {
            requests.push(AdjudicationRequest {
                field: field.to_string(),
                candidates,
            });
        }
    }

    requests
}

pub fn apply_adjudication_response(
    response: &AdjudicationModelResponse,
    request: &AdjudicationRequest,
) -> AdjudicationResult {
    let candidate_values: Vec<&str> = request
        .candidates
        .iter()
        .map(|c| c.value.as_str())
        .collect();

    match &response.value {
        Some(value) => {
            if candidate_values.iter().any(|c| *c == value) {
                AdjudicationResult {
                    field: response.field.clone(),
                    outcome: AdjudicationOutcome::Resolved {
                        value: value.clone(),
                        confidence: FieldConfidence::MediumConfidencePresent,
                        reason: response.reason.clone(),
                    },
                }
            } else {
                AdjudicationResult {
                    field: response.field.clone(),
                    outcome: AdjudicationOutcome::Rejected {
                        model_value: value.clone(),
                        reason: format!(
                            "model proposed value not in candidate set: {:?}",
                            candidate_values
                        ),
                    },
                }
            }
        }
        None => AdjudicationResult {
            field: response.field.clone(),
            outcome: AdjudicationOutcome::Absent {
                reason: response.reason.clone(),
            },
        },
    }
}

pub fn apply_adjudication_results(report: &mut FieldScoreReport, results: &[AdjudicationResult]) {
    for result in results {
        let Some(score) = report.scores.iter_mut().find(|s| s.field == result.field) else {
            continue;
        };
        match &result.outcome {
            AdjudicationOutcome::Resolved {
                value,
                confidence,
                reason,
            } => {
                score.confidence = confidence.clone();
                score.value = Some(value.clone());
                score.reason = format!("adjudicated: {}", reason);
            }
            AdjudicationOutcome::Absent { reason } => {
                score.confidence = FieldConfidence::HighConfidenceAbsent;
                score.value = None;
                score.reason = format!("adjudicated absent: {}", reason);
            }
            AdjudicationOutcome::Rejected { .. } => {
                // Leave as unresolved — model couldn't help
            }
        }
    }

    // Recompute summary
    let mut high_confidence_present = Vec::new();
    let mut medium_confidence_present = Vec::new();
    let mut high_confidence_absent = Vec::new();
    let mut unresolved = Vec::new();
    for score in &report.scores {
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
    report.summary.high_confidence_present = high_confidence_present;
    report.summary.medium_confidence_present = medium_confidence_present;
    report.summary.high_confidence_absent = high_confidence_absent;
    report.summary.unresolved = unresolved;
    report.summary.eligible_for_auto_publish =
        report.summary.unresolved.is_empty() && report.summary.medium_confidence_present.is_empty();
}
