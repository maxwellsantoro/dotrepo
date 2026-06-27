use crate::util::{identity_from_index_claim_path, index_record_mirror_path};
use crate::{
    display_root, generate_check_repository, inspect_surface_states, load_manifest_from_root,
    record_status_name, repository_identity, validate_repository,
};
use anyhow::{anyhow, bail, Context, Result};
use dotrepo_schema::{Manifest, RecordMode};
use serde::Serialize;
use std::path::Path;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AdoptionStatusItem {
    pub name: String,
    pub ready: bool,
    pub detail: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AdoptionRepositoryIdentity {
    pub host: String,
    pub owner: String,
    pub repo: String,
    pub url: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AdoptionStatusReport {
    pub root: String,
    pub has_native_record: bool,
    pub validation_passed: bool,
    pub can_claim_from_native: bool,
    pub ci_workflow_present: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub record_status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub repository_identity: Option<AdoptionRepositoryIdentity>,
    pub managed_surface_check_passed: bool,
    pub managed_surface_checked: usize,
    pub managed_surface_stale: Vec<String>,
    pub surface_findings: usize,
    pub checks: Vec<AdoptionStatusItem>,
    pub next_steps: Vec<String>,
}

pub fn adoption_status_repository(root: &Path) -> AdoptionStatusReport {
    let validation = validate_repository(root);
    let manifest = load_manifest_from_root(root).ok();
    let has_native_record = manifest
        .as_ref()
        .is_some_and(|manifest| manifest.record.mode == RecordMode::Native);
    let record_status = has_native_record
        .then(|| {
            manifest
                .as_ref()
                .map(|manifest| record_status_name(&manifest.record.status).to_string())
        })
        .flatten();
    let repository_identity = native_repository_identity_from_manifest(manifest.as_ref()).ok();
    let can_claim_from_native = has_native_record && repository_identity.is_some();
    let ci_workflow_present = root.join(".github/workflows/dotrepo-check.yml").exists();
    let generate_check = generate_check_repository(root);
    let (managed_surface_check_passed, managed_surface_checked, managed_surface_stale) =
        match generate_check {
            Ok(report) => (report.stale.is_empty(), report.checked, report.stale),
            Err(_) => (false, 0, Vec::new()),
        };
    let surface_findings = inspect_surface_states(root)
        .map(|findings| findings.len())
        .unwrap_or(0);

    let checks = vec![
        AdoptionStatusItem {
            name: "native record".into(),
            ready: has_native_record,
            detail: if has_native_record {
                ".repo is present and record.mode is native".into()
            } else {
                "start with init, import, or adopt-overlay".into()
            },
        },
        AdoptionStatusItem {
            name: "validation".into(),
            ready: validation.valid,
            detail: if validation.valid {
                "manifest validates".into()
            } else {
                format!("{} validation diagnostic(s)", validation.diagnostics.len())
            },
        },
        AdoptionStatusItem {
            name: "claim identity".into(),
            ready: can_claim_from_native,
            detail: if let Some(identity) = &repository_identity {
                format!(
                    "repo.homepage resolves to {}/{}/{}",
                    identity.host, identity.owner, identity.repo
                )
            } else {
                "set repo.homepage to a host/owner/repo URL before claim-from-native".into()
            },
        },
        AdoptionStatusItem {
            name: "ci workflow".into(),
            ready: ci_workflow_present,
            detail: if ci_workflow_present {
                ".github/workflows/dotrepo-check.yml exists".into()
            } else {
                "run dotrepo ci init to scaffold the maintainer loop".into()
            },
        },
        AdoptionStatusItem {
            name: "managed surfaces".into(),
            ready: managed_surface_check_passed,
            detail: if managed_surface_check_passed {
                format!("{managed_surface_checked} generated surface(s) are in sync")
            } else if managed_surface_stale.is_empty() {
                "generate --check is not ready for this record".into()
            } else {
                format!(
                    "{} generated surface(s) are stale: {}",
                    managed_surface_stale.len(),
                    managed_surface_stale.join(", ")
                )
            },
        },
        AdoptionStatusItem {
            name: "surface inspection".into(),
            ready: surface_findings == 0,
            detail: if surface_findings == 0 {
                "managed surfaces are present and aligned".into()
            } else {
                format!(
                    "{surface_findings} managed surface issue(s) reported by inspect_surface_states"
                )
            },
        },
    ];

    let mut next_steps = Vec::new();
    if !has_native_record {
        next_steps
            .push("Run dotrepo init, import, or adopt-overlay to create a native .repo.".into());
    }
    if !validation.valid {
        next_steps.push("Run dotrepo validate and fix reported manifest diagnostics.".into());
    }
    if !ci_workflow_present {
        next_steps.push("Run dotrepo ci init to add the native-repo check workflow.".into());
    }
    if !managed_surface_check_passed {
        next_steps.push(
            "Run dotrepo doctor and dotrepo generate --check to inspect surface readiness.".into(),
        );
    }
    if has_native_record && repository_identity.is_none() {
        next_steps.push(
            "Set repo.homepage to the canonical host/owner/repo URL before claim-from-native."
                .into(),
        );
    }
    if next_steps.is_empty() {
        next_steps.push(
            "Native adoption loop is ready for validate, trust, CI, and claim-from-native.".into(),
        );
    }

    AdoptionStatusReport {
        root: display_root(root),
        has_native_record,
        validation_passed: validation.valid,
        can_claim_from_native,
        ci_workflow_present,
        record_status,
        repository_identity,
        managed_surface_check_passed,
        managed_surface_checked,
        managed_surface_stale,
        surface_findings,
        checks,
        next_steps,
    }
}

pub fn native_repository_identity(manifest: &Manifest) -> Result<AdoptionRepositoryIdentity> {
    native_repository_identity_from_manifest(Some(manifest))
}

pub fn canonical_mirror_path_for_claim_path(claim_path: &Path) -> Result<String> {
    let (host, owner, repo) = identity_from_index_claim_path(claim_path).ok_or_else(|| {
        anyhow!("claim path must be repos/<host>/<owner>/<repo>/claims/<claim-id>")
    })?;
    Ok(index_record_mirror_path(&host, &owner, &repo))
}

pub fn validate_claim_path_matches_native_identity(
    claim_path: &Path,
    native_identity: &AdoptionRepositoryIdentity,
) -> Result<()> {
    let (host, owner, repo) = identity_from_index_claim_path(claim_path).ok_or_else(|| {
        anyhow!("claim path must be repos/<host>/<owner>/<repo>/claims/<claim-id>")
    })?;
    if host != native_identity.host
        || owner != native_identity.owner
        || repo != native_identity.repo
    {
        bail!(
            "claim path identity {host}/{owner}/{repo} does not match native repo.homepage identity {}/{}/{}",
            native_identity.host,
            native_identity.owner,
            native_identity.repo
        );
    }
    Ok(())
}

pub fn render_dotrepo_ci_workflow(version: &str) -> String {
    let repository = env!("CARGO_PKG_REPOSITORY").trim_end_matches('/');
    let asset = format!("dotrepo-{version}-x86_64-unknown-linux-gnu.tar.gz");
    let release_base = format!("{repository}/releases/download/v{version}");
    format!(
        r#"name: dotrepo-check

on:
  pull_request:
  push:
    branches: [main, master]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      # Linux x86_64 release bundle only; use cargo install on other platforms.
      - uses: actions/checkout@v6
      - name: Install dotrepo
        env:
          DOTREPO_VERSION: "{version}"
          DOTREPO_ASSET: "{asset}"
          DOTREPO_RELEASE_BASE: "{release_base}"
        run: |
          set -euo pipefail
          mkdir -p "$HOME/.local/bin"
          curl -fsSLo "$RUNNER_TEMP/$DOTREPO_ASSET" "$DOTREPO_RELEASE_BASE/$DOTREPO_ASSET"
          curl -fsSLo "$RUNNER_TEMP/$DOTREPO_ASSET.sha256" "$DOTREPO_RELEASE_BASE/$DOTREPO_ASSET.sha256"
          (
            cd "$RUNNER_TEMP"
            sha256sum -c "$DOTREPO_ASSET.sha256"
          )
          tar -xzf "$RUNNER_TEMP/$DOTREPO_ASSET" -C "$RUNNER_TEMP"
          install "$RUNNER_TEMP/dotrepo-$DOTREPO_VERSION-x86_64-unknown-linux-gnu/bin/dotrepo" "$HOME/.local/bin/dotrepo"
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"
      - name: Run dotrepo checks
        run: |
          dotrepo --root . validate
          dotrepo --root . query repo.build --raw
          dotrepo --root . trust
          dotrepo --root . adoption-status
          dotrepo --root . doctor
          dotrepo --root . generate --check
"#
    )
}

fn native_repository_identity_from_manifest(
    manifest: Option<&Manifest>,
) -> Result<AdoptionRepositoryIdentity> {
    let manifest = manifest.context("native record requires a root .repo")?;
    if manifest.record.mode == RecordMode::Overlay {
        return Err(anyhow!("native identity requires a native record"));
    }
    let homepage = manifest
        .repo
        .homepage
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| anyhow!("native identity requires repo.homepage"))?;
    let (host, owner, repo) = repository_identity(homepage).ok_or_else(|| {
        anyhow!("native identity requires repo.homepage to be host/owner/repo URL")
    })?;
    Ok(AdoptionRepositoryIdentity {
        host,
        owner,
        repo,
        url: homepage.to_string(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use dotrepo_schema::RecordStatus;
    use std::fs;
    use std::path::PathBuf;

    #[test]
    fn record_status_uses_lowercase_contract() {
        let root =
            std::env::temp_dir().join(format!("dotrepo-adoption-status-{}", std::process::id()));
        fs::create_dir_all(&root).expect("temp dir created");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "widget"
description = "Widget toolkit."
homepage = "https://github.com/acme/widget"
"#,
        )
        .expect("manifest written");

        let report = adoption_status_repository(&root);
        assert_eq!(report.record_status.as_deref(), Some("canonical"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn record_status_omitted_for_overlay_only_roots() {
        let root =
            std::env::temp_dir().join(format!("dotrepo-adoption-overlay-{}", std::process::id()));
        fs::create_dir_all(&root).expect("temp dir created");

        let report = adoption_status_repository(&root);
        assert!(!report.has_native_record);
        assert!(report.record_status.is_none());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn repository_identity_parses_homepage_urls_consistently() {
        assert_eq!(
            repository_identity("https://github.com/acme/widget/tree/main"),
            Some(("github.com".into(), "acme".into(), "widget".into()))
        );
        assert_eq!(
            repository_identity("https://github.com/acme/widget.git?tab=readme"),
            Some(("github.com".into(), "acme".into(), "widget".into()))
        );
        assert!(repository_identity("git+https://github.com/acme/widget").is_none());
    }

    #[test]
    fn canonical_mirror_path_derives_from_claim_path() {
        let claim_path = PathBuf::from("repos/github.com/acme/widget/claims/claim-01");
        assert_eq!(
            canonical_mirror_path_for_claim_path(&claim_path).expect("mirror path"),
            "repos/github.com/acme/widget/record.toml"
        );
    }

    #[test]
    fn validate_claim_path_rejects_identity_mismatch() {
        let claim_path = PathBuf::from("repos/github.com/other/widget/claims/claim-01");
        let native_identity = AdoptionRepositoryIdentity {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            url: "https://github.com/acme/widget".into(),
        };
        assert!(
            validate_claim_path_matches_native_identity(&claim_path, &native_identity).is_err()
        );
    }

    #[test]
    fn adoption_status_surfaces_surface_inspection_check() {
        let root =
            std::env::temp_dir().join(format!("dotrepo-adoption-surfaces-{}", std::process::id()));
        fs::create_dir_all(&root).expect("temp dir created");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "widget"
description = "Widget toolkit."
homepage = "https://github.com/acme/widget"
"#,
        )
        .expect("manifest written");

        let report = adoption_status_repository(&root);
        assert!(report
            .checks
            .iter()
            .any(|check| check.name == "surface inspection"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn record_status_name_matches_schema_contract() {
        assert_eq!(record_status_name(&RecordStatus::Canonical), "canonical");
        assert_eq!(record_status_name(&RecordStatus::Draft), "draft");
    }
}
