//! Remote `dotrepo.lookup` policy, URL normalization, and SSRF protections.

use anyhow::{anyhow, bail, Result};
use reqwest::blocking::Client;
use reqwest::Url;
use serde_json::Value;
use std::net::{IpAddr, SocketAddr, ToSocketAddrs};
use std::time::Duration;

pub(crate) const DEFAULT_PUBLIC_BASE_URL: &str = "https://dotrepo.org";
pub(crate) const ALLOWED_LOOKUP_BASE_URLS: &[&str] =
    &["https://dotrepo.org", "https://dotrepo-org.workers.dev"];
pub(crate) const REMOTE_LOOKUP_TIMEOUT: Duration = Duration::from_secs(15);

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
pub(crate) struct LookupTarget {
    pub(crate) host: String,
    pub(crate) owner: String,
    pub(crate) repo: String,
    pub(crate) repository_url: String,
    pub(crate) path: Option<String>,
    pub(crate) source: &'static str,
}

pub(crate) fn resolve_lookup_target(arguments: &Value) -> Result<LookupTarget> {
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

fn env_flag_enabled(name: &str) -> bool {
    matches!(
        std::env::var(name).ok().as_deref().map(str::trim),
        Some("1") | Some("true") | Some("TRUE") | Some("yes") | Some("YES")
    )
}

pub(crate) fn allow_custom_lookup_base_url() -> bool {
    env_flag_enabled("DOTREPO_MCP_ALLOW_CUSTOM_BASE_URL")
}

fn allow_local_lookup_base_url() -> bool {
    env_flag_enabled("DOTREPO_MCP_UNSAFE_ALLOW_LOCAL_BASE_URL")
}

fn is_blocked_lookup_ip(addr: &IpAddr) -> bool {
    if allow_local_lookup_base_url() {
        return false;
    }

    match addr {
        IpAddr::V4(v4) => {
            let octets = v4.octets();
            // CGNAT / shared address space (RFC 6598): 100.64.0.0/10
            let is_cgnat = octets[0] == 100 && (octets[1] & 0xc0) == 0x40;
            // Documentation / benchmarking (RFC 5737): 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24
            let is_documentation = matches!(
                (octets[0], octets[1], octets[2]),
                (192, 0, 2) | (198, 51, 100) | (203, 0, 113)
            );
            v4.is_private()
                || v4.is_loopback()
                || v4.is_link_local()
                || v4.is_unspecified()
                || v4.is_broadcast()
                || v4.is_multicast()
                || is_cgnat
                || is_documentation
                || (octets[0] == 169 && octets[1] == 254)
        }
        IpAddr::V6(v6) => {
            let segments = v6.segments();
            // Unique local (fc00::/7), link-local (fe80::/10), multicast (ff00::/8),
            // documentation (2001:db8::/32).
            v6.is_loopback()
                || v6.is_unspecified()
                || v6.is_multicast()
                || (segments[0] & 0xfe00) == 0xfc00
                || (segments[0] & 0xffc0) == 0xfe80
                || (segments[0] == 0x2001 && segments[1] == 0x0db8)
        }
    }
}

fn is_blocked_lookup_host(host: &str) -> bool {
    if allow_local_lookup_base_url() {
        return host.trim().is_empty();
    }
    let host = host.trim().trim_end_matches('.').to_ascii_lowercase();
    if host.is_empty() {
        return true;
    }
    if host == "localhost" || host.ends_with(".localhost") {
        return true;
    }
    if host == "0.0.0.0" {
        return true;
    }

    let without_zone = host.split('%').next().unwrap_or(&host);
    if without_zone == "::1" {
        return true;
    }
    if let Some(stripped) = without_zone
        .strip_prefix('[')
        .and_then(|v| v.strip_suffix(']'))
    {
        if stripped == "::1" {
            return true;
        }
    }

    if let Ok(addr) = without_zone.parse::<IpAddr>() {
        return is_blocked_lookup_ip(&addr);
    }

    matches!(
        host.as_str(),
        "metadata.google.internal"
            | "metadata.goog"
            | "metadata"
            | "metadata.aws.internal"
            | "instance-data"
            | "kubernetes.default"
            | "kubernetes.default.svc"
            | "kubernetes.default.svc.cluster.local"
    )
}

/// Resolve a snapshot meta path against an allowlisted lookup base URL without
/// allowing host escape via protocol-relative (`//evil`) or absolute URLs.
pub(crate) fn resolve_same_origin_path_url(base_url: &str, path: &str) -> Result<String> {
    let path = path.trim();
    if path.is_empty() {
        bail!("snapshot path must not be empty");
    }
    if path.contains("://") || path.starts_with("//") {
        bail!(
            "snapshot path must be a same-origin absolute path, not a full or protocol-relative URL"
        );
    }
    if !path.starts_with('/') {
        bail!("snapshot path must start with /");
    }
    if path.split('/').any(|segment| segment == "..") {
        bail!("snapshot path must not contain '..' segments");
    }

    let base = Url::parse(base_url)
        .map_err(|err| anyhow!("invalid lookup base URL `{}`: {}", base_url, err))?;
    let joined = base
        .join(path)
        .map_err(|err| anyhow!("invalid snapshot path `{}`: {}", path, err))?;
    if joined.scheme() != base.scheme() || joined.host_str() != base.host_str() {
        bail!(
            "snapshot path `{}` must remain on the lookup base origin {}",
            path,
            remote_public_root(base_url)
        );
    }
    if joined.port_or_known_default() != base.port_or_known_default() {
        bail!(
            "snapshot path `{}` must not change the lookup base port",
            path
        );
    }
    Ok(joined.as_str().to_string())
}

fn resolve_safe_lookup_addresses(url: &str) -> Result<Vec<SocketAddr>> {
    let parsed = Url::parse(url).map_err(|err| anyhow!("invalid lookup URL `{}`: {}", url, err))?;
    let host = parsed
        .host_str()
        .ok_or_else(|| anyhow!("lookup URL must include a host: {}", url))?;
    if is_blocked_lookup_host(host) {
        bail!("lookup host `{}` is not allowed for remote lookup", host);
    }
    let port = parsed.port_or_known_default().unwrap_or(443);

    if let Ok(addr) = host.parse::<IpAddr>() {
        return validate_lookup_addresses(host, vec![SocketAddr::new(addr, port)]);
    }

    let endpoint = format!("{host}:{port}");
    let resolved = endpoint
        .to_socket_addrs()
        .map_err(|err| anyhow!("failed to resolve lookup host `{}`: {}", host, err))?;
    validate_lookup_addresses(host, resolved.collect())
}

fn validate_lookup_addresses(host: &str, addresses: Vec<SocketAddr>) -> Result<Vec<SocketAddr>> {
    if addresses.is_empty() {
        bail!("lookup host `{}` did not resolve to any address", host);
    }
    for addr in &addresses {
        if is_blocked_lookup_ip(&addr.ip()) {
            bail!(
                "lookup host `{}` resolves to blocked address {}",
                host,
                addr.ip()
            );
        }
    }
    Ok(addresses)
}

fn ensure_lookup_endpoint_safe(url: &str) -> Result<()> {
    resolve_safe_lookup_addresses(url).map(|_| ())
}

pub(crate) fn normalize_public_base_url(value: &str) -> Result<String> {
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
        "https" => {}
        "http" if allow_local_lookup_base_url() => {}
        "http" => bail!(
            "baseUrl must use HTTPS; set DOTREPO_MCP_UNSAFE_ALLOW_LOCAL_BASE_URL=1 only for local development"
        ),
        other => bail!("unsupported baseUrl scheme: {}", other),
    }
    let host = url
        .host_str()
        .ok_or_else(|| anyhow!("baseUrl must include a host: {}", value))?;
    if is_blocked_lookup_host(host) {
        bail!("baseUrl host `{}` is not allowed for remote lookup", host);
    }

    let normalized = url.as_str().trim_end_matches('/').to_string();
    if allow_custom_lookup_base_url() {
        return Ok(normalized);
    }

    if ALLOWED_LOOKUP_BASE_URLS
        .iter()
        .any(|allowed| normalized.eq_ignore_ascii_case(allowed))
    {
        return Ok(normalized);
    }

    bail!(
        "baseUrl `{}` is not in the default allowlist; set DOTREPO_MCP_ALLOW_CUSTOM_BASE_URL=1 to opt in",
        normalized
    )
}

