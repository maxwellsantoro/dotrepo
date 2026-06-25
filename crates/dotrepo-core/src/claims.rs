use anyhow::{anyhow, bail, Result};

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Component, Path, PathBuf};

use crate::selection::{CandidateManifest, RepositoryIdentity};
use crate::util::{display_path, repository_identity};
use crate::validation::{index_error, IndexFinding};

pub(crate) const SUPPORTED_CLAIM_SCHEMA: &str = "dotrepo-claim/v0";
pub(crate) const SUPPORTED_CLAIM_EVENT_SCHEMA: &str = "dotrepo-claim-event/v0";

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct RecordClaimContext {
    pub id: String,
    pub state: ClaimState,
    pub handoff: ClaimHandoffOutcome,
    pub claim_path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latest_event: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimRecord {
    pub schema: String,
    pub claim: ClaimMetadata,
    pub identity: ClaimIdentity,
    pub claimant: Claimant,
    pub target: ClaimTarget,
    #[serde(default)]
    pub resolution: Option<ClaimResolution>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimMetadata {
    pub id: String,
    pub kind: ClaimKind,
    pub state: ClaimState,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimKind {
    MaintainerAuthority,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimState {
    Draft,
    Submitted,
    InReview,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimIdentity {
    pub host: String,
    pub owner: String,
    pub repo: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Claimant {
    pub display_name: String,
    pub asserted_role: String,
    #[serde(default)]
    pub contact: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimTarget {
    #[serde(default)]
    pub index_paths: Vec<String>,
    #[serde(default)]
    pub record_sources: Vec<String>,
    #[serde(default)]
    pub canonical_repo_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimResolution {
    #[serde(default)]
    pub canonical_record_path: Option<String>,
    #[serde(default)]
    pub canonical_mirror_path: Option<String>,
    #[serde(default)]
    pub result_event: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimEvent {
    pub schema: String,
    pub event: ClaimEventMetadata,
    #[serde(default)]
    pub transition: Option<ClaimTransition>,
    pub summary: ClaimSummary,
    #[serde(default)]
    pub links: Option<ClaimEventLinks>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimEventMetadata {
    pub sequence: u32,
    pub kind: ClaimEventKind,
    pub timestamp: String,
    pub actor: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimEventKind {
    Submitted,
    ReviewStarted,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
    Corrected,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimTransition {
    pub from: ClaimState,
    pub to: ClaimState,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimSummary {
    pub text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimEventLinks {
    #[serde(default)]
    pub claim: Option<String>,
    #[serde(default)]
    pub review_notes: Option<String>,
    #[serde(default)]
    pub canonical_record_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct LoadedClaimEvent {
    pub path: String,
    pub event: ClaimEvent,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct LoadedClaimDirectory {
    pub claim_path: String,
    pub claim: ClaimRecord,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_path: Option<String>,
    pub events: Vec<LoadedClaimEvent>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimHandoffOutcome {
    PendingCanonical,
    Superseded,
    Parallel,
    Rejected,
    Withdrawn,
    Disputed,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ClaimInspectionReport {
    pub claim_path: String,
    pub state: ClaimState,
    pub kind: ClaimKind,
    pub identity: ClaimIdentity,
    pub claimant: Claimant,
    pub target: ClaimTargetInspection,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resolution: Option<ClaimResolution>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_path: Option<String>,
    pub events: Vec<ClaimEventInspection>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ClaimTargetInspection {
    pub index_paths: Vec<String>,
    pub record_sources: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub canonical_repo_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub handoff: Option<ClaimHandoffOutcome>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ClaimEventInspection {
    pub path: String,
    pub sequence: u32,
    pub kind: ClaimEventKind,
    pub timestamp: String,
    pub actor: String,
    pub summary: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub from: Option<ClaimState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub to: Option<ClaimState>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimScaffoldInput {
    pub host: String,
    pub owner: String,
    pub repo: String,
    pub claim_id: String,
    pub claimant_display_name: String,
    pub asserted_role: String,
    pub contact: Option<String>,
    pub record_sources: Vec<String>,
    pub canonical_repo_url: Option<String>,
    pub create_review_md: bool,
    pub timestamp: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimScaffoldPlan {
    pub claim_dir: PathBuf,
    pub claim_path: PathBuf,
    pub claim_text: String,
    pub review_path: Option<PathBuf>,
    pub review_text: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimEventAppendInput {
    pub kind: ClaimEventKind,
    pub actor: String,
    pub summary: String,
    pub timestamp: String,
    pub corrected_state: Option<ClaimState>,
    pub canonical_record_path: Option<String>,
    pub canonical_mirror_path: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimEventAppendPlan {
    pub claim_dir: PathBuf,
    pub claim_path: PathBuf,
    pub claim_text: String,
    pub event_path: PathBuf,
    pub event_text: String,
    pub next_state: ClaimState,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ClaimDirectoryIdentity {
    host: String,
    owner: String,
    repo: String,
    claim_id: String,
}

pub fn parse_claim_record(input: &str) -> Result<ClaimRecord> {
    let claim = toml::from_str::<ClaimRecord>(input)
        .map_err(|e| anyhow!("failed to parse claim record: {}", e))?;
    validate_claim_record(&claim)?;
    Ok(claim)
}

pub fn parse_claim_event(input: &str) -> Result<ClaimEvent> {
    let event = toml::from_str::<ClaimEvent>(input)
        .map_err(|e| anyhow!("failed to parse claim event: {}", e))?;
    validate_claim_event(&event)?;
    Ok(event)
}

pub fn load_claim_directory(root: &Path, claim_dir: &Path) -> Result<LoadedClaimDirectory> {
    let claim_path = claim_dir.join("claim.toml");
    if !claim_path.is_file() {
        bail!(
            "claim directory is missing claim.toml: {}",
            claim_path.display()
        );
    }

    let claim_text = fs::read_to_string(&claim_path)
        .map_err(|e| anyhow!("failed to read {}: {}", claim_path.display(), e))?;
    let claim =
        parse_claim_record(&claim_text).map_err(|e| anyhow!("{}: {}", claim_path.display(), e))?;

    let review_path = claim_dir.join("review.md");
    let review = review_path
        .is_file()
        .then(|| display_path(root, &review_path));

    let events_dir = claim_dir.join("events");
    let mut event_paths = Vec::new();
    if events_dir.is_dir() {
        for entry in fs::read_dir(&events_dir)
            .map_err(|e| anyhow!("failed to read {}: {}", events_dir.display(), e))?
        {
            let entry =
                entry.map_err(|e| anyhow!("failed to inspect {}: {}", events_dir.display(), e))?;
            let path = entry.path();
            if path.extension().and_then(|ext| ext.to_str()) == Some("toml") {
                event_paths.push(path);
            }
        }
        event_paths.sort();
    }

    let mut events = Vec::new();
    for path in event_paths {
        let text = fs::read_to_string(&path)
            .map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
        let event = parse_claim_event(&text).map_err(|e| anyhow!("{}: {}", path.display(), e))?;
        events.push(LoadedClaimEvent {
            path: display_path(root, &path),
            event,
        });
    }

    Ok(LoadedClaimDirectory {
        claim_path: display_path(root, &claim_path),
        claim,
        review_path: review,
        events,
    })
}

pub fn inspect_claim_directory(root: &Path, claim_dir: &Path) -> Result<ClaimInspectionReport> {
    let loaded = load_claim_directory(root, claim_dir)?;
    Ok(claim_inspection_report(&loaded))
}

pub fn scaffold_claim_directory(
    root: &Path,
    input: &ClaimScaffoldInput,
) -> Result<ClaimScaffoldPlan> {
    require_path_segment("identity.host", &input.host)?;
    require_path_segment("identity.owner", &input.owner)?;
    require_path_segment("identity.repo", &input.repo)?;
    require_path_segment("claim.id", &input.claim_id)?;
    require_non_empty("claimant.display_name", &input.claimant_display_name)?;
    require_non_empty("claimant.asserted_role", &input.asserted_role)?;
    require_non_empty("claim.created_at", &input.timestamp)?;

    let repo_dir = root
        .join("repos")
        .join(&input.host)
        .join(&input.owner)
        .join(&input.repo);
    let record_path = repo_dir.join("record.toml");
    if !record_path.is_file() {
        bail!(
            "no index record found at {}; claims can only be scaffolded for existing index repositories",
            record_path.display()
        );
    }

    let claim_dir = repo_dir.join("claims").join(&input.claim_id);
    let claim_path = claim_dir.join("claim.toml");
    let review_path = input.create_review_md.then(|| claim_dir.join("review.md"));
    let record_source_values = input
        .record_sources
        .iter()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .collect::<Vec<_>>();
    let contact = input
        .contact
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let canonical_repo_url = input
        .canonical_repo_url
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let claim = ClaimRecord {
        schema: SUPPORTED_CLAIM_SCHEMA.into(),
        claim: ClaimMetadata {
            id: format!(
                "{}/{}/{}/{}",
                input.host, input.owner, input.repo, input.claim_id
            ),
            kind: ClaimKind::MaintainerAuthority,
            state: ClaimState::Draft,
            created_at: input.timestamp.clone(),
            updated_at: input.timestamp.clone(),
        },
        identity: ClaimIdentity {
            host: input.host.clone(),
            owner: input.owner.clone(),
            repo: input.repo.clone(),
        },
        claimant: Claimant {
            display_name: input.claimant_display_name.clone(),
            asserted_role: input.asserted_role.clone(),
            contact,
        },
        target: ClaimTarget {
            index_paths: vec![format!(
                "repos/{}/{}/{}/record.toml",
                input.host, input.owner, input.repo
            )],
            record_sources: record_source_values,
            canonical_repo_url,
        },
        resolution: None,
    };
    validate_claim_record(&claim)?;
    let claim_text =
        toml::to_string_pretty(&claim).map_err(|e| anyhow!("failed to render claim.toml: {e}"))?;
    let review_text = review_path
        .as_ref()
        .map(|_| render_claim_review_template(&claim));

    Ok(ClaimScaffoldPlan {
        claim_dir,
        claim_path,
        claim_text,
        review_path,
        review_text,
    })
}

pub fn append_claim_event(
    root: &Path,
    claim_dir: &Path,
    input: &ClaimEventAppendInput,
) -> Result<ClaimEventAppendPlan> {
    require_non_empty("event.actor", &input.actor)?;
    require_non_empty("summary.text", &input.summary)?;
    require_non_empty("event.timestamp", &input.timestamp)?;

    let loaded = load_claim_directory(root, claim_dir)?;
    let next_sequence = loaded
        .events
        .last()
        .map(|event| event.event.event.sequence + 1)
        .unwrap_or(1);
    let current_state = loaded.claim.claim.state.clone();
    let next_state = next_claim_state(
        &current_state,
        &input.kind,
        !loaded.events.is_empty(),
        input.corrected_state.as_ref(),
    )?;
    let transition = event_transition_for(&current_state, &next_state, &input.kind);
    let canonical_record_path = input
        .canonical_record_path
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let canonical_mirror_path = input
        .canonical_mirror_path
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let records_canonical_handoff =
        canonical_record_path.is_some() || canonical_mirror_path.is_some();
    if records_canonical_handoff && next_state != ClaimState::Accepted {
        bail!("canonical handoff links are only valid when the resulting claim state is accepted");
    }
    let review_notes_link = if loaded.review_path.is_some()
        && matches!(
            input.kind,
            ClaimEventKind::Accepted | ClaimEventKind::Corrected
        ) {
        Some("../review.md".into())
    } else {
        None
    };
    let links = if review_notes_link.is_some() || canonical_record_path.is_some() {
        Some(ClaimEventLinks {
            claim: Some("../claim.toml".into()),
            review_notes: review_notes_link,
            canonical_record_path: canonical_record_path.clone(),
        })
    } else {
        None
    };
    let event = ClaimEvent {
        schema: SUPPORTED_CLAIM_EVENT_SCHEMA.into(),
        event: ClaimEventMetadata {
            sequence: next_sequence,
            kind: input.kind.clone(),
            timestamp: input.timestamp.clone(),
            actor: input.actor.clone(),
        },
        transition,
        summary: ClaimSummary {
            text: input.summary.clone(),
        },
        links,
    };
    validate_claim_event(&event)?;

    let mut updated_claim = loaded.claim.clone();
    updated_claim.claim.updated_at = input.timestamp.clone();
    updated_claim.claim.state = next_state.clone();
    let result_event = format!(
        "events/{next_sequence:04}-{}.toml",
        claim_event_kind_slug(&input.kind)
    );
    updated_claim.resolution = update_claim_resolution(
        &loaded.claim,
        &input.kind,
        &next_state,
        canonical_record_path.clone(),
        canonical_mirror_path.clone(),
        &result_event,
    )?;
    validate_claim_record(&updated_claim)?;

    let event_label = claim_event_kind_slug(&input.kind);
    let event_file_name = format!("{next_sequence:04}-{event_label}.toml");
    let event_path = claim_dir.join("events").join(&event_file_name);
    let event_text =
        toml::to_string_pretty(&event).map_err(|e| anyhow!("failed to render claim event: {e}"))?;
    let claim_text = toml::to_string_pretty(&updated_claim)
        .map_err(|e| anyhow!("failed to render updated claim.toml: {e}"))?;

    let mut simulated_events = loaded.events.clone();
    simulated_events.push(LoadedClaimEvent {
        path: display_path(root, &event_path),
        event: event.clone(),
    });
    let relative_claim = PathBuf::from(&loaded.claim_path);
    let history_findings =
        validate_claim_event_history(&relative_claim, &updated_claim, &simulated_events);
    if let Some(finding) = history_findings.first() {
        bail!("{}", finding.message);
    }
    let resolution_findings =
        validate_claim_resolution_consistency(&relative_claim, &updated_claim);
    if let Some(finding) = resolution_findings.first() {
        bail!("{}", finding.message);
    }

    Ok(ClaimEventAppendPlan {
        claim_dir: claim_dir.to_path_buf(),
        claim_path: claim_dir.join("claim.toml"),
        claim_text,
        event_path,
        event_text,
        next_state,
    })
}
fn claim_inspection_report(loaded: &LoadedClaimDirectory) -> ClaimInspectionReport {
    ClaimInspectionReport {
        claim_path: loaded.claim_path.clone(),
        state: loaded.claim.claim.state.clone(),
        kind: loaded.claim.claim.kind.clone(),
        identity: loaded.claim.identity.clone(),
        claimant: loaded.claim.claimant.clone(),
        target: ClaimTargetInspection {
            index_paths: loaded.claim.target.index_paths.clone(),
            record_sources: loaded.claim.target.record_sources.clone(),
            canonical_repo_url: loaded.claim.target.canonical_repo_url.clone(),
            handoff: derived_claim_handoff(&loaded.claim),
        },
        resolution: loaded.claim.resolution.clone(),
        review_path: loaded.review_path.clone(),
        events: loaded
            .events
            .iter()
            .map(|loaded_event| ClaimEventInspection {
                path: loaded_event.path.clone(),
                sequence: loaded_event.event.event.sequence,
                kind: loaded_event.event.event.kind.clone(),
                timestamp: loaded_event.event.event.timestamp.clone(),
                actor: loaded_event.event.event.actor.clone(),
                summary: loaded_event.event.summary.text.clone(),
                from: loaded_event
                    .event
                    .transition
                    .as_ref()
                    .map(|transition| transition.from.clone()),
                to: loaded_event
                    .event
                    .transition
                    .as_ref()
                    .map(|transition| transition.to.clone()),
            })
            .collect(),
    }
}

fn derived_claim_handoff(claim: &ClaimRecord) -> Option<ClaimHandoffOutcome> {
    match claim.claim.state {
        ClaimState::Draft | ClaimState::Submitted | ClaimState::InReview => None,
        ClaimState::Accepted => {
            let has_canonical_link = claim
                .resolution
                .as_ref()
                .map(|resolution| {
                    resolution.canonical_record_path.is_some()
                        || resolution.canonical_mirror_path.is_some()
                })
                .unwrap_or(false);
            Some(if has_canonical_link {
                ClaimHandoffOutcome::Superseded
            } else {
                ClaimHandoffOutcome::PendingCanonical
            })
        }
        ClaimState::Rejected => Some(ClaimHandoffOutcome::Rejected),
        ClaimState::Withdrawn => Some(ClaimHandoffOutcome::Withdrawn),
        ClaimState::Disputed => Some(ClaimHandoffOutcome::Disputed),
    }
}

fn render_claim_review_template(claim: &ClaimRecord) -> String {
    format!(
        "# Claim review\n\n- Claim: `{}`\n- Repository: `{}/{}/{}`\n- Status: `{:?}`\n- Reviewer:\n- Decision:\n- Notes:\n",
        claim.claim.id,
        claim.identity.host,
        claim.identity.owner,
        claim.identity.repo,
        claim.claim.state
    )
}

fn next_claim_state(
    current: &ClaimState,
    kind: &ClaimEventKind,
    has_events: bool,
    corrected_state: Option<&ClaimState>,
) -> Result<ClaimState> {
    match kind {
        ClaimEventKind::Submitted => {
            if *current != ClaimState::Draft || has_events {
                bail!("submitted events are only valid for draft claims without prior history");
            }
            Ok(ClaimState::Submitted)
        }
        ClaimEventKind::ReviewStarted => {
            if *current != ClaimState::Submitted {
                bail!("review_started events are only valid for submitted claims");
            }
            Ok(ClaimState::InReview)
        }
        ClaimEventKind::Accepted => {
            if !matches!(current, ClaimState::Submitted | ClaimState::InReview) {
                bail!("accepted events are only valid for submitted or in_review claims");
            }
            Ok(ClaimState::Accepted)
        }
        ClaimEventKind::Rejected => {
            if !matches!(current, ClaimState::Submitted | ClaimState::InReview) {
                bail!("rejected events are only valid for submitted or in_review claims");
            }
            Ok(ClaimState::Rejected)
        }
        ClaimEventKind::Withdrawn => {
            if !matches!(
                current,
                ClaimState::Draft | ClaimState::Submitted | ClaimState::InReview
            ) {
                bail!("withdrawn events are only valid before terminal review outcomes");
            }
            Ok(ClaimState::Withdrawn)
        }
        ClaimEventKind::Disputed => {
            if !matches!(current, ClaimState::Submitted | ClaimState::InReview) {
                bail!("disputed events are only valid for submitted or in_review claims");
            }
            Ok(ClaimState::Disputed)
        }
        ClaimEventKind::Corrected => {
            if !has_events {
                bail!("corrected events require prior claim history");
            }
            if let Some(state) = corrected_state {
                if *state == ClaimState::Draft {
                    bail!("corrected events must not reset a claim back to draft");
                }
                Ok(state.clone())
            } else {
                Ok(current.clone())
            }
        }
    }
}

fn event_transition_for(
    current: &ClaimState,
    next: &ClaimState,
    kind: &ClaimEventKind,
) -> Option<ClaimTransition> {
    if matches!(kind, ClaimEventKind::Corrected) {
        return None;
    }

    Some(ClaimTransition {
        from: current.clone(),
        to: next.clone(),
    })
}

fn claim_event_kind_slug(kind: &ClaimEventKind) -> &'static str {
    match kind {
        ClaimEventKind::Submitted => "submitted",
        ClaimEventKind::ReviewStarted => "review-started",
        ClaimEventKind::Accepted => "accepted",
        ClaimEventKind::Rejected => "rejected",
        ClaimEventKind::Withdrawn => "withdrawn",
        ClaimEventKind::Disputed => "disputed",
        ClaimEventKind::Corrected => "corrected",
    }
}

fn update_claim_resolution(
    existing: &ClaimRecord,
    kind: &ClaimEventKind,
    next_state: &ClaimState,
    canonical_record_path: Option<String>,
    canonical_mirror_path: Option<String>,
    result_event: &str,
) -> Result<Option<ClaimResolution>> {
    if *next_state != ClaimState::Accepted {
        return Ok(None);
    }

    let provided_links = canonical_record_path.is_some() || canonical_mirror_path.is_some();
    match kind {
        ClaimEventKind::Accepted => {
            if !provided_links {
                return Ok(None);
            }
            Ok(Some(ClaimResolution {
                canonical_record_path,
                canonical_mirror_path,
                result_event: Some(result_event.into()),
            }))
        }
        ClaimEventKind::Corrected => {
            if !provided_links {
                return Ok(existing.resolution.clone());
            }
            let mut resolution = existing.resolution.clone().unwrap_or(ClaimResolution {
                canonical_record_path: None,
                canonical_mirror_path: None,
                result_event: None,
            });
            resolution.canonical_record_path = canonical_record_path;
            resolution.canonical_mirror_path = canonical_mirror_path;
            resolution.result_event = Some(result_event.into());
            Ok(Some(resolution))
        }
        _ => Ok(existing.resolution.clone()),
    }
}

pub(crate) fn candidate_claim_context(
    root: &Path,
    candidate: &CandidateManifest,
) -> Option<RecordClaimContext> {
    let handoff_root = match candidate.path.parent() {
        Some(parent) => parent.join("claims"),
        None => return None,
    };
    if !handoff_root.is_dir() {
        return None;
    }

    let mut claim_dirs = fs::read_dir(&handoff_root)
        .ok()?
        .filter_map(|entry| entry.ok())
        .filter_map(|entry| {
            entry
                .file_type()
                .ok()
                .filter(|ty| ty.is_dir())
                .map(|_| entry.path())
        })
        .collect::<Vec<_>>();
    claim_dirs.sort();

    let manifest_path = candidate.manifest_path.as_str();
    let mut matching = claim_dirs
        .into_iter()
        .filter_map(|claim_dir| load_claim_directory(root, &claim_dir).ok())
        .filter_map(|loaded| {
            let handoff = derived_claim_handoff(&loaded.claim)?;
            if matches!(
                handoff,
                ClaimHandoffOutcome::Rejected | ClaimHandoffOutcome::Withdrawn
            ) {
                return None;
            }
            if !claim_matches_candidate(&loaded.claim, manifest_path, candidate) {
                return None;
            }
            Some((loaded, handoff))
        })
        .collect::<Vec<_>>();

    matching.sort_by(|left, right| {
        right
            .0
            .claim
            .claim
            .updated_at
            .cmp(&left.0.claim.claim.updated_at)
            .then_with(|| left.0.claim_path.cmp(&right.0.claim_path))
    });

    let (loaded, handoff) = matching.into_iter().next()?;
    Some(RecordClaimContext {
        id: loaded.claim.claim.id,
        state: loaded.claim.claim.state,
        handoff,
        claim_path: loaded.claim_path,
        latest_event: loaded.events.last().map(|event| event.path.clone()),
        review_path: loaded.review_path,
    })
}

pub(crate) fn claim_matches_candidate(
    claim: &ClaimRecord,
    manifest_path: &str,
    candidate: &CandidateManifest,
) -> bool {
    if claim
        .target
        .index_paths
        .iter()
        .any(|path| path == manifest_path)
    {
        return true;
    }

    if claim
        .resolution
        .as_ref()
        .and_then(|resolution| resolution.canonical_mirror_path.as_deref())
        .is_some_and(|path| path == manifest_path)
    {
        return true;
    }

    if claim
        .resolution
        .as_ref()
        .and_then(|resolution| resolution.canonical_record_path.as_deref())
        .is_some_and(|path| path == manifest_path)
    {
        return true;
    }

    if candidate
        .manifest
        .record
        .source
        .as_deref()
        .is_some_and(|source| {
            claim
                .target
                .record_sources
                .iter()
                .any(|record_source| record_source == source)
        })
    {
        return true;
    }

    candidate.identity.as_ref().is_some_and(|identity| {
        claim.identity.host == identity.host
            && claim.identity.owner == identity.owner
            && claim.identity.repo == identity.repo
    })
}

fn validate_claim_record(claim: &ClaimRecord) -> Result<()> {
    if claim.schema != SUPPORTED_CLAIM_SCHEMA {
        bail!(
            "unsupported claim schema `{}`; expected {}",
            claim.schema,
            SUPPORTED_CLAIM_SCHEMA
        );
    }

    require_non_empty("claim.id", &claim.claim.id)?;
    require_non_empty("claim.created_at", &claim.claim.created_at)?;
    require_non_empty("claim.updated_at", &claim.claim.updated_at)?;
    require_non_empty("identity.host", &claim.identity.host)?;
    require_non_empty("identity.owner", &claim.identity.owner)?;
    require_non_empty("identity.repo", &claim.identity.repo)?;
    require_non_empty("claimant.display_name", &claim.claimant.display_name)?;
    require_non_empty("claimant.asserted_role", &claim.claimant.asserted_role)?;
    if claim.target.index_paths.is_empty()
        && claim.target.record_sources.is_empty()
        && claim.target.canonical_repo_url.is_none()
    {
        bail!(
            "claim.target must include at least one index path, record source, or canonical repo url"
        );
    }
    Ok(())
}

fn validate_claim_event(event: &ClaimEvent) -> Result<()> {
    if event.schema != SUPPORTED_CLAIM_EVENT_SCHEMA {
        bail!(
            "unsupported claim event schema `{}`; expected {}",
            event.schema,
            SUPPORTED_CLAIM_EVENT_SCHEMA
        );
    }

    if event.event.sequence == 0 {
        bail!("event.sequence must be greater than zero");
    }
    require_non_empty("event.timestamp", &event.event.timestamp)?;
    require_non_empty("event.actor", &event.event.actor)?;
    require_non_empty("summary.text", &event.summary.text)?;
    Ok(())
}

fn require_non_empty(field: &str, value: &str) -> Result<()> {
    if value.trim().is_empty() {
        bail!("{field} must not be empty");
    }
    Ok(())
}

pub(crate) fn require_path_segment(field: &str, value: &str) -> Result<()> {
    require_non_empty(field, value)?;
    let path = Path::new(value);
    let mut components = path.components();
    if !matches!(components.next(), Some(Component::Normal(_))) || components.next().is_some() {
        bail!("{field} must be a single path segment");
    }
    Ok(())
}

pub(crate) fn resolve_repository_local_path(root: &Path, value: &str) -> Result<PathBuf> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        bail!("path must not be empty");
    }

    let path = Path::new(trimmed);
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::Normal(part) => normalized.push(part),
            Component::CurDir => {}
            Component::ParentDir => bail!("path must stay within the repository root"),
            Component::RootDir | Component::Prefix(_) => {
                bail!("path must be relative to the repository root")
            }
        }
    }

    Ok(root.join(normalized))
}
pub(crate) fn claim_directory_identity(
    index_root: &Path,
    claim_dir: &Path,
) -> Result<ClaimDirectoryIdentity> {
    let relative = claim_dir.strip_prefix(index_root).map_err(|_| {
        anyhow!(
            "claim directories must live under index_root/repos/<host>/<owner>/<repo>/claims/<id>/"
        )
    })?;
    let segments = relative
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    if segments.len() != 6
        || segments[0] != "repos"
        || segments[4] != "claims"
        || segments[5].trim().is_empty()
    {
        bail!("claim directories must live under repos/<host>/<owner>/<repo>/claims/<claim-id>/");
    }

    Ok(ClaimDirectoryIdentity {
        host: segments[1].clone(),
        owner: segments[2].clone(),
        repo: segments[3].clone(),
        claim_id: segments[5].clone(),
    })
}

pub(crate) fn validate_claim_identity_alignment(
    relative_claim: &Path,
    expected: &ClaimDirectoryIdentity,
    claim: &ClaimRecord,
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();

    if claim.identity.host != expected.host
        || claim.identity.owner != expected.owner
        || claim.identity.repo != expected.repo
    {
        findings.push(index_error(
            relative_claim.to_path_buf(),
            format!(
                "claim.identity resolves to {}/{}/{}, but claim path is repos/{}/{}/{}/claims/{}/claim.toml",
                claim.identity.host,
                claim.identity.owner,
                claim.identity.repo,
                expected.host,
                expected.owner,
                expected.repo,
                expected.claim_id
            ),
        ));
    }

    if claim.claim.id.trim().is_empty() {
        findings.push(index_error(
            relative_claim.to_path_buf(),
            "claim.id must not be empty",
        ));
    } else {
        let expected_prefix = format!("{}/{}/{}/", expected.host, expected.owner, expected.repo);
        if !claim.claim.id.starts_with(&expected_prefix) {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "claim.id must start with {expected_prefix} to match the containing repository identity"
                ),
            ));
        }
    }

    for index_path in &claim.target.index_paths {
        match parse_index_record_identity(index_path) {
            Some(identity)
                if identity.host == expected.host
                    && identity.owner == expected.owner
                    && identity.repo == expected.repo => {}
            Some(identity) => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.index_paths includes {}, which resolves to {}/{}/{}, but claim path is repos/{}/{}/{}",
                    index_path, identity.host, identity.owner, identity.repo, expected.host, expected.owner, expected.repo
                ),
            )),
            None => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.index_paths includes `{}`; expected repos/<host>/<owner>/<repo>/record.toml",
                    index_path
                ),
            )),
        }
    }

    for record_source in &claim.target.record_sources {
        match repository_identity(record_source) {
            Some((host, owner, repo))
                if host == expected.host && owner == expected.owner && repo == expected.repo => {}
            Some((host, owner, repo)) => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.record_sources includes {}, which resolves to {}/{}/{}, but claim path is repos/{}/{}/{}",
                    record_source, host, owner, repo, expected.host, expected.owner, expected.repo
                ),
            )),
            None => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.record_sources includes `{}`; expected an absolute repository URL",
                    record_source
                ),
            )),
        }
    }

    if let Some(canonical_repo_url) = &claim.target.canonical_repo_url {
        match repository_identity(canonical_repo_url) {
            Some((host, owner, repo))
                if host == expected.host && owner == expected.owner && repo == expected.repo => {}
            Some((host, owner, repo)) => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.canonical_repo_url resolves to {}/{}/{}, but claim path is repos/{}/{}/{}",
                    host, owner, repo, expected.host, expected.owner, expected.repo
                ),
            )),
            None => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.canonical_repo_url `{}` must be an absolute repository URL",
                    canonical_repo_url
                ),
            )),
        }
    }

    findings
}

