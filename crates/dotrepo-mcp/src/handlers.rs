//! Tool handler bodies for each `dotrepo.*` MCP tool.
//!
//! Each handler takes the raw `arguments` `Value` from a `tools/call`
//! request and returns a `(summary, structured)` pair on success. Argument
//! parsing helpers and the shared root-resolution policy also live here.
//! JSON-RPC dispatch and MCP tool-result wrapping live in [`crate::dispatch`];
//! tool schema declarations live in [`crate::tools`].

use crate::lookup::{
    allow_custom_lookup_base_url, build_remote_lookup_client, fetch_remote_json,
    normalize_public_base_url, remote_public_root, remote_query_url, remote_repository_url,
    resolve_lookup_target, ALLOWED_LOOKUP_BASE_URLS, DEFAULT_PUBLIC_BASE_URL,
};
use anyhow::{anyhow, bail, Result};
use dotrepo_core::{
    adoption_status_repository, current_timestamp_rfc3339, display_path, generate_check_repository,
    import_preview_repository, import_repository_with_options, inspect_claim_directory,
    query_repository, record_summary, resolve_claim_directory, resolve_workspace_repository_root,
    trust_repository, validate_repository, write_import_outputs, ImportMode, ImportOptions,
};
use reqwest::Url;
use serde_json::{json, to_value, Value};
use std::path::{Path, PathBuf};

pub(crate) fn tool_validate(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let report = validate_repository(&root);
    let summary = if report.valid {
        "manifest valid"
    } else {
        "manifest invalid"
    };
    Ok((summary.into(), to_value(report)?))
}

pub(crate) fn tool_query(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let path = required_string(&arguments, "path")?;
    let report = query_repository(&root, path)?;
    Ok((format!("queried {}", path), to_value(report)?))
}

pub(crate) fn tool_trust(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let report = trust_repository(&root)?;
    Ok(("trust metadata loaded".into(), to_value(report)?))
}

pub(crate) fn tool_adoption_status(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let report = adoption_status_repository(&root);
    let summary = if report.next_steps.len() == 1
        && report
            .next_steps
            .first()
            .is_some_and(|step| step.contains("ready"))
    {
        "native adoption loop ready"
    } else {
        "native adoption loop needs attention"
    };
    Ok((summary.into(), to_value(report)?))
}

