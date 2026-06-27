use crate::{
    display_root, generate_check_repository, inspect_surface_states, load_manifest_from_root,
    validate_repository,
};
use anyhow::{anyhow, Context, Result};
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
    let record_status = manifest
        .as_ref()
        .map(|manifest| format!("{:?}", manifest.record.status));
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
                    "{} generated surface(s) are stale",
                    managed_surface_stale.len()
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
    let (host, owner, repo) = repository_identity_from_url(homepage).ok_or_else(|| {
        anyhow!("native identity requires repo.homepage to be host/owner/repo URL")
    })?;
    Ok(AdoptionRepositoryIdentity {
        host,
        owner,
        repo,
        url: homepage.to_string(),
    })
}

fn repository_identity_from_url(url: &str) -> Option<(String, String, String)> {
    let (_scheme, rest) = url.split_once("://")?;
    let without_query = rest
        .split(['?', '#'])
        .next()
        .unwrap_or(rest)
        .trim_end_matches('/');
    let mut parts = without_query.split('/').filter(|part| !part.is_empty());
    let host = parts.next()?.to_string();
    let owner = parts.next()?.to_string();
    let repo = parts.next()?.trim_end_matches(".git").to_string();
    if parts.next().is_some() || host.is_empty() || owner.is_empty() || repo.is_empty() {
        return None;
    }
    Some((host, owner, repo))
}
