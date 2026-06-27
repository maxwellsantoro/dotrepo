use anyhow::{bail, Result};
use dotrepo_schema::{Manifest, RecordMode, RecordStatus};
use serde_json::Value;
use std::path::Path;
use std::sync::Arc;

use super::util::{display_path, manifest_path, repository_identity};
use super::{
    load_manifest_file, record_summary, validate_manifest, LoadedManifest, PublicSelectedRecord,
    SelectedRecord, SelectionReason,
};
use crate::claims::{candidate_claim_context, ClaimState};
use crate::public::public_record_artifacts;
use crate::query::{manifest_to_json, query_manifest_value_from_json};
use crate::validation::collect_record_dirs;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct RepositoryIdentity {
    pub(crate) host: String,
    pub(crate) owner: String,
    pub(crate) repo: String,
}

#[derive(Debug, Clone)]
pub(crate) struct CandidateManifest {
    pub(crate) manifest_path: String,
    pub(crate) path: std::path::PathBuf,
    pub(crate) manifest: Arc<Manifest>,
    pub(crate) manifest_json: Value,
    pub(crate) identity: Option<RepositoryIdentity>,
    pub(crate) rank: u8,
}

pub(crate) fn resolve_selection_reason(
    candidates: &[CandidateManifest],
    selected: &CandidateManifest,
) -> SelectionReason {
    if candidates.len() == 1 {
        return SelectionReason::OnlyMatchingRecord;
    }

    if candidates.iter().any(|candidate| {
        candidate.manifest_path != selected.manifest_path && candidate.rank == selected.rank
    }) {
        return SelectionReason::EqualAuthorityConflict;
    }

    if matches!(selected.manifest.record.status, RecordStatus::Canonical) {
        SelectionReason::CanonicalPreferred
    } else {
        SelectionReason::HigherStatusOverlay
    }
}

pub(crate) fn resolve_conflict_reason(
    selected_reason: SelectionReason,
    selected: &CandidateManifest,
    competing: &CandidateManifest,
) -> SelectionReason {
    match selected_reason {
        SelectionReason::OnlyMatchingRecord => SelectionReason::OnlyMatchingRecord,
        SelectionReason::CanonicalPreferred | SelectionReason::HigherStatusOverlay => {
            selected_reason
        }
        SelectionReason::EqualAuthorityConflict => {
            if competing.rank == selected.rank {
                SelectionReason::EqualAuthorityConflict
            } else {
                SelectionReason::HigherStatusOverlay
            }
        }
    }
}

pub(crate) fn resolve_competing_value(candidate: &CandidateManifest, path: &str) -> Option<Value> {
    query_manifest_value_from_json(&candidate.manifest_json, path).ok()
}

pub(crate) fn resolve_candidates(root: &Path) -> Result<Vec<CandidateManifest>> {
    let mut candidates = load_direct_candidates(root)?;
    if !candidates.is_empty() {
        let direct_identities = unique_identities(
            candidates
                .iter()
                .filter_map(|candidate| candidate.identity.clone()),
        );
        if direct_identities.len() > 1 {
            bail!("multiple root candidates describe different repository identities");
        }

        if let Some(identity) = direct_identities.first() {
            for candidate in load_descendant_candidates(root)? {
                if candidate.identity.as_ref() == Some(identity) {
                    candidates.push(candidate);
                }
            }
        }

        sort_candidates(&mut candidates, root);
        return Ok(candidates);
    }

    let descendants = load_descendant_candidates(root)?;
    if descendants.is_empty() {
        bail!(
            "failed to read {}: no .repo, record.toml, or descendant record.toml candidates found",
            manifest_path(root).display()
        );
    }

    let identities = unique_identities(
        descendants
            .iter()
            .filter_map(|candidate| candidate.identity.clone()),
    );
    let mut candidates = if identities.len() == 1 {
        let identity = &identities[0];
        descendants
            .into_iter()
            .filter(|candidate| candidate.identity.as_ref() == Some(identity))
            .collect::<Vec<_>>()
    } else if identities.is_empty() && descendants.len() == 1 {
        descendants
    } else if identities.is_empty() {
        bail!("multiple candidate overlays were found, but none expose a resolvable repository identity");
    } else {
        bail!("multiple repository identities were found under the query root; point query/trust at one repository scope");
    };

    sort_candidates(&mut candidates, root);
    Ok(candidates)
}

fn load_direct_candidates(root: &Path) -> Result<Vec<CandidateManifest>> {
    let mut candidates = Vec::new();
    for name in [".repo", "record.toml"] {
        let path = root.join(name);
        if !path.exists() {
            continue;
        }

        let document = load_manifest_file(&path)?;
        validate_manifest(root, &document.manifest)?;
        candidates.push(candidate_from_document(root, &document)?);
    }
    Ok(candidates)
}

