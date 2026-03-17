use crate::CrawlerStateSnapshot;
use anyhow::{Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub(crate) struct StateWritePlan {
    pub state_path: PathBuf,
    pub state_text: String,
    pub state: CrawlerStateSnapshot,
}

#[allow(dead_code)]
pub(crate) fn load_state(path: &Path) -> Result<CrawlerStateSnapshot> {
    if !path.exists() {
        return Ok(CrawlerStateSnapshot::default());
    }

    let text = fs::read_to_string(path)
        .with_context(|| format!("failed to read crawler state {}", path.display()))?;
    toml::from_str(&text)
        .with_context(|| format!("failed to parse crawler state {}", path.display()))
}

#[allow(dead_code)]
pub(crate) fn plan_state_write(
    path: &Path,
    state: &CrawlerStateSnapshot,
) -> Result<StateWritePlan> {
    let state_text = toml::to_string_pretty(state).context("failed to serialize crawler state")?;
    Ok(StateWritePlan {
        state_path: path.to_path_buf(),
        state_text,
        state: state.clone(),
    })
}

#[allow(dead_code)]
pub(crate) fn write_state(path: &Path, state: &CrawlerStateSnapshot) -> Result<StateWritePlan> {
    let plan = plan_state_write(path, state)?;
    if let Some(parent) = plan.state_path.parent() {
        fs::create_dir_all(parent).with_context(|| {
            format!(
                "failed to create crawler state parent directory {}",
                parent.display()
            )
        })?;
    }
    fs::write(&plan.state_path, &plan.state_text).with_context(|| {
        format!(
            "failed to write crawler state {}",
            plan.state_path.display()
        )
    })?;
    Ok(plan)
}
