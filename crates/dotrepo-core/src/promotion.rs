use anyhow::{bail, Result};
use dotrepo_schema::{render_manifest, Manifest, RecordStatus};
use std::fs;
use std::path::Path;

use crate::import::{
    is_actionable_security_url, is_quality_url, FieldConfidence, FieldScore, FieldScoreReport,
};
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
    /// True when a prior verified-or-higher status/confidence was restored
    /// onto `manifest` because no field-level regression was found.
    pub preserved: bool,
    /// Fields that were present (or high-confidence-absent) in the previous
    /// record but are missing/unresolved in the fresh import. Non-empty only
    /// when `preserved` is false and a genuine regression justified letting
    /// the fresh, lower status stand.
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

/// Tracked fields whose presence we can compare between a previous on-disk
/// manifest and a freshly rebuilt import, mirroring the field set scored by
/// `dotrepo_core::import::score_import_fields`. A field counts as "present"
/// here when it carries a real, non-placeholder value; `owners.security_contact
/// = "unknown"` is treated the same as absent because that value is itself an
/// intentional, documented absence marker (see `docs/import-baseline-audit.md`).
fn tracked_field_presence(manifest: &Manifest) -> Vec<(&'static str, bool)> {
    let non_empty = |value: Option<&str>| value.is_some_and(|v| !v.trim().is_empty());
    let owners = manifest.owners.as_ref();
    let docs = manifest.docs.as_ref();
    let security_contact = owners.and_then(|o| o.security_contact.as_deref());
    vec![
        (
            "repo.homepage",
            non_empty(manifest.repo.homepage.as_deref()),
        ),
        ("repo.build", non_empty(manifest.repo.build.as_deref())),
        ("repo.test", non_empty(manifest.repo.test.as_deref())),
        (
            "owners.security_contact",
            security_contact.is_some_and(|contact| contact != "unknown")
                && non_empty(security_contact),
        ),
        (
            "owners.team",
            non_empty(owners.and_then(|o| o.team.as_deref())),
        ),
        ("docs.root", non_empty(docs.and_then(|d| d.root.as_deref()))),
        (
            "docs.getting_started",
            non_empty(docs.and_then(|d| d.getting_started.as_deref())),
        ),
    ]
}

/// Fields present in `previous` but missing in `fresh`: a genuine regression,
/// as opposed to the fresh import merely scoring an unchanged or additional
/// field below high confidence.
fn regressed_fields(previous: &Manifest, fresh: &Manifest) -> Vec<String> {
    let fresh_presence: std::collections::HashMap<&str, bool> =
        tracked_field_presence(fresh).into_iter().collect();
    tracked_field_presence(previous)
        .into_iter()
        .filter(|(field, was_present)| {
            *was_present && !fresh_presence.get(field).copied().unwrap_or(false)
        })
        .map(|(field, _)| field.to_string())
        .collect()
}

