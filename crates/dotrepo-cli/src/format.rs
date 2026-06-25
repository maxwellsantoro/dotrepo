use anyhow::{bail, Result};
use dotrepo_core::{
    ClaimHandoffOutcome, ClaimInspectionReport, ConflictRelationship, DoctorOwnershipHonesty,
    DoctorRecommendedMode, DoctorSurface, ManagedFileState, SelectionReason, SurfacePreviewReport,
    TrustReport,
};
use dotrepo_schema::Trust;
use serde_json::Value;

pub fn format_trust_report(report: &TrustReport) -> String {
    let selected = &report.selection.record;
    let mut lines = vec![
        format!(
            "selected: {} ({:?}, {:?})",
            selected.manifest_path, selected.record.mode, selected.record.status
        ),
        format!(
            "selection reason: {}",
            format_selection_reason(report.selection.reason)
        ),
    ];

    append_record_details(
        &mut lines,
        "",
        selected.record.source.as_deref(),
        selected.record.trust.as_ref(),
        selected.claim.as_ref(),
    );

    if !report.conflicts.is_empty() {
        lines.push("conflicts:".into());
        for conflict in &report.conflicts {
            lines.push(format!(
                "- {} ({:?}, {:?})",
                conflict.record.manifest_path,
                conflict.record.record.mode,
                conflict.record.record.status
            ));
            lines.push(format!(
                "  relationship: {}",
                format_conflict_relationship(conflict.relationship)
            ));
            lines.push(format!(
                "  reason: {}",
                format_selection_reason(conflict.reason)
            ));
            append_record_details(
                &mut lines,
                "  ",
                conflict.record.record.source.as_deref(),
                conflict.record.record.trust.as_ref(),
                conflict.record.claim.as_ref(),
            );
        }
    }

    lines.join("\n")
}

pub fn format_claim_report(report: &ClaimInspectionReport) -> String {
    let mut lines = vec![
        format!("claim: {}", report.claim_path),
        format!("state: {:?}", report.state),
        format!("kind: {:?}", report.kind),
        format!(
            "identity: {}/{}/{}",
            report.identity.host, report.identity.owner, report.identity.repo
        ),
        format!(
            "claimant: {} ({})",
            report.claimant.display_name, report.claimant.asserted_role
        ),
    ];

    if let Some(contact) = &report.claimant.contact {
        lines.push(format!("contact: {}", contact));
    }
    if let Some(review_path) = &report.review_path {
        lines.push(format!("review: {}", review_path));
    }
    if let Some(handoff) = report.target.handoff {
        lines.push(format!("handoff: {}", format_claim_handoff(handoff)));
    }
    if !report.target.index_paths.is_empty() {
        lines.push("target index paths:".into());
        for path in &report.target.index_paths {
            lines.push(format!("- {}", path));
        }
    }
    if !report.target.record_sources.is_empty() {
        lines.push("target record sources:".into());
        for source in &report.target.record_sources {
            lines.push(format!("- {}", source));
        }
    }
    if let Some(url) = &report.target.canonical_repo_url {
        lines.push(format!("canonical repo url: {}", url));
    }
    if let Some(resolution) = &report.resolution {
        if let Some(path) = &resolution.canonical_record_path {
            lines.push(format!("canonical record path: {}", path));
        }
        if let Some(path) = &resolution.canonical_mirror_path {
            lines.push(format!("canonical mirror path: {}", path));
        }
        if let Some(path) = &resolution.result_event {
            lines.push(format!("result event: {}", path));
        }
    }
    if !report.events.is_empty() {
        lines.push("events:".into());
        for event in &report.events {
            let mut line = format!(
                "- [{}] {:?} at {} by {}",
                event.sequence, event.kind, event.timestamp, event.actor
            );
            if let (Some(from), Some(to)) = (&event.from, &event.to) {
                line.push_str(&format!(" ({from:?} -> {to:?})"));
            }
            lines.push(line);
            lines.push(format!("  {}", event.summary));
        }
    }

    lines.join("\n")
}

pub fn format_query_value(value: &Value, raw: bool) -> Result<String> {
    match value {
        Value::String(text) => Ok(text.clone()),
        Value::Null => {
            if raw {
                Ok(String::new())
            } else {
                Ok("null".into())
            }
        }
        Value::Bool(flag) => Ok(flag.to_string()),
        Value::Number(number) => Ok(number.to_string()),
        Value::Array(_) | Value::Object(_) => {
            if raw {
                bail!("--raw is only supported for scalar query results");
            }
            Ok(serde_json::to_string_pretty(value)?)
        }
    }
}

fn append_record_details(
    lines: &mut Vec<String>,
    indent: &str,
    source: Option<&str>,
    trust: Option<&Trust>,
    claim: Option<&dotrepo_core::RecordClaimContext>,
) {
    lines.push(format!("{}source: {}", indent, source.unwrap_or("none")));
    if let Some(trust) = trust {
        lines.push(format!(
            "{}confidence: {}",
            indent,
            trust.confidence.as_deref().unwrap_or("none")
        ));
        lines.push(format!(
            "{}provenance: {}",
            indent,
            format_provenance(&trust.provenance)
        ));
        lines.push(format!(
            "{}notes: {}",
            indent,
            trust.notes.as_deref().unwrap_or("none")
        ));
    } else {
        lines.push(format!("{}confidence: none", indent));
        lines.push(format!("{}provenance: none", indent));
        lines.push(format!("{}notes: none", indent));
    }
    if let Some(claim) = claim {
        lines.push(format!(
            "{}claim: {:?} ({})",
            indent,
            claim.state,
            format_claim_handoff(claim.handoff)
        ));
        lines.push(format!("{}claim path: {}", indent, claim.claim_path));
    }
}