pub(crate) fn validate_claim_event_history(
    relative_claim: &Path,
    claim: &ClaimRecord,
    events: &[LoadedClaimEvent],
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();

    if events.is_empty() {
        if claim.claim.state != ClaimState::Draft {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                "non-draft claims must include at least one event in events/",
            ));
        }
        return findings;
    }

    let mut expected_sequence = 1_u32;
    for loaded in events {
        let event = &loaded.event;
        if event.event.sequence != expected_sequence {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "claim events must use contiguous sequence numbers starting at 1; expected {}, found {} in {}",
                    expected_sequence, event.event.sequence, loaded.path
                ),
            ));
            expected_sequence = event.event.sequence.saturating_add(1);
        } else {
            expected_sequence += 1;
        }

        let requires_transition = !matches!(event.event.kind, ClaimEventKind::Corrected);
        if requires_transition && event.transition.is_none() {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "{} must include a transition block for event kind {:?}",
                    loaded.path, event.event.kind
                ),
            ));
        }
        if let Some(transition) = &event.transition {
            if transition.from == transition.to {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    format!(
                        "{} has a transition where from and to are both {:?}",
                        loaded.path, transition.to
                    ),
                ));
            }
            if !transition_matches_event_kind(transition.to.clone(), &event.event.kind) {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    format!(
                        "{} transitions to {:?}, which does not match event kind {:?}",
                        loaded.path, transition.to, event.event.kind
                    ),
                ));
            }
        }
    }

    if let Some(last) = events.last() {
        let terminal_state = last
            .event
            .transition
            .as_ref()
            .map(|transition| transition.to.clone())
            .unwrap_or_else(|| claim.claim.state.clone());
        if terminal_state != claim.claim.state {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "claim.state is {:?}, but the last event in {} resolves to {:?}",
                    claim.claim.state, last.path, terminal_state
                ),
            ));
        }
    }

    findings
}

