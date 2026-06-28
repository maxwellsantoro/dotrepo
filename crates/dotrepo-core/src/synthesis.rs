use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{
    parse_synthesis_document, render_synthesis_document, validate_synthesis_document, Manifest,
    SynthesisArchitecture, SynthesisDocument, SynthesisForAgents, SynthesisMode, SynthesisRecord,
};
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};

use super::load_manifest_from_root;
use super::util::{display_path, display_root, parse_rfc3339, validate_shell_safe_command};

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

fn validate_synthesis_command(field: &str, value: &str) -> Result<()> {
    validate_shell_safe_command(field, value)
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
        root: display_root(root)?,
        synthesis_path: display_path(root, &loaded.path)?,
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
    plan_synthesis_write(root, &manifest, synthesis)
}

/// Validate and render a synthesis document against an already-loaded factual manifest.
///
/// Crawler writeback uses this form because factual and synthesis files are planned
/// atomically before either file exists on disk.
pub fn plan_synthesis_write(
    root: &Path,
    manifest: &Manifest,
    synthesis: &SynthesisDocument,
) -> Result<SynthesisWritePlan> {
    validate_synthesis(manifest, synthesis)?;
    let synthesis_text = render_synthesis_document(synthesis)?;
    Ok(SynthesisWritePlan {
        synthesis_path: synthesis_path(root),
        synthesis: synthesis.clone(),
        synthesis_text,
    })
}

fn factual_command_or_placeholder(value: &Option<String>, placeholder: &str) -> String {
    value
        .as_deref()
        .filter(|command| !command.trim().is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| placeholder.to_string())
}

/// Generate a minimal "Generated" mode synthesis document using facts from the manifest.
/// This is a starting point for production synthesis (M3); the result should be reviewed
/// and may be supplemented with architecture/key concepts from README or manual curation.
///
/// `generated_at` must be a valid RFC3339 timestamp. Callers should run `validate_synthesis`
/// before persisting. `how_to_build` / `how_to_test` are populated from `manifest.repo` when
/// present and non-empty (and will pass validation).
pub fn generate_basic_synthesis(
    manifest: &Manifest,
    generated_at: &str,
    source_commit: &str,
    model: &str,
    provider: &str,
) -> SynthesisDocument {
    let how_to_build = factual_command_or_placeholder(
        &manifest.repo.build,
        "See repository documentation or build system for instructions.",
    );
    let how_to_test = factual_command_or_placeholder(
        &manifest.repo.test,
        "See repository documentation or test system for instructions.",
    );

    // Minimal placeholders; real production use would enrich from README analysis.
    SynthesisDocument {
        schema: "dotrepo-synthesis/v0".to_string(),
        synthesis: SynthesisRecord {
            generated_at: generated_at.to_string(),
            source_commit: source_commit.to_string(),
            model: model.to_string(),
            provider: provider.to_string(),
            mode: SynthesisMode::Generated,
            architecture: SynthesisArchitecture {
                summary: if manifest.repo.description.trim().is_empty() {
                    "See README for project purpose.".to_string()
                } else {
                    manifest.repo.description.clone()
                },
                entry_points: vec![],
                key_concepts: vec![],
            },
            for_agents: SynthesisForAgents {
                how_to_build,
                how_to_test,
                how_to_contribute: "See CONTRIBUTING.md or repository guidelines.".to_string(),
                gotchas: vec![],
            },
        },
    }
}
