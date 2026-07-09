//! Auto-promotion to verified and unjustified-downgrade guard after factual planning.

use crate::CrawlDiagnostic;
use anyhow::Result;
use dotrepo_core::{
    guard_against_unjustified_downgrade, promote_to_verified, FieldScoreReport, ImportPlan,
};
use dotrepo_schema::{render_manifest, Manifest};

/// Apply auto-promotion and, when a prior verified record exists, the downgrade guard.
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

    if let Some(guard_outcome) =
        guard_against_unjustified_downgrade(previous_manifest, &mut import_plan.manifest)
    {
        if guard_outcome.preserved {
            diagnostics.push(CrawlDiagnostic::info(
                "pipeline.downgrade_guard_preserved",
                "preserved prior verified status: no previously present field regressed in this refresh"
                    .to_string(),
            ));
            import_plan.manifest_text = render_manifest(&import_plan.manifest)?;
            if let Some(ref mut evidence) = import_plan.evidence_text {
                evidence.push_str(
                    "\n## Downgrade guard\n\nA prior verified status was preserved because no previously present field regressed in this refresh.\n",
                );
            }
        } else {
            diagnostics.push(CrawlDiagnostic::info(
                "pipeline.downgrade_guard_allowed",
                format!(
                    "allowed downgrade from a prior verified status: {} field(s) regressed: {}",
                    guard_outcome.regressed_fields.len(),
                    guard_outcome.regressed_fields.join(", "),
                ),
            ));
            if let Some(ref mut evidence) = import_plan.evidence_text {
                evidence.push_str(&format!(
                    "\n## Downgrade guard\n\nStatus dropped from a prior verified record because the following previously present field(s) regressed: {}.\n",
                    guard_outcome.regressed_fields.join(", "),
                ));
            }
        }
    }
    Ok(())
}
