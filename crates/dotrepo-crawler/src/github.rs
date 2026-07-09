use crate::materialize::{ConventionalRepositoryFiles, RepositoryTextFile};
use crate::{
    CrawlerStateSnapshot, DiscoveredRepository, GitHubRepositorySnapshot, NetworkUsage,
    RefreshCandidate, RepositoryRef, StarBand,
};
use anyhow::{anyhow, Context, Result};
use reqwest::blocking::{Client, Response};
use reqwest::header::{HeaderMap, HeaderName, HeaderValue, ACCEPT, AUTHORIZATION, USER_AGENT};
use reqwest::{StatusCode, Url};
use serde::de::DeserializeOwned;
use serde::Deserialize;
use std::cell::RefCell;
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::time::Duration;

const GITHUB_API_VERSION: &str = "2022-11-28";
const README_CANDIDATES: &[&str] = &[
    "README.md",
    "README.MD",
    "readme.md",
    "README.mdx",
    "README.markdown",
    "README",
];
// Every entry here must have a matching deterministic parser in
// dotrepo-core (see crates/dotrepo-core/src/import/mod.rs's
// `load_first_existing_file` calls) — otherwise the crawler fetches bytes
// that are never used. Historically this list only covered
// Cargo.toml/package.json/pyproject.toml/go.mod, so every other ecosystem
// dotrepo-core already knows how to parse (Maven, Gradle, Composer, Mix,
// Rebar, CMake presets, Makefile, justfile, Rakefile, setup.py/setup.cfg)
// was silently starved of the one file it needed. CONTRIBUTING files feed
// doc-declared command extraction. `.csproj` / `.sln` are handled in
// `fetch_dotnet_manifest_files` because their filenames are not fixed.
const SUPPLEMENTAL_ROOT_FILES: &[&str] = &[
    "Cargo.toml",
    "CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
    "package.json",
    "pyproject.toml",
    "go.mod",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "mix.exs",
    "rebar.config",
    "CMakePresets.json",
    "GNUmakefile",
    "Makefile",
    "makefile",
    "justfile",
    "Justfile",
    "Rakefile",
    "rakefile",
    // Wrapper marker files: import command inference only checks their
    // presence, but without materializing them the Maven/Gradle manifest
    // tiers emit bare `mvn`/`gradle` for repositories that ship a wrapper.
    "gradlew",
    "mvnw",
];
const MAX_WORKFLOW_FILES: usize = 8;
const GITHUB_HTTP_TIMEOUT: Duration = Duration::from_secs(30);
const GITHUB_HTTP_CONNECT_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_RATE_LIMIT_RETRIES: u32 = 3;
const RATE_LIMIT_RETRY_BASE: Duration = Duration::from_secs(2);

