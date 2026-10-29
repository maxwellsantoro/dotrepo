//! Mechanical integrity checks for attached contextual-candidate source bindings.
//! Matching bytes/spans do not establish prerequisite completeness or execution.

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use anyhow::{anyhow, bail, ensure, Result};
use serde::Deserialize;
use sha2::{Digest, Sha256};

use super::read::read_input;
use super::{ImportPlan, VerificationCheck, VerificationReport, VerificationSeverity};

const MAX_BINDINGS: usize = 128;
const MAX_BINDINGS_JSON_BYTES: usize = 128 * 1024;
const CHECK_PREFIX: &str = "context-source-bindings/";

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Binding {
    path: String,
    sha256: String,
    start_line: u64,
    end_line: u64,
}

fn contained_path(path: &str) -> bool {
    !path.is_empty()
        && path.len() <= 4096
        && !path.contains(['\\', ':'])
        && !path.chars().any(char::is_control)
        && path.split('/').all(|part| !matches!(part, "" | "." | ".."))
}

fn verify_attachment(
    root: &Path,
    plan: &ImportPlan,
    candidate: &dotrepo_schema::BuildTestCandidate,
    evidence: &toml::Value,
) -> Result<()> {
    let current = serde_json::to_value(candidate)?;
    let recorded: serde_json::Value = serde_json::from_str(
        evidence
            .get("valueJson")
            .and_then(toml::Value::as_str)
            .ok_or_else(|| anyhow!("candidate valueJson must be a JSON string"))?,
    )?;
    ensure!(
        recorded == current,
        "candidate differs from its bound exact value"
    );
    let generated = plan
        .manifest
        .record
        .generated_at
        .as_deref()
        .filter(|value| !value.is_empty())
        .ok_or_else(|| anyhow!("candidate generation time is absent"))?;
    ensure!(
        evidence.get("checkedAt").and_then(toml::Value::as_str) == Some(generated),
        "candidate source assessment time differs from generation time"
    );
    let source = &candidate
        .context
        .as_ref()
        .ok_or_else(|| anyhow!("attached candidate context is absent"))?
        .source;
    ensure!(
        evidence.get("source").and_then(toml::Value::as_str) == Some(source.as_str()),
        "candidate context source differs from assessment source"
    );
    let raw = evidence
        .get("sourceBindingsJson")
        .and_then(toml::Value::as_str)
        .ok_or_else(|| anyhow!("sourceBindingsJson must be a JSON string"))?;
    ensure!(
        raw.len() <= MAX_BINDINGS_JSON_BYTES,
        "source binding attachment exceeds byte limit"
    );
    let bindings: Vec<Binding> = serde_json::from_str(raw)?;
    ensure!(
        !bindings.is_empty() && bindings.len() <= MAX_BINDINGS,
        "source binding set must contain 1..={MAX_BINDINGS} entries"
    );
    let mut seen = BTreeSet::new();
    let mut sources = BTreeMap::new();
    for binding in bindings {
        ensure!(
            contained_path(&binding.path),
            "invalid contained source path"
        );
        ensure!(
            binding.sha256.len() == 64
                && binding
                    .sha256
                    .bytes()
                    .all(|byte| byte.is_ascii_digit() || matches!(byte, b'a'..=b'f')),
            "source SHA256 must be 64 lowercase hexadecimal digits"
        );
        ensure!(
            seen.insert((binding.path.clone(), binding.start_line, binding.end_line)),
            "duplicate source binding span"
        );
        if !sources.contains_key(&binding.path) {
            let contents = read_input(root, Path::new(&binding.path))?;
            let digest = Sha256::digest(contents.as_bytes())
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect::<String>();
            sources.insert(
                binding.path.clone(),
                (digest, contents.lines().count() as u64),
            );
        }
        let (digest, lines) = &sources[&binding.path];
        ensure!(
            *digest == binding.sha256,
            "source hash differs for {}",
            binding.path
        );
        ensure!(
            binding.start_line >= 1
                && binding.start_line <= binding.end_line
                && binding.end_line <= *lines,
            "source line range is invalid for {}",
            binding.path
        );
    }
    for path in [&candidate.source, source] {
        if !contained_path(path) || !sources.contains_key(path) {
            bail!("candidate command/context source is not in its binding set");
        }
    }
    Ok(())
}

/// Each candidate carrying this attachment gets one integrity-only check.
/// An attachment's absence keeps the preexisting importer behavior unchanged.
pub(super) fn verify(root: &Path, plan: &ImportPlan) -> Vec<VerificationCheck> {
    let mut checks = Vec::new();
    for (purpose, candidates) in [
        ("build", &plan.manifest.repo.build_candidates),
        ("test", &plan.manifest.repo.test_candidates),
    ] {
        for (index, candidate) in candidates.iter().enumerate() {
            let field = format!("repo.{purpose}_candidates.{index}");
            let Some(evidence) = plan
                .manifest
                .x
                .get("dotrepo")
                .and_then(|extension| extension.get("field_evidence"))
                .and_then(|fields| fields.get(&field))
                .filter(|entry| entry.get("sourceBindingsJson").is_some())
            else {
                continue;
            };
            let (severity, message) = match verify_attachment(root, plan, candidate, evidence) {
                Ok(()) => (VerificationSeverity::Pass, "Attached source hashes, line ranges, exact candidate, source and assessment time match; prerequisite completeness remains unresolved.".to_owned()),
                Err(error) => (VerificationSeverity::Failure, format!("Attached contextual source integrity failed: {error}")),
            };
            checks.push(VerificationCheck {
                check_id: format!("{CHECK_PREFIX}{field}"),
                field,
                severity,
                message,
            });
        }
    }
    checks
}

/// Missing checks cannot qualify an attached candidate, even if tuple/time match.
pub(super) fn source_bindings_intact(report: &VerificationReport, field: &str) -> bool {
    let id = format!("{CHECK_PREFIX}{field}");
    let checks = report
        .checks
        .iter()
        .filter(|check| check.check_id == id && check.field == field)
        .collect::<Vec<_>>();
    !checks.is_empty()
        && checks
            .iter()
            .all(|check| check.severity == VerificationSeverity::Pass)
}

#[cfg(test)]
mod tests;
