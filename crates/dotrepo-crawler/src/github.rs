use crate::materialize::ConventionalRepositoryFiles;
use crate::{GitHubRepositorySnapshot, RepositoryRef};
use anyhow::{anyhow, Context, Result};
use reqwest::blocking::{Client, Response};
use reqwest::header::{HeaderMap, HeaderName, HeaderValue, ACCEPT, AUTHORIZATION, USER_AGENT};
use reqwest::{StatusCode, Url};
use serde::de::DeserializeOwned;
use serde::Deserialize;
use std::collections::BTreeMap;

const GITHUB_API_VERSION: &str = "2022-11-28";

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
        Ok(ConventionalRepositoryFiles {
            readme: self.get_optional_text(self.raw_url(
                repository,
                default_branch,
                "README.md",
            )?)?,
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
        })
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