pub(crate) trait GitHubClient {
    fn fetch_repository_head(
        &self,
        repository: &RepositoryRef,
        default_branch: Option<&str>,
    ) -> Result<RepositoryHeadSnapshot>;
    fn fetch_repository_snapshot(
        &self,
        repository: &RepositoryRef,
    ) -> Result<GitHubRepositorySnapshot>;
    fn fetch_repository_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        languages: &[String],
    ) -> Result<ConventionalRepositoryFiles>;

    /// Cumulative network requests/bytes observed while servicing this
    /// client's fetch methods. Default is zero for fakes/stubs used in
    /// tests; `HttpGitHubClient` overrides this with real counters.
    fn network_usage(&self) -> NetworkUsage {
        NetworkUsage::default()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct RepositoryHeadSnapshot {
    pub default_branch: String,
    pub head_sha: Option<String>,
}

pub(crate) trait GitHubDiscoveryClient {
    fn search_repositories(
        &self,
        host: &str,
        star_band: &StarBand,
        page: usize,
        per_page: usize,
        include_archived: bool,
        include_forks: bool,
    ) -> Result<Vec<DiscoveredRepository>>;
}

pub(crate) fn refresh_candidates_from_state_impl(
    state: &CrawlerStateSnapshot,
) -> Result<Vec<RefreshCandidate>> {
    let client = HttpGitHubClient::new()?;
    refresh_candidates_from_state_with_client(state, &client)
}

fn refresh_candidates_from_state_with_client<C: GitHubClient>(
    state: &CrawlerStateSnapshot,
    client: &C,
) -> Result<Vec<RefreshCandidate>> {
    let mut candidates = Vec::with_capacity(state.repositories.len());
    for record in &state.repositories {
        if record.repository.host.trim() != "github.com" {
            return Err(anyhow!(
                "refresh planning currently supports github.com only, got {} for {}/{}/{}",
                record.repository.host,
                record.repository.host,
                record.repository.owner,
                record.repository.repo
            ));
        }

        let head =
            client.fetch_repository_head(&record.repository, record.default_branch.as_deref())?;
        candidates.push(RefreshCandidate {
            repository: record.repository.clone(),
            default_branch: Some(head.default_branch),
            head_sha: head.head_sha,
        });
    }

    Ok(candidates)
}

pub(crate) struct HttpGitHubClient {
    client: Client,
    api_base_url: Url,
    raw_base_url: Url,
    /// GitHubClient methods take `&self` (the trait is shared across many
    /// call sites in pipeline.rs), so request/byte counters use interior
    /// mutability rather than a `&mut self` receiver.
    network: RefCell<NetworkUsage>,
}

impl HttpGitHubClient {
    pub(crate) fn new() -> Result<Self> {
        let mut headers = HeaderMap::new();
        headers.insert(
            USER_AGENT,
            HeaderValue::from_str(&format!("dotrepo-crawler/{}", env!("CARGO_PKG_VERSION")))
                .context("failed to build GitHub user-agent header")?,
        );
        headers.insert(
            ACCEPT,
            HeaderValue::from_static("application/vnd.github+json"),
        );
        headers.insert(
            HeaderName::from_static("x-github-api-version"),
            HeaderValue::from_static(GITHUB_API_VERSION),
        );
        if let Some(token) = github_token() {
            headers.insert(
                AUTHORIZATION,
                HeaderValue::from_str(&format!("Bearer {token}"))
                    .context("failed to build GitHub authorization header")?,
            );
        }

        let client = build_http_client(headers)?;

        Ok(Self {
            client,
            api_base_url: Url::parse("https://api.github.com/")
                .context("failed to parse GitHub API base URL")?,
            raw_base_url: Url::parse("https://raw.githubusercontent.com/")
                .context("failed to parse GitHub raw base URL")?,
            network: RefCell::new(NetworkUsage::default()),
        })
    }

    fn api_url(&self, repository: &RepositoryRef, extra_segments: &[&str]) -> Result<Url> {
        let mut url = self.api_base_url.clone();
        {
            let mut segments = url
                .path_segments_mut()
                .map_err(|_| anyhow!("GitHub API base URL does not support path segments"))?;
            segments.extend(["repos", repository.owner.as_str(), repository.repo.as_str()]);
            segments.extend(extra_segments.iter().copied());
        }
        Ok(url)
    }

    fn search_url(
        &self,
        host: &str,
        star_band: &StarBand,
        page: usize,
        per_page: usize,
        include_archived: bool,
        include_forks: bool,
    ) -> Result<Url> {
        if host.trim() != "github.com" {
            return Err(anyhow!(
                "GitHub discovery currently supports github.com identities only"
            ));
        }

        let mut url = self
            .api_base_url
            .join("search/repositories")
            .context("failed to build GitHub search URL")?;
        let query = build_repository_search_query(star_band, include_archived, include_forks);
        url.query_pairs_mut()
            .append_pair("q", &query)
            .append_pair("sort", "stars")
            .append_pair("order", "desc")
            .append_pair("per_page", &per_page.to_string())
            .append_pair("page", &page.to_string());
        Ok(url)
    }

    fn raw_url(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        relative_path: &str,
    ) -> Result<Url> {
        let mut url = self.raw_base_url.clone();
        {
            let mut segments = url
                .path_segments_mut()
                .map_err(|_| anyhow!("GitHub raw base URL does not support path segments"))?;
            segments.extend([
                repository.owner.as_str(),
                repository.repo.as_str(),
                default_branch,
            ]);
            segments.extend(relative_path.split('/'));
        }
        Ok(url)
    }

    fn contents_url(
        &self,
        repository: &RepositoryRef,
        relative_path: &str,
        default_branch: &str,
    ) -> Result<Url> {
        let mut url = self.api_url(repository, &["contents"])?;
        {
            let mut segments = url
                .path_segments_mut()
                .map_err(|_| anyhow!("GitHub contents URL does not support path segments"))?;
            segments.extend(relative_path.split('/'));
        }
        url.query_pairs_mut().append_pair("ref", default_branch);
        Ok(url)
    }

    fn get_json<T: DeserializeOwned>(&self, url: Url) -> Result<T> {
        let response = self.send_with_retry(url.clone())?;
        response
            .json()
            .with_context(|| format!("failed to decode GitHub response {}", url.as_str()))
    }

    fn get_optional_text(&self, url: Url) -> Result<Option<String>> {
        let response = self.send_with_retry(url.clone())?;

        if response.status() == StatusCode::NOT_FOUND {
            return Ok(None);
        }

        let text = response
            .text()
            .with_context(|| format!("failed to decode text response {}", url.as_str()))?;
        Ok(Some(text))
    }

    fn get_optional_json<T: DeserializeOwned>(&self, url: Url) -> Result<Option<T>> {
        let response = self.send_with_retry(url.clone())?;

        if response.status() == StatusCode::NOT_FOUND {
            return Ok(None);
        }

        let decoded = response
            .json()
            .with_context(|| format!("failed to decode GitHub response {}", url.as_str()))?;
        Ok(Some(decoded))
    }

    fn fetch_first_available_file(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        candidates: &[&'static str],
    ) -> Result<Option<RepositoryTextFile>> {
        for candidate in candidates {
            if let Some(contents) =
                self.get_optional_text(self.raw_url(repository, default_branch, candidate)?)?
            {
                return Ok(Some(RepositoryTextFile {
                    relative_path: PathBuf::from(candidate),
                    contents,
                }));
            }
        }

        Ok(None)
    }

    fn fetch_optional_repository_file(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        relative_path: &str,
    ) -> Result<Option<RepositoryTextFile>> {
        Ok(self
            .get_optional_text(self.raw_url(repository, default_branch, relative_path)?)?
            .map(|contents| RepositoryTextFile {
                relative_path: PathBuf::from(relative_path),
                contents,
            }))
    }

    fn fetch_workflow_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
    ) -> Result<Vec<RepositoryTextFile>> {
        let entries = self
            .get_optional_json::<Vec<ContentsEntry>>(self.contents_url(
                repository,
                ".github/workflows",
                default_branch,
            )?)?
            .unwrap_or_default();
        let mut workflow_paths = entries
            .into_iter()
            .filter(|entry| entry.entry_type == "file")
            .filter(|entry| {
                let lower = entry.path.to_ascii_lowercase();
                lower.ends_with(".yml") || lower.ends_with(".yaml")
            })
            .map(|entry| entry.path)
            .collect::<Vec<_>>();
        workflow_paths.sort();
        workflow_paths.truncate(MAX_WORKFLOW_FILES);

        let mut files = Vec::new();
        for path in workflow_paths {
            if let Some(file) =
                self.fetch_optional_repository_file(repository, default_branch, &path)?
            {
                files.push(file);
            }
        }
        Ok(files)
    }

    /// Nested Python manifests (`python/setup.py`, nested `pyproject.toml`) when
    /// Python is a primary language and root files do not already provide commands.
    fn fetch_python_manifest_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        languages: &[String],
    ) -> Result<Vec<RepositoryTextFile>> {
        if !python_is_primary_language(languages) {
            return Ok(Vec::new());
        }

        // Root pyproject/setup/tox already in SUPPLEMENTAL_ROOT_FILES.
        let mut tree_url = self.api_url(repository, &["git", "trees", default_branch])?;
        tree_url.query_pairs_mut().append_pair("recursive", "1");
        let tree = self
            .get_optional_json::<GitTreeResponse>(tree_url)?
            .unwrap_or(GitTreeResponse { tree: Vec::new() });

        let mut paths: Vec<String> = tree
            .tree
            .iter()
            .filter(|entry| entry.entry_type == "blob")
            .map(|entry| entry.path.clone())
            .filter(|path| {
                let lower = path.to_ascii_lowercase();
                let name = path.rsplit('/').next().unwrap_or(path);
                matches!(
                    name,
                    "pyproject.toml" | "setup.py" | "setup.cfg" | "tox.ini"
                ) && path.matches('/').count() <= 2
                    && !lower.contains("/examples/")
                    && !lower.contains("/samples/")
                    && !lower.contains("/benchmarks/")
                    && !lower.contains("/tests/")
                    && !lower.contains("/release/")
                    && !lower.starts_with("release/")
                    && !lower.contains("/packaging/")
            })
            .collect();
        paths.sort_by(|left, right| {
            python_manifest_path_preference(left)
                .cmp(&python_manifest_path_preference(right))
                .then_with(|| left.cmp(right))
        });
        paths.truncate(5);

        let mut files = Vec::new();
        for path in paths {
            if matches!(
                path.as_str(),
                "pyproject.toml" | "setup.py" | "setup.cfg" | "tox.ini"
            ) {
                continue;
            }
            if let Some(file) =
                self.fetch_optional_repository_file(repository, default_branch, &path)?
            {
                files.push(file);
            }
        }
        Ok(files)
    }

    /// Nested `package.json` files for JS/TS monorepos when root scripts are
    /// absent or incomplete. Selection prefers apps/api, server, web over SDK
    /// and example packages (mirrors `load_best_package_json` ranking).
    fn fetch_node_manifest_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        languages: &[String],
    ) -> Result<Vec<RepositoryTextFile>> {
        if !js_ts_is_primary_language(languages) {
            return Ok(Vec::new());
        }

        // Root package.json is already fetched via SUPPLEMENTAL_ROOT_FILES.
        // Only tree-walk when monorepo layout is likely.
        let monorepo_markers = [
            "pnpm-workspace.yaml",
            "pnpm-workspace.yml",
            "lerna.json",
            "nx.json",
            "turbo.json",
            "rush.json",
        ];
        let mut has_marker = false;
        for marker in monorepo_markers {
            if self
                .fetch_optional_repository_file(repository, default_branch, marker)?
                .is_some()
            {
                has_marker = true;
                break;
            }
        }

        let mut tree_url = self.api_url(repository, &["git", "trees", default_branch])?;
        tree_url.query_pairs_mut().append_pair("recursive", "1");
        let tree = self
            .get_optional_json::<GitTreeResponse>(tree_url)?
            .unwrap_or(GitTreeResponse { tree: Vec::new() });
        let package_paths: Vec<String> = tree
            .tree
            .iter()
            .filter(|entry| entry.entry_type == "blob")
            .map(|entry| entry.path.clone())
            .filter(|path| path.ends_with("package.json"))
            .collect();
        if package_paths.is_empty() {
            return Ok(Vec::new());
        }
        // Nested packages only when a monorepo marker exists or multiple package.json files.
        if !has_marker && package_paths.len() <= 1 {
            return Ok(Vec::new());
        }

        let mut ranked = package_paths;
        ranked.sort_by(|left, right| {
            node_package_json_path_preference(left)
                .cmp(&node_package_json_path_preference(right))
                .then_with(|| left.cmp(right))
        });
        ranked.truncate(6);

        let mut files = Vec::new();
        for path in ranked {
            if path == "package.json" {
                continue; // already materialized via supplemental list
            }
            if let Some(file) =
                self.fetch_optional_repository_file(repository, default_branch, &path)?
            {
                files.push(file);
            }
        }
        Ok(files)
    }

    /// Materialize .NET entrypoints when C#/F# is a primary language signal.
    /// Root `.sln` / `.csproj` always win; nested tree walks run only when
    /// .NET is among the top languages so secondary SDK projects (e.g.
    /// `apps/dot-net-sdk` in a TypeScript monorepo) do not become `repo.build`.
    fn fetch_dotnet_manifest_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        languages: &[String],
    ) -> Result<Vec<RepositoryTextFile>> {
        if !dotnet_language_signal(languages) {
            return Ok(Vec::new());
        }

        let mut files = Vec::new();
        let mut root_contents_url = self.api_url(repository, &["contents"])?;
        root_contents_url
            .query_pairs_mut()
            .append_pair("ref", default_branch);
        let entries = self
            .get_optional_json::<Vec<ContentsEntry>>(root_contents_url)?
            .unwrap_or_default();

        for path in first_root_paths_with_suffixes(&entries, &[".sln", ".csproj"], 4) {
            if let Some(file) =
                self.fetch_optional_repository_file(repository, default_branch, &path)?
            {
                files.push(file);
            }
        }

        if files.iter().any(|file| {
            let lower = file.relative_path.to_string_lossy().to_ascii_lowercase();
            lower.ends_with(".csproj") || lower.ends_with(".sln")
        }) {
            return Ok(files);
        }

        // Nested monorepo walk only when .NET ranks in the top languages.
        if !dotnet_is_primary_language(languages) {
            return Ok(files);
        }

        let mut tree_url = self.api_url(repository, &["git", "trees", default_branch])?;
        tree_url.query_pairs_mut().append_pair("recursive", "1");
        let tree = self
            .get_optional_json::<GitTreeResponse>(tree_url)?
            .unwrap_or(GitTreeResponse { tree: Vec::new() });
        for path in select_dotnet_paths_from_tree(&tree.tree, 4) {
            if let Some(file) =
                self.fetch_optional_repository_file(repository, default_branch, &path)?
            {
                files.push(file);
            }
        }
        Ok(files)
    }

    fn send_with_retry(&self, url: Url) -> Result<Response> {
        let mut attempt = 0;
        loop {
            let response = self
                .client
                .get(url.clone())
                .send()
                .with_context(|| format!("failed to GET {}", url.as_str()))?;

            // Count every attempt (including rate-limited retries) as real
            // network traffic. `content_length()` reads the header only, so
            // this never consumes the body the caller still needs to read.
            {
                let mut usage = self.network.borrow_mut();
                usage.requests += 1;
                usage.bytes += response.content_length().unwrap_or(0);
            }

            let status = response.status();
            if status.is_success() || status == StatusCode::NOT_FOUND {
                return Ok(response);
            }

            let is_rate_limited = status == StatusCode::TOO_MANY_REQUESTS
                || response
                    .headers()
                    .get("x-ratelimit-remaining")
                    .and_then(|value| value.to_str().ok())
                    == Some("0");

            if !is_rate_limited || attempt >= MAX_RATE_LIMIT_RETRIES {
                let body = response.text().unwrap_or_default();
                if is_rate_limited {
                    return Err(anyhow!(
                        "GitHub API rate limited after {} retries {}: HTTP {} {}",
                        attempt,
                        url,
                        status.as_u16(),
                        compact_error_body(&body)
                    ));
                }
                return Err(anyhow!(
                    "GitHub request failed {}: HTTP {} {}",
                    url,
                    status.as_u16(),
                    compact_error_body(&body)
                ));
            }

            let sleep_duration = rate_limit_sleep_duration(&response, attempt);
            let _ = response.text(); // drain body
            eprintln!(
                "dotrepo-crawler: rate limited on {} (attempt {}/{}), sleeping {:.1}s",
                url.path(),
                attempt + 1,
                MAX_RATE_LIMIT_RETRIES,
                sleep_duration.as_secs_f64()
            );
            std::thread::sleep(sleep_duration);
            attempt += 1;
        }
    }
}

