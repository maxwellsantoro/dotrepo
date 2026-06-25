use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{
    parse_synthesis_document, render_synthesis_document, validate_synthesis_document, Manifest,
    SynthesisDocument,
};
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};

use super::load_manifest_from_root;
use super::util::{display_path, parse_rfc3339};

#[derive(Debug, Clone)]
pub struct LoadedSynthesis {
    pub path: PathBuf,
    pub raw: Vec<u8>,
    pub synthesis: SynthesisDocument,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SynthesisReadReport {
    pub root: String,
    pub synthesis_path: String,
    pub synthesis: SynthesisDocument,
}

#[derive(Debug, Clone)]
pub struct SynthesisWritePlan {
    pub synthesis_path: PathBuf,
    pub synthesis: SynthesisDocument,
    pub synthesis_text: String,
}

fn synthesis_path(root: &Path) -> PathBuf {
    root.join("synthesis.toml")
}

fn contains_unsafe_shell_like_value(value: &str) -> bool {
    value.contains('\n')
        || value.contains('\r')
        || value.contains('\0')
        || value.contains("`")
        || value.contains("$(")
        || value.contains("${")
}

fn validate_synthesis_command(field: &str, value: &str) -> Result<()> {
    if contains_unsafe_shell_like_value(value) {
        bail!("{field} contains an unsafe shell-like value");
    }
    Ok(())
}

pub fn load_synthesis_document(root: &Path) -> Result<LoadedSynthesis> {
    let path = synthesis_path(root);
    let raw = fs::read(&path).map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
    let text = std::str::from_utf8(&raw)
        .map_err(|e| anyhow!("failed to decode {} as UTF-8: {}", path.display(), e))?;
    let synthesis = parse_synthesis_document(text)?;
    Ok(LoadedSynthesis {
        path,
        raw,
        synthesis,
    })
}

pub fn load_synthesis_from_root(root: &Path) -> Result<SynthesisDocument> {
    Ok(load_synthesis_document(root)?.synthesis)
}

pub fn get_synthesis(root: &Path) -> Result<SynthesisReadReport> {
    let loaded = load_synthesis_document(root)?;
    Ok(SynthesisReadReport {
        root: root.display().to_string(),
        synthesis_path: display_path(root, &loaded.path),
        synthesis: loaded.synthesis,
    })
}

pub fn validate_synthesis(manifest: &Manifest, synthesis: &SynthesisDocument) -> Result<()> {
    validate_synthesis_document(synthesis).map_err(|err| anyhow!("{err}"))?;
    parse_rfc3339("synthesis.generated_at", &synthesis.synthesis.generated_at)?;
    validate_synthesis_command(
        "synthesis.for_agents.how_to_build",
        &synthesis.synthesis.for_agents.how_to_build,
    )?;
    validate_synthesis_command(
        "synthesis.for_agents.how_to_test",
        &synthesis.synthesis.for_agents.how_to_test,
    )?;

    if let Some(build) = manifest.repo.build.as_deref() {
        if !build.trim().is_empty()
            && build.trim() != synthesis.synthesis.for_agents.how_to_build.trim()
        {
            bail!("synthesis.for_agents.how_to_build conflicts with factual repo.build");
        }
    }
    if let Some(test) = manifest.repo.test.as_deref() {
        if !test.trim().is_empty()
            && test.trim() != synthesis.synthesis.for_agents.how_to_test.trim()
        {
            bail!("synthesis.for_agents.how_to_test conflicts with factual repo.test");
        }
    }

    Ok(())
}

pub fn write_synthesis(root: &Path, synthesis: &SynthesisDocument) -> Result<SynthesisWritePlan> {
    let manifest = load_manifest_from_root(root)?;
    validate_synthesis(&manifest, synthesis)?;
    let synthesis_text = render_synthesis_document(synthesis)?;
    Ok(SynthesisWritePlan {
        synthesis_path: synthesis_path(root),
        synthesis: synthesis.clone(),
        synthesis_text,
    })
}