pub(crate) fn remote_public_root(base_url: &str) -> String {
    base_url.trim_end_matches('/').to_string()
}

pub(crate) fn remote_repository_url(
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

pub(crate) fn remote_query_url(
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

pub(crate) fn build_remote_lookup_client(base_url: &str) -> Result<Client> {
    let parsed = Url::parse(base_url)
        .map_err(|err| anyhow!("invalid lookup base URL `{}`: {}", base_url, err))?;
    let host = parsed
        .host_str()
        .ok_or_else(|| anyhow!("lookup base URL must include a host: {}", base_url))?;
    let addresses = resolve_safe_lookup_addresses(base_url)?;

    Client::builder()
        .user_agent(format!("dotrepo-mcp/{}", env!("CARGO_PKG_VERSION")))
        .timeout(REMOTE_LOOKUP_TIMEOUT)
        .redirect(reqwest::redirect::Policy::none())
        .resolve_to_addrs(host, &addresses)
        .build()
        .map_err(Into::into)
}

pub(crate) fn fetch_remote_json(client: &Client, url: &str) -> Result<Value> {
    ensure_lookup_endpoint_safe(url)?;
    let response = client
        .get(url)
        .send()
        .map_err(|error| anyhow!("failed to GET {}: {}", url, error))?;
    let status = response.status();
    if !status.is_success() {
        let body = response
            .text()
            .map_err(|error| anyhow!("failed to read error body from {}: {}", url, error))?;
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::mcp_env_test_lock;
    use std::sync::MutexGuard;

    struct LookupEnvGuard {
        _guard: MutexGuard<'static, ()>,
    }

    impl Drop for LookupEnvGuard {
        fn drop(&mut self) {
            clear_lookup_base_url_env();
        }
    }

    fn lock_lookup_base_url_env() -> LookupEnvGuard {
        let guard = mcp_env_test_lock()
            .lock()
            // Test-only env cleanup should not cascade if another lookup test panics.
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        clear_lookup_base_url_env();
        LookupEnvGuard { _guard: guard }
    }

    fn clear_lookup_base_url_env() {
        // SAFETY: test-only env cleanup between lookup URL policy tests.
        unsafe {
            std::env::remove_var("DOTREPO_MCP_ALLOW_CUSTOM_BASE_URL");
            std::env::remove_var("DOTREPO_MCP_UNSAFE_ALLOW_LOCAL_BASE_URL");
        }
    }

    #[test]
    fn normalize_public_base_url_blocks_private_hosts_by_default() {
        let _env_guard = lock_lookup_base_url_env();
        let err = normalize_public_base_url("https://127.0.0.1:8080")
            .expect_err("loopback should be blocked");
        assert!(err.to_string().contains("not allowed"));

        let err = normalize_public_base_url("https://192.168.1.10")
            .expect_err("private network should be blocked");
        assert!(err.to_string().contains("not allowed"));
    }

    #[test]
    fn normalize_public_base_url_requires_https_by_default() {
        let _env_guard = lock_lookup_base_url_env();
        let err = normalize_public_base_url("http://dotrepo.org")
            .expect_err("default public origins must use HTTPS");
        assert!(err.to_string().contains("must use HTTPS"));
    }

    #[test]
    fn ensure_lookup_endpoint_safe_blocks_literal_private_ips() {
        let _env_guard = lock_lookup_base_url_env();
        let err = ensure_lookup_endpoint_safe("https://127.0.0.1/v0/meta.json")
            .expect_err("literal loopback IP should be blocked");
        assert!(err.to_string().contains("not allowed"));
    }

    #[test]
    fn validate_lookup_addresses_rejects_any_private_resolution() {
        let _env_guard = lock_lookup_base_url_env();
        let addresses = vec![
            "93.184.216.34:443".parse().expect("public address"),
            "127.0.0.1:443".parse().expect("loopback address"),
        ];
        let err = validate_lookup_addresses("rebind.example", addresses)
            .expect_err("mixed public and private answers must be blocked");
        assert!(err.to_string().contains("blocked address 127.0.0.1"));
    }

    #[test]
    fn normalize_public_base_url_allows_default_public_origins() {
        let _env_guard = lock_lookup_base_url_env();
        assert_eq!(
            normalize_public_base_url("https://dotrepo.org").expect("dotrepo.org allowed"),
            "https://dotrepo.org"
        );
        assert_eq!(
            normalize_public_base_url("dotrepo-org.workers.dev").expect("workers.dev allowed"),
            "https://dotrepo-org.workers.dev"
        );
    }

    #[test]
    fn normalize_public_base_url_requires_opt_in_for_custom_origins() {
        let _env_guard = lock_lookup_base_url_env();
        let err = normalize_public_base_url("https://example.com")
            .expect_err("custom origin should require opt-in");
        assert!(err
            .to_string()
            .contains("DOTREPO_MCP_ALLOW_CUSTOM_BASE_URL"));
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
    fn resolve_same_origin_path_url_keeps_allowlisted_origin() {
        let _env_guard = lock_lookup_base_url_env();
        assert_eq!(
            resolve_same_origin_path_url("https://dotrepo.org", "/v0/repos/index.json")
                .expect("relative path joins"),
            "https://dotrepo.org/v0/repos/index.json"
        );
    }

    #[test]
    fn resolve_same_origin_path_url_rejects_protocol_relative_and_absolute() {
        let _env_guard = lock_lookup_base_url_env();
        let err = resolve_same_origin_path_url("https://dotrepo.org", "//evil.example/v0/x")
            .expect_err("protocol-relative path must be rejected");
        assert!(err.to_string().contains("same-origin"));

        let err = resolve_same_origin_path_url(
            "https://dotrepo.org",
            "https://evil.example/v0/repos/index.json",
        )
        .expect_err("absolute URL path must be rejected");
        assert!(err.to_string().contains("same-origin"));
    }

    #[test]
    fn resolve_same_origin_path_url_rejects_parent_segments() {
        let _env_guard = lock_lookup_base_url_env();
        let err = resolve_same_origin_path_url("https://dotrepo.org", "/v0/../secret")
            .expect_err(".. segments must be rejected");
        assert!(err.to_string().contains(".."));
    }

    #[test]
    fn is_blocked_lookup_ip_covers_cgnat_and_documentation_ranges() {
        let _env_guard = lock_lookup_base_url_env();
        assert!(is_blocked_lookup_ip(
            &"100.64.0.1".parse().expect("cgnat address")
        ));
        assert!(is_blocked_lookup_ip(
            &"192.0.2.1".parse().expect("documentation address")
        ));
        assert!(is_blocked_lookup_ip(
            &"224.0.0.1".parse().expect("multicast address")
        ));
        assert!(!is_blocked_lookup_ip(
            &"93.184.216.34".parse().expect("public address")
        ));
    }

    #[test]
    fn is_blocked_lookup_host_covers_cloud_metadata_names() {
        let _env_guard = lock_lookup_base_url_env();
        assert!(is_blocked_lookup_host("metadata.google.internal"));
        assert!(is_blocked_lookup_host("metadata"));
        assert!(is_blocked_lookup_host("instance-data"));
        assert!(!is_blocked_lookup_host("dotrepo.org"));
    }
}
