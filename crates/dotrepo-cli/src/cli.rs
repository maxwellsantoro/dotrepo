use clap::{Parser, Subcommand, ValueEnum};
use dotrepo_core::{ClaimEventKind, DoctorSurface, ImportMode};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "dotrepo")]
#[command(about = "reference cli for the dotrepo protocol")]
pub struct Cli {
    /// Repository root containing `.repo` or overlay records.
    #[arg(long, default_value = ".")]
    pub root: PathBuf,
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// Initialize a canonical root `.repo` scaffold.
    Init {
        /// Overwrite an existing root `.repo`.
        #[arg(long)]
        force: bool,
    },
    /// Import conventional repository surfaces into a dotrepo record.
    Import {
        /// Record mode for the imported manifest.
        #[arg(long, value_enum, default_value_t = ImportModeArg::Native)]
        mode: ImportModeArg,
        /// Explicit repository source URL for overlays.
        #[arg(long)]
        source: Option<String>,
        /// Overwrite previously imported artifacts.
        #[arg(long)]
        force: bool,
    },
    /// Bootstrap a native `.repo` from an existing public overlay record.
    AdoptOverlay {
        /// Path to an overlay record.toml from the public index.
        overlay_record: PathBuf,
        /// Overwrite an existing root `.repo`.
        #[arg(long)]
        force: bool,
    },
    /// Validate only the root `.repo` or root `record.toml`.
    Validate,
    /// Validate a public index tree rooted at `index/`.
    ValidateIndex {
        /// Index root to validate.
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
    },
    /// Analyze index records for promotion eligibility to verified status.
    PromotionReport {
        /// Index root to analyze.
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Apply eligible draft/imported/inferred promotions after reporting.
        #[arg(long)]
        apply: bool,
        /// Maximum number of promotions to apply.
        #[arg(long, requires = "apply")]
        limit: Option<usize>,
        /// Emit the full report as JSON.
        #[arg(long)]
        json: bool,
        /// Show per-record details including blockers.
        #[arg(long)]
        verbose: bool,
    },
    /// Query one field from the selected record, preserving trust-aware selection in `--json`.
    Query {
        /// Dot-path such as `repo.name` or `record.trust.provenance`.
        path: String,
        /// Emit the full conflict-aware query report as JSON.
        #[arg(long, conflicts_with = "raw")]
        json: bool,
        /// Emit only the selected scalar value. Refuses when competing records exist.
        #[arg(long, conflicts_with = "json")]
        raw: bool,
    },
    /// Render generated compatibility surfaces or fail when they drift.
    Generate {
        /// Check generated surfaces for drift without writing files.
        #[arg(long)]
        check: bool,
    },
    /// Inspect unmanaged conventional files at the repository root.
    Doctor {
        /// Emit the full doctor report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Adopt one supported Markdown surface into managed-region sync.
    Manage {
        /// Conventional surface to manage.
        surface: PreviewSurfaceArg,
        /// Convert the existing file into a managed-region file.
        #[arg(long)]
        adopt: bool,
    },
    /// Preview how dotrepo would render or replace one managed surface.
    Preview {
        /// Conventional surface to preview.
        #[arg(long, value_enum, conflicts_with = "all")]
        surface: Option<PreviewSurfaceArg>,
        /// Preview every supported surface.
        #[arg(long, conflicts_with = "surface")]
        all: bool,
        /// Emit the full preview report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Inspect trust, authority handoff, and competing records for one repository identity.
    Trust {
        /// Emit the full conflict-aware trust report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Summarize native adoption readiness for the current repository.
    AdoptionStatus {
        /// Emit the full adoption readiness report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Scaffold CI for the canonical native-repo maintainer loop.
    Ci {
        #[command(subcommand)]
        command: CiCommand,
    },
    /// Inspect one maintainer-claim directory from the index.
    Claim {
        /// Claim directory relative to --root.
        path: PathBuf,
        /// Emit the full claim inspection report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Scaffold a draft maintainer-claim directory for one index repository.
    ClaimInit {
        /// Repository host under index_root/repos/<host>/<owner>/<repo>/.
        #[arg(long)]
        host: String,
        /// Repository owner under index_root/repos/<host>/<owner>/<repo>/.
        #[arg(long)]
        owner: String,
        /// Repository name under index_root/repos/<host>/<owner>/<repo>/.
        #[arg(long)]
        repo: String,
        /// Claim directory name under claims/<claim-id>/.
        #[arg(long)]
        claim_id: String,
        /// Claimant display name recorded in claim.toml.
        #[arg(long)]
        claimant_name: String,
        /// Claimed repository role, such as `maintainer`.
        #[arg(long)]
        asserted_role: String,
        /// Optional claimant contact detail.
        #[arg(long)]
        contact: Option<String>,
        /// Additional record source URLs tied to this claim.
        #[arg(long = "record-source")]
        record_sources: Vec<String>,
        /// Optional canonical repository URL for the claim target.
        #[arg(long)]
        canonical_repo_url: Option<String>,
        /// Create a placeholder review.md next to claim.toml.
        #[arg(long)]
        review_md: bool,
        /// Replace an existing empty scaffold, but never overwrite event history.
        #[arg(long)]
        force: bool,
    },
    /// Scaffold a maintainer claim from the current native `.repo`.
    ClaimFromNative {
        /// Index root where the overlay claim directory should be created.
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Claim directory name under claims/<claim-id>/.
        #[arg(long)]
        claim_id: String,
        /// Claimant display name recorded in claim.toml.
        #[arg(long)]
        claimant_name: String,
        /// Claimed repository role, such as `maintainer`.
        #[arg(long, default_value = "maintainer")]
        asserted_role: String,
        /// Optional claimant contact detail.
        #[arg(long)]
        contact: Option<String>,
        /// Create a placeholder review.md next to claim.toml.
        #[arg(long)]
        review_md: bool,
        /// Replace an existing empty scaffold, but never overwrite event history.
        #[arg(long)]
        force: bool,
    },
    /// Append a new claim event and update the current claim state.
    ClaimEvent {
        /// Claim directory relative to --root.
        path: PathBuf,
        /// Event kind to append.
        #[arg(long, value_enum)]
        kind: ClaimEventKindArg,
        /// Actor label recorded in the event.
        #[arg(long)]
        actor: String,
        /// Short event summary recorded in the audit trail.
        #[arg(long)]
        summary: String,
        /// Optional corrected current state when kind=corrected.
        #[arg(long, value_enum)]
        corrected_state: Option<CorrectedClaimStateArg>,
        /// Optional canonical `.repo` path recorded for accepted handoff.
        #[arg(long)]
        canonical_record_path: Option<String>,
        /// Optional canonical mirror record path recorded for accepted handoff.
        #[arg(long)]
        canonical_mirror_path: Option<String>,
    },
    /// Append a submitted claim event with the claim path derived from the current native `.repo`.
    ClaimSubmitNative {
        /// Index root containing the claim directory.
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Claim directory name under claims/<claim-id>/.
        #[arg(long)]
        claim_id: String,
        /// Actor label recorded in the event.
        #[arg(long, default_value = "claimant")]
        actor: String,
        /// Short event summary recorded in the audit trail.
        #[arg(long, default_value = "Submitted maintainer claim.")]
        summary: String,
    },
    /// Append an accepted claim event with canonical links from the current native `.repo`.
    ClaimAcceptNative {
        /// Index root containing the claim directory.
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Claim directory relative to --index-root.
        #[arg(
            value_name = "CLAIM_PATH",
            help = "Claim directory relative to --index-root"
        )]
        path: Option<PathBuf>,
        /// Claim directory name under claims/<claim-id>; derives path from repo.homepage.
        #[arg(long)]
        claim_id: Option<String>,
        /// Actor label recorded in the event.
        #[arg(long, default_value = "index-reviewer")]
        actor: String,
        /// Short event summary recorded in the audit trail.
        #[arg(
            long,
            default_value = "Accepted maintainer claim with canonical native record."
        )]
        summary: String,
    },
    /// Inspect or export public read-only index responses.
    Public {
        #[command(subcommand)]
        command: PublicCommand,
    },
}

#[derive(Subcommand)]
pub enum PublicCommand {
    /// Render one public repository summary response as JSON.
    Summary {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Render one compact public research profile response as JSON.
    Profile {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Render compact public research profiles for multiple repositories.
    BatchProfiles {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Repository identity as host/owner/repo or https://host/owner/repo.
        #[arg(long = "repo", required = true)]
        repos: Vec<String>,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Render public query responses for multiple repositories and dot paths.
    BatchQuery {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Repository identity as host/owner/repo or https://host/owner/repo.
        #[arg(long = "repo", required = true)]
        repos: Vec<String>,
        /// Dot path to query. Repeat for multiple fields.
        #[arg(long = "path", required = true)]
        paths: Vec<String>,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Compare compact public research profiles for multiple repositories.
    Compare {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Repository identity as host/owner/repo or https://host/owner/repo.
        #[arg(long = "repo", required = true)]
        repos: Vec<String>,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Traverse public repository references declared in the selected profile.
    Relations {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Search compact public research profiles by text and structured filters.
    Search {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        /// Text query matched against identity, name, purpose, homepage, license, languages, and topics.
        #[arg(long)]
        q: Option<String>,
        /// Required language. Repeat for multiple required languages.
        #[arg(long = "language")]
        languages: Vec<String>,
        /// Required topic. Repeat for multiple required topics.
        #[arg(long = "topic")]
        topics: Vec<String>,
        /// Required selected record status. Repeat for accepted statuses.
        #[arg(long = "status")]
        statuses: Vec<String>,
        /// Required trust confidence. Repeat for accepted confidence values.
        #[arg(long = "confidence")]
        confidences: Vec<String>,
        /// Require a build command signal.
        #[arg(long)]
        require_build: bool,
        /// Require a test command signal.
        #[arg(long)]
        require_test: bool,
        /// Require documentation signal.
        #[arg(long)]
        require_docs: bool,
        /// Require security contact signal.
        #[arg(long)]
        require_security_contact: bool,
        /// Require license signal.
        #[arg(long)]
        require_license: bool,
        /// Maximum results to return.
        #[arg(long)]
        limit: Option<usize>,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Render one public trust response as JSON.
    Trust {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Render one public query response as JSON.
    Query {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        path: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Export the static-first public JSON tree for repository summary, profile, and trust.
    Export {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        #[arg(long, default_value = "public")]
        out_dir: PathBuf,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for exported responses.
        #[arg(long)]
        stale_after_hours: Option<i64>,
        /// Fixed RFC 3339 generation timestamp for deterministic export review.
        #[arg(long)]
        generated_at: Option<String>,
        /// Fixed RFC 3339 staleness timestamp for deterministic export review.
        #[arg(long)]
        stale_after: Option<String>,
    },
}

#[derive(Subcommand)]
pub enum CiCommand {
    /// Write the starter GitHub Actions workflow for native-repo checks.
    Init {
        /// Replace an existing workflow file.
        #[arg(long)]
        force: bool,
        /// Release version to pin in the workflow, such as `1.0.0`.
        #[arg(long)]
        version: Option<String>,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
pub enum ImportModeArg {
    Native,
    Overlay,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
pub enum PreviewSurfaceArg {
    Readme,
    Security,
    Contributing,
    Codeowners,
    PullRequestTemplate,
}

#[derive(Clone, Debug, Eq, PartialEq, ValueEnum)]
pub enum ClaimEventKindArg {
    Submitted,
    ReviewStarted,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
    Corrected,
}

#[derive(Clone, Debug, Eq, PartialEq, ValueEnum)]
pub enum CorrectedClaimStateArg {
    Submitted,
    InReview,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
}

impl From<ImportModeArg> for ImportMode {
    fn from(value: ImportModeArg) -> Self {
        match value {
            ImportModeArg::Native => ImportMode::Native,
            ImportModeArg::Overlay => ImportMode::Overlay,
        }
    }
}

impl From<PreviewSurfaceArg> for DoctorSurface {
    fn from(value: PreviewSurfaceArg) -> Self {
        match value {
            PreviewSurfaceArg::Readme => DoctorSurface::Readme,
            PreviewSurfaceArg::Security => DoctorSurface::Security,
            PreviewSurfaceArg::Contributing => DoctorSurface::Contributing,
            PreviewSurfaceArg::Codeowners => DoctorSurface::Codeowners,
            PreviewSurfaceArg::PullRequestTemplate => DoctorSurface::PullRequestTemplate,
        }
    }
}

impl From<ClaimEventKindArg> for ClaimEventKind {
    fn from(value: ClaimEventKindArg) -> Self {
        match value {
            ClaimEventKindArg::Submitted => ClaimEventKind::Submitted,
            ClaimEventKindArg::ReviewStarted => ClaimEventKind::ReviewStarted,
            ClaimEventKindArg::Accepted => ClaimEventKind::Accepted,
            ClaimEventKindArg::Rejected => ClaimEventKind::Rejected,
            ClaimEventKindArg::Withdrawn => ClaimEventKind::Withdrawn,
            ClaimEventKindArg::Disputed => ClaimEventKind::Disputed,
            ClaimEventKindArg::Corrected => ClaimEventKind::Corrected,
        }
    }
}

impl From<CorrectedClaimStateArg> for dotrepo_core::ClaimState {
    fn from(value: CorrectedClaimStateArg) -> Self {
        match value {
            CorrectedClaimStateArg::Submitted => dotrepo_core::ClaimState::Submitted,
            CorrectedClaimStateArg::InReview => dotrepo_core::ClaimState::InReview,
            CorrectedClaimStateArg::Accepted => dotrepo_core::ClaimState::Accepted,
            CorrectedClaimStateArg::Rejected => dotrepo_core::ClaimState::Rejected,
            CorrectedClaimStateArg::Withdrawn => dotrepo_core::ClaimState::Withdrawn,
            CorrectedClaimStateArg::Disputed => dotrepo_core::ClaimState::Disputed,
        }
    }
}
