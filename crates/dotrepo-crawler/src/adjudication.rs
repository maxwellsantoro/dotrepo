use anyhow::{Context, Result};
use dotrepo_core::{
    AdjudicationProvider, AdjudicationProviderResponse, AdjudicationRequest, AdjudicationTier,
    AdjudicationTierProvider,
};
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Debug, Clone)]
pub struct HttpAdjudicationProvider {
    pub endpoint: String,
    pub tier: AdjudicationTier,
    pub provider: String,
    pub model: Option<String>,
    pub api_key_env: Option<String>,
    client: Client,
}

impl HttpAdjudicationProvider {
    pub fn new(
        endpoint: impl Into<String>,
        tier: AdjudicationTier,
        provider: impl Into<String>,
        model: Option<String>,
        api_key_env: Option<String>,
    ) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(120))
            .build()
            .context("failed to build adjudication HTTP client")?;
        Ok(Self {
            endpoint: endpoint.into(),
            tier,
            provider: provider.into(),
            model,
            api_key_env,
            client,
        })
    }

    pub fn metadata(&self) -> AdjudicationTierProvider {
        AdjudicationTierProvider {
            tier: self.tier,
            provider: self.provider.clone(),
            model: self.model.clone(),
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct AdjudicationHttpRequest<'a> {
    field: &'a str,
    candidates: &'a [dotrepo_core::AdjudicationCandidate],
    provider: &'a str,
    model: Option<&'a str>,
    tier: &'a str,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AdjudicationHttpResponse {
    field: String,
    value: Option<String>,
    confidence: dotrepo_core::AdjudicationModelConfidence,
    reason: String,
    source: Option<String>,
    tokens_used: Option<u64>,
}

impl AdjudicationProvider for HttpAdjudicationProvider {
    fn tier(&self) -> AdjudicationTier {
        self.tier
    }

    fn adjudicate(&self, request: &AdjudicationRequest) -> Result<AdjudicationProviderResponse> {
        let payload = AdjudicationHttpRequest {
            field: &request.field,
            candidates: &request.candidates,
            provider: &self.provider,
            model: self.model.as_deref(),
            tier: self.tier.as_str(),
        };

        let mut builder = self
            .client
            .post(&self.endpoint)
            .json(&payload)
            .header("content-type", "application/json");
        if let Some(env_name) = self.api_key_env.as_deref() {
            if let Ok(key) = std::env::var(env_name) {
                if !key.trim().is_empty() {
                    builder = builder.bearer_auth(key.trim());
                }
            }
        }

        let response = builder
            .send()
            .with_context(|| format!("adjudication request to {} failed", self.endpoint))?
            .error_for_status()
            .with_context(|| format!("adjudication provider {} returned an error", self.endpoint))?
            .json::<AdjudicationHttpResponse>()
            .with_context(|| {
                format!(
                    "adjudication provider {} returned invalid JSON",
                    self.endpoint
                )
            })?;

        Ok(AdjudicationProviderResponse {
            response: dotrepo_core::AdjudicationModelResponse {
                field: response.field,
                value: response.value,
                confidence: response.confidence,
                reason: response.reason,
                source: response.source,
            },
            tokens_used: response.tokens_used.unwrap_or(0),
        })
    }
}

#[derive(Debug, Clone, Default)]
pub struct ResolvedAdjudicationProviders {
    pub local_primary: Option<HttpAdjudicationProvider>,
    pub local_second_opinion: Option<HttpAdjudicationProvider>,
    pub api_escalation: Option<HttpAdjudicationProvider>,
}

pub fn resolve_adjudication_providers_from_env() -> Result<ResolvedAdjudicationProviders> {
    let mut resolved = ResolvedAdjudicationProviders::default();

    if let Ok(endpoint) = std::env::var("DOTREPO_ADJUDICATION_URL") {
        let endpoint = endpoint.trim().to_string();
        if !endpoint.is_empty() {
            resolved.local_primary = Some(HttpAdjudicationProvider::new(
                endpoint,
                AdjudicationTier::LocalPrimary,
                std::env::var("DOTREPO_ADJUDICATION_PROVIDER")
                    .unwrap_or_else(|_| "local-sidecar".into()),
                std::env::var("DOTREPO_ADJUDICATION_MODEL").ok(),
                None,
            )?);
        }
    }

    if let Ok(endpoint) = std::env::var("DOTREPO_ADJUDICATION_SECOND_OPINION_URL") {
        let endpoint = endpoint.trim().to_string();
        if !endpoint.is_empty() {
            resolved.local_second_opinion = Some(HttpAdjudicationProvider::new(
                endpoint,
                AdjudicationTier::LocalSecondOpinion,
                std::env::var("DOTREPO_ADJUDICATION_SECOND_OPINION_PROVIDER")
                    .unwrap_or_else(|_| "local-second-opinion".into()),
                std::env::var("DOTREPO_ADJUDICATION_SECOND_OPINION_MODEL").ok(),
                None,
            )?);
        }
    }

    if let Ok(endpoint) = std::env::var("DOTREPO_ADJUDICATION_API_URL") {
        let endpoint = endpoint.trim().to_string();
        if !endpoint.is_empty() {
            resolved.api_escalation = Some(HttpAdjudicationProvider::new(
                endpoint,
                AdjudicationTier::ApiEscalation,
                std::env::var("DOTREPO_ADJUDICATION_API_PROVIDER")
                    .unwrap_or_else(|_| "openrouter".into()),
                std::env::var("DOTREPO_ADJUDICATION_API_MODEL").ok(),
                Some("DOTREPO_ADJUDICATION_API_KEY".into()),
            )?);
        }
    }

    Ok(resolved)
}

pub fn import_escalation_options_from_env() -> dotrepo_core::ImportEscalationOptions {
    let max_adjudication_calls = std::env::var("INDEX_MAX_ADJUDICATION_CALLS")
        .ok()
        .and_then(|value| value.trim().parse().ok())
        .unwrap_or(0);
    let enable_second_opinion = std::env::var("DOTREPO_ADJUDICATION_SECOND_OPINION_URL")
        .ok()
        .is_some_and(|value| !value.trim().is_empty());
    let enable_api_escalation = std::env::var("DOTREPO_ADJUDICATION_API_URL")
        .ok()
        .is_some_and(|value| !value.trim().is_empty());

    dotrepo_core::ImportEscalationOptions {
        max_adjudication_calls,
        enable_second_opinion,
        enable_api_escalation,
    }
}
