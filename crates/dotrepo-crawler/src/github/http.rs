//! Bounded GET transport and rate-limit retries. Content decoding stays fail-closed.

use super::HttpGitHubClient;
use anyhow::{anyhow, Context, Result};
use reqwest::blocking::{Client, Response};
use reqwest::header::HeaderMap;
use reqwest::{StatusCode, Url};
use std::time::Duration;

const GITHUB_HTTP_TIMEOUT: Duration = Duration::from_secs(30);
const GITHUB_HTTP_CONNECT_TIMEOUT: Duration = Duration::from_secs(10);
// Shared across transport and rate-limit failures, not a budget per category.
const MAX_HTTP_RETRIES: u32 = 3;
const RETRY_BASE: Duration = Duration::from_secs(2);

impl HttpGitHubClient {
    pub(super) fn send_with_retry(&self, url: Url) -> Result<Response> {
        self.send_with_retry_using(url, std::thread::sleep)
    }

    fn send_with_retry_using(&self, url: Url, mut sleep: impl FnMut(Duration)) -> Result<Response> {
        let mut retries = 0;
        loop {
            // Count attempts even when no response arrives. Received bytes remain
            // the existing Content-Length proxy, not a wire-traffic measurement.
            self.network.borrow_mut().requests += 1;
            let response = match self.client.get(url.clone()).send() {
                Ok(response) => response,
                Err(error) => {
                    let retryable = !error.is_builder()
                        && !error.is_redirect()
                        && (error.is_timeout() || error.is_connect() || error.is_request());
                    let error = anyhow::Error::new(error);
                    if !retryable || retries >= MAX_HTTP_RETRIES {
                        // Callers retain err.to_string(); include the underlying
                        // cause here instead of losing it behind a context chain.
                        return Err(anyhow!(
                            "failed to GET {} after {} retries: {error:#}",
                            url,
                            retries
                        ));
                    }
                    let delay = retry_backoff(retries);
                    eprintln!(
                        "dotrepo-crawler: GET transport failure on {} (retry {}/{}), sleeping {:.1}s: {error:#}",
                        url.path(), retries + 1, MAX_HTTP_RETRIES, delay.as_secs_f64()
                    );
                    sleep(delay);
                    retries += 1;
                    continue;
                }
            };
            self.network.borrow_mut().bytes += response.content_length().unwrap_or(0);

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
            if !is_rate_limited || retries >= MAX_HTTP_RETRIES {
                let body = response.text().unwrap_or_default();
                if is_rate_limited {
                    return Err(anyhow!(
                        "GitHub API rate limited after {} retries {}: HTTP {} {}",
                        retries,
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

            let delay = rate_limit_sleep_duration(&response, retries);
            let _ = response.text();
            eprintln!(
                "dotrepo-crawler: rate limited on {} (retry {}/{}), sleeping {:.1}s",
                url.path(),
                retries + 1,
                MAX_HTTP_RETRIES,
                delay.as_secs_f64()
            );
            sleep(delay);
            retries += 1;
        }
    }
}

pub(super) fn build_http_client(headers: HeaderMap) -> Result<Client> {
    Client::builder()
        .default_headers(headers)
        .connect_timeout(GITHUB_HTTP_CONNECT_TIMEOUT)
        .timeout(GITHUB_HTTP_TIMEOUT)
        .build()
        .context("failed to build GitHub HTTP client")
}

fn retry_backoff(retries: u32) -> Duration {
    let jitter = (u64::from(retries) * 37) % 1000;
    RETRY_BASE * 2u32.pow(retries) + Duration::from_millis(jitter)
}

fn rate_limit_sleep_duration(response: &Response, retries: u32) -> Duration {
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
            return Duration::from_secs((reset_epoch - now_epoch).min(120));
        }
    }
    retry_backoff(retries)
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
mod tests;
