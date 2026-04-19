use anyhow::{Context, Result};
use clap::Parser;
use dotrepo_core::{
    build_public_freshness, public_repository_query_or_error_with_base, PublicErrorCode,
    PublicErrorResponse, PublicFreshness,
};
use serde::Serialize;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Component, Path, PathBuf};
use url::form_urlencoded;

#[derive(Parser)]
#[command(name = "dotrepo-public-query")]
#[command(about = "Thin HTTP wrapper for the dotrepo public query contract")]
struct Cli {
    /// Index snapshot root used to answer public query requests.
    #[arg(long, default_value = "index")]
    index_root: PathBuf,
    /// Address to bind, for example 127.0.0.1:3000.
    #[arg(long, default_value = "127.0.0.1:3000")]
    bind: String,
    /// URL base path prefix for hosted public links, such as `/dotrepo`.
    #[arg(long, default_value = "/")]
    base_path: String,
    /// Optional exported public tree to serve on the same origin as query.
    #[arg(long)]
    public_root: Option<PathBuf>,
    /// Advisory staleness window in hours for rendered responses.
    #[arg(long)]
    stale_after_hours: Option<i64>,
    /// Fixed RFC 3339 generation timestamp for deterministic review.
    #[arg(long)]
    generated_at: Option<String>,
    /// Fixed RFC 3339 staleness timestamp for deterministic review.
    #[arg(long)]
    stale_after: Option<String>,
}

#[derive(Debug, Clone)]
struct ServerState {
    index_root: PathBuf,
    base_path: String,
    public_root: Option<PathBuf>,
    freshness: PublicFreshness,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum Route {
    Healthz,
    Query {
        host: String,
        owner: String,
        repo: String,
        path: String,
    },
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    let freshness = build_public_freshness(
        &cli.index_root,
        cli.stale_after_hours,
        cli.generated_at.as_deref(),
        cli.stale_after.as_deref(),
    )?;
    let state = ServerState {
        index_root: cli.index_root,
        base_path: normalize_base_path(&cli.base_path),
        public_root: cli.public_root,
        freshness,
    };

    let listener =
        TcpListener::bind(&cli.bind).with_context(|| format!("failed to bind {}", cli.bind))?;
    eprintln!("dotrepo-public-query listening on {}", cli.bind);

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                if let Err(err) = handle_connection(stream, &state) {
                    eprintln!("request handling failed: {err}");
                }
            }
            Err(err) => eprintln!("failed to accept connection: {err}"),
        }
    }

    Ok(())
}

fn normalize_base_path(base_path: &str) -> String {
    let trimmed = base_path.trim();
    if trimmed.is_empty() || trimmed == "/" {
        "/".into()
    } else {
        format!("/{}", trimmed.trim_matches('/'))
    }
}

fn handle_connection(mut stream: TcpStream, state: &ServerState) -> Result<()> {
    let mut reader = BufReader::new(
        stream
            .try_clone()
            .context("failed to clone request stream")?,
    );
    let mut request_line = String::new();
    if reader
        .read_line(&mut request_line)
        .context("failed to read request line")?
        == 0
    {
        return Ok(());
    }

    loop {
        let mut header = String::new();
        let bytes = reader
            .read_line(&mut header)
            .context("failed to read request header")?;
        if bytes == 0 || header == "\r\n" {
            break;
        }
    }

    let mut parts = request_line.split_whitespace();
    let method = parts.next().unwrap_or_default();
    let target = parts.next().unwrap_or_default();
    if method != "GET" {
        return write_text_response(&mut stream, 405, "method not allowed");
    }

    match route_request(target, &state.base_path) {
        Err(err) => write_text_response(&mut stream, 400, &err.to_string()),
        Ok(Some(Route::Healthz)) => write_text_response(&mut stream, 200, "ok"),
        Ok(Some(Route::Query {
            host,
            owner,
            repo,
            path,
        })) => {
            let response = public_repository_query_or_error_with_base(
                &state.index_root,
                &host,
                &owner,
                &repo,
                &path,
                state.freshness.clone(),
                &state.base_path,
            );
            match response {
                Ok(body) => write_json_response(&mut stream, 200, &body),
                Err(body) => {
                    write_json_response(&mut stream, status_for_public_error(&body), &body)
                }
            }
        }
        Ok(None) => {
            if let Some(public_root) = &state.public_root {
                if let Some(static_path) =
                    resolve_static_path(target, &state.base_path, public_root)?
                {
                    return write_static_file_response(&mut stream, &static_path);
                }
            }
            write_text_response(&mut stream, 404, "not found")
        }
    }
}

