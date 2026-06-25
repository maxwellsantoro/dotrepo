use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{CompatMode, Manifest, RecordMode};

use crate::load_manifest_document;
use crate::render::{
    ensure_trailing_newline, generated_banner, render_contributing, render_contributing_body,
    render_pull_request_template, render_security_body, CommentStyle,
};
use crate::util::{display_path, manifest_path, source_digest};
use crate::{
    DoctorFinding, DoctorOwnershipHonesty, DoctorRecommendedMode, DoctorRendererCoverage,
    DoctorSurface, LoadedManifest, ManagedFileState, SurfacePreview,
};

use super::readme::{render_readme, render_readme_body};
use super::{
    inspect_managed_surface, is_dotrepo_generated, managed_region_id, merge_managed_region,
    render_managed_markdown, ManagedSurface, ManagedSurfaceStatus,
};

pub(crate) fn ensure_native_managed_surface_record(
    manifest: &Manifest,
    action: &str,
) -> Result<()> {
    if manifest.record.mode == RecordMode::Overlay {
        bail!(
            "{} is only supported for native records; found record.mode = \"overlay\"",
            action
        );
    }

    Ok(())
}

pub(crate) fn all_doctor_surfaces() -> &'static [DoctorSurface] {
    &[
        DoctorSurface::Readme,
        DoctorSurface::Security,
        DoctorSurface::Contributing,
        DoctorSurface::Codeowners,
        DoctorSurface::PullRequestTemplate,
    ]
}

pub(crate) fn load_doctor_manifest(root: &Path) -> Result<Option<LoadedManifest>> {
    let path = manifest_path(root);
    if !path.exists() {
        return Ok(None);
    }
    load_manifest_document(root).map(Some)
}

pub(crate) fn build_managed_surface_doctor_finding(
    root: &Path,
    surface: ManagedSurface,
    status: ManagedSurfaceStatus,
    loaded_manifest: Option<&LoadedManifest>,
) -> Result<DoctorFinding> {
    let doctor_surface = doctor_surface_for_managed(surface);
    let mut finding = base_doctor_finding(
        relative_or_absolute(root, &status.path),
        doctor_surface,
        status.state,
        status
            .message
            .unwrap_or_else(|| default_state_message(status.state)),
    );

    if let Some(loaded_manifest) = loaded_manifest {
        apply_doctor_surface_manifest_metadata(
            root,
            &mut finding,
            loaded_manifest,
            status.current.as_deref(),
        )?;
    }

    Ok(finding)
}

pub(crate) fn build_unsupported_surface_doctor_finding(
    relative: &str,
    state: ManagedFileState,
    message: String,
    loaded_manifest: Option<&LoadedManifest>,
) -> DoctorFinding {
    let mut finding = base_doctor_finding(
        PathBuf::from(relative),
        doctor_surface_for_unsupported_path(relative),
        state,
        message,
    );

    if let Some(loaded_manifest) = loaded_manifest {
        apply_all_or_nothing_surface_manifest_metadata(&mut finding, &loaded_manifest.manifest);
    }

    finding
}

pub(crate) fn ensure_surface_adoption_is_enabled(
    surface: DoctorSurface,
    manifest: &Manifest,
) -> Result<()> {
    match surface {
        DoctorSurface::Readme => Ok(()),
        DoctorSurface::Security | DoctorSurface::Contributing => {
            if declared_mode_for_surface(manifest, surface) == Some(CompatMode::Generate) {
                Ok(())
            } else {
                bail!(
                    "{} adoption requires compat.github.{} = \"generate\" first",
                    doctor_surface_cli_name(surface),
                    doctor_surface_cli_name(surface)
                )
            }
        }
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => bail!(
            "{} does not support managed-region adoption",
            doctor_surface_cli_name(surface)
        ),
    }
}

