use anyhow::{bail, Result};
use dotrepo_schema::{Manifest, RecordStatus};
use std::fs;
use std::path::Path;

use crate::import::{FieldConfidence, FieldScore, FieldScoreReport};
use crate::validation::collect_record_paths;

#[derive(Debug, Clone)]
pub struct PromotionRecordScore {
    pub path: String,
    pub source_url: Option<String>,
    pub status: Option<String>,
    pub scores: Vec<FieldScore>,
    pub eligible: bool,
}

#[derive(Debug, Clone, Default)]
pub struct PromotionSummary {
    pub total_records: usize,
    pub eligible_count: usize,
    pub promotion_candidate_count: usize,
    pub field_blocker_counts: std::collections::HashMap<String, usize>,
}

#[derive(Debug, Clone)]
pub struct PromotionReport {
    pub records: Vec<PromotionRecordScore>,
    pub summary: PromotionSummary,
}

#[derive(Debug, Clone)]
pub struct PromotionAppliedRecord {
    pub path: String,
    pub previous_status: String,
    pub reason: String,
}

#[derive(Debug, Clone, Default)]
pub struct PromotionApplyReport {
    pub promoted_records: Vec<PromotionAppliedRecord>,
    pub skipped_eligible_count: usize,
}
#[derive(Debug, Clone)]
pub struct PromotionOutcome {
    pub promoted: bool,
    pub previous_status: String,
    pub reason: String,
}

#[derive(Debug, Clone, Default)]
pub struct DowngradeGuardOutcome {
    /// Retained for API compatibility. Fresh verification is always required,
    /// so prior authority is never restored by this report.
    pub preserved: bool,
    /// Factual fields that changed since the previous verified record.
    pub regressed_fields: Vec<String>,
}

fn status_rank(status: &RecordStatus) -> u8 {
    match status {
        RecordStatus::Draft => 0,
        RecordStatus::Imported => 1,
        RecordStatus::Inferred => 2,
        RecordStatus::Reviewed => 3,
        RecordStatus::Verified => 4,
        RecordStatus::Canonical => 5,
    }
}

/// Report changes when a previously verified overlay receives a lower fresh score.
/// Previous authority is never evidence for new verification: callers must use
/// the current field scores to promote a refresh. In particular, canonical
/// authority cannot be inherited by an autonomously rebuilt overlay.
pub fn guard_against_unjustified_downgrade(
    previous: Option<&Manifest>,
    fresh: &mut Manifest,
) -> Option<DowngradeGuardOutcome> {
    let previous = previous?;
    if previous.record.status != RecordStatus::Verified
        || status_rank(&fresh.record.status) >= status_rank(&previous.record.status)
    {
        return None;
    }
    fn changes(
        path: &str,
        old: &serde_json::Value,
        new: &serde_json::Value,
        out: &mut Vec<String>,
    ) {
        if old == new {
            return;
        }
        if let (Some(old), Some(new)) = (old.as_object(), new.as_object()) {
            let keys: std::collections::BTreeSet<_> = old.keys().chain(new.keys()).collect();
            for key in keys {
                changes(
                    &format!("{path}.{key}"),
                    &old.get(key).cloned().unwrap_or_default(),
                    &new.get(key).cloned().unwrap_or_default(),
                    out,
                );
            }
        } else {
            out.push(path.to_string());
        }
    }
    let old = serde_json::to_value(previous).expect("manifest is serializable");
    let new = serde_json::to_value(&*fresh).expect("manifest is serializable");
    let mut regressed_fields = Vec::new();
    for field in ["repo", "owners", "docs", "readme", "compat", "relations"] {
        changes(field, &old[field], &new[field], &mut regressed_fields);
    }
    Some(DowngradeGuardOutcome {
        preserved: false,
        regressed_fields,
    })
}

pub fn promote_to_verified(manifest: &mut Manifest, report: &FieldScoreReport) -> PromotionOutcome {
    let previous_status = match manifest.record.status {
        RecordStatus::Draft => "draft",
        RecordStatus::Imported => "imported",
        RecordStatus::Inferred => "inferred",
        RecordStatus::Reviewed => "reviewed",
        RecordStatus::Verified => "verified",
        RecordStatus::Canonical => "canonical",
    }
    .to_string();

    // Never downgrade from reviewed or canonical
    if matches!(
        manifest.record.status,
        RecordStatus::Reviewed | RecordStatus::Canonical
    ) {
        return PromotionOutcome {
            promoted: false,
            previous_status,
            reason: "record already at reviewed or canonical; will not downgrade".to_string(),
        };
    }

    if !report.summary.eligible_for_auto_publish {
        return PromotionOutcome {
            promoted: false,
            previous_status,
            reason: format!(
                "not all fields are honestly resolved: {} unresolved, {} medium-confidence",
                report.summary.unresolved.len(),
                report.summary.medium_confidence_present.len(),
            ),
        };
    }

    manifest.record.status = RecordStatus::Verified;

    // Update trust provenance and confidence
    if let Some(ref mut trust) = manifest.record.trust {
        trust.confidence = Some("high".into());
        if !trust.provenance.contains(&"verified".to_string()) {
            trust.provenance.push("verified".into());
        }
        let existing_notes = trust.notes.take().unwrap_or_default();
        trust.notes = Some(if existing_notes.is_empty() {
            "Auto-promoted to verified: all fields are honestly resolved.".to_string()
        } else {
            format!(
                "{} Auto-promoted to verified: all fields are honestly resolved.",
                existing_notes
            )
        });
    }

    PromotionOutcome {
        promoted: true,
        previous_status,
        reason: "all fields are high-confidence present or high-confidence absent".to_string(),
    }
}

