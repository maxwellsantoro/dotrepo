use anyhow::{anyhow, bail, Result};
use dotrepo_core::{
    current_timestamp_rfc3339, display_path, generate_check_repository, import_preview_repository,
    import_repository_with_options, inspect_claim_directory, query_repository, record_summary,
    trust_repository, validate_repository, ImportMode, ImportOptions,
};
use dotrepo_transport::{
    read_jsonrpc_message as read_message, write_jsonrpc_message as write_message,
};
use reqwest::blocking::Client;
use reqwest::Url;
use serde::Deserialize;
use serde_json::{json, to_value, Value};
use std::fs;
use std::fs::{File, OpenOptions};
use std::io::{self, BufReader};
use std::io::{ErrorKind, Write};
use std::path::{Path, PathBuf};
use std::time::Duration;

const JSONRPC_VERSION: &str = "2.0";
const SUPPORTED_PROTOCOL_VERSIONS: &[&str] = &["2025-11-25", "2025-06-18", "2024-11-05"];
const SERVER_NAME: &str = "dotrepo-mcp";
const DEFAULT_PUBLIC_BASE_URL: &str = "https://dotrepo.org";
const REMOTE_LOOKUP_TIMEOUT: Duration = Duration::from_secs(15);

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut reader = BufReader::new(stdin.lock());
    let mut writer = stdout.lock();
    let mut state = ServerState::default();

    while let Some(message) = read_message(&mut reader)? {
        let request = match serde_json::from_slice::<JsonRpcRequest>(&message) {
            Ok(request) => request,
            Err(err) => {
                write_message(
                    &mut writer,
                    &error_response(
                        Value::Null,
                        -32700,
                        format!("failed to parse request: {}", err),
                        None,
                    ),
                )?;
                continue;
            }
        };

        if let Some(response) = handle_request(&mut state, request) {
            write_message(&mut writer, &response)?;
        }
    }

    Ok(())
}

#[derive(Debug, Default)]
struct ServerState {
    initialized: bool,
    protocol_version: Option<&'static str>,
}

#[derive(Debug, Deserialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    #[serde(default)]
    id: Option<Value>,
    method: String,
    #[serde(default)]
    params: Value,
}

fn handle_request(state: &mut ServerState, request: JsonRpcRequest) -> Option<Value> {
    if request.jsonrpc != JSONRPC_VERSION {
        return request.id.map(|id| {
            error_response(
                id,
                -32600,
                format!("unsupported jsonrpc version: {}", request.jsonrpc),
                None,
            )
        });
    }

    if request.id.is_none() {
        handle_notification(state, request.method, request.params);
        return None;
    }

    let id = request.id.expect("id checked above");

    let result = match dispatch_request(state, &request.method, request.params) {
        Ok(result) => response(id, result),
        Err(err) => error_response(id, -32603, err.to_string(), None),
    };

    Some(result)
}

fn handle_notification(state: &mut ServerState, method: String, _params: Value) {
    if method == "notifications/initialized" {
        state.initialized = true;
    }
}

fn dispatch_request(state: &mut ServerState, method: &str, params: Value) -> Result<Value> {
    match method {
        "initialize" => handle_initialize(state, params),
        "ping" => Ok(json!({})),
        "tools/list" => {
            ensure_initialized(state)?;
            Ok(json!({ "tools": tool_definitions() }))
        }
        "tools/call" => {
            ensure_initialized(state)?;
            handle_tool_call(params)
        }
        _ => bail!("method not found: {}", method),
    }
}

fn handle_initialize(state: &mut ServerState, params: Value) -> Result<Value> {
    let requested = params
        .get("protocolVersion")
        .and_then(Value::as_str)
        .unwrap_or(SUPPORTED_PROTOCOL_VERSIONS[0]);
    let negotiated = negotiate_protocol_version(requested);
    state.protocol_version = Some(negotiated);

    Ok(json!({
        "protocolVersion": negotiated,
        "capabilities": {
            "tools": {
                "listChanged": false
            }
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "title": "dotrepo MCP Server",
            "version": env!("CARGO_PKG_VERSION")
        },
        "instructions": "Use dotrepo.query for trust-aware field lookups, dotrepo.trust for record provenance, and dotrepo.import_preview before dotrepo.import_write."
    }))
}