pub(crate) fn preview_surface(
    root: &Path,
    loaded_manifest: &LoadedManifest,
    surface: DoctorSurface,
) -> Result<SurfacePreview> {
    let manifest = &loaded_manifest.manifest;
    match surface {
        DoctorSurface::Readme | DoctorSurface::Security | DoctorSurface::Contributing => {
            let managed_surface = managed_surface_for_doctor(surface);
            let status = inspect_managed_surface(root, managed_surface)?;
            let finding = build_managed_surface_doctor_finding(
                root,
                managed_surface,
                status.clone(),
                Some(loaded_manifest),
            )?;
            let proposed = expected_preview_output_for_managed_surface(
                root,
                surface,
                manifest,
                &loaded_manifest.raw,
                &status,
            )?;
            Ok(SurfacePreview {
                finding,
                current: status.current,
                proposed,
                full_replacement: matches!(
                    status.state,
                    ManagedFileState::Unmanaged
                        | ManagedFileState::MalformedManaged
                        | ManagedFileState::Unsupported
                ),
                preserves_unmanaged_content: status.state == ManagedFileState::PartiallyManaged,
            })
        }
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {
            let status = inspect_all_or_nothing_surface(root, surface)?;
            let mut finding = base_doctor_finding(
                relative_or_absolute(root, &status.path),
                surface,
                status.state,
                status
                    .message
                    .clone()
                    .unwrap_or_else(|| default_state_message(status.state)),
            );
            apply_all_or_nothing_surface_manifest_metadata(&mut finding, manifest);
            Ok(SurfacePreview {
                finding,
                current: status.current,
                proposed: expected_generated_surface_contents(
                    root,
                    surface,
                    manifest,
                    &loaded_manifest.raw,
                )?,
                full_replacement: status.state == ManagedFileState::Unsupported,
                preserves_unmanaged_content: false,
            })
        }
    }
}

pub(crate) fn managed_surface_for_adoption(surface: DoctorSurface) -> Result<ManagedSurface> {
    match surface {
        DoctorSurface::Readme => Ok(ManagedSurface::Readme),
        DoctorSurface::Security => Ok(ManagedSurface::Security),
        DoctorSurface::Contributing => Ok(ManagedSurface::Contributing),
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => bail!(
            "partial management is not supported for `{}`; `manage --adopt` is available only for readme, security, and contributing",
            doctor_surface_cli_name(surface)
        ),
    }
}

pub(crate) fn adopt_unmanaged_surface(
    surface: ManagedSurface,
    current: &str,
    body: &str,
) -> String {
    let mut out = String::new();
    let trimmed_current = current.trim_end_matches('\n');
    if !trimmed_current.is_empty() {
        out.push_str(trimmed_current);
        out.push_str("\n\n");
    }
    out.push_str(&managed_region_block(surface, body));
    out
}

pub(crate) fn default_state_message(state: ManagedFileState) -> String {
    match state {
        ManagedFileState::Missing => "managed surface is missing".into(),
        ManagedFileState::FullyGenerated => "fully generated by dotrepo".into(),
        ManagedFileState::PartiallyManaged => {
            "managed regions are valid; unmanaged content outside the markers is preserved".into()
        }
        ManagedFileState::Unmanaged => {
            "file exists outside dotrepo management; unmanaged prose is preserved and does not fail generate --check by itself".into()
        }
        ManagedFileState::MalformedManaged => {
            "managed-region markers are malformed and must be fixed before sync can proceed".into()
        }
        ManagedFileState::Unsupported => {
            "file is in an unsupported managed-sync state for this surface".into()
        }
    }
}

fn base_doctor_finding(
    path: PathBuf,
    surface: DoctorSurface,
    state: ManagedFileState,
    message: String,
) -> DoctorFinding {
    DoctorFinding {
        path,
        surface,
        state,
        message,
        declared_mode: None,
        supports_managed_regions: surface_supports_managed_regions(surface),
        supports_full_generation: surface_supports_full_generation(surface),
        ownership_honesty: None,
        recommended_mode: None,
        would_drop_unmanaged_content: None,
        renderer_coverage: Some(surface_renderer_coverage(surface)),
        advice: Vec::new(),
    }
}

