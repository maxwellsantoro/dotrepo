use super::super::{FieldConfidence, FieldScoreReport};

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportEscalationReport {
    pub deterministic_requests: usize,
    pub deterministic_resolved: usize,
    pub security_owners_deepened: usize,
    /// Provider invocation attempts, including failed requests and timeouts.
    pub model_calls: usize,
    pub model_resolved: usize,
    /// Complete total only when every attempted call reported native usage.
    pub tokens_used: Option<u64>,
    pub tokens_used_known_subtotal: u64,
    pub unknown_token_usage_calls: usize,
    pub token_usage_complete: bool,
    pub remaining_unresolved: usize,
    pub adjudication_tiers_used: Vec<super::super::adjudication::AdjudicationTier>,
}

impl Default for ImportEscalationReport {
    fn default() -> Self {
        Self {
            deterministic_requests: 0,
            deterministic_resolved: 0,
            security_owners_deepened: 0,
            model_calls: 0,
            model_resolved: 0,
            tokens_used: Some(0),
            tokens_used_known_subtotal: 0,
            unknown_token_usage_calls: 0,
            token_usage_complete: true,
            remaining_unresolved: 0,
            adjudication_tiers_used: Vec::new(),
        }
    }
}

impl ImportEscalationReport {
    pub(super) fn record_token_usage(&mut self, tokens: Option<u64>) {
        if let Some(tokens) = tokens {
            self.tokens_used_known_subtotal += tokens;
        } else {
            self.unknown_token_usage_calls += 1;
            self.token_usage_complete = false;
        }
        self.tokens_used = self
            .token_usage_complete
            .then_some(self.tokens_used_known_subtotal);
    }
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