/// Guards a freshly rebuilt overlay import against silently regressing an
/// already-`verified`-or-higher on-disk record. The crawler rebuilds each
/// overlay manifest from scratch on every refresh; without this guard, a
/// record already at `verified`/`high` confidence could drop back to a lower
/// status/confidence purely because the fresh re-scoring judged some field
/// (often a newly gained one) below high confidence, even though nothing the
/// previous record had established was actually lost. That is re-scoring
/// noise, not a real regression, and should not silently discard trust state.
///
/// If `previous` is `Some` and at `verified` or higher, and `fresh`'s status
/// is currently lower than `previous`'s, this checks whether any field
/// `previous` had present (or intentionally absent) is now missing/unresolved
/// in `fresh`:
/// - If no such regression is found, `fresh`'s status and confidence are
///   restored to `previous`'s, and a clear note is appended explaining why.
/// - If a genuine regression is found, `fresh` is left as scored (the lower
///   status honestly reflects what changed), and the caller can surface
///   `regressed_fields` in evidence/notes so this isn't silently lost either.
///
/// Returns `None` when there is no prior record to protect, the prior record
/// was below `verified`, or the fresh status is already at or above the
/// previous status (nothing to guard).
pub fn guard_against_unjustified_downgrade(
    previous: Option<&Manifest>,
    fresh: &mut Manifest,
) -> Option<DowngradeGuardOutcome> {
    let previous = previous?;
    if status_rank(&previous.record.status) < status_rank(&RecordStatus::Verified) {
        return None;
    }
    if status_rank(&fresh.record.status) >= status_rank(&previous.record.status) {
        return None;
    }

    let regressed = regressed_fields(previous, fresh);
    if !regressed.is_empty() {
        return Some(DowngradeGuardOutcome {
            preserved: false,
            regressed_fields: regressed,
        });
    }

    fresh.record.status = previous.record.status.clone();
    let previous_confidence = previous
        .record
        .trust
        .as_ref()
        .and_then(|trust| trust.confidence.clone())
        .unwrap_or_else(|| "high".to_string());
    let previous_provenance = previous
        .record
        .trust
        .as_ref()
        .map(|trust| trust.provenance.clone())
        .unwrap_or_default();
    if let Some(ref mut trust) = fresh.record.trust {
        trust.confidence = Some(previous_confidence);
        for entry in previous_provenance {
            if !trust.provenance.contains(&entry) {
                trust.provenance.push(entry);
            }
        }
        let existing_notes = trust.notes.take().unwrap_or_default();
        let guard_note = "Preserved prior verified status: no previously present field regressed in this refresh.";
        trust.notes = Some(if existing_notes.is_empty() {
            guard_note.to_string()
        } else if existing_notes.contains(guard_note) {
            existing_notes
        } else {
            format!("{existing_notes} {guard_note}")
        });
    }

    Some(DowngradeGuardOutcome {
        preserved: true,
        regressed_fields: Vec::new(),
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

fn field_score_report_from_scores(scores: &[FieldScore]) -> FieldScoreReport {
    let mut high_confidence_present = Vec::new();
    let mut medium_confidence_present = Vec::new();
    let mut high_confidence_absent = Vec::new();
    let mut unresolved = Vec::new();

    for score in scores {
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

    FieldScoreReport {
        scores: scores.to_vec(),
        summary: crate::import::FieldScoreSummary {
            eligible_for_auto_publish: unresolved.is_empty()
                && medium_confidence_present.is_empty(),
            high_confidence_present,
            medium_confidence_present,
            high_confidence_absent,
            unresolved,
        },
    }
}

pub fn score_index_record_for_promotion(manifest: &Manifest) -> Vec<FieldScore> {
    let mut scores = Vec::new();
    let provenance = manifest
        .record
        .trust
        .as_ref()
        .map(|t| t.provenance.clone())
        .unwrap_or_default();

    // repo.name — always high confidence if present (post-cleaners guarantee)
    scores.push(FieldScore {
        field: "repo.name".into(),
        confidence: if manifest.repo.name.is_empty() {
            FieldConfidence::Unresolved
        } else {
            FieldConfidence::HighConfidencePresent
        },
        source: None,
        value: if manifest.repo.name.is_empty() {
            None
        } else {
            Some(manifest.repo.name.clone())
        },
        reason: if manifest.repo.name.is_empty() {
            "name not set".into()
        } else {
            "post-cleaners guarantee quality".into()
        },
    });

    // repo.description — high confidence if present
    scores.push(FieldScore {
        field: "repo.description".into(),
        confidence: if manifest.repo.description.is_empty() {
            FieldConfidence::Unresolved
        } else {
            FieldConfidence::HighConfidencePresent
        },
        source: None,
        value: if manifest.repo.description.is_empty() {
            None
        } else {
            Some(manifest.repo.description.clone())
        },
        reason: if manifest.repo.description.is_empty() {
            "description not set".into()
        } else {
            "post-cleaners guarantee quality".into()
        },
    });

    // repo.homepage
    if let Some(ref homepage) = manifest.repo.homepage {
        let is_github_url = homepage.contains("github.com");
        scores.push(FieldScore {
            field: "repo.homepage".into(),
            confidence: if is_quality_url(homepage) {
                FieldConfidence::HighConfidencePresent
            } else {
                FieldConfidence::MediumConfidencePresent
            },
            source: None,
            value: Some(homepage.clone()),
            reason: if is_github_url {
                "GitHub repo URL, no dedicated site found".into()
            } else {
                "quality URL".into()
            },
        });
    } else {
        scores.push(FieldScore {
            field: "repo.homepage".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no homepage".into(),
        });
    }

    // repo.build / repo.test — score primarily from provenance.
    // We still perform a narrow, exact-phrase check against trust.notes to detect
    // intra-tier command conflicts (the only remaining case that should surface as
    // Unresolved for promotion analysis). This is the single documented exception to
    // "do not parse notes for scoring". When a machine-readable conflict marker is
    // added to Trust/Record we can remove the notes check entirely.
    let has_imported_provenance = provenance.iter().any(|p| p == "imported");
    let has_inferred_provenance = provenance.iter().any(|p| p == "inferred");
    let trust_notes = manifest
        .record
        .trust
        .as_ref()
        .and_then(|t| t.notes.as_deref())
        .unwrap_or("");

    if let Some(ref build) = manifest.repo.build {
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: if has_imported_provenance {
                FieldConfidence::HighConfidencePresent
            } else if has_inferred_provenance {
                FieldConfidence::MediumConfidencePresent
            } else {
                FieldConfidence::HighConfidencePresent
            },
            source: None,
            value: Some(build.clone()),
            reason: if has_imported_provenance {
                "from manifest source".into()
            } else if has_inferred_provenance {
                "from workflow or inferred fallback".into()
            } else {
                "present, provenance not specified".into()
            },
        });
    } else {
        let is_conflict = trust_notes.contains("Left `repo.build` unset because")
            && trust_notes.contains("conflicting build commands");
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: if is_conflict {
                FieldConfidence::Unresolved
            } else {
                FieldConfidence::HighConfidenceAbsent
            },
            source: None,
            value: None,
            reason: if is_conflict {
                "intra-tier conflict left field unset during import".into()
            } else {
                "no build command sources".into()
            },
        });
    }

    if let Some(ref test) = manifest.repo.test {
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: if has_imported_provenance {
                FieldConfidence::HighConfidencePresent
            } else if has_inferred_provenance {
                FieldConfidence::MediumConfidencePresent
            } else {
                FieldConfidence::HighConfidencePresent
            },
            source: None,
            value: Some(test.clone()),
            reason: if has_imported_provenance {
                "from manifest source".into()
            } else if has_inferred_provenance {
                "from workflow or inferred fallback".into()
            } else {
                "present, provenance not specified".into()
            },
        });
    } else {
        let is_conflict = trust_notes.contains("Left `repo.test` unset because")
            && trust_notes.contains("conflicting test commands");
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: if is_conflict {
                FieldConfidence::Unresolved
            } else {
                FieldConfidence::HighConfidenceAbsent
            },
            source: None,
            value: None,
            reason: if is_conflict {
                "intra-tier conflict left field unset during import".into()
            } else {
                "no test command sources".into()
            },
        });
    }

    // owners.security_contact
    let owners = manifest.owners.as_ref();
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
                source: None,
                value: Some(contact.into()),
                reason: "direct email or mailing list".into(),
            });
        } else if is_actionable_security_url(contact) {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                source: None,
                value: Some(contact.into()),
                reason: "actionable security reporting URL".into(),
            });
        } else {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::MediumConfidencePresent,
                source: None,
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
            reason: "no security contact sources found".into(),
        });
    }

    // owners.team
    let team = owners.and_then(|o| o.team.as_deref());
    scores.push(FieldScore {
        field: "owners.team".into(),
        confidence: if team.is_some() {
            FieldConfidence::HighConfidencePresent
        } else {
            FieldConfidence::HighConfidenceAbsent
        },
        source: None,
        value: team.map(|t| t.to_string()),
        reason: if team.is_some() {
            "clear CODEOWNERS team".into()
        } else {
            "no single clear team".into()
        },
    });

    // docs.root
    if let Some(ref docs) = &manifest.docs {
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
                reason: "no docs site".into(),
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
    if let Some(ref docs) = &manifest.docs {
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
                reason: "no getting started link".into(),
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

    scores
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

pub fn apply_index_promotions(
    index_root: &Path,
    limit: Option<usize>,
) -> Result<PromotionApplyReport> {
    let repos_dir = index_root.join("repos");
    if !repos_dir.exists() {
        bail!("index repos directory not found: {}", repos_dir.display());
    }

    let mut record_paths = Vec::new();
    collect_record_paths(&repos_dir, &mut record_paths)?;
    record_paths.sort();

    let mut promoted_records = Vec::new();
    let mut skipped_eligible_count = 0;
    let max_promotions = limit.unwrap_or(usize::MAX);

    for path in record_paths {
        let contents = fs::read_to_string(&path)?;
        let mut manifest: Manifest = toml::from_str(&contents)?;
        let scores = score_index_record_for_promotion(&manifest);
        let score_report = field_score_report_from_scores(&scores);
        let eligible = score_report.summary.eligible_for_auto_publish;
        let is_candidate = matches!(
            manifest.record.status,
            RecordStatus::Draft | RecordStatus::Imported | RecordStatus::Inferred
        );
        if !eligible || !is_candidate {
            continue;
        }

        if promoted_records.len() >= max_promotions {
            skipped_eligible_count += 1;
            continue;
        }

        let outcome = promote_to_verified(&mut manifest, &score_report);
        if !outcome.promoted {
            continue;
        }
        let rendered = render_manifest(&manifest)?;
        fs::write(&path, rendered)?;
        append_auto_promotion_evidence(&path)?;
        let relative = path
            .strip_prefix(&repos_dir)
            .unwrap_or(&path)
            .to_string_lossy()
            .to_string();
        promoted_records.push(PromotionAppliedRecord {
            path: relative,
            previous_status: outcome.previous_status,
            reason: outcome.reason,
        });
    }

    Ok(PromotionApplyReport {
        promoted_records,
        skipped_eligible_count,
    })
}

fn append_auto_promotion_evidence(record_path: &Path) -> Result<()> {
    let evidence_path = record_path
        .parent()
        .map(|parent| parent.join("evidence.md"))
        .unwrap_or_else(|| Path::new("evidence.md").to_path_buf());
    let section = "\n## Auto-promotion\n\nRecord auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.\n";
    match fs::read_to_string(&evidence_path) {
        Ok(existing) if existing.contains("auto-promoted to verified") => Ok(()),
        Ok(mut existing) => {
            existing.push_str(section);
            fs::write(evidence_path, existing)?;
            Ok(())
        }
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            fs::write(evidence_path, section.trim_start())?;
            Ok(())
        }
        Err(err) => Err(err.into()),
    }
}