/// Inspect retained, value-bound assessments. This does not inspect upstream sources
/// and cannot authorize standalone promotion; use a fresh crawler verification.
pub fn score_index_record_for_promotion(manifest: &Manifest) -> Vec<FieldScore> {
    let evidence = crate::public::field_evidence(manifest);
    [
        "repo.name",
        "repo.description",
        "repo.homepage",
        "repo.build",
        "repo.test",
        "owners.security_contact",
        "owners.team",
        "docs.root",
        "docs.getting_started",
    ]
    .into_iter()
    .map(|field| {
        let value = crate::query_manifest_value(manifest, field).unwrap_or_default();
        let assessment = evidence.get(field);
        let get = |key| {
            assessment
                .and_then(|a| a.get(key))
                .and_then(serde_json::Value::as_str)
        };
        let source = get("source")
            .filter(|s| !s.trim().is_empty())
            .map(str::to_owned);
        let confidence = match (get("state"), get("confidence"), get("method")) {
            (Some("present"), Some("high"), Some("extracted"))
                if value.as_str().is_some_and(|v| !v.trim().is_empty()) && source.is_some() =>
            {
                FieldConfidence::HighConfidencePresent
            }
            (Some("present"), Some("medium"), Some("extracted" | "inferred"))
                if value.as_str().is_some_and(|v| !v.trim().is_empty()) =>
            {
                FieldConfidence::MediumConfidencePresent
            }
            (Some("not_found"), Some("high"), Some("not_found_in_inspected_sources"))
                if value.is_null() =>
            {
                FieldConfidence::HighConfidenceAbsent
            }
            _ => FieldConfidence::Unresolved,
        };
        FieldScore {
            field: field.into(),
            confidence: confidence.clone(),
            source,
            value: value.as_str().map(str::to_owned),
            reason: if confidence == FieldConfidence::Unresolved {
                "missing, invalidated, or insufficient field assessment; fresh inspection required"
                    .into()
            } else {
                "retained field assessment only; fresh inspection required for promotion".into()
            },
        }
    })
    .collect()
}

pub fn analyze_index_promotion(index_root: &Path) -> Result<PromotionReport> {
    let repos_dir = index_root.join("repos");
    if !repos_dir.exists() {
        bail!("index repos directory not found: {}", repos_dir.display());
    }

    let mut records: Vec<PromotionRecordScore> = Vec::new();
    let mut record_paths = Vec::new();
    collect_record_paths(&repos_dir, &mut record_paths)?;

    for path in record_paths {
        let relative = path
            .strip_prefix(&repos_dir)
            .unwrap_or(&path)
            .to_string_lossy()
            .to_string();

        let contents = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(e) => {
                records.push(PromotionRecordScore {
                    path: relative,
                    source_url: None,
                    status: None,
                    scores: vec![FieldScore {
                        field: "record.read".into(),
                        confidence: FieldConfidence::Unresolved,
                        source: None,
                        value: None,
                        reason: format!("unreadable: {e}"),
                    }],
                    eligible: false,
                });
                continue;
            }
        };
        let manifest: Manifest = match toml::from_str(&contents) {
            Ok(m) => m,
            Err(e) => {
                records.push(PromotionRecordScore {
                    path: relative,
                    source_url: None,
                    status: None,
                    scores: vec![FieldScore {
                        field: "record.parse".into(),
                        confidence: FieldConfidence::Unresolved,
                        source: None,
                        value: None,
                        reason: format!("invalid TOML: {e}"),
                    }],
                    eligible: false,
                });
                continue;
            }
        };

        let scores = score_index_record_for_promotion(&manifest);
        let eligible = scores.iter().all(|s| {
            s.confidence == FieldConfidence::HighConfidencePresent
                || s.confidence == FieldConfidence::HighConfidenceAbsent
        });

        let status_str = match manifest.record.status {
            dotrepo_schema::RecordStatus::Draft => "draft".to_string(),
            dotrepo_schema::RecordStatus::Imported => "imported".to_string(),
            dotrepo_schema::RecordStatus::Inferred => "inferred".to_string(),
            dotrepo_schema::RecordStatus::Reviewed => "reviewed".to_string(),
            dotrepo_schema::RecordStatus::Verified => "verified".to_string(),
            dotrepo_schema::RecordStatus::Canonical => "canonical".to_string(),
        };

        records.push(PromotionRecordScore {
            path: relative,
            source_url: manifest.record.source.clone(),
            status: Some(status_str),
            scores,
            eligible,
        });
    }

    records.sort_by(|a, b| a.path.cmp(&b.path));

    let mut field_blocker_counts = std::collections::HashMap::new();
    for record in &records {
        if !record.eligible {
            for score in &record.scores {
                if score.confidence == FieldConfidence::Unresolved
                    || score.confidence == FieldConfidence::MediumConfidencePresent
                {
                    *field_blocker_counts.entry(score.field.clone()).or_insert(0) += 1;
                }
            }
        }
    }

    let eligible_count = records.iter().filter(|r| r.eligible).count();
    let promotion_candidate_count = records
        .iter()
        .filter(|record| {
            record.eligible
                && matches!(
                    record.status.as_deref(),
                    Some("draft" | "imported" | "inferred")
                )
        })
        .count();
    let total_records = records.len();

    Ok(PromotionReport {
        records,
        summary: PromotionSummary {
            total_records,
            eligible_count,
            promotion_candidate_count,
            field_blocker_counts,
        },
    })
}

/// Standalone manifests cannot establish that the claimed checks actually ran.
/// Keep the facade compatible, but fail before any record or evidence file write.
pub fn apply_index_promotions(
    _index_root: &Path,
    _limit: Option<usize>,
) -> Result<PromotionApplyReport> {
    bail!("standalone promotion is disabled: run a fresh crawler verification against inspected sources; retained assessments and record-wide provenance cannot authorize --apply")
}
