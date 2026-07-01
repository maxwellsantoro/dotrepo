use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{parse_synthesis_document, Manifest, SynthesisDocument, SynthesisMode};
use std::fs;
use std::path::Path;

use crate::query::query_manifest_value;
use crate::selection::{
    public_selected_record, resolve_candidates, resolve_competing_value, resolve_conflict_reason,
    resolve_selection_reason, CandidateManifest,
};
use crate::synthesis::validate_synthesis;
use crate::util::{display_path, record_status_name};
use crate::{ConflictRelationship, SelectionReason};

use super::*;

pub(crate) fn public_record_artifacts(
    display_root: &Path,
    candidate: &CandidateManifest,
) -> Option<PublicRecordArtifacts> {
    let evidence_path = candidate.path.parent()?.join("evidence.md");
    if !evidence_path.is_file() {
        return None;
    }
    let relative = display_path(display_root, &evidence_path).ok()?;
    Some(PublicRecordArtifacts {
        evidence_path: Some(relative),
    })
}

fn public_repository_fields(manifest: &Manifest) -> PublicRepositoryFields {
    PublicRepositoryFields {
        name: manifest.repo.name.clone(),
        description: manifest.repo.description.clone(),
        homepage: non_empty_value(manifest.repo.homepage.as_deref()),
        docs_root: manifest
            .docs
            .as_ref()
            .and_then(|docs| non_empty_value(docs.root.as_deref())),
        getting_started: manifest
            .docs
            .as_ref()
            .and_then(|docs| non_empty_value(docs.getting_started.as_deref())),
        owners_team: manifest
            .owners
            .as_ref()
            .and_then(|owners| non_empty_value(owners.team.as_deref())),
        security_contact: manifest
            .owners
            .as_ref()
            .and_then(|owners| non_empty_value(owners.security_contact.as_deref()))
            .filter(|value| value != "unknown"),
    }
}

fn public_research_execution(manifest: &Manifest) -> PublicResearchExecution {
    PublicResearchExecution {
        build: non_empty_value(manifest.repo.build.as_deref()),
        test: non_empty_value(manifest.repo.test.as_deref()),
        build_candidates: public_command_candidates(&manifest.repo.build_candidates),
        test_candidates: public_command_candidates(&manifest.repo.test_candidates),
    }
}

fn public_command_candidates(
    candidates: &[dotrepo_schema::BuildTestCandidate],
) -> Vec<PublicCommandCandidate> {
    candidates
        .iter()
        .map(|candidate| PublicCommandCandidate {
            command: candidate.command.clone(),
            ecosystem: candidate.ecosystem.clone(),
            source: candidate.source.clone(),
        })
        .collect()
}

fn public_research_docs(manifest: &Manifest) -> PublicResearchDocs {
    let docs = manifest.docs.as_ref();
    PublicResearchDocs {
        root: docs.and_then(|docs| non_empty_value(docs.root.as_deref())),
        getting_started: docs.and_then(|docs| non_empty_value(docs.getting_started.as_deref())),
        architecture: docs.and_then(|docs| non_empty_value(docs.architecture.as_deref())),
        api: docs.and_then(|docs| non_empty_value(docs.api.as_deref())),
    }
}

fn public_research_ownership(manifest: &Manifest) -> PublicResearchOwnership {
    let owners = manifest.owners.as_ref();
    PublicResearchOwnership {
        maintainers: owners
            .map(|owners| owners.maintainers.clone())
            .unwrap_or_default(),
        team: owners.and_then(|owners| non_empty_value(owners.team.as_deref())),
        security_contact: owners
            .and_then(|owners| non_empty_value(owners.security_contact.as_deref()))
            .filter(|value| value != "unknown"),
    }
}

fn public_research_completeness(
    manifest: &Manifest,
    docs: &PublicResearchDocs,
    ownership: &PublicResearchOwnership,
    conflict_count: usize,
) -> PublicResearchCompleteness {
    PublicResearchCompleteness {
        has_build: non_empty_value(manifest.repo.build.as_deref()).is_some(),
        has_test: non_empty_value(manifest.repo.test.as_deref()).is_some(),
        has_docs: docs.root.is_some()
            || docs.getting_started.is_some()
            || docs.architecture.is_some()
            || docs.api.is_some(),
        has_security_contact: ownership.security_contact.is_some(),
        has_ownership_signal: !ownership.maintainers.is_empty() || ownership.team.is_some(),
        has_license: non_empty_value(manifest.repo.license.as_deref()).is_some(),
        conflict_count,
    }
}