fn load_descendant_candidates(root: &Path) -> Result<Vec<CandidateManifest>> {
    let mut record_dirs = Vec::new();
    collect_record_dirs(root, &mut record_dirs)?;
    record_dirs.sort();

    let root_record = root.join("record.toml");
    let mut candidates = Vec::new();
    for record_dir in record_dirs {
        let path = record_dir.join("record.toml");
        if path == root_record {
            continue;
        }
        let document = load_manifest_file(&path)?;
        validate_manifest(root, &document.manifest)?;
        candidates.push(candidate_from_document(root, &document)?);
    }
    Ok(candidates)
}

pub(crate) fn candidate_from_document(
    root: &Path,
    document: &LoadedManifest,
) -> Result<CandidateManifest> {
    // Share the Arc; the underlying Manifest is parsed only once at load time.
    let manifest = std::sync::Arc::clone(&document.manifest);
    let manifest_json = manifest_to_json(&manifest)?;
    Ok(CandidateManifest {
        manifest_path: display_path(root, &document.path)?,
        path: document.path.clone(),
        rank: precedence_rank(&manifest),
        identity: manifest_identity(root, document),
        manifest,
        manifest_json,
    })
}

/// Computes the total precedence order for candidate records.
///
/// The documented ladder (docs/trust-model.md and RFC 0004) is:
/// canonical .repo (native) > canonical mirror/overlay > verified (any mode) >
/// reviewed > imported > inferred > draft.
///
/// Native only receives a numeric bonus when status == Canonical (7 vs 6).
/// For every lower status tier, higher status wins regardless of `record.mode`.
/// This matches the contract: "when no canonical record exists, a higher-status
/// overlay may supersede a lower-status native/overlay". The maintainer claim
/// workflow is the mechanism that produces a canonical native at the repository
/// root and thereby wins selection.
///
/// Tie-breakers after rank are lexicographic manifest_path (stable).
fn precedence_rank(manifest: &Manifest) -> u8 {
    match (&manifest.record.mode, &manifest.record.status) {
        (RecordMode::Native, RecordStatus::Canonical) => 7,
        (_, RecordStatus::Canonical) => 6,
        (_, RecordStatus::Verified) => 5,
        (_, RecordStatus::Reviewed) => 4,
        (_, RecordStatus::Imported) => 3,
        (_, RecordStatus::Inferred) => 2,
        (_, RecordStatus::Draft) => 1,
    }
}

fn manifest_identity(root: &Path, document: &LoadedManifest) -> Option<RepositoryIdentity> {
    document
        .manifest
        .record
        .source
        .as_deref()
        .and_then(repository_identity)
        .map(repository_identity_parts)
        .or_else(|| {
            document
                .manifest
                .repo
                .homepage
                .as_deref()
                .and_then(repository_identity)
                .map(repository_identity_parts)
        })
        .or_else(|| index_manifest_identity(root, &document.path))
}

fn index_manifest_identity(root: &Path, path: &Path) -> Option<RepositoryIdentity> {
    let relative = path.strip_prefix(root).ok()?;
    let segments = relative
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    let repos_index = segments.iter().position(|segment| segment == "repos")?;
    let tail = &segments[repos_index + 1..];
    if tail.len() != 4 || tail[3] != "record.toml" {
        return None;
    }
    Some(RepositoryIdentity {
        host: tail[0].clone(),
        owner: tail[1].clone(),
        repo: tail[2].clone(),
    })
}

fn unique_identities(
    identities: impl Iterator<Item = RepositoryIdentity>,
) -> Vec<RepositoryIdentity> {
    let mut unique = Vec::new();
    for identity in identities {
        if !unique.iter().any(|existing| existing == &identity) {
            unique.push(identity);
        }
    }
    unique
}

fn repository_identity_parts(parts: (String, String, String)) -> RepositoryIdentity {
    RepositoryIdentity {
        host: parts.0,
        owner: parts.1,
        repo: parts.2,
    }
}

pub(crate) fn sort_candidates(candidates: &mut [CandidateManifest], root: &Path) {
    candidates.sort_by(|left, right| {
        right
            .rank
            .cmp(&left.rank)
            .then_with(|| {
                claim_selection_boost(root, right).cmp(&claim_selection_boost(root, left))
            })
            .then_with(|| left.manifest_path.cmp(&right.manifest_path))
    });
}

fn claim_selection_boost(root: &Path, candidate: &CandidateManifest) -> u8 {
    candidate_claim_context(root, candidate)
        .map(|context| match context.state {
            ClaimState::Accepted => 2,
            ClaimState::InReview => 1,
            _ => 0,
        })
        .unwrap_or(0)
}

pub(crate) fn selected_record(root: &Path, candidate: &CandidateManifest) -> SelectedRecord {
    SelectedRecord {
        manifest_path: candidate.manifest_path.clone(),
        record: record_summary(&candidate.manifest),
        claim: candidate_claim_context(root, candidate),
    }
}

pub(crate) fn public_selected_record(
    display_root: &Path,
    candidate: &CandidateManifest,
) -> PublicSelectedRecord {
    PublicSelectedRecord {
        manifest_path: display_path(display_root, &candidate.path)
            .unwrap_or_else(|_| candidate.path.display().to_string()),
        record: record_summary(&candidate.manifest),
        claim: candidate_claim_context(display_root, candidate),
        artifacts: public_record_artifacts(display_root, candidate),
    }
}