pub(crate) fn validate_claim_resolution_consistency(
    relative_claim: &Path,
    claim: &ClaimRecord,
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let resolution = claim.resolution.as_ref();
    let has_canonical_link = resolution
        .map(|resolution| {
            resolution.canonical_record_path.is_some() || resolution.canonical_mirror_path.is_some()
        })
        .unwrap_or(false);

    match claim.claim.state {
        ClaimState::Rejected | ClaimState::Withdrawn => {
            if has_canonical_link {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    "rejected or withdrawn claims must not record canonical handoff links",
                ));
            }
        }
        ClaimState::Disputed => {
            if has_canonical_link {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    "disputed claims must not record completed canonical handoff links",
                ));
            }
        }
        ClaimState::Accepted => {
            if let Some(resolution) = resolution {
                if resolution.result_event.is_none() {
                    findings.push(index_error(
                        relative_claim.to_path_buf(),
                        "accepted claims with a resolution block must include resolution.result_event",
                    ));
                }
                if let Some(canonical_mirror_path) = &resolution.canonical_mirror_path {
                    if parse_index_record_identity(canonical_mirror_path).is_none() {
                        findings.push(index_error(
                            relative_claim.to_path_buf(),
                            format!(
                                "resolution.canonical_mirror_path `{}` must match repos/<host>/<owner>/<repo>/record.toml",
                                canonical_mirror_path
                            ),
                        ));
                    }
                }
            }
        }
        _ => {}
    }

    findings
}

fn transition_matches_event_kind(target: ClaimState, kind: &ClaimEventKind) -> bool {
    if matches!(kind, ClaimEventKind::Corrected) {
        return true;
    }
    matches!(
        (target, kind),
        (ClaimState::Submitted, ClaimEventKind::Submitted)
            | (ClaimState::InReview, ClaimEventKind::ReviewStarted)
            | (ClaimState::Accepted, ClaimEventKind::Accepted)
            | (ClaimState::Rejected, ClaimEventKind::Rejected)
            | (ClaimState::Withdrawn, ClaimEventKind::Withdrawn)
            | (ClaimState::Disputed, ClaimEventKind::Disputed)
    )
}

fn parse_index_record_identity(path: &str) -> Option<RepositoryIdentity> {
    let segments = Path::new(path)
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    if segments.len() != 5
        || segments[0] != "repos"
        || segments[4] != "record.toml"
        || segments[1].trim().is_empty()
        || segments[2].trim().is_empty()
        || segments[3].trim().is_empty()
    {
        return None;
    }

    Some(RepositoryIdentity {
        host: segments[1].clone(),
        owner: segments[2].clone(),
        repo: segments[3].clone(),
    })
}