fn record_mode_name(mode: &dotrepo_schema::RecordMode) -> &'static str {
    match mode {
        dotrepo_schema::RecordMode::Native => "native",
        dotrepo_schema::RecordMode::Overlay => "overlay",
    }
}

fn public_research_record(index_root: &Path, selected: &CandidateManifest) -> PublicResearchRecord {
    PublicResearchRecord {
        manifest_path: display_path(index_root, &selected.path)
            .unwrap_or_else(|_| selected.path.display().to_string()),
        mode: record_mode_name(&selected.manifest.record.mode).to_string(),
        source: selected.manifest.record.source.clone(),
        generated_at: selected.manifest.record.generated_at.clone(),
        evidence_path: public_record_artifacts(index_root, selected)
            .and_then(|artifacts| artifacts.evidence_path),
    }
}

fn public_research_trust(
    selected: &CandidateManifest,
    selection_reason: SelectionReason,
) -> PublicResearchTrust {
    let trust = selected.manifest.record.trust.as_ref();
    PublicResearchTrust {
        selected_status: record_status_name(&selected.manifest.record.status).to_string(),
        confidence: trust.and_then(|trust| non_empty_value(trust.confidence.as_deref())),
        provenance: trust
            .map(|trust| trust.provenance.clone())
            .unwrap_or_default(),
        selection_reason,
    }
}

fn synthesis_mode_name(mode: &SynthesisMode) -> &'static str {
    match mode {
        SynthesisMode::Generated => "generated",
        SynthesisMode::Contributed => "contributed",
    }
}

fn public_research_synthesis_from_document(
    display_root: &Path,
    synthesis_path: &Path,
    synthesis: SynthesisDocument,
) -> PublicResearchSynthesis {
    PublicResearchSynthesis {
        synthesis_path: display_path(display_root, synthesis_path)
            .unwrap_or_else(|_| synthesis_path.display().to_string()),
        generated_at: synthesis.synthesis.generated_at,
        source_commit: synthesis.synthesis.source_commit,
        model: synthesis.synthesis.model,
        provider: synthesis.synthesis.provider,
        mode: synthesis_mode_name(&synthesis.synthesis.mode).to_string(),
        architecture: PublicResearchSynthesisArchitecture {
            summary: synthesis.synthesis.architecture.summary,
            entry_points: synthesis.synthesis.architecture.entry_points,
            key_concepts: synthesis.synthesis.architecture.key_concepts,
        },
        for_agents: PublicResearchSynthesisForAgents {
            how_to_build: synthesis.synthesis.for_agents.how_to_build,
            how_to_test: synthesis.synthesis.for_agents.how_to_test,
            how_to_contribute: synthesis.synthesis.for_agents.how_to_contribute,
            gotchas: synthesis.synthesis.for_agents.gotchas,
        },
    }
}

fn public_research_synthesis(
    index_root: &Path,
    selected: &CandidateManifest,
) -> Result<Option<PublicResearchSynthesis>> {
    let Some(record_root) = selected.path.parent() else {
        return Ok(None);
    };
    let synthesis_path = record_root.join("synthesis.toml");
    if !synthesis_path.is_file() {
        return Ok(None);
    }
    let raw = fs::read_to_string(&synthesis_path)
        .map_err(|err| anyhow!("failed to read {}: {}", synthesis_path.display(), err))?;
    let synthesis = parse_synthesis_document(&raw)
        .map_err(|err| anyhow!("failed to parse {}: {}", synthesis_path.display(), err))?;
    validate_synthesis(&selected.manifest, &synthesis)
        .map_err(|err| anyhow!("invalid {}: {}", synthesis_path.display(), err))?;
    Ok(Some(public_research_synthesis_from_document(
        index_root,
        &synthesis_path,
        synthesis,
    )))
}

fn ensure_public_query_input_version(snapshot: &PublicQueryInputSnapshot) -> Result<()> {
    if snapshot.api_version != PUBLIC_API_VERSION {
        bail!(
            "unsupported public query input apiVersion: {}",
            snapshot.api_version
        );
    }
    Ok(())
}