fn build_http_client(headers: HeaderMap) -> Result<Client> {
    Client::builder()
        .default_headers(headers)
        .connect_timeout(GITHUB_HTTP_CONNECT_TIMEOUT)
        .timeout(GITHUB_HTTP_TIMEOUT)
        .build()
        .context("failed to build GitHub HTTP client")
}

impl GitHubClient for HttpGitHubClient {
    fn fetch_repository_head(
        &self,
        repository: &RepositoryRef,
        default_branch: Option<&str>,
    ) -> Result<RepositoryHeadSnapshot> {
        if let Some(default_branch) = trim_optional(default_branch.map(str::to_string)) {
            if let Some(branch) = self.get_optional_json::<BranchApiResponse>(
                self.api_url(repository, &["branches", default_branch.as_str()])?,
            )? {
                return Ok(RepositoryHeadSnapshot {
                    default_branch,
                    head_sha: Some(branch.commit.sha),
                });
            }
        }

        let repo = self.get_json::<RepositoryApiResponse>(self.api_url(repository, &[])?)?;
        let branch = self.get_json::<BranchApiResponse>(
            self.api_url(repository, &["branches", repo.default_branch.as_str()])?,
        )?;

        Ok(RepositoryHeadSnapshot {
            default_branch: repo.default_branch,
            head_sha: Some(branch.commit.sha),
        })
    }