pub fn format_selection_reason(reason: SelectionReason) -> &'static str {
    match reason {
        SelectionReason::OnlyMatchingRecord => "only matching record",
        SelectionReason::CanonicalPreferred => {
            "canonical record preferred over lower-authority competing records"
        }
        SelectionReason::HigherStatusOverlay => {
            "higher-status overlay preferred over lower-status competing overlays"
        }
        SelectionReason::EqualAuthorityConflict => {
            "equal-authority conflict; selected by stable path ordering while preserving competing records"
        }
    }
}

pub fn format_conflict_relationship(relationship: ConflictRelationship) -> &'static str {
    match relationship {
        ConflictRelationship::Superseded => "superseded",
        ConflictRelationship::Parallel => "parallel",
    }
}

pub fn format_claim_handoff(handoff: ClaimHandoffOutcome) -> &'static str {
    match handoff {
        ClaimHandoffOutcome::PendingCanonical => "pending_canonical",
        ClaimHandoffOutcome::Superseded => "superseded",
        ClaimHandoffOutcome::Parallel => "parallel",
        ClaimHandoffOutcome::Rejected => "rejected",
        ClaimHandoffOutcome::Withdrawn => "withdrawn",
        ClaimHandoffOutcome::Disputed => "disputed",
    }
}

pub fn format_provenance(provenance: &[String]) -> String {
    if provenance.is_empty() {
        "none".into()
    } else {
        provenance.join(", ")
    }
}

pub fn format_managed_file_state(state: ManagedFileState) -> &'static str {
    match state {
        ManagedFileState::Missing => "missing",
        ManagedFileState::FullyGenerated => "fully_generated",
        ManagedFileState::PartiallyManaged => "partially_managed",
        ManagedFileState::Unmanaged => "unmanaged",
        ManagedFileState::MalformedManaged => "malformed_managed",
        ManagedFileState::Unsupported => "unsupported",
    }
}

pub fn format_doctor_surface(surface: DoctorSurface) -> &'static str {
    match surface {
        DoctorSurface::Readme => "readme",
        DoctorSurface::Security => "security",
        DoctorSurface::Contributing => "contributing",
        DoctorSurface::Codeowners => "codeowners",
        DoctorSurface::PullRequestTemplate => "pull_request_template",
    }
}

pub fn format_doctor_recommended_mode(mode: DoctorRecommendedMode) -> &'static str {
    match mode {
        DoctorRecommendedMode::Generate => "generate",
        DoctorRecommendedMode::PartiallyManaged => "partially_managed",
        DoctorRecommendedMode::Skip => "skip",
    }
}

pub fn format_doctor_ownership_honesty(honesty: DoctorOwnershipHonesty) -> &'static str {
    match honesty {
        DoctorOwnershipHonesty::Honest => "honest",
        DoctorOwnershipHonesty::LossyFullGeneration => "lossy_full_generation",
    }
}

pub fn print_surface_preview_report(report: &SurfacePreviewReport) {
    println!("dotrepo preview");
    for preview in &report.previews {
        println!(
            "surface: {}",
            format_doctor_surface(preview.finding.surface)
        );
        println!("path: {}", preview.finding.path.display());
        println!(
            "state: {}",
            format_managed_file_state(preview.finding.state)
        );
        if let Some(mode) = preview.finding.declared_mode.clone() {
            println!("declared mode: {}", format_compat_mode(mode));
        }
        if let Some(honesty) = preview.finding.ownership_honesty {
            println!(
                "ownership honesty: {}",
                format_doctor_ownership_honesty(honesty)
            );
        }
        if let Some(mode) = preview.finding.recommended_mode {
            println!("recommended mode: {}", format_doctor_recommended_mode(mode));
        }
        if let Some(drop) = preview.finding.would_drop_unmanaged_content {
            println!("content loss risk: {}", if drop { "yes" } else { "no" });
        }
        println!(
            "preserves unmanaged content: {}",
            if preview.preserves_unmanaged_content {
                "yes"
            } else {
                "no"
            }
        );
        println!(
            "replacement mode: {}",
            if preview.full_replacement {
                "full_replacement"
            } else {
                "in_place_or_create"
            }
        );
        println!("summary: {}", preview.finding.message);
        if !preview.finding.advice.is_empty() {
            println!("advice:");
            for advice in &preview.finding.advice {
                println!("- {}", advice);
            }
        }
        if let Some(current) = &preview.current {
            println!("current:");
            println!("{}", current);
        }
        println!("proposed:");
        println!("{}", preview.proposed);
    }
}

pub fn format_compat_mode(mode: dotrepo_schema::CompatMode) -> &'static str {
    match mode {
        dotrepo_schema::CompatMode::Generate => "generate",
        dotrepo_schema::CompatMode::Skip => "skip",
    }
}