fn handle_tool_call(params: Value) -> Result<Value> {
    let name = params
        .get("name")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow!("tools/call requires a tool name"))?;
    let arguments = params
        .get("arguments")
        .cloned()
        .unwrap_or_else(|| Value::Object(Default::default()));

    let result = match name {
        "dotrepo.validate" => tool_validate(arguments),
        "dotrepo.query" => tool_query(arguments),
        "dotrepo.trust" => tool_trust(arguments),
        "dotrepo.lookup" => tool_lookup(arguments),
        "dotrepo.claim_inspect" => tool_claim_inspect(arguments),
        "dotrepo.generate_check" => tool_generate_check(arguments),
        "dotrepo.import_preview" => tool_import_preview(arguments),
        "dotrepo.import_write" => tool_import_write(arguments),
        _ => bail!("unknown tool: {}", name),
    };

    match result {
        Ok((summary, structured)) => Ok(tool_success(summary, structured)),
        Err(err) => Ok(tool_failure(
            format!("tool `{}` failed", name),
            json!({ "error": err.to_string() }),
        )),
    }
}

fn tool_validate(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let report = validate_repository(&root);
    let summary = if report.valid {
        "manifest valid"
    } else {
        "manifest invalid"
    };
    Ok((summary.into(), to_value(report)?))
}

fn tool_query(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let path = required_string(&arguments, "path")?;
    let report = query_repository(&root, path)?;
    Ok((format!("queried {}", path), to_value(report)?))
}

fn tool_trust(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let report = trust_repository(&root)?;
    Ok(("trust metadata loaded".into(), to_value(report)?))
}