fn route_request(target: &str, base_path: &str) -> Result<Option<Route>> {
    let (path, query) = target.split_once('?').unwrap_or((target, ""));
    if path == "/healthz" {
        return Ok(Some(Route::Healthz));
    }

    let prefix = if base_path == "/" {
        "/v0/repos/"
    } else {
        return route_request_with_base(path, query, base_path);
    };

    let Some(rest) = path.strip_prefix(prefix) else {
        return Ok(None);
    };
    parse_query_route(rest, query)
}

fn route_request_with_base(path: &str, query: &str, base_path: &str) -> Result<Option<Route>> {
    let expected_prefix = format!("{}/v0/repos/", base_path.trim_end_matches('/'));
    let Some(rest) = path.strip_prefix(&expected_prefix) else {
        return Ok(None);
    };
    parse_query_route(rest, query)
}

fn parse_query_route(rest: &str, query: &str) -> Result<Option<Route>> {
    let segments = rest.split('/').collect::<Vec<_>>();
    if segments.len() != 4 || segments[3] != "query" {
        return Ok(None);
    }

    let path = required_query_param(query, "path")?;
    Ok(Some(Route::Query {
        host: decode_identity_component(segments[0], "host")?,
        owner: decode_identity_component(segments[1], "owner")?,
        repo: decode_identity_component(segments[2], "repo")?,
        path,
    }))
}

fn required_query_param(query: &str, key: &str) -> Result<String> {
    form_urlencoded::parse(query.as_bytes())
        .find_map(|(candidate, value)| (candidate == key).then(|| value.into_owned()))
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| anyhow::anyhow!("missing query parameter `{key}`"))
}

fn decode_component(raw: &str) -> Result<String> {
    required_query_param(&format!("x={raw}"), "x")
}

fn decode_identity_component(raw: &str, field: &str) -> Result<String> {
    let decoded = decode_component(raw)?;
    if matches!(
        Path::new(&decoded).components().next(),
        Some(Component::CurDir | Component::ParentDir)
    ) {
        anyhow::bail!("invalid repository identity: {field} must be a single path segment");
    }
    Ok(decoded)
}

fn resolve_static_path(
    target: &str,
    base_path: &str,
    public_root: &Path,
) -> Result<Option<PathBuf>> {
    let (path, _) = target.split_once('?').unwrap_or((target, ""));
    let relative = static_relative_path(path, base_path)?;
    let Some(relative) = relative else {
        return Ok(None);
    };
    if !is_safe_relative_path(&relative) {
        return Ok(None);
    }
    let candidate = if relative.as_os_str().is_empty() {
        public_root.join("index.html")
    } else {
        public_root.join(&relative)
    };
    if candidate.is_file() {
        return Ok(Some(candidate));
    }

    let directory_index = if relative.as_os_str().is_empty() {
        None
    } else {
        Some(public_root.join(relative).join("index.html"))
    };
    Ok(directory_index.filter(|path| path.is_file()))
}

