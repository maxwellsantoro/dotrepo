use super::super::adjudication::{
    AdjudicationTier, ImportEscalationOptions, TieredAdjudicationProviders,
};
use super::super::{
    apply_adjudication_response, apply_adjudication_results, build_adjudication_requests,
    AdjudicationModelConfidence, AdjudicationOutcome, FieldScoreReport, ImportPlan,
};
use super::deterministic::apply_adjudication_to_import_plan;
use super::report::{recompute_field_score_summary, ImportEscalationReport};

pub(crate) fn run_model_escalation(
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