    fn fetch_repository_snapshot(
        &self,
        repository: &RepositoryRef,
    ) -> Result<GitHubRepositorySnapshot> {
        let repo = self.get_json::<RepositoryApiResponse>(self.api_url(repository, &[])?)?;
        let branch = self.get_json::<BranchApiResponse>(
            self.api_url(repository, &["branches", repo.default_branch.as_str()])?,
        )?;
        let languages =
            self.get_json::<BTreeMap<String, u64>>(self.api_url(repository, &["languages"])?)?;
        let topics = self.get_json::<TopicsApiResponse>(self.api_url(repository, &["topics"])?)?;

        Ok(GitHubRepositorySnapshot {
            html_url: repo.html_url,
            clone_url: repo.clone_url,
            default_branch: repo.default_branch,
            head_sha: Some(branch.commit.sha),
            description: trim_optional(repo.description),
            homepage: trim_optional(repo.homepage),
            license: repo
                .license
                .and_then(|license| trim_optional(license.spdx_id.or(license.name))),
            languages: languages_by_byte_count_descending(languages),
            topics: topics.names,
            visibility: trim_optional(repo.visibility),
            stars: Some(repo.stargazers_count),
            archived: repo.archived,
            fork: repo.fork,
            parent: repo.parent.and_then(|p| {
                p.full_name
                    .filter(|f| !f.trim().is_empty())
                    .map(|f| format!("github.com/{}", f))
                    .or_else(|| p.html_url.and_then(|u| normalize_parent_from_url(&u)))
            }),
        })
    }