pub(crate) fn tool_lookup(arguments: Value) -> Result<(String, Value)> {
    let target = resolve_lookup_target(&arguments)?;
    let base_url = optional_string(&arguments, "baseUrl")
        .unwrap_or_else(|| DEFAULT_PUBLIC_BASE_URL.to_string());
    let base_url = normalize_public_base_url(&base_url)?;
    let client = build_remote_lookup_client(&base_url)?;

    let snapshot_url = format!("{}/v0/meta.json", remote_public_root(&base_url));
    let snapshot = fetch_remote_json(&client, &snapshot_url)?;
    let snapshot_root = snapshot
        .pointer("/paths/root")
        .and_then(Value::as_str)
        .filter(|path| path.starts_with('/') && !path.contains(".."));
    let pointer_url = |path: &str| -> Option<String> {
        Url::parse(&base_url)
            .ok()?
            .join(path)
            .ok()
            .map(|url| url.to_string())
    };
    let summary_url = match snapshot_root {
        Some(root) => pointer_url(&format!(
            "{}/repos/{}/{}/{}/index.json",
            root.trim_end_matches('/'),
            target.host,
            target.owner,
            target.repo
        ))
        .ok_or_else(|| anyhow!("remote snapshot root is not a valid URL path"))?,
        None => remote_repository_url(
            &base_url,
            &target.host,
            &target.owner,
            &target.repo,
            "index.json",
        ),
    };
    let trust_url = match snapshot_root {
        Some(root) => pointer_url(&format!(
            "{}/repos/{}/{}/{}/trust.json",
            root.trim_end_matches('/'),
            target.host,
            target.owner,
            target.repo
        ))
        .ok_or_else(|| anyhow!("remote snapshot root is not a valid URL path"))?,
        None => remote_repository_url(
            &base_url,
            &target.host,
            &target.owner,
            &target.repo,
            "trust.json",
        ),
    };
    let inventory_url = snapshot
        .pointer("/paths/inventory")
        .and_then(Value::as_str)
        .filter(|path| path.starts_with('/') && !path.contains(".."))
        .and_then(pointer_url)
        .unwrap_or_else(|| format!("{}/v0/repos/index.json", remote_public_root(&base_url)));

    let summary = fetch_remote_json(&client, &summary_url)?;
    let trust = fetch_remote_json(&client, &trust_url)?;
    let query_template = summary
        .get("links")
        .and_then(|links| links.get("queryTemplate"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| anyhow!("remote lookup summary is missing links.queryTemplate"))?;

    let query = if let Some(path) = target.path.as_deref() {
        let query_url =
            remote_query_url(&base_url, &target.host, &target.owner, &target.repo, path)?;
        Some(fetch_remote_json(&client, query_url.as_str())?)
    } else {
        None
    };

    let custom_base_url = allow_custom_lookup_base_url()
        && !ALLOWED_LOOKUP_BASE_URLS
            .iter()
            .any(|allowed| base_url.eq_ignore_ascii_case(allowed));

    let structured = json!({
        "baseUrl": remote_public_root(&base_url),
        "customBaseUrl": custom_base_url,
        "identity": {
            "host": target.host,
            "owner": target.owner,
            "repo": target.repo,
        },
        "lookup": {
            "source": target.source,
            "repositoryUrl": target.repository_url,
            "requestedPath": target.path,
        },
        "links": {
            "snapshot": snapshot_url,
            "inventory": inventory_url,
            "summary": summary_url,
            "trust": trust_url,
            "queryTemplate": query_template,
        },
        "snapshot": snapshot,
        "summary": summary,
        "trust": trust,
        "query": query,
    });
    Ok((
        format!(
            "resolved hosted lookup for {}/{}/{}",
            target.host, target.owner, target.repo
        ),
        structured,
    ))
}

pub(crate) fn tool_claim_inspect(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let claim_path = required_string(&arguments, "claimPath")?;
    let claim_dir = resolve_claim_directory(&root, claim_path)?;
    let report = inspect_claim_directory(&root, &claim_dir)?;
    Ok(("claim history loaded".into(), to_value(report)?))
}

pub(crate) fn tool_generate_check(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let report = generate_check_repository(&root)?;
    Ok((
        format!(
            "checked {} generated outputs; {} stale",
            report.checked,
            report.stale.len()
        ),
        to_value(report)?,
    ))
}

pub(crate) fn tool_import_preview(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let mode = import_mode(&arguments)?;
    let source = optional_string(&arguments, "source");
    let report = import_preview_repository(&root, mode, source.as_deref())?;
    Ok(("import preview ready".into(), to_value(report)?))
}

pub(crate) fn tool_import_write(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments)?;
    let mode = import_mode(&arguments)?;
    let source = optional_string(&arguments, "source");
    let force = arguments
        .get("force")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let plan = import_repository_with_options(
        &root,
        mode,
        source.as_deref(),
        &ImportOptions {
            generated_at: Some(current_timestamp_rfc3339()?),
            github: None,
        },
    )?;
    let written_paths = write_import_plan(&root, &plan, force)?;

    let structured = json!({
        "root": root.display().to_string(),
        "mode": import_mode_name(mode),
        "writtenPaths": written_paths,
        "importedSources": plan.imported_sources,
        "inferredFields": plan.inferred_fields,
        "record": record_summary(&plan.manifest),
    });
    Ok(("imported repository metadata".into(), structured))
}

pub(crate) fn write_import_plan(
    root: &Path,
    plan: &dotrepo_core::ImportPlan,
    force: bool,
) -> Result<Vec<String>> {
    let mut outputs = vec![(plan.manifest_path.clone(), plan.manifest_text.clone())];
    if let (Some(path), Some(contents)) = (&plan.evidence_path, &plan.evidence_text) {
        outputs.push((path.clone(), contents.clone()));
    }

    let written_paths = outputs
        .iter()
        .map(|(path, _)| display_path(root, path))
        .collect::<Result<Vec<_>, _>>()?;
    write_import_outputs(outputs, force, "force=true")?;

    Ok(written_paths)
}

fn env_flag_enabled(name: &str) -> bool {
    matches!(
        std::env::var(name).ok().as_deref().map(str::trim),
        Some("1") | Some("true") | Some("TRUE") | Some("yes") | Some("YES")
    )
}

fn allow_absolute_repository_root() -> bool {
    env_flag_enabled("DOTREPO_MCP_ALLOW_ABSOLUTE_ROOT")
}

pub(crate) fn resolve_root(arguments: &Value) -> Result<PathBuf> {
    let raw = optional_string(arguments, "root").unwrap_or_else(|| ".".into());
    resolve_workspace_repository_root(&raw, allow_absolute_repository_root())
}

pub(crate) fn required_string<'a>(arguments: &'a Value, field: &str) -> Result<&'a str> {
    arguments
        .get(field)
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| anyhow!("missing required string argument `{}`", field))
}

pub(crate) fn optional_string(arguments: &Value, field: &str) -> Option<String> {
    arguments
        .get(field)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

fn import_mode(arguments: &Value) -> Result<ImportMode> {
    match optional_string(arguments, "mode")
        .as_deref()
        .unwrap_or("native")
    {
        "native" => Ok(ImportMode::Native),
        "overlay" => Ok(ImportMode::Overlay),
        other => bail!("unsupported import mode: {}", other),
    }
}

fn import_mode_name(mode: ImportMode) -> &'static str {
    match mode {
        ImportMode::Native => "native",
        ImportMode::Overlay => "overlay",
    }
}
