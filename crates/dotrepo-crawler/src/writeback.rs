use crate::CrawlWritebackPlan;
use anyhow::{bail, Context, Result};
use std::fs;
use std::path::PathBuf;

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub(crate) struct WritebackReport {
    pub record_root: PathBuf,
    pub manifest_path: PathBuf,
    pub evidence_path: Option<PathBuf>,
    pub synthesis_path: Option<PathBuf>,
}

#[allow(dead_code)]
pub(crate) fn apply_writeback_plan(plan: &CrawlWritebackPlan) -> Result<WritebackReport> {
    fs::create_dir_all(&plan.record_root)
        .with_context(|| format!("failed to create {}", plan.record_root.display()))?;
    fs::write(
        &plan.factual.manifest_path,
        &plan.factual.import_plan.manifest_text,
    )
    .with_context(|| {
        format!(
            "failed to write factual manifest {}",
            plan.factual.manifest_path.display()
        )
    })?;

    match (
        plan.factual.evidence_path.as_ref(),
        plan.factual.import_plan.evidence_text.as_ref(),
    ) {
        (Some(path), Some(text)) => {
            fs::write(path, text)
                .with_context(|| format!("failed to write evidence {}", path.display()))?;
        }
        (Some(_), None) => bail!("writeback plan is missing evidence text"),
        (None, Some(_)) => bail!("writeback plan is missing an evidence path"),
        (None, None) => {}
    }

    if let Some(synthesis) = &plan.synthesis {
        fs::write(
            &synthesis.synthesis_path,
            &synthesis.write_plan.synthesis_text,
        )
        .with_context(|| {
            format!(
                "failed to write synthesis document {}",
                synthesis.synthesis_path.display()
            )
        })?;
    }

    Ok(WritebackReport {
        record_root: plan.record_root.clone(),
        manifest_path: plan.factual.manifest_path.clone(),
        evidence_path: plan.factual.evidence_path.clone(),
        synthesis_path: plan
            .synthesis
            .as_ref()
            .map(|synthesis| synthesis.synthesis_path.clone()),
    })
}