    fn fetch_repository_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
        languages: &[String],
    ) -> Result<ConventionalRepositoryFiles> {
        let mut extra_files = Vec::new();
        for relative_path in SUPPLEMENTAL_ROOT_FILES {
            if let Some(file) =
                self.fetch_optional_repository_file(repository, default_branch, relative_path)?
            {
                extra_files.push(file);
            }
        }
        extra_files.extend(self.fetch_workflow_files(repository, default_branch)?);
        extra_files.extend(self.fetch_node_manifest_files(
            repository,
            default_branch,
            languages,
        )?);
        extra_files.extend(self.fetch_python_manifest_files(
            repository,
            default_branch,
            languages,
        )?);
        extra_files.extend(self.fetch_dotnet_manifest_files(
            repository,
            default_branch,
            languages,
        )?);

        Ok(ConventionalRepositoryFiles {
            readme: self.fetch_first_available_file(
                repository,
                default_branch,
                README_CANDIDATES,
            )?,
            root_codeowners: self.get_optional_text(self.raw_url(
                repository,
                default_branch,
                "CODEOWNERS",
            )?)?,
            github_codeowners: self.get_optional_text(self.raw_url(
                repository,
                default_branch,
                ".github/CODEOWNERS",
            )?)?,
            root_security: self.get_optional_text(self.raw_url(
                repository,
                default_branch,
                "SECURITY.md",
            )?)?,
            github_security: self.get_optional_text(self.raw_url(
                repository,
                default_branch,
                ".github/SECURITY.md",
            )?)?,
            extra_files,
        })
    }

    fn network_usage(&self) -> NetworkUsage {
        self.network.borrow().clone()
    }
}

impl GitHubDiscoveryClient for HttpGitHubClient {
    fn search_repositories(
        &self,
        host: &str,
        star_band: &StarBand,
        page: usize,
        per_page: usize,
        include_archived: bool,
        include_forks: bool,
    ) -> Result<Vec<DiscoveredRepository>> {
        let response = self.get_json::<SearchRepositoriesApiResponse>(self.search_url(
            host,
            star_band,
            page,
            per_page,
            include_archived,
            include_forks,
        )?)?;

        Ok(response
            .items
            .into_iter()
            .map(|item| DiscoveredRepository {
                repository: RepositoryRef {
                    host: host.into(),
                    owner: item.owner.login,
                    repo: item.name,
                },
                stars: item.stargazers_count,
                default_branch: item.default_branch,
                archived: item.archived,
                fork: item.fork,
            })
            .collect())
    }
}

fn github_token() -> Option<String> {
    std::env::var("GITHUB_TOKEN")
        .ok()
        .or_else(|| std::env::var("GH_TOKEN").ok())
        .map(|token| token.trim().to_string())
        .filter(|token| !token.is_empty())
}

fn rate_limit_sleep_duration(response: &Response, attempt: u32) -> Duration {
    let reset_seconds = response
        .headers()
        .get("x-ratelimit-reset")
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.parse::<u64>().ok());

    if let Some(reset_epoch) = reset_seconds {
        let now_epoch = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        if reset_epoch > now_epoch {
            let wait = reset_epoch - now_epoch;
            return Duration::from_secs(wait.min(120));
        }
    }

    let jitter = (attempt as u64 * 37) % 1000;
    RATE_LIMIT_RETRY_BASE * 2u32.pow(attempt) + Duration::from_millis(jitter)
}

fn compact_error_body(body: &str) -> String {
    let compact = body.split_whitespace().collect::<Vec<_>>().join(" ");
    if compact.is_empty() {
        "without response body".into()
    } else {
        compact
    }
}

