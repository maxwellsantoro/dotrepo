use super::super::{FieldConfidence, FieldScoreReport};

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
    pub adjudication_tiers_used: Vec<super::super::adjudication::AdjudicationTier>,
}

pub(crate) fn recompute_field_score_summary(field_scores: &mut FieldScoreReport) {
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
