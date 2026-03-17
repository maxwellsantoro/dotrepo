use anyhow::{Context, Result};
use clap::Parser;
use dotrepo_core::{
    build_public_freshness, public_repository_query_or_error_with_base, PublicErrorCode,
    PublicErrorResponse, PublicFreshness,
};
use serde::Serialize;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
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
        Ok(None) => write_text_response(&mut stream, 404, "not found"),
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
        host: decode_component(segments[0])?,
        owner: decode_component(segments[1])?,
        repo: decode_component(segments[2])?,
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