fn tool_lookup(arguments: Value) -> Result<(String, Value)> {
    let target = resolve_lookup_target(&arguments)?;
    let base_url = optional_string(&arguments, "baseUrl")
        .unwrap_or_else(|| DEFAULT_PUBLIC_BASE_URL.to_string());
    let base_url = normalize_public_base_url(&base_url)?;
    let client = build_remote_lookup_client()?;

    let summary_url = remote_repository_url(
        &base_url,
        &target.host,
        &target.owner,
        &target.repo,
        "index.json",
    );
    let trust_url = remote_repository_url(
        &base_url,
        &target.host,
        &target.owner,
        &target.repo,
        "trust.json",
    );
    let snapshot_url = format!("{}/v0/meta.json", remote_public_root(&base_url));
    let inventory_url = format!("{}/v0/repos/index.json", remote_public_root(&base_url));

    let summary = fetch_remote_json(&client, &summary_url)?;
    let trust = fetch_remote_json(&client, &trust_url)?;
    let snapshot = fetch_remote_json(&client, &snapshot_url)?;
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

    let structured = json!({
        "baseUrl": remote_public_root(&base_url),
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

fn tool_claim_inspect(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let claim_path = required_string(&arguments, "claimPath")?;
    let claim_dir = if Path::new(claim_path).is_absolute() {
        PathBuf::from(claim_path)
    } else {
        root.join(claim_path)
    };
    let report = inspect_claim_directory(&root, &claim_dir)?;
    Ok(("claim history loaded".into(), to_value(report)?))
}

fn tool_generate_check(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
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

fn tool_import_preview(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let mode = import_mode(&arguments)?;
    let source = optional_string(&arguments, "source");
    let report = import_preview_repository(&root, mode, source.as_deref())?;
    Ok(("import preview ready".into(), to_value(report)?))
}

fn tool_import_write(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
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

fn write_import_plan(
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
        .collect::<Vec<_>>();
    write_import_outputs(outputs, force)?;

    Ok(written_paths)
}

struct ReservedImportOutput {
    path: PathBuf,
    contents: String,
    file: File,
}

fn write_import_outputs(outputs: Vec<(PathBuf, String)>, force: bool) -> Result<()> {
    if force {
        for (path, contents) in outputs {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::write(path, contents)?;
        }
        return Ok(());
    }

    let mut reserved = Vec::new();
    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let file = match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(file) => file,
            Err(err) => {
                cleanup_reserved_import_outputs(reserved);
                return Err(match err.kind() {
                    ErrorKind::AlreadyExists => anyhow!(
                        "{} already exists; rerun with force=true to overwrite imported artifacts",
                        path.display()
                    ),
                    _ => err.into(),
                });
            }
        };

        reserved.push(ReservedImportOutput {
            path,
            contents,
            file,
        });
    }

    for idx in 0..reserved.len() {
        let write_result = {
            let reserved_output = &mut reserved[idx];
            reserved_output
                .file
                .write_all(reserved_output.contents.as_bytes())
                .and_then(|_| reserved_output.file.flush())
        };
        if let Err(err) = write_result {
            cleanup_reserved_import_outputs(reserved);
            return Err(err.into());
        }
    }

    Ok(())
}

fn cleanup_reserved_import_outputs(outputs: Vec<ReservedImportOutput>) {
    let paths = outputs
        .into_iter()
        .map(|reserved| reserved.path)
        .collect::<Vec<_>>();
    for path in paths {
        let _ = fs::remove_file(path);
    }
}

fn resolve_root(arguments: &Value) -> PathBuf {
    optional_string(arguments, "root")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

fn required_string<'a>(arguments: &'a Value, field: &str) -> Result<&'a str> {
    arguments
        .get(field)
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| anyhow!("missing required string argument `{}`", field))
}

fn optional_string(arguments: &Value, field: &str) -> Option<String> {
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

#[derive(Debug, Clone, Copy)]
enum LookupTargetSource {
    RepositoryUrl,
    Identity,
}

impl LookupTargetSource {
    fn as_str(self) -> &'static str {
        match self {
            LookupTargetSource::RepositoryUrl => "repository_url",
            LookupTargetSource::Identity => "identity",
        }
    }
}

#[derive(Debug, Clone)]
struct LookupTarget {
    host: String,
    owner: String,
    repo: String,
    repository_url: String,
    path: Option<String>,
    source: &'static str,
}

fn resolve_lookup_target(arguments: &Value) -> Result<LookupTarget> {
    let path = optional_string(arguments, "path");
    if let Some(repository_url) = optional_string(arguments, "repositoryUrl") {
        let (host, owner, repo) = parse_repository_url(&repository_url)?;
        return Ok(LookupTarget {
            host,
            owner,
            repo,
            repository_url,
            path,
            source: LookupTargetSource::RepositoryUrl.as_str(),
        });
    }

    let host = required_string(arguments, "host")?.to_string();
    let owner = required_string(arguments, "owner")?.to_string();
    let repo = required_string(arguments, "repo")?.to_string();
    validate_lookup_identity(&host, &owner, &repo)?;
    Ok(LookupTarget {
        repository_url: format!("https://{}/{}/{}", host, owner, repo),
        host,
        owner,
        repo,
        path,
        source: LookupTargetSource::Identity.as_str(),
    })
}

fn parse_repository_url(value: &str) -> Result<(String, String, String)> {
    let trimmed = value.trim();
    let with_scheme = if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        trimmed.to_string()
    } else {
        format!("https://{}", trimmed.trim_start_matches('/'))
    };
    let url = Url::parse(&with_scheme)
        .map_err(|err| anyhow!("invalid repositoryUrl `{}`: {}", value, err))?;
    let host = url
        .host_str()
        .ok_or_else(|| anyhow!("repositoryUrl is missing a host: {}", value))?
        .to_string();
    let segments = url
        .path_segments()
        .map(|segments| {
            segments
                .filter(|segment| !segment.is_empty())
                .map(str::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();

    let (identity_host, owner, repo): (String, String, String) =
        if segments.len() >= 5 && segments[0] == "v0" && segments[1] == "repos" {
            (
                segments[2].clone(),
                segments[3].clone(),
                trim_repo_suffix(&segments[4]),
            )
        } else if segments.len() >= 2 {
            (
                host.clone(),
                segments[0].clone(),
                trim_repo_suffix(&segments[1]),
            )
        } else {
            bail!(
                "repositoryUrl must include at least owner/repo path segments: {}",
                value
            );
        };
    validate_lookup_identity(&identity_host, &owner, &repo)?;
    Ok((identity_host, owner, repo))
}

fn trim_repo_suffix(value: &str) -> String {
    value.strip_suffix(".git").unwrap_or(value).to_string()
}

fn validate_lookup_identity(host: &str, owner: &str, repo: &str) -> Result<()> {
    for (field, value) in [("host", host), ("owner", owner), ("repo", repo)] {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            bail!("lookup {} must not be empty", field);
        }
        if trimmed.contains('/') {
            bail!("lookup {} must be a single path segment", field);
        }
    }
    Ok(())
}

fn normalize_public_base_url(value: &str) -> Result<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        bail!("baseUrl must not be empty");
    }
    let with_scheme = if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        trimmed.to_string()
    } else {
        format!("https://{}", trimmed.trim_start_matches('/'))
    };
    let url =
        Url::parse(&with_scheme).map_err(|err| anyhow!("invalid baseUrl `{}`: {}", value, err))?;
    match url.scheme() {
        "http" | "https" => {}
        other => bail!("unsupported baseUrl scheme: {}", other),
    }
    Ok(url.as_str().trim_end_matches('/').to_string())
}

fn remote_public_root(base_url: &str) -> String {
    base_url.trim_end_matches('/').to_string()
}

fn remote_repository_url(
    base_url: &str,
    host: &str,
    owner: &str,
    repo: &str,
    leaf: &str,
) -> String {
    format!(
        "{}/v0/repos/{}/{}/{}/{}",
        remote_public_root(base_url),
        host,
        owner,
        repo,
        leaf
    )
}

fn remote_query_url(
    base_url: &str,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
) -> Result<Url> {
    let mut url = Url::parse(&format!(
        "{}/v0/repos/{}/{}/{}/query",
        remote_public_root(base_url),
        host,
        owner,
        repo
    ))?;
    url.query_pairs_mut().append_pair("path", path);
    Ok(url)
}