fn apply_doctor_surface_manifest_metadata(
    root: &Path,
    finding: &mut DoctorFinding,
    loaded_manifest: &LoadedManifest,
    current: Option<&str>,
) -> Result<()> {
    let manifest = &loaded_manifest.manifest;
    finding.declared_mode = declared_mode_for_surface(manifest, finding.surface);

    match finding.surface {
        DoctorSurface::Readme => {
            if finding.state == ManagedFileState::PartiallyManaged {
                finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                finding.recommended_mode = Some(DoctorRecommendedMode::PartiallyManaged);
                finding.would_drop_unmanaged_content = Some(false);
            } else if finding.state == ManagedFileState::FullyGenerated {
                finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                finding.recommended_mode = Some(DoctorRecommendedMode::Generate);
                finding.would_drop_unmanaged_content = Some(false);
            }
        }
        DoctorSurface::Security | DoctorSurface::Contributing => {
            if finding.declared_mode == Some(CompatMode::Generate) {
                match finding.state {
                    ManagedFileState::FullyGenerated => {
                        finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                        finding.recommended_mode = Some(DoctorRecommendedMode::Generate);
                        finding.would_drop_unmanaged_content = Some(false);
                    }
                    ManagedFileState::PartiallyManaged => {
                        finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                        finding.recommended_mode = Some(DoctorRecommendedMode::PartiallyManaged);
                        finding.would_drop_unmanaged_content = Some(false);
                    }
                    ManagedFileState::Unmanaged => {
                        let expected = expected_generated_surface_contents(
                            root,
                            finding.surface,
                            manifest,
                            &loaded_manifest.raw,
                        )?;
                        if current != Some(expected.as_str()) {
                            finding.ownership_honesty =
                                Some(DoctorOwnershipHonesty::LossyFullGeneration);
                            finding.recommended_mode =
                                Some(DoctorRecommendedMode::PartiallyManaged);
                            finding.would_drop_unmanaged_content = Some(true);
                            finding.message = format!(
                                "{} is declared as fully generated, but the current renderer can only reproduce a minimal dotrepo-owned block from this manifest. Regenerating would replace repository-specific prose. Prefer `partially_managed` or `skip` unless the generated stub is the full file you want.",
                                finding.path.display()
                            );
                            finding.advice = vec![
                                format!(
                                    "Run `dotrepo preview --surface {}` before changing compat mode.",
                                    doctor_surface_cli_name(finding.surface)
                                ),
                                "Use managed regions to preserve repository-specific prose outside the dotrepo-owned block.".into(),
                            ];
                        }
                    }
                    ManagedFileState::Missing
                    | ManagedFileState::MalformedManaged
                    | ManagedFileState::Unsupported => {}
                }
            }
        }
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {}
    }

    Ok(())
}

fn apply_all_or_nothing_surface_manifest_metadata(
    finding: &mut DoctorFinding,
    manifest: &Manifest,
) {
    finding.declared_mode = declared_mode_for_surface(manifest, finding.surface);

    if finding.declared_mode != Some(CompatMode::Generate) {
        return;
    }

    match finding.state {
        ManagedFileState::Missing | ManagedFileState::FullyGenerated => {
            finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
            finding.recommended_mode = Some(DoctorRecommendedMode::Generate);
            finding.would_drop_unmanaged_content = Some(false);
        }
        ManagedFileState::Unsupported => {
            finding.ownership_honesty = Some(DoctorOwnershipHonesty::LossyFullGeneration);
            finding.recommended_mode = Some(DoctorRecommendedMode::Skip);
            finding.would_drop_unmanaged_content = Some(true);
            finding.message = format!(
                "{} is declared as fully generated, but partial management is not supported for this surface. dotrepo can only fully replace it or leave it unmanaged. Prefer `skip` unless the generated template is the entire file you want.",
                finding.path.display()
            );
            finding.advice = vec![
                format!(
                    "Run `dotrepo preview --surface {}` before enabling full generation.",
                    doctor_surface_cli_name(finding.surface)
                ),
                "Keep this surface unmanaged if the checked-in file contains richer policy or workflow content than the current template can express.".into(),
            ];
        }
        ManagedFileState::PartiallyManaged
        | ManagedFileState::Unmanaged
        | ManagedFileState::MalformedManaged => {}
    }
}