fn trim_optional(value: Option<String>) -> Option<String> {
    value
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn build_repository_search_query(
    star_band: &StarBand,
    include_archived: bool,
    include_forks: bool,
) -> String {
    let mut query = vec![format!("stars:{}", render_star_band(star_band))];
    if !include_archived {
        query.push("archived:false".into());
    }
    if !include_forks {
        query.push("fork:false".into());
    }
    query.join(" ")
}

fn render_star_band(star_band: &StarBand) -> String {
    match star_band.max_stars {
        Some(max_stars) if max_stars > star_band.min_stars => {
            format!("{}..{}", star_band.min_stars, max_stars - 1)
        }
        Some(_) => format!(">={}", star_band.min_stars),
        None => format!(">={}", star_band.min_stars),
    }
}

/// GitHub's `/languages` endpoint reports byte counts per language, which is
/// the only signal for which language actually dominates a repository.
/// `BTreeMap<String, u64>`'s key iteration order is alphabetical, not
/// byte-count order, so collecting `.into_keys()` directly silently
/// discards that signal and reports languages alphabetically instead of by
/// dominance -- every downstream consumer treating `repo.languages[0]` (or
/// any small prefix) as "the primary language(s)" would be misled. Sorts by
/// byte count descending, breaking ties alphabetically for determinism.
fn languages_by_byte_count_descending(languages: BTreeMap<String, u64>) -> Vec<String> {
    let mut by_bytes: Vec<(String, u64)> = languages.into_iter().collect();
    by_bytes.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    by_bytes.into_iter().map(|(name, _)| name).collect()
}

fn normalize_parent_from_url(u: &str) -> Option<String> {
    let u = u.trim().trim_end_matches('/');
    u.strip_prefix("https://github.com/")
        .or_else(|| u.strip_prefix("http://github.com/"))
        .map(|rest| format!("github.com/{}", rest.trim_start_matches('/')))
}

#[derive(Debug, Deserialize)]
struct RepositoryApiResponse {
    html_url: String,
    clone_url: String,
    default_branch: String,
    description: Option<String>,
    homepage: Option<String>,
    license: Option<LicenseApiResponse>,
    visibility: Option<String>,
    stargazers_count: u64,
    archived: bool,
    fork: bool,
    parent: Option<ParentApiResponse>,
}

#[derive(Debug, Deserialize)]
struct ParentApiResponse {
    full_name: Option<String>,
    html_url: Option<String>,
}

#[derive(Debug, Deserialize)]
struct LicenseApiResponse {
    spdx_id: Option<String>,
    name: Option<String>,
}

#[derive(Debug, Deserialize)]
struct BranchApiResponse {
    commit: BranchCommitApiResponse,
}

#[derive(Debug, Deserialize)]
struct BranchCommitApiResponse {
    sha: String,
}

#[derive(Debug, Deserialize)]
struct TopicsApiResponse {
    #[serde(default)]
    names: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct SearchRepositoriesApiResponse {
    #[serde(default)]
    items: Vec<SearchRepositoryApiResponse>,
}

#[derive(Debug, Deserialize)]
struct SearchRepositoryApiResponse {
    owner: SearchOwnerApiResponse,
    name: String,
    stargazers_count: u64,
    default_branch: Option<String>,
    archived: bool,
    fork: bool,
}

#[derive(Debug, Deserialize)]
struct SearchOwnerApiResponse {
    login: String,
}

#[derive(Debug, Deserialize)]
struct ContentsEntry {
    #[serde(rename = "type")]
    entry_type: String,
    path: String,
}

#[derive(Debug, Deserialize)]
struct GitTreeResponse {
    #[serde(default)]
    tree: Vec<GitTreeEntry>,
}

#[derive(Debug, Deserialize)]
struct GitTreeEntry {
    path: String,
    #[serde(rename = "type")]
    entry_type: String,
}

/// Selects root-level paths ending with any of `suffixes`, sorted, capped.
fn first_root_paths_with_suffixes(
    entries: &[ContentsEntry],
    suffixes: &[&str],
    limit: usize,
) -> Vec<String> {
    let mut paths: Vec<String> = entries
        .iter()
        .filter(|entry| entry.entry_type == "file")
        .map(|entry| entry.path.clone())
        .filter(|path| {
            let lower = path.to_ascii_lowercase();
            suffixes.iter().any(|suffix| lower.ends_with(suffix))
        })
        .collect();
    paths.sort();
    paths.truncate(limit);
    paths
}

/// Prefer non-test `.sln` / `.csproj` blobs from a recursive git tree.
fn select_dotnet_paths_from_tree(entries: &[GitTreeEntry], limit: usize) -> Vec<String> {
    let mut paths: Vec<String> = entries
        .iter()
        .filter(|entry| entry.entry_type == "blob")
        .map(|entry| entry.path.clone())
        .filter(|path| {
            let lower = path.to_ascii_lowercase();
            (lower.ends_with(".csproj") || lower.ends_with(".sln"))
                && !lower.contains("/obj/")
                && !lower.contains("/bin/")
                // Secondary SDK / sample trees in polyglot monorepos.
                && !lower.contains("/sdk/")
                && !lower.contains("-sdk/")
                && !lower.contains("dot-net-sdk")
                && !lower.contains("/bindings/")
                && !lower.contains("/examples/")
                && !lower.contains("/samples/")
                && path.matches('/').count() <= 3
        })
        .collect();
    paths.sort_by(|left, right| {
        let left_test = is_likely_test_dotnet_path(left);
        let right_test = is_likely_test_dotnet_path(right);
        left_test.cmp(&right_test).then_with(|| left.cmp(right))
    });
    paths.truncate(limit);
    paths
}

fn is_likely_test_dotnet_path(path: &str) -> bool {
    let lower = path.to_ascii_lowercase();
    lower.contains(".tests.")
        || lower.contains(".test.")
        || lower.contains("/tests/")
        || lower.contains("/test/")
        || lower.ends_with("tests.csproj")
        || lower.ends_with("test.csproj")
}

fn is_dotnet_language(name: &str) -> bool {
    matches!(name, "C#" | "F#" | "Visual Basic")
}

/// Any .NET language signal in the repository language list.
fn dotnet_language_signal(languages: &[String]) -> bool {
    languages.iter().any(|lang| is_dotnet_language(lang))
}

/// .NET ranks among the top languages (by GitHub byte-count order).
fn dotnet_is_primary_language(languages: &[String]) -> bool {
    languages
        .iter()
        .take(3)
        .any(|lang| is_dotnet_language(lang))
}

fn is_js_ts_language(name: &str) -> bool {
    matches!(
        name,
        "JavaScript" | "TypeScript" | "Vue" | "Svelte" | "Astro"
    )
}

fn js_ts_is_primary_language(languages: &[String]) -> bool {
    languages.iter().take(3).any(|lang| is_js_ts_language(lang))
}

fn python_is_primary_language(languages: &[String]) -> bool {
    languages
        .iter()
        .take(3)
        .any(|lang| lang == "Python" || lang == "Jupyter Notebook")
}

fn python_manifest_path_preference(path: &str) -> i32 {
    let lower = path.replace('\\', "/").to_ascii_lowercase();
    if matches!(
        lower.as_str(),
        "pyproject.toml" | "setup.py" | "setup.cfg" | "tox.ini"
    ) {
        return 0;
    }
    if lower.contains("/examples/") || lower.contains("/samples/") || lower.contains("/benchmarks/")
    {
        return 200;
    }
    if lower.starts_with("release/")
        || lower.contains("/release/")
        || lower.contains("/packaging/")
        || lower.contains("/ci/")
    {
        return 160;
    }
    if lower.starts_with("python/") || lower.contains("/python/") {
        return 10;
    }
    if lower.starts_with("src/") {
        return 20;
    }
    if lower.contains("/packages/") {
        return 30;
    }
    50
}

/// Lower is better; keep in sync with core `package_json_path_preference`.
fn node_package_json_path_preference(path: &str) -> i32 {
    let lower = path.replace('\\', "/").to_ascii_lowercase();
    if lower == "package.json" {
        return 0;
    }
    if lower.contains("/examples/")
        || lower.contains("/samples/")
        || lower.contains("/fixtures/")
        || lower.contains("/example/")
    {
        return 200;
    }
    if lower.contains("test-suite")
        || lower.contains("test-site")
        || lower.contains("/tests/")
        || lower.contains("/__tests__/")
        || lower.contains("/e2e/")
    {
        return 180;
    }
    if lower.contains("/sdk/")
        || lower.contains("-sdk/")
        || lower.contains("/js-sdk/")
        || lower.contains("/python-sdk/")
    {
        return 150;
    }
    if lower.contains("/native/") {
        return 140;
    }
    if lower == "server/package.json" || lower.ends_with("/server/package.json") {
        return 10;
    }
    if lower == "api/package.json"
        || lower.ends_with("/api/package.json")
        || lower.contains("/apps/api/")
    {
        return 11;
    }
    if lower == "web/package.json" || lower.ends_with("/web/package.json") {
        return 12;
    }
    if lower.contains("/apps/") {
        return 20;
    }
    if lower.contains("/packages/") {
        return 25;
    }
    50
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;
    use std::time::{Duration, Instant};

    #[test]
    fn http_client_times_out_hung_requests() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener binds");
        let address = listener.local_addr().expect("listener address");
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("client connects");
            let mut request = [0_u8; 1024];
            let _ = stream.read(&mut request);
            thread::sleep(Duration::from_millis(250));
            let _ = stream.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}");
        });

        let client = Client::builder()
            .timeout(Duration::from_millis(50))
            .build()
            .expect("client builds");
        let url =
            Url::parse(&format!("http://{address}/repos/example/project")).expect("URL parses");

        let start = Instant::now();
        let err = client
            .get(url.clone())
            .send()
            .with_context(|| format!("failed to GET {}", url.as_str()))
            .expect_err("hung request should time out");
        let elapsed = start.elapsed();

        assert!(elapsed < Duration::from_secs(1));
        assert!(err.to_string().contains("failed to GET"));

        handle.join().expect("server thread completes");
    }

    #[test]
    fn first_root_paths_with_suffixes_picks_sorted_csproj_and_sln() {
        let entries = vec![
            ContentsEntry {
                entry_type: "dir".into(),
                path: "src".into(),
            },
            ContentsEntry {
                entry_type: "file".into(),
                path: "Zeta.csproj".into(),
            },
            ContentsEntry {
                entry_type: "file".into(),
                path: "Alpha.csproj".into(),
            },
            ContentsEntry {
                entry_type: "file".into(),
                path: "App.sln".into(),
            },
            ContentsEntry {
                entry_type: "file".into(),
                path: "README.md".into(),
            },
        ];
        assert_eq!(
            first_root_paths_with_suffixes(&entries, &[".csproj", ".sln"], 4),
            vec![
                "Alpha.csproj".to_string(),
                "App.sln".to_string(),
                "Zeta.csproj".to_string()
            ]
        );
    }

    #[test]
    fn select_dotnet_paths_from_tree_prefers_non_test_projects() {
        let tree = vec![
            GitTreeEntry {
                path: "tests/Unit.Tests.csproj".into(),
                entry_type: "blob".into(),
            },
            GitTreeEntry {
                path: "src/Lib/Lib.csproj".into(),
                entry_type: "blob".into(),
            },
            GitTreeEntry {
                path: "App.sln".into(),
                entry_type: "blob".into(),
            },
            GitTreeEntry {
                path: "apps/dot-net-sdk/Firecrawl/Firecrawl.csproj".into(),
                entry_type: "blob".into(),
            },
        ];
        assert_eq!(
            select_dotnet_paths_from_tree(&tree, 2),
            vec!["App.sln".to_string(), "src/Lib/Lib.csproj".to_string()]
        );
        // SDK trees are excluded entirely (polyglot monorepo guard).
        assert!(!select_dotnet_paths_from_tree(&tree, 10)
            .iter()
            .any(|path| path.contains("dot-net-sdk")));
    }

    #[test]
    fn node_package_json_path_preference_ranks_apps_over_sdks() {
        assert!(
            node_package_json_path_preference("server/package.json")
                < node_package_json_path_preference("apps/js-sdk/package.json")
        );
        assert!(
            node_package_json_path_preference("apps/api/package.json")
                < node_package_json_path_preference("examples/demo/package.json")
        );
        assert!(js_ts_is_primary_language(&[
            "TypeScript".into(),
            "Python".into()
        ]));
        assert!(!js_ts_is_primary_language(&["Python".into(), "Go".into()]));
    }

    #[test]
    fn dotnet_primary_language_requires_top_rank() {
        assert!(dotnet_is_primary_language(&[
            "C#".into(),
            "PowerShell".into()
        ]));
        assert!(!dotnet_is_primary_language(&[
            "TypeScript".into(),
            "Python".into(),
            "Rust".into(),
            "C#".into()
        ]));
        assert!(dotnet_language_signal(&["TypeScript".into(), "C#".into()]));
        assert!(!dotnet_language_signal(&[
            "TypeScript".into(),
            "Python".into()
        ]));
    }

    #[test]
    fn languages_by_byte_count_descending_orders_by_dominance_not_alphabetically() {
        // Reproduces a real case found via the audit sampler: docker/awesome-compose
        // and firecrawl/firecrawl were both misclassified into the "Rust" family
        // because repo.languages was collected from a BTreeMap (alphabetical key
        // order) instead of GitHub's actual byte-count signal, so a minor vendored
        // Rust file could outrank the repository's actual dominant language.
        let mut languages = BTreeMap::new();
        languages.insert("Rust".to_string(), 120u64);
        languages.insert("Go".to_string(), 50_000u64);
        languages.insert("Dockerfile".to_string(), 2_000u64);
        languages.insert("Shell".to_string(), 800u64);

        assert_eq!(
            languages_by_byte_count_descending(languages),
            vec!["Go", "Dockerfile", "Shell", "Rust"]
        );
    }

    #[test]
    fn languages_by_byte_count_descending_breaks_ties_alphabetically() {
        let mut languages = BTreeMap::new();
        languages.insert("Zig".to_string(), 100u64);
        languages.insert("Ada".to_string(), 100u64);

        assert_eq!(
            languages_by_byte_count_descending(languages),
            vec!["Ada", "Zig"]
        );
    }

    #[test]
    fn languages_by_byte_count_descending_handles_empty_map() {
        assert_eq!(
            languages_by_byte_count_descending(BTreeMap::new()),
            Vec::<String>::new()
        );
    }

    #[test]
    fn supplemental_root_files_cover_every_dotrepo_core_deterministic_parser() {
        // Regression guard: every one of these ecosystems has a deterministic
        // parser in dotrepo-core (see crates/dotrepo-core/src/import/mod.rs's
        // `load_first_existing_file` calls), so the crawler must actually
        // fetch the file that parser needs. Before this list was expanded,
        // only Cargo.toml/package.json/pyproject.toml/go.mod were fetched,
        // silently starving Maven, Gradle, Composer, Mix, Rebar, CMake
        // presets, Makefile, justfile, Rakefile, and setup.py/setup.cfg of
        // the one file each needed -- live crawls of real repositories
        // (e.g. facebook/zstd, nodejs/node) never detected build/test
        // commands that were plainly present in their root Makefile.
        let expected = [
            "Cargo.toml",
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "package.json",
            "pyproject.toml",
            "go.mod",
            "setup.py",
            "setup.cfg",
            "tox.ini",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "composer.json",
            "mix.exs",
            "rebar.config",
            "CMakePresets.json",
            "GNUmakefile",
            "Makefile",
            "makefile",
            "justfile",
            "Justfile",
            "Rakefile",
            "rakefile",
        ];
        for name in expected {
            assert!(
                SUPPLEMENTAL_ROOT_FILES.contains(&name),
                "SUPPLEMENTAL_ROOT_FILES must fetch {name} for its dotrepo-core parser to ever see it"
            );
        }
    }

    #[test]
    fn build_http_client_applies_timeouts_and_headers() {
        let mut headers = HeaderMap::new();
        headers.insert(USER_AGENT, HeaderValue::from_static("dotrepo-test"));
        let client = build_http_client(headers).expect("client builds");

        let err = client
            .get("http://127.0.0.1:9/")
            .send()
            .expect_err("request should fail quickly");
        let message = err.to_string().to_ascii_lowercase();
        assert!(
            message.contains("connection refused")
                || message.contains("timed out")
                || message.contains("error sending request")
        );
    }

    struct FakeGitHubClient;

    impl GitHubClient for FakeGitHubClient {
        fn fetch_repository_head(
            &self,
            repository: &RepositoryRef,
            _default_branch: Option<&str>,
        ) -> Result<RepositoryHeadSnapshot> {
            Ok(RepositoryHeadSnapshot {
                default_branch: "main".into(),
                head_sha: Some(format!("{}-sha", repository.repo)),
            })
        }

        fn fetch_repository_snapshot(
            &self,
            _repository: &RepositoryRef,
        ) -> Result<GitHubRepositorySnapshot> {
            unreachable!("refresh candidate planning should not fetch full repository snapshots")
        }

        fn fetch_repository_files(
            &self,
            _repository: &RepositoryRef,
            _default_branch: &str,
            _languages: &[String],
        ) -> Result<ConventionalRepositoryFiles> {
            unreachable!("not used in refresh candidate planning tests")
        }
    }

    #[test]
    fn refresh_candidates_from_state_uses_repository_heads() {
        let state = CrawlerStateSnapshot {
            repositories: vec![
                crate::CrawlStateRecord {
                    repository: RepositoryRef {
                        host: "github.com".into(),
                        owner: "tokio-rs".into(),
                        repo: "tokio".into(),
                    },
                    default_branch: Some("master".into()),
                    head_sha: Some("old".into()),
                    last_factual_crawl_at: Some("2026-03-20T00:00:00Z".into()),
                    last_synthesis_success_at: None,
                    last_synthesis_failure: None,
                    synthesis_model: None,
                },
                crate::CrawlStateRecord {
                    repository: RepositoryRef {
                        host: "github.com".into(),
                        owner: "fastapi".into(),
                        repo: "fastapi".into(),
                    },
                    default_branch: Some("master".into()),
                    head_sha: Some("stale".into()),
                    last_factual_crawl_at: Some("2026-03-20T00:00:00Z".into()),
                    last_synthesis_success_at: None,
                    last_synthesis_failure: None,
                    synthesis_model: None,
                },
            ],
        };

        let candidates =
            refresh_candidates_from_state_with_client(&state, &FakeGitHubClient).expect("plans");

        assert_eq!(candidates.len(), 2);
        assert_eq!(candidates[0].repository.repo, "tokio");
        assert_eq!(candidates[0].default_branch.as_deref(), Some("main"));
        assert_eq!(candidates[0].head_sha.as_deref(), Some("tokio-sha"));
        assert_eq!(candidates[1].repository.repo, "fastapi");
        assert_eq!(candidates[1].head_sha.as_deref(), Some("fastapi-sha"));
    }
}
