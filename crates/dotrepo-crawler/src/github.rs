use crate::materialize::{ConventionalRepositoryFiles, RepositoryTextFile};
use crate::{DiscoveredRepository, GitHubRepositorySnapshot, RepositoryRef, StarBand};
use anyhow::{anyhow, Context, Result};
use reqwest::blocking::{Client, Response};
use reqwest::header::{HeaderMap, HeaderName, HeaderValue, ACCEPT, AUTHORIZATION, USER_AGENT};
use reqwest::{StatusCode, Url};
use serde::de::DeserializeOwned;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::PathBuf;

const GITHUB_API_VERSION: &str = "2022-11-28";
const README_CANDIDATES: &[&str] = &[
    "README.md",
    "README.MD",
    "readme.md",
    "README.mdx",
    "README.markdown",
    "README",
];
const SUPPLEMENTAL_ROOT_FILES: &[&str] =
    &["Cargo.toml", "package.json", "pyproject.toml", "go.mod"];
const MAX_WORKFLOW_FILES: usize = 8;

pub(crate) trait GitHubClient {
    fn fetch_repository_snapshot(
        &self,
        repository: &RepositoryRef,
    ) -> Result<GitHubRepositorySnapshot>;
    fn fetch_repository_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
    ) -> Result<ConventionalRepositoryFiles>;
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

pub(crate) struct HttpGitHubClient {
    client: Client,
    api_base_url: Url,
    raw_base_url: Url,
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

        let client = Client::builder()
            .default_headers(headers)
            .build()
            .context("failed to build GitHub HTTP client")?;

        Ok(Self {
            client,
            api_base_url: Url::parse("https://api.github.com/")
                .context("failed to parse GitHub API base URL")?,
            raw_base_url: Url::parse("https://raw.githubusercontent.com/")
                .context("failed to parse GitHub raw base URL")?,
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
        let response = self
            .client
            .get(url.clone())
            .send()
            .with_context(|| format!("failed to GET {}", url.as_str()))?;
        let response = error_for_status(response, url.as_str())?;
        response
            .json()
            .with_context(|| format!("failed to decode GitHub response {}", url.as_str()))
    }

    fn get_optional_text(&self, url: Url) -> Result<Option<String>> {
        let response = self
            .client
            .get(url.clone())
            .send()
            .with_context(|| format!("failed to GET {}", url.as_str()))?;

        if response.status() == StatusCode::NOT_FOUND {
            return Ok(None);
        }

        let response = error_for_status(response, url.as_str())?;
        let text = response
            .text()
            .with_context(|| format!("failed to decode text response {}", url.as_str()))?;
        Ok(Some(text))
    }

    fn get_optional_json<T: DeserializeOwned>(&self, url: Url) -> Result<Option<T>> {
        let response = self
            .client
            .get(url.clone())
            .send()
            .with_context(|| format!("failed to GET {}", url.as_str()))?;

        if response.status() == StatusCode::NOT_FOUND {
            return Ok(None);
        }

        let response = error_for_status(response, url.as_str())?;
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
}

impl GitHubClient for HttpGitHubClient {
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
            languages: languages.into_keys().collect(),
            topics: topics.names,
            visibility: trim_optional(repo.visibility),
            stars: Some(repo.stargazers_count),
            archived: repo.archived,
            fork: repo.fork,
        })
    }

    fn fetch_repository_files(
        &self,
        repository: &RepositoryRef,
        default_branch: &str,
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

fn error_for_status(response: Response, url: &str) -> Result<Response> {
    let status = response.status();
    if status.is_success() {
        return Ok(response);
    }

    let rate_limited = status == StatusCode::TOO_MANY_REQUESTS
        || response
            .headers()
            .get("x-ratelimit-remaining")
            .and_then(|value| value.to_str().ok())
            == Some("0");
    let body = response.text().unwrap_or_default();
    if rate_limited || body.to_ascii_lowercase().contains("rate limit") {
        return Err(anyhow!(
            "GitHub API rate limited {}: HTTP {} {}",
            url,
            status.as_u16(),
            compact_error_body(&body)
        ));
    }

    Err(anyhow!(
        "GitHub request failed {}: HTTP {} {}",
        url,
        status.as_u16(),
        compact_error_body(&body)
    ))
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
        Some(max_stars) => format!("{}..{}", star_band.min_stars, max_stars),
        None => format!(">={}", star_band.min_stars),
    }
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