fn doctor_surface_for_managed(surface: ManagedSurface) -> DoctorSurface {
    match surface {
        ManagedSurface::Readme => DoctorSurface::Readme,
        ManagedSurface::Security => DoctorSurface::Security,
        ManagedSurface::Contributing => DoctorSurface::Contributing,
    }
}

fn managed_surface_for_doctor(surface: DoctorSurface) -> ManagedSurface {
    match surface {
        DoctorSurface::Readme => ManagedSurface::Readme,
        DoctorSurface::Security => ManagedSurface::Security,
        DoctorSurface::Contributing => ManagedSurface::Contributing,
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {
            panic!("no managed-surface equivalent for {:?}", surface)
        }
    }
}

fn doctor_surface_for_unsupported_path(relative: &str) -> DoctorSurface {
    if relative.to_ascii_lowercase().contains("codeowners") {
        DoctorSurface::Codeowners
    } else {
        DoctorSurface::PullRequestTemplate
    }
}

fn doctor_surface_cli_name(surface: DoctorSurface) -> &'static str {
    match surface {
        DoctorSurface::Readme => "readme",
        DoctorSurface::Security => "security",
        DoctorSurface::Contributing => "contributing",
        DoctorSurface::Codeowners => "codeowners",
        DoctorSurface::PullRequestTemplate => "pull_request_template",
    }
}

fn surface_supports_managed_regions(surface: DoctorSurface) -> bool {
    matches!(
        surface,
        DoctorSurface::Readme | DoctorSurface::Security | DoctorSurface::Contributing
    )
}

fn surface_supports_full_generation(_surface: DoctorSurface) -> bool {
    true
}

fn surface_renderer_coverage(surface: DoctorSurface) -> DoctorRendererCoverage {
    match surface {
        DoctorSurface::Readme | DoctorSurface::Codeowners => DoctorRendererCoverage::Structured,
        DoctorSurface::Security
        | DoctorSurface::Contributing
        | DoctorSurface::PullRequestTemplate => DoctorRendererCoverage::StubOnly,
    }
}

fn declared_mode_for_surface(manifest: &Manifest, surface: DoctorSurface) -> Option<CompatMode> {
    let github = manifest
        .compat
        .as_ref()
        .and_then(|compat| compat.github.as_ref());
    match surface {
        DoctorSurface::Readme => None,
        DoctorSurface::Security => github.and_then(|github| github.security.clone()),
        DoctorSurface::Contributing => github.and_then(|github| github.contributing.clone()),
        DoctorSurface::Codeowners => github.and_then(|github| github.codeowners.clone()),
        DoctorSurface::PullRequestTemplate => {
            github.and_then(|github| github.pull_request_template.clone())
        }
    }
}

