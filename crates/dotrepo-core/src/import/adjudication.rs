use super::{AdjudicationModelResponse, AdjudicationRequest};
use anyhow::Result;
use serde::{Deserialize, Serialize};

/// Response from an adjudication provider, including token spend telemetry.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdjudicationProviderResponse {
    pub response: AdjudicationModelResponse,
    pub tokens_used: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AdjudicationTier {
    Deterministic,
    LocalPrimary,
    LocalSecondOpinion,
    ApiEscalation,
}

impl AdjudicationTier {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Deterministic => "deterministic",
            Self::LocalPrimary => "local_primary",
            Self::LocalSecondOpinion => "local_second_opinion",
            Self::ApiEscalation => "api_escalation",
        }
    }
}

/// Provider metadata carried in crawl telemetry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AdjudicationTierProvider {
    pub tier: AdjudicationTier,
    pub provider: String,
    pub model: Option<String>,
}

/// Pluggable narrow adjudication backend for tiers 2–4.
pub trait AdjudicationProvider: Send + Sync {
    fn tier(&self) -> AdjudicationTier;
    fn adjudicate(&self, request: &AdjudicationRequest) -> Result<AdjudicationProviderResponse>;
}

/// Tier-scoped provider slot used by the escalation ladder.
pub struct TieredAdjudicationProviders<'a> {
    pub local_primary: Option<&'a dyn AdjudicationProvider>,
    pub local_second_opinion: Option<&'a dyn AdjudicationProvider>,
    pub api_escalation: Option<&'a dyn AdjudicationProvider>,
}

impl<'a> TieredAdjudicationProviders<'a> {
    pub fn provider_for_tier(
        &self,
        tier: AdjudicationTier,
    ) -> Option<&'a dyn AdjudicationProvider> {
        match tier {
            AdjudicationTier::LocalPrimary => self.local_primary,
            AdjudicationTier::LocalSecondOpinion => self.local_second_opinion,
            AdjudicationTier::ApiEscalation => self.api_escalation,
            AdjudicationTier::Deterministic => None,
        }
    }
}

/// Caps and feature flags for model escalation during import.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ImportEscalationOptions {
    pub max_adjudication_calls: usize,
    pub enable_second_opinion: bool,
    pub enable_api_escalation: bool,
}

/// No-op provider used when model tiers are disabled.
#[derive(Debug, Clone, Copy, Default)]
pub struct NoopAdjudicationProvider;

impl AdjudicationProvider for NoopAdjudicationProvider {
    fn tier(&self) -> AdjudicationTier {
        AdjudicationTier::LocalPrimary
    }

    fn adjudicate(&self, _request: &AdjudicationRequest) -> Result<AdjudicationProviderResponse> {
        anyhow::bail!("adjudication provider is disabled")
    }
}

/// Fixed-response provider for tests and deterministic harnesses.
#[derive(Debug)]
pub struct StubAdjudicationProvider {
    pub tier: AdjudicationTier,
    pub responses: Vec<AdjudicationProviderResponse>,
    next: std::sync::Mutex<usize>,
}

impl StubAdjudicationProvider {
    pub fn new(tier: AdjudicationTier, responses: Vec<AdjudicationProviderResponse>) -> Self {
        Self {
            tier,
            responses,
            next: std::sync::Mutex::new(0),
        }
    }
}

impl AdjudicationProvider for StubAdjudicationProvider {
    fn tier(&self) -> AdjudicationTier {
        self.tier
    }

    fn adjudicate(&self, _request: &AdjudicationRequest) -> Result<AdjudicationProviderResponse> {
        let mut index = self.next.lock().unwrap_or_else(|p| p.into_inner());
        let response = self
            .responses
            .get(*index)
            .ok_or_else(|| anyhow::anyhow!("stub provider exhausted"))?
            .clone();
        *index += 1;
        Ok(response)
    }
}