pub fn public_repository_summary(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicRepositorySummaryResponse> {
    public_repository_summary_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_summary_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicRepositorySummaryResponse> {
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_repository_summary_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
        base_path,
    )
}

pub(crate) fn public_repository_summary_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicRepositorySummaryResponse> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);

    Ok(PublicRepositorySummaryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        repository: public_repository_fields(&selected.manifest),
        selection: PublicSelectionReport {
            reason,
            record: public_selected_record(index_root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: None,
                record: public_selected_record(index_root, candidate),
            })
            .collect(),
        links: public_links_with_base(
            host,
            owner,
            repo,
            PublicLinkKind::Repository,
            None,
            base_path,
        )?,
    })
}

pub fn public_repository_trust(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicTrustResponse> {
    public_repository_trust_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_trust_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicTrustResponse> {
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_repository_trust_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
        base_path,
    )
}

pub(crate) fn public_repository_trust_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicTrustResponse> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);

    Ok(PublicTrustResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        selection: PublicSelectionReport {
            reason,
            record: public_selected_record(index_root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: None,
                record: public_selected_record(index_root, candidate),
            })
            .collect(),
        links: public_links_with_base(host, owner, repo, PublicLinkKind::Trust, None, base_path)?,
    })
}

pub fn public_repository_profile(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicResearchProfileResponse> {
    public_repository_profile_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_profile_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicResearchProfileResponse> {
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_repository_profile_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
        base_path,
    )
}

pub(crate) fn public_repository_profile_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicResearchProfileResponse> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);
    let docs = public_research_docs(&selected.manifest);
    let ownership = public_research_ownership(&selected.manifest);
    let synthesis = public_research_synthesis(index_root, selected)?;
    let conflicts = candidates
        .iter()
        .skip(1)
        .map(|candidate| PublicConflictReport {
            relationship: if candidate.rank == selected.rank {
                ConflictRelationship::Parallel
            } else {
                ConflictRelationship::Superseded
            },
            reason: resolve_conflict_reason(reason, selected, candidate),
            value: None,
            record: public_selected_record(index_root, candidate),
        })
        .collect::<Vec<_>>();

    Ok(PublicResearchProfileResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        record: public_research_record(index_root, selected),
        purpose: selected.manifest.repo.description.clone(),
        name: selected.manifest.repo.name.clone(),
        homepage: non_empty_value(selected.manifest.repo.homepage.as_deref()),
        license: non_empty_value(selected.manifest.repo.license.as_deref()),
        visibility: non_empty_value(selected.manifest.repo.visibility.as_deref()),
        project_status: non_empty_value(selected.manifest.repo.status.as_deref()),
        languages: selected.manifest.repo.languages.clone(),
        topics: selected.manifest.repo.topics.clone(),
        execution: public_research_execution(&selected.manifest),
        completeness: public_research_completeness(
            &selected.manifest,
            &docs,
            &ownership,
            conflicts.len(),
        ),
        docs,
        ownership,
        trust: public_research_trust(selected, reason),
        synthesis,
        conflicts,
        links: public_links_with_base(host, owner, repo, PublicLinkKind::Profile, None, base_path)?,
    })
}

pub fn public_repository_query(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
) -> Result<PublicQueryResponse> {
    public_repository_query_with_base(index_root, host, owner, repo, path, freshness, "/")
}

pub fn public_repository_query_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicQueryResponse> {
    let scope_root = index_repository_scope(index_root, host, owner, repo)?;
    let candidates = resolve_candidates(&scope_root)?;
    let selected = &candidates[0];
    let value = query_manifest_value(&selected.manifest, path)?;
    let reason = resolve_selection_reason(&candidates, selected);

    Ok(PublicQueryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        path: path.to_string(),
        value,
        selection: PublicSelectionReport {
            reason,
            record: public_selected_record(index_root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: resolve_competing_value(candidate, path),
                record: public_selected_record(index_root, candidate),
            })
            .collect(),
        links: public_links_with_base(
            host,
            owner,
            repo,
            PublicLinkKind::Query,
            Some(path),
            base_path,
        )?,
    })
}

pub fn public_repository_batch_profiles_with_base(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicBatchProfileResponse> {
    normalize_public_base_path(base_path)?;
    validate_batch_identities(identities)?;
    let mut results = Vec::new();
    for identity in identities {
        let requested_identity = PublicRepositoryIdentity {
            host: identity.host.clone(),
            owner: identity.owner.clone(),
            repo: identity.repo.clone(),
            source: identity.source.clone(),
        };
        match public_repository_profile_or_error_with_base_ref(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            &freshness,
            base_path,
        ) {
            Ok(profile) => results.push(PublicBatchProfileItem {
                identity: profile.identity.clone(),
                profile: Some(Box::new(profile)),
                error: None,
            }),
            Err(error) => results.push(PublicBatchProfileItem {
                identity: requested_identity,
                profile: None,
                error: Some(error.error),
            }),
        }
    }

    Ok(PublicBatchProfileResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        result_count: results.len(),
        results,
    })
}