fn build_remote_lookup_client() -> Result<Client> {
    Client::builder()
        .user_agent(format!("dotrepo-mcp/{}", env!("CARGO_PKG_VERSION")))
        .timeout(REMOTE_LOOKUP_TIMEOUT)
        .build()
        .map_err(Into::into)
}

fn fetch_remote_json(client: &Client, url: &str) -> Result<Value> {
    let response = client
        .get(url)
        .send()
        .map_err(|error| anyhow!("failed to GET {}: {}", url, error))?;
    let status = response.status();
    if !status.is_success() {
        let body = response.text().unwrap_or_default();
        bail!(
            "remote lookup request failed {}: HTTP {} {}",
            url,
            status.as_u16(),
            compact_error_body(&body)
        );
    }
    response
        .json::<Value>()
        .map_err(|error| anyhow!("failed to decode JSON from {}: {}", url, error))
}

fn compact_error_body(body: &str) -> String {
    let compact = body.split_whitespace().collect::<Vec<_>>().join(" ");
    if compact.is_empty() {
        "without response body".into()
    } else {
        compact
    }
}

fn ensure_initialized(state: &ServerState) -> Result<()> {
    if state.protocol_version.is_none() {
        bail!("server must receive initialize before calling tools");
    }
    if !state.initialized {
        bail!("server must receive notifications/initialized before calling tools");
    }
    Ok(())
}

fn negotiate_protocol_version(requested: &str) -> &'static str {
    SUPPORTED_PROTOCOL_VERSIONS
        .iter()
        .copied()
        .find(|version| *version == requested)
        .unwrap_or(SUPPORTED_PROTOCOL_VERSIONS[0])
}

fn tool_definitions() -> Vec<Value> {
    vec![
        json!({
            "name": "dotrepo.validate",
            "title": "Validate dotrepo record",
            "description": "Validate the manifest at the given repository root and return trust-aware diagnostics.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.query",
            "title": "Query manifest path",
            "description": "Query a dot-path such as repo.name or record.trust.provenance and return the value with record trust context.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." },
                    "path": { "type": "string", "description": "Dot-path to query." }
                },
                "required": ["path"],
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.trust",
            "title": "Read trust metadata",
            "description": "Return record status, mode, source, and trust metadata for the manifest at the given root.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.lookup",
            "title": "Lookup hosted public repository",
            "description": "Resolve a repository URL or identity against the hosted public surface and return summary, trust, and query entrypoints without cloning.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repositoryUrl": { "type": "string", "description": "Repository URL such as https://github.com/owner/repo or a hosted dotrepo repository URL." },
                    "host": { "type": "string", "description": "Repository host when resolving by identity." },
                    "owner": { "type": "string", "description": "Repository owner when resolving by identity." },
                    "repo": { "type": "string", "description": "Repository name when resolving by identity." },
                    "path": { "type": "string", "description": "Optional dot-path to resolve immediately through the hosted query route." },
                    "baseUrl": { "type": "string", "description": "Hosted public origin; defaults to https://dotrepo.org." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.claim_inspect",
            "title": "Inspect maintainer claim",
            "description": "Inspect one maintainer-claim directory and return current state, target context, derived handoff, and ordered event history.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Index root containing repos/<host>/<owner>/<repo>/claims/..." },
                    "claimPath": { "type": "string", "description": "Claim directory relative to root or an absolute path." }
                },
                "required": ["claimPath"],
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.generate_check",
            "title": "Preview generated outputs",
            "description": "Check dotrepo-managed outputs and report which generated files are stale without writing files.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.import_preview",
            "title": "Preview imported manifest",
            "description": "Preview a native or overlay import derived from README.md, CODEOWNERS, and SECURITY.md.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root to import from." },
                    "mode": { "type": "string", "enum": ["native", "overlay"], "description": "Import mode; defaults to native." },
                    "source": { "type": "string", "description": "Absolute repository URL required for overlay imports." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.import_write",
            "title": "Write imported manifest",
            "description": "Write a native .repo or overlay record.toml plus evidence.md using the same import pipeline as import_preview.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root to import from." },
                    "mode": { "type": "string", "enum": ["native", "overlay"], "description": "Import mode; defaults to native." },
                    "source": { "type": "string", "description": "Absolute repository URL required for overlay imports." },
                    "force": { "type": "boolean", "description": "Overwrite existing import artifacts when true." }
                },
                "additionalProperties": false
            }
        }),
    ]
}

fn tool_success(summary: String, structured: Value) -> Value {
    let text = format!(
        "{}\n\n{}",
        summary,
        serde_json::to_string_pretty(&structured).expect("structured content serializes")
    );
    json!({
        "content": [
            {
                "type": "text",
                "text": text
            }
        ],
        "structuredContent": structured,
        "isError": false
    })
}