fn expected_generated_surface_contents(
    root: &Path,
    surface: DoctorSurface,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<String> {
    let digest = source_digest(source_bytes);
    match surface {
        DoctorSurface::Readme => render_readme(root, manifest, source_bytes),
        DoctorSurface::Security => Ok(render_managed_markdown(
            generated_banner(CommentStyle::Html, manifest, &digest),
            &render_security_body(manifest),
        )),
        DoctorSurface::Contributing => Ok(render_contributing(manifest, &digest)),
        DoctorSurface::Codeowners => {
            let owners = manifest
                .owners
                .as_ref()
                .map(|owners| owners.maintainers.join(" "))
                .unwrap_or_else(|| "@maintainers".into());
            Ok(format!(
                "{}\n* {}\n",
                generated_banner(CommentStyle::Hash, manifest, &digest),
                owners
            ))
        }
        DoctorSurface::PullRequestTemplate => Ok(render_pull_request_template(manifest, &digest)),
    }
}

fn expected_preview_output_for_managed_surface(
    root: &Path,
    surface: DoctorSurface,
    manifest: &Manifest,
    source_bytes: &[u8],
    status: &ManagedSurfaceStatus,
) -> Result<String> {
    let full_expected = expected_generated_surface_contents(root, surface, manifest, source_bytes)?;
    match status.state {
        ManagedFileState::PartiallyManaged => {
            let body = match surface {
                DoctorSurface::Readme => render_readme_body(root, manifest)?,
                DoctorSurface::Security => render_security_body(manifest),
                DoctorSurface::Contributing => render_contributing_body(manifest),
                DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {
                    bail!("surface does not support managed-region preview bodies")
                }
            };
            let current = status.current.as_deref().ok_or_else(|| {
                anyhow!(
                    "partially managed file {} is missing current contents",
                    status.path.display()
                )
            })?;
            merge_managed_region(
                &status.path,
                managed_surface_for_doctor(surface),
                current,
                &body,
            )
        }
        _ => Ok(full_expected),
    }
}

fn inspect_all_or_nothing_surface(
    root: &Path,
    surface: DoctorSurface,
) -> Result<ManagedSurfaceStatus> {
    let candidate_paths = all_or_nothing_surface_paths(surface)
        .iter()
        .map(|relative| root.join(relative))
        .filter(|path| path.exists())
        .collect::<Vec<_>>();

    if candidate_paths.len() > 1 {
        let paths = candidate_paths
            .iter()
            .map(|path| display_path(root, path))
            .collect::<Vec<_>>()
            .join(", ");
        return Ok(ManagedSurfaceStatus {
            path: candidate_paths[0].clone(),
            state: ManagedFileState::Unsupported,
            current: None,
            message: Some(format!(
                "multiple candidate files exist for this surface ({paths}); keep one authoritative path before enabling sync"
            )),
        });
    }

    let Some(path) = candidate_paths.first() else {
        return Ok(ManagedSurfaceStatus {
            path: root.join(all_or_nothing_surface_paths(surface)[0]),
            state: ManagedFileState::Missing,
            current: None,
            message: Some("managed surface is missing".into()),
        });
    };

    let current = fs::read_to_string(path)
        .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
    if is_dotrepo_generated(&current) {
        return Ok(ManagedSurfaceStatus {
            path: path.clone(),
            state: ManagedFileState::FullyGenerated,
            current: Some(current),
            message: Some("fully generated by dotrepo".into()),
        });
    }

    Ok(ManagedSurfaceStatus {
        path: path.clone(),
        state: ManagedFileState::Unsupported,
        current: Some(current),
        message: Some(
            "conventional surface exists outside the managed-region contract for this file; keep it unmanaged or convert it to a fully generated dotrepo surface".into(),
        ),
    })
}

fn all_or_nothing_surface_paths(surface: DoctorSurface) -> &'static [&'static str] {
    match surface {
        DoctorSurface::Codeowners => &[".github/CODEOWNERS", "CODEOWNERS"],
        DoctorSurface::PullRequestTemplate => &[
            ".github/pull_request_template.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            "pull_request_template.md",
            "PULL_REQUEST_TEMPLATE.md",
        ],
        DoctorSurface::Readme | DoctorSurface::Security | DoctorSurface::Contributing => {
            panic!(
                "surface does not use all-or-nothing path resolution: {:?}",
                surface
            )
        }
    }
}

fn managed_region_block(surface: ManagedSurface, body: &str) -> String {
    format!(
        "<!-- dotrepo:begin id={} -->\n{}<!-- dotrepo:end id={} -->\n",
        managed_region_id(surface),
        ensure_trailing_newline(body),
        managed_region_id(surface)
    )
}

fn relative_or_absolute(root: &Path, path: &Path) -> PathBuf {
    path.strip_prefix(root)
        .map(PathBuf::from)
        .unwrap_or_else(|_| path.to_path_buf())
}
