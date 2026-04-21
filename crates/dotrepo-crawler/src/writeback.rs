use crate::CrawlWritebackPlan;
use anyhow::{bail, Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct WritebackReport {
    pub record_root: PathBuf,
    pub manifest_path: PathBuf,
    pub evidence_path: Option<PathBuf>,
    pub synthesis_path: Option<PathBuf>,
}

pub(crate) fn apply_writeback_plan(plan: &CrawlWritebackPlan) -> Result<WritebackReport> {
    fs::create_dir_all(&plan.record_root)
        .with_context(|| format!("failed to create {}", plan.record_root.display()))?;

    let manifest_tmp = plan.factual.manifest_path.with_extension("toml.tmp");
    write_atomic(&manifest_tmp, &plan.factual.import_plan.manifest_text, &plan.factual.manifest_path)
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
            let evidence_tmp = path.with_extension("md.tmp");
            write_atomic(&evidence_tmp, text, path)
                .with_context(|| format!("failed to write evidence {}", path.display()))?;
        }
        (Some(_), None) => bail!("writeback plan is missing evidence text"),
        (None, Some(_)) => bail!("writeback plan is missing an evidence path"),
        (None, None) => {}
    }

    if let Some(synthesis) = &plan.synthesis {
        let synth_tmp = synthesis.synthesis_path.with_extension("toml.tmp");
        write_atomic(&synth_tmp, &synthesis.write_plan.synthesis_text, &synthesis.synthesis_path)
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

fn write_atomic(tmp_path: &Path, contents: &str, final_path: &Path) -> Result<()> {
    fs::write(tmp_path, contents)
        .with_context(|| format!("failed to write temp file {}", tmp_path.display()))?;
    fs::rename(tmp_path, final_path)
        .with_context(|| format!("failed to rename {} to {}", tmp_path.display(), final_path.display()))
}