fn tool_failure(summary: String, structured: Value) -> Value {
    let text = format!(
        "{}\n\n{}",
        summary,
        serde_json::to_string_pretty(&structured).expect("structured content serializes")
    );
    json!({
        "content": [
            {
                "type": "text",
                "text": text
            }
        ],
        "structuredContent": structured,
        "isError": true
    })
}

fn response(id: Value, result: Value) -> Value {
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "result": result
    })
}

fn error_response(id: Value, code: i64, message: String, data: Option<Value>) -> Value {
    let mut error = json!({
        "code": code,
        "message": message,
    });
    if let Some(data) = data {
        error["data"] = data;
    }
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "error": error
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn initialize_and_list_tools() {
        let (mut state, init_response) = initialized_state();
        assert_eq!(init_response["result"]["protocolVersion"], "2025-11-25");

        let tools_response = handle_request(&mut state, request(2, "tools/list", json!({})))
            .expect("tools/list responds");
        let tools = tools_response["result"]["tools"]
            .as_array()
            .expect("tool list");
        assert!(tools
            .iter()
            .any(|tool| tool["name"] == Value::String("dotrepo.query".into())));
        assert!(tools
            .iter()
            .any(|tool| tool["name"] == Value::String("dotrepo.lookup".into())));
        assert!(tools
            .iter()
            .any(|tool| tool["name"] == Value::String("dotrepo.import_preview".into())));
        assert!(tools
            .iter()
            .any(|tool| tool["name"] == Value::String("dotrepo.claim_inspect".into())));
    }

    #[test]
    fn query_tool_returns_trust_context() {
        let root = temp_dir("query");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");

        let response = call_tool(
            "dotrepo.query",
            json!({
                "root": root.display().to_string(),
                "path": "repo.name"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"]["value"],
            Value::String("orbit".into())
        );
        assert_eq!(
            response["result"]["structuredContent"]["selection"]["reason"],
            Value::String("only_matching_record".into())
        );
        assert_eq!(
            response["result"]["structuredContent"]["selection"]["record"]["record"]["status"],
            Value::String("canonical".into())
        );
        assert_eq!(
            response["result"]["structuredContent"]["conflicts"],
            Value::Array(Vec::new())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_preview_reports_inferred_overlay_fallbacks() {
        let root = temp_dir("import-preview");

        let response = call_tool(
            "dotrepo.import_preview",
            json!({
                "root": root.display().to_string(),
                "mode": "overlay",
                "source": "https://github.com/example/project"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"]["record"]["status"],
            Value::String("inferred".into())
        );
        assert!(response["result"]["structuredContent"]["inferredFields"]
            .as_array()
            .expect("inferred fields")
            .iter()
            .any(|field| field == "repo.name"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_tool_returns_structured_diagnostics() {
        let root = temp_dir("validate");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "broken"
description = "Missing source and trust"
"#,
        )
        .expect("manifest written");

        let response = call_tool(
            "dotrepo.validate",
            json!({
                "root": root.display().to_string()
            }),
        );
        let structured = &response["result"]["structuredContent"];
        assert_eq!(structured["valid"], Value::Bool(false));
        assert!(
            structured["diagnostics"]
                .as_array()
                .expect("diagnostics array")
                .len()
                >= 2
        );
        assert_eq!(
            structured["diagnostics"][0]["severity"],
            Value::String("error".into())
        );
        assert!(structured["diagnostics"]
            .as_array()
            .expect("diagnostics array")
            .iter()
            .any(|diagnostic| diagnostic["source"] == Value::String("validate_manifest".into())));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn tools_require_initialized_notification() {
        let mut state = ServerState::default();
        let _ = handle_request(
            &mut state,
            request(
                1,
                "initialize",
                json!({
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": { "name": "test", "version": "0" }
                }),
            ),
        );

        let response = handle_request(&mut state, request(2, "tools/list", json!({})))
            .expect("tools/list responds");
        assert_eq!(
            response["error"]["message"],
            Value::String(
                "server must receive notifications/initialized before calling tools".into()
            )
        );
    }

    #[test]
    fn import_write_respects_force_flag() {
        let root = temp_dir("import-write");
        fs::write(
            root.join("README.md"),
            "# Example\n\nImported description.\n",
        )
        .expect("README written");
        fs::write(root.join(".repo"), "preexisting\n").expect(".repo written");

        let response = call_tool(
            "dotrepo.import_write",
            json!({
                "root": root.display().to_string(),
                "mode": "native"
            }),
        );
        assert_eq!(response["result"]["isError"], Value::Bool(true));
        assert!(response["result"]["structuredContent"]["error"]
            .as_str()
            .expect("error string")
            .contains("already exists"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn write_import_output_refuses_to_clobber_existing_file_without_force() {
        let root = temp_dir("import-write-helper");
        let path = root.join(".repo");
        fs::write(&path, "existing\n").expect("existing file written");

        let err = write_import_outputs(vec![(path.clone(), "replacement\n".into())], false)
            .expect_err("existing file should be preserved");
        assert!(err.to_string().contains("already exists"));
        assert_eq!(
            fs::read_to_string(&path).expect("file readable"),
            "existing\n"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_write_refuses_existing_evidence_without_leaving_partial_manifest() {
        let root = temp_dir("import-write-no-partial");
        fs::write(
            root.join("README.md"),
            "# Example Project\n\nProject summary from the README.\n",
        )
        .expect("README written");
        fs::write(root.join("evidence.md"), "preexisting evidence\n").expect("evidence written");

        let plan = import_repository_with_options(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/project"),
            &ImportOptions {
                generated_at: Some(current_timestamp_rfc3339().expect("timestamp")),
            },
        )
        .expect("import plan builds");
        let err = write_import_plan(&root, &plan, false).expect_err("write should fail");

        assert!(err.to_string().contains("already exists"));
        assert!(!root.join("record.toml").exists());
        assert_eq!(
            fs::read_to_string(root.join("evidence.md")).expect("evidence readable"),
            "preexisting evidence\n"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn maintainer_path_tools_match_core_reports() {
        let root = temp_dir("parity-native");
        write_native_parity_repo(&root);

        let validate = call_tool(
            "dotrepo.validate",
            json!({ "root": root.display().to_string() }),
        );
        assert_eq!(
            validate["result"]["structuredContent"],
            to_value(validate_repository(&root)).expect("validate report serializes")
        );

        let query = call_tool(
            "dotrepo.query",
            json!({
                "root": root.display().to_string(),
                "path": "repo.build"
            }),
        );
        assert_eq!(
            query["result"]["structuredContent"],
            to_value(query_repository(&root, "repo.build").expect("query report"))
                .expect("query report serializes")
        );

        let trust = call_tool(
            "dotrepo.trust",
            json!({ "root": root.display().to_string() }),
        );
        assert_eq!(
            trust["result"]["structuredContent"],
            to_value(trust_repository(&root).expect("trust report"))
                .expect("trust report serializes")
        );

        let generate = call_tool(
            "dotrepo.generate_check",
            json!({ "root": root.display().to_string() }),
        );
        assert_eq!(
            generate["result"]["structuredContent"],
            to_value(generate_check_repository(&root).expect("generate-check report"))
                .expect("generate-check report serializes")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn claim_inspect_tool_matches_core_report() {
        let root = temp_dir("claim-inspect");
        let record_dir = root.join("repos/github.com/acme/widget");
        let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
index_paths = ["repos/github.com/acme/widget/record.toml"]
record_sources = ["https://github.com/acme/widget"]
canonical_repo_url = "https://github.com/acme/widget"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/acme/widget/record.toml"
result_event = "events/0002-accepted.toml"
"#,
        )
        .expect("claim written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");
        fs::write(
            claim_dir.join("events/0002-accepted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "accepted"

[summary]
text = "Accepted claim."
"#,
        )
        .expect("accepted event written");

        let response = call_tool(
            "dotrepo.claim_inspect",
            json!({
                "root": root.display().to_string(),
                "claimPath": "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"],
            to_value(inspect_claim_directory(&root, &claim_dir).expect("claim report"))
                .expect("claim report serializes")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_preview_tool_matches_core_report() {
        let root = temp_dir("parity-import-preview");
        fs::write(
            root.join("README.md"),
            "# Example\n\nImported description.\n",
        )
        .expect("README written");

        let response = call_tool(
            "dotrepo.import_preview",
            json!({
                "root": root.display().to_string(),
                "mode": "overlay",
                "source": "https://github.com/example/project"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"],
            to_value(
                import_preview_repository(
                    &root,
                    ImportMode::Overlay,
                    Some("https://github.com/example/project"),
                )
                .expect("import preview report"),
            )
            .expect("import preview report serializes")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn parse_repository_url_supports_upstream_and_hosted_urls() {
        assert_eq!(
            parse_repository_url("github.com/tokio-rs/tokio").expect("repo url parses"),
            ("github.com".into(), "tokio-rs".into(), "tokio".into())
        );
        assert_eq!(
            parse_repository_url(
                "https://dotrepo.org/v0/repos/github.com/tokio-rs/tokio/index.json"
            )
            .expect("hosted repo url parses"),
            ("github.com".into(), "tokio-rs".into(), "tokio".into())
        );
    }

    #[test]
    fn lookup_tool_fetches_hosted_summary_trust_and_query() {
        let routes = vec![
            (
                "/v0/meta.json",
                json!({
                    "apiVersion": "v0",
                    "generatedAt": "2026-04-18T03:02:00Z",
                    "snapshotDigest": "abc123",
                    "staleAfter": "2026-04-19T03:02:00Z",
                    "strategy": "static_summary_and_trust",
                }),
            ),
            (
                "/v0/repos/github.com/example/orbit/index.json",
                json!({
                    "apiVersion": "v0",
                    "freshness": {
                        "generatedAt": "2026-04-18T03:02:00Z",
                        "snapshotDigest": "abc123",
                        "staleAfter": "2026-04-19T03:02:00Z",
                    },
                    "identity": {
                        "host": "github.com",
                        "owner": "example",
                        "repo": "orbit",
                        "source": "https://github.com/example/orbit",
                    },
                    "repository": {
                        "name": "orbit",
                        "description": "Fast local-first sync engine",
                    },
                    "selection": {
                        "reason": "only_matching_record",
                        "record": {
                            "manifestPath": "repos/github.com/example/orbit/record.toml",
                            "record": {
                                "mode": "overlay",
                                "status": "reviewed",
                            },
                        },
                    },
                    "conflicts": [],
                    "links": {
                        "self": "/v0/repos/github.com/example/orbit/index.json",
                        "trust": "/v0/repos/github.com/example/orbit/trust.json",
                        "queryTemplate": "/v0/repos/github.com/example/orbit/query?path={dot_path}",
                        "indexPath": "repos/github.com/example/orbit/",
                    },
                }),
            ),
            (
                "/v0/repos/github.com/example/orbit/trust.json",
                json!({
                    "apiVersion": "v0",
                    "freshness": {
                        "generatedAt": "2026-04-18T03:02:00Z",
                        "snapshotDigest": "abc123",
                        "staleAfter": "2026-04-19T03:02:00Z",
                    },
                    "identity": {
                        "host": "github.com",
                        "owner": "example",
                        "repo": "orbit",
                        "source": "https://github.com/example/orbit",
                    },
                    "selection": {
                        "reason": "only_matching_record",
                        "record": {
                            "manifestPath": "repos/github.com/example/orbit/record.toml",
                            "record": {
                                "mode": "overlay",
                                "status": "reviewed",
                            },
                        },
                    },
                    "conflicts": [],
                    "links": {
                        "self": "/v0/repos/github.com/example/orbit/trust.json",
                        "repository": "/v0/repos/github.com/example/orbit/index.json",
                        "queryTemplate": "/v0/repos/github.com/example/orbit/query?path={dot_path}",
                        "indexPath": "repos/github.com/example/orbit/",
                    },
                }),
            ),
            (
                "/v0/repos/github.com/example/orbit/query?path=repo.description",
                json!({
                    "apiVersion": "v0",
                    "freshness": {
                        "generatedAt": "2026-04-18T03:02:00Z",
                        "snapshotDigest": "abc123",
                        "staleAfter": "2026-04-19T03:02:00Z",
                    },
                    "identity": {
                        "host": "github.com",
                        "owner": "example",
                        "repo": "orbit",
                        "source": "https://github.com/example/orbit",
                    },
                    "path": "repo.description",
                    "value": "Fast local-first sync engine",
                    "selection": {
                        "reason": "only_matching_record",
                        "record": {
                            "manifestPath": "repos/github.com/example/orbit/record.toml",
                            "record": {
                                "mode": "overlay",
                                "status": "reviewed",
                            },
                        },
                    },
                    "conflicts": [],
                    "links": {
                        "self": "/v0/repos/github.com/example/orbit/query?path=repo.description",
                        "repository": "/v0/repos/github.com/example/orbit/index.json",
                        "trust": "/v0/repos/github.com/example/orbit/trust.json",
                        "queryTemplate": "/v0/repos/github.com/example/orbit/query?path={dot_path}",
                        "indexPath": "repos/github.com/example/orbit/",
                    },
                }),
            ),
        ];
        let (_server, base_url) = start_json_server(routes);

        let response = call_tool(
            "dotrepo.lookup",
            json!({
                "repositoryUrl": "https://github.com/example/orbit",
                "path": "repo.description",
                "baseUrl": base_url,
            }),
        );
        let structured = &response["result"]["structuredContent"];
        assert_eq!(
            structured["identity"],
            json!({
                "host": "github.com",
                "owner": "example",
                "repo": "orbit",
            })
        );
        assert_eq!(
            structured["lookup"]["source"],
            Value::String("repository_url".into())
        );
        assert_eq!(
            structured["query"]["value"],
            Value::String("Fast local-first sync engine".into())
        );
        assert_eq!(
            structured["links"]["queryTemplate"],
            Value::String("/v0/repos/github.com/example/orbit/query?path={dot_path}".into())
        );
        assert_eq!(
            structured["summary"]["repository"]["name"],
            Value::String("orbit".into())
        );
    }

    #[test]
    fn message_framing_round_trips() {
        let message = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping"
        });
        let mut bytes = Vec::new();
        write_message(&mut bytes, &message).expect("message written");

        let mut reader = BufReader::new(std::io::Cursor::new(bytes));
        let payload = read_message(&mut reader)
            .expect("message read")
            .expect("payload present");
        let decoded: Value = serde_json::from_slice(&payload).expect("payload decodes");
        assert_eq!(decoded, message);
    }

    fn call_tool(name: &str, arguments: Value) -> Value {
        let (mut state, _) = initialized_state();
        handle_request(
            &mut state,
            request(
                2,
                "tools/call",
                json!({
                    "name": name,
                    "arguments": arguments
                }),
            ),
        )
        .expect("tool call responds")
    }

    fn initialized_state() -> (ServerState, Value) {
        let mut state = ServerState::default();
        let init_response = handle_request(
            &mut state,
            request(
                1,
                "initialize",
                json!({
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": { "name": "test", "version": "0" }
                }),
            ),
        )
        .expect("initialize responds");
        handle_request(
            &mut state,
            notification("notifications/initialized", json!({})),
        );
        (state, init_response)
    }

    fn request(id: i64, method: &str, params: Value) -> JsonRpcRequest {
        JsonRpcRequest {
            jsonrpc: JSONRPC_VERSION.into(),
            id: Some(Value::Number(id.into())),
            method: method.into(),
            params,
        }
    }

    fn notification(method: &str, params: Value) -> JsonRpcRequest {
        JsonRpcRequest {
            jsonrpc: JSONRPC_VERSION.into(),
            id: None,
            method: method.into(),
            params,
        }
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-mcp-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }

    fn write_native_parity_repo(root: &Path) {
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared", "verified"]
notes = "Maintainer-controlled source of truth."

[repo]
name = "orbit"
description = "Fast local-first sync engine"
build = "cargo build"
test = "cargo test"

[owners]
security_contact = "security@example.com"

[readme]
title = "Orbit"
sections = ["overview", "security"]

[compat.github]
codeowners = "skip"
security = "skip"
contributing = "skip"
pull_request_template = "skip"
"#,
        )
        .expect("manifest written");

        let document = dotrepo_core::load_manifest_document(root).expect("manifest loads");
        let outputs = dotrepo_core::managed_outputs(root, &document.manifest, &document.raw)
            .expect("outputs");
        for (path, contents) in outputs {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent).expect("output parent exists");
            }
            fs::write(path, contents).expect("output written");
        }
    }

    struct TestServer {
        join: Option<thread::JoinHandle<()>>,
    }

    impl Drop for TestServer {
        fn drop(&mut self) {
            if let Some(join) = self.join.take() {
                join.join().expect("server thread joins");
            }
        }
    }

    fn start_json_server(routes: Vec<(&'static str, Value)>) -> (TestServer, String) {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener binds");
        let address = listener.local_addr().expect("listener address");
        let routes = routes
            .into_iter()
            .map(|(path, body)| {
                (
                    path.to_string(),
                    serde_json::to_string(&body).expect("route JSON serializes"),
                )
            })
            .collect::<Vec<_>>();
        let expected_requests = routes.len();
        let handle = thread::spawn(move || {
            for _ in 0..expected_requests {
                let (mut stream, _) = listener.accept().expect("client connects");
                let mut buffer = [0_u8; 4096];
                let bytes_read = stream.read(&mut buffer).expect("request readable");
                let request = String::from_utf8_lossy(&buffer[..bytes_read]);
                let request_line = request.lines().next().expect("request line");
                let path = request_line
                    .split_whitespace()
                    .nth(1)
                    .expect("request path")
                    .to_string();
                let body = routes
                    .iter()
                    .find(|(candidate, _)| *candidate == path)
                    .map(|(_, body)| body.clone());
                let (status_line, response_body) = if let Some(body) = body {
                    ("HTTP/1.1 200 OK", body)
                } else {
                    (
                        "HTTP/1.1 404 Not Found",
                        serde_json::to_string(&json!({ "error": "not found" }))
                            .expect("404 serializes"),
                    )
                };
                let response = format!(
                    "{status_line}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    response_body.len(),
                    response_body
                );
                stream
                    .write_all(response.as_bytes())
                    .expect("response written");
            }
        });
        (
            TestServer { join: Some(handle) },
            format!("http://{}", address),
        )
    }
}
