use anyhow::{bail, Result};
use dotrepo_schema::{Manifest, RecordStatus};
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
    pub field_blocker_counts: std::collections::HashMap<String, usize>,
}

#[derive(Debug, Clone)]
pub struct PromotionReport {
    pub records: Vec<PromotionRecordScore>,
    pub summary: PromotionSummary,
}
#[derive(Debug, Clone)]
pub struct PromotionOutcome {
    pub promoted: bool,
    pub previous_status: String,
    pub reason: String,
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
    let total_records = records.len();

    Ok(PromotionReport {
        records,
        summary: PromotionSummary {
            total_records,
            eligible_count,
            field_blocker_counts,
        },
    })
}