fn static_relative_path(path: &str, base_path: &str) -> Result<Option<PathBuf>> {
    if base_path == "/" {
        if path == "/" || path.is_empty() {
            return Ok(Some(PathBuf::new()));
        }
        return Ok(path.strip_prefix('/').map(PathBuf::from));
    }

    if path == base_path {
        return Ok(Some(PathBuf::new()));
    }

    let prefix = format!("{}/", base_path.trim_end_matches('/'));
    Ok(path.strip_prefix(&prefix).map(PathBuf::from))
}

fn is_safe_relative_path(path: &Path) -> bool {
    path.components().all(|component| match component {
        Component::Normal(_) => true,
        Component::CurDir => true,
        Component::RootDir | Component::ParentDir | Component::Prefix(_) => false,
    })
}

fn content_type_for_path(path: &Path) -> &'static str {
    match path.extension().and_then(|ext| ext.to_str()) {
        Some("html") => "text/html; charset=utf-8",
        Some("json") => "application/json",
        Some("txt") => "text/plain; charset=utf-8",
        Some("md") => "text/markdown; charset=utf-8",
        _ => "application/octet-stream",
    }
}

fn write_static_file_response(stream: &mut TcpStream, path: &Path) -> Result<()> {
    let bytes = std::fs::read(path)
        .with_context(|| format!("failed to read static file {}", path.display()))?;
    write_response(stream, 200, content_type_for_path(path), &bytes)
}

fn write_text_response(stream: &mut TcpStream, status: u16, body: &str) -> Result<()> {
    write_response(stream, status, "text/plain; charset=utf-8", body.as_bytes())
}

fn write_json_response<T: Serialize>(stream: &mut TcpStream, status: u16, body: &T) -> Result<()> {
    let bytes = serde_json::to_vec_pretty(body).context("failed to serialize json response")?;
    write_response(stream, status, "application/json", &bytes)
}

fn write_response(
    stream: &mut TcpStream,
    status: u16,
    content_type: &str,
    body: &[u8],
) -> Result<()> {
    let status_text = match status {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        _ => "Internal Server Error",
    };
    write!(
        stream,
        "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        status,
        status_text,
        content_type,
        body.len()
    )
    .context("failed to write response headers")?;
    stream
        .write_all(body)
        .context("failed to write response body")?;
    stream.flush().context("failed to flush response")?;
    Ok(())
}

fn status_for_public_error(error: &PublicErrorResponse) -> u16 {
    match error.error.code {
        PublicErrorCode::InvalidRepositoryIdentity => 400,
        PublicErrorCode::QueryPathNotFound | PublicErrorCode::RepositoryNotFound => 404,
        PublicErrorCode::InternalError => 500,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn route_request_rejects_dot_segments_in_repository_identity() {
        let err = route_request("/v0/repos/github.com/../orbit/query?path=repo.name", "/")
            .expect_err("dot segment rejected");
        assert_eq!(
            err.to_string(),
            "invalid repository identity: owner must be a single path segment"
        );
    }

    #[test]
    fn route_request_decodes_valid_repository_identity() {
        let route = route_request(
            "/v0/repos/github.com/example/orbit/query?path=repo.name",
            "/",
        )
        .expect("route parses");
        assert_eq!(
            route,
            Some(Route::Query {
                host: "github.com".into(),
                owner: "example".into(),
                repo: "orbit".into(),
                path: "repo.name".into(),
            })
        );
    }

    #[test]
    fn resolve_static_path_serves_directory_index() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("unix time")
            .as_nanos();
        let temp_root = std::env::temp_dir().join(format!("dotrepo-public-query-test-{unique}"));
        let docs_dir = temp_root.join("docs");
        fs::create_dir_all(&docs_dir).expect("create docs dir");
        fs::write(docs_dir.join("index.html"), "<h1>Docs</h1>").expect("write index");

        let resolved = resolve_static_path("/docs/", "/", &temp_root)
            .expect("path resolves")
            .expect("directory index exists");

        assert_eq!(resolved, docs_dir.join("index.html"));
        fs::remove_dir_all(&temp_root).expect("cleanup temp dir");
    }
}