pub fn public_repository_batch_profiles(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
) -> Result<PublicBatchProfileResponse> {
    public_repository_batch_profiles_with_base(index_root, identities, freshness, "/")
}

pub fn public_repository_batch_query_with_base(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    paths: &[String],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicBatchQueryResponse> {
    normalize_public_base_path(base_path)?;
    validate_batch_query_paths(identities, paths)?;
    let mut results = Vec::new();
    for identity in identities {
        for path in paths {
            let requested_identity = PublicRepositoryIdentity {
                host: identity.host.clone(),
                owner: identity.owner.clone(),
                repo: identity.repo.clone(),
                source: identity.source.clone(),
            };
            match public_repository_query_or_error_with_base_ref(
                index_root,
                &identity.host,
                &identity.owner,
                &identity.repo,
                path,
                &freshness,
                base_path,
            ) {
                Ok(query) => results.push(PublicBatchQueryItem {
                    identity: query.identity.clone(),
                    path: path.clone(),
                    query: Some(Box::new(query)),
                    error: None,
                }),
                Err(error) => results.push(PublicBatchQueryItem {
                    identity: requested_identity,
                    path: path.clone(),
                    query: None,
                    error: Some(error.error),
                }),
            }
        }
    }

    Ok(PublicBatchQueryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        repository_count: identities.len(),
        path_count: paths.len(),
        result_count: results.len(),
        results,
    })
}

pub fn public_repository_batch_query(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    paths: &[String],
    freshness: PublicFreshness,
) -> Result<PublicBatchQueryResponse> {
    public_repository_batch_query_with_base(index_root, identities, paths, freshness, "/")
}

pub fn public_query_input_snapshot(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicQueryInputSnapshot> {
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_query_input_snapshot_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
    )
}

pub(crate) fn public_query_input_snapshot_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
) -> Result<PublicQueryInputSnapshot> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);

    Ok(PublicQueryInputSnapshot {
        api_version: PUBLIC_API_VERSION.to_string(),
        freshness,
        identity: public_identity(host, owner, repo, selected),
        selection: PublicQueryInputSelection {
            reason,
            record: public_selected_record(index_root, selected),
            manifest: (*selected.manifest).clone(),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicQueryInputConflict {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                record: public_selected_record(index_root, candidate),
                manifest: (*candidate.manifest).clone(),
            })
            .collect(),
    })
}

pub fn public_repository_query_from_input_with_base(
    snapshot: &PublicQueryInputSnapshot,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicQueryResponse> {
    ensure_public_query_input_version(snapshot)?;
    let value = query_manifest_value(&snapshot.selection.manifest, path)?;
    let identity = &snapshot.identity;

    Ok(PublicQueryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: identity.clone(),
        path: path.to_string(),
        value,
        selection: PublicSelectionReport {
            reason: snapshot.selection.reason,
            record: snapshot.selection.record.clone(),
        },
        conflicts: snapshot
            .conflicts
            .iter()
            .map(|candidate| PublicConflictReport {
                relationship: candidate.relationship,
                reason: candidate.reason,
                value: query_manifest_value(&candidate.manifest, path).ok(),
                record: candidate.record.clone(),
            })
            .collect(),
        links: public_links_with_base(
            &identity.host,
            &identity.owner,
            &identity.repo,
            PublicLinkKind::Query,
            Some(path),
            base_path,
        )?,
    })
}

pub fn load_public_query_input_snapshot(
    export_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
) -> Result<PublicQueryInputSnapshot> {
    validate_public_identity(host, owner, repo)?;
    let path = export_root.join(public_query_input_relative_path(host, owner, repo));
    let text = fs::read_to_string(&path)
        .map_err(|error| anyhow!("failed to read {}: {}", path.display(), error))?;
    let snapshot = serde_json::from_str::<PublicQueryInputSnapshot>(&text)
        .map_err(|error| anyhow!("failed to parse {}: {}", path.display(), error))?;
    ensure_public_query_input_version(&snapshot)?;
    Ok(snapshot)
}
