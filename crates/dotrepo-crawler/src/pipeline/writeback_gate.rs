//! Promotion based on fresh field scores and reporting of prior verification changes.

use crate::CrawlDiagnostic;
use anyhow::Result;
use dotrepo_core::{
    guard_against_unjustified_downgrade, promote_to_verified, FieldScoreReport, ImportPlan,
};
use dotrepo_schema::{render_manifest, Manifest};

/// Apply auto-promotion and report lower fresh scores without inheriting authority.
/// Updates `import_plan` in place (manifest text + evidence) and appends diagnostics.
pub(crate) fn apply_promotion_and_downgrade_guard(
    import_plan: &mut ImportPlan,
    field_scores: &FieldScoreReport,
    previous_manifest: Option<&Manifest>,
    diagnostics: &mut Vec<CrawlDiagnostic>,
) -> Result<()> {
    let promotion = promote_to_verified(&mut import_plan.manifest, field_scores);
    if promotion.promoted {
        diagnostics.push(CrawlDiagnostic::info(
            "pipeline.auto_promoted",
            format!(
                "auto-promoted record from {} to verified: {}",
                promotion.previous_status, promotion.reason,
            ),
        ));
        import_plan.manifest_text = render_manifest(&import_plan.manifest)?;
        if let Some(ref mut evidence) = import_plan.evidence_text {
            evidence.push_str("\n## Auto-promotion\n\nAll fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.\n");
        }
    }

    if let Some(outcome) =
        guard_against_unjustified_downgrade(previous_manifest, &mut import_plan.manifest)
    {
        diagnostics.push(CrawlDiagnostic::info(
            "pipeline.downgrade_guard_allowed",
            format!(
                "fresh field scores do not justify verified status; {} factual fields changed",
                outcome.regressed_fields.len()
            ),
        ));
        if let Some(evidence) = &mut import_plan.evidence_text {
            evidence.push_str("\n## Fresh verification\n\nPrior verified authority was not inherited: this refresh must qualify using its current field scores.\n");
        }
    }
    Ok(())
}
