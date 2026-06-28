use crate::{
    CrawlDiagnostic, SynthesisPlan, SynthesisSourceDocument, SynthesizeRepositoryReport,
    SynthesizeRepositoryRequest,
};
use anyhow::{bail, Context, Result};
use dotrepo_core::{generate_basic_synthesis, plan_synthesis_write};
use reqwest::blocking::Client;
use reqwest::StatusCode;
use serde::{Deserialize, Serialize};
use std::time::Duration;

const SYNTHESIS_URL_ENV: &str = "DOTREPO_SYNTHESIS_URL";
const SYNTHESIS_API_KEY_ENV: &str = "DOTREPO_SYNTHESIS_API_KEY";
const MAX_SOURCE_DOCUMENTS: usize = 12;
const MAX_SOURCE_DOCUMENT_CHARS: usize = 32_000;
const MAX_SOURCE_TOTAL_CHARS: usize = 128_000;

trait SynthesisProvider {
    fn synthesize(
        &self,
        request: &SynthesizeRepositoryRequest,
    ) -> Result<SynthesisProviderResponse>;
}

struct HttpSynthesisProvider {
    endpoint: String,
    client: Client,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SynthesisHttpRequest<'a> {
    repository: &'a crate::RepositoryRef,
    factual_manifest: &'a dotrepo_schema::Manifest,
    sources: &'a [SynthesisSourceDocument],
    model: &'a str,
    provider: &'a str,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
#[serde(deny_unknown_fields)]
struct SynthesisProviderResponse {
    architecture: SynthesisArchitectureResponse,
    for_agents: SynthesisForAgentsResponse,
    #[serde(default)]
    tokens_used: u64,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
#[serde(deny_unknown_fields)]
struct SynthesisArchitectureResponse {
    summary: String,
    #[serde(default)]
    entry_points: Vec<String>,
    #[serde(default)]
    key_concepts: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
#[serde(deny_unknown_fields)]
struct SynthesisForAgentsResponse {
    how_to_contribute: String,
    #[serde(default)]
    gotchas: Vec<String>,
}

impl HttpSynthesisProvider {
    fn from_env() -> Result<Self> {
        let endpoint = std::env::var(SYNTHESIS_URL_ENV)
            .with_context(|| format!("{SYNTHESIS_URL_ENV} is required for synthesis"))?;
        if endpoint.trim().is_empty() {
            bail!("{SYNTHESIS_URL_ENV} must not be empty");
        }
        let client = Client::builder()
            .timeout(Duration::from_secs(120))
            .build()
            .context("failed to build synthesis HTTP client")?;
        Ok(Self {
            endpoint: endpoint.trim().into(),
            client,
        })
    }
}

impl SynthesisProvider for HttpSynthesisProvider {
    fn synthesize(
        &self,
        request: &SynthesizeRepositoryRequest,
    ) -> Result<SynthesisProviderResponse> {
        let payload = SynthesisHttpRequest {
            repository: &request.repository,
            factual_manifest: &request.manifest,
            sources: &request.sources,
            model: &request.model,
            provider: &request.provider,
        };
        let mut builder = self
            .client
            .post(&self.endpoint)
            .header("content-type", "application/json")
            .json(&payload);
        if let Ok(key) = std::env::var(SYNTHESIS_API_KEY_ENV) {
            if !key.trim().is_empty() {
                builder = builder.bearer_auth(key.trim());
            }
        }
        let response = builder
            .send()
            .with_context(|| format!("synthesis request to {} failed", self.endpoint))?;
        if response.status() == StatusCode::TOO_MANY_REQUESTS {
            bail!("synthesis provider rate limited the request (HTTP 429)");
        }
        response
            .error_for_status()
            .with_context(|| format!("synthesis provider {} returned an error", self.endpoint))?
            .json::<SynthesisProviderResponse>()
            .with_context(|| format!("synthesis provider {} returned invalid JSON", self.endpoint))
    }
}

fn validate_source_bounds(sources: &[SynthesisSourceDocument]) -> Result<()> {
    if sources.len() > MAX_SOURCE_DOCUMENTS {
        bail!("synthesis source bound exceeded: at most {MAX_SOURCE_DOCUMENTS} documents");
    }
    let mut total_chars = 0usize;
    for (index, source) in sources.iter().enumerate() {
        if source.path.trim().is_empty() {
            bail!("synthesis source path at index {index} must not be empty");
        }
        let chars = source.contents.chars().count();
        if chars > MAX_SOURCE_DOCUMENT_CHARS {
            bail!(
                "synthesis source bound exceeded for {}: at most {MAX_SOURCE_DOCUMENT_CHARS} characters",
                source.path
            );
        }
        total_chars += chars;
    }
    if total_chars > MAX_SOURCE_TOTAL_CHARS {
        bail!("synthesis source bound exceeded: at most {MAX_SOURCE_TOTAL_CHARS} total characters");
    }
    Ok(())
}

fn validate_grounded_entry_points(
    entry_points: &[String],
    sources: &[SynthesisSourceDocument],
) -> Result<()> {
    for entry_point in entry_points {
        let candidate = entry_point.trim().trim_start_matches("./");
        if candidate.is_empty()
            || candidate.starts_with('/')
            || candidate.split('/').any(|segment| segment == "..")
        {
            bail!("synthesis entry point is not a safe relative path: {entry_point}");
        }
        let grounded = sources.iter().any(|source| {
            source.path.trim().trim_start_matches("./") == candidate
                || source.contents.contains(candidate)
        });
        if !grounded {
            bail!("synthesis entry point is not grounded in source context: {entry_point}");
        }
    }
    Ok(())
}

fn synthesize_repository_with_provider(
    request: &SynthesizeRepositoryRequest,
    provider: &dyn SynthesisProvider,
) -> Result<SynthesizeRepositoryReport> {
    request.repository.validate_identity()?;
    validate_source_bounds(&request.sources)?;
    let generated_at = request
        .generated_at
        .as_deref()
        .filter(|value| !value.trim().is_empty())
        .context("synthesis generated_at must not be empty")?;
    let source_commit = request
        .source_commit
        .as_deref()
        .filter(|value| !value.trim().is_empty())
        .context("synthesis source_commit must not be empty")?;
    let response = provider.synthesize(request)?;
    validate_grounded_entry_points(&response.architecture.entry_points, &request.sources)?;

    // Start from factual commands, then admit only bounded non-factual model output.
    let mut synthesis = generate_basic_synthesis(
        &request.manifest,
        generated_at,
        source_commit,
        &request.model,
        &request.provider,
    );
    synthesis.synthesis.architecture.summary = response.architecture.summary;
    synthesis.synthesis.architecture.entry_points = response.architecture.entry_points;
    synthesis.synthesis.architecture.key_concepts = response.architecture.key_concepts;
    synthesis.synthesis.for_agents.how_to_contribute = response.for_agents.how_to_contribute;
    synthesis.synthesis.for_agents.gotchas = response.for_agents.gotchas;

    let write_plan = plan_synthesis_write(&request.record_root, &request.manifest, &synthesis)?;
    Ok(SynthesizeRepositoryReport {
        repository: request.repository.clone(),
        record_root: request.record_root.clone(),
        synthesis: Some(SynthesisPlan {
            synthesis_path: write_plan.synthesis_path.clone(),
            write_plan,
        }),
        failure: None,
        diagnostics: vec![CrawlDiagnostic::info(
            "synthesis.completed",
            format!(
                "generated bounded synthesis from {} source documents using {} tokens",
                request.sources.len(),
                response.tokens_used
            ),
        )],
    })
}

pub(crate) fn synthesize_repository_impl(
    request: &SynthesizeRepositoryRequest,
) -> Result<SynthesizeRepositoryReport> {
    if request.model.trim().is_empty() {
        bail!("synthesis model must not be empty");
    }
    if request.provider.trim().is_empty() {
        bail!("synthesis provider must not be empty");
    }
    let provider = HttpSynthesisProvider::from_env()?;
    synthesize_repository_with_provider(request, &provider)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::RepositoryRef;
    use std::cell::Cell;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    struct FakeProvider {
        calls: Cell<usize>,
    }

    impl SynthesisProvider for FakeProvider {
        fn synthesize(
            &self,
            _request: &SynthesizeRepositoryRequest,
        ) -> Result<SynthesisProviderResponse> {
            self.calls.set(self.calls.get() + 1);
            Ok(SynthesisProviderResponse {
                architecture: SynthesisArchitectureResponse {
                    summary: "A shared core powers the command and protocol surfaces.".into(),
                    entry_points: vec!["crates/example/src/lib.rs".into()],
                    key_concepts: vec!["factual authority".into()],
                },
                for_agents: SynthesisForAgentsResponse {
                    how_to_contribute: "Update behavior and its fixtures together.".into(),
                    gotchas: vec!["Keep generated guidance separate from facts.".into()],
                },
                tokens_used: 321,
            })
        }
    }

    fn request() -> SynthesizeRepositoryRequest {
        let manifest = dotrepo_schema::parse_manifest(
            r#"schema = "dotrepo/v0.1"
[record]
mode = "overlay"
status = "verified"
source = "https://github.com/example/orbit"
[repo]
name = "orbit"
description = "An example repository"
build = "cargo build --workspace"
test = "cargo test --workspace"
"#,
        )
        .expect("manifest parses");
        SynthesizeRepositoryRequest {
            record_root: std::env::temp_dir().join("dotrepo-synthesis-plan"),
            repository: RepositoryRef {
                host: "github.com".into(),
                owner: "example".into(),
                repo: "orbit".into(),
            },
            manifest,
            sources: vec![SynthesisSourceDocument {
                path: "README.md".into(),
                contents: "# Orbit\n\nAn example repository. Start in crates/example/src/lib.rs."
                    .into(),
            }],
            generated_at: Some("2026-06-28T12:00:00Z".into()),
            source_commit: Some("abc123".into()),
            model: "research-model".into(),
            provider: "sidecar".into(),
        }
    }

    #[test]
    fn provider_output_builds_valid_plan_without_overwriting_factual_commands() {
        let provider = FakeProvider {
            calls: Cell::new(0),
        };

        let report =
            synthesize_repository_with_provider(&request(), &provider).expect("synthesis succeeds");
        let plan = report.synthesis.expect("synthesis plan");

        assert_eq!(provider.calls.get(), 1);
        assert_eq!(
            plan.write_plan.synthesis.synthesis.for_agents.how_to_build,
            "cargo build --workspace"
        );
        assert_eq!(
            plan.write_plan.synthesis.synthesis.for_agents.how_to_test,
            "cargo test --workspace"
        );
        assert_eq!(
            plan.write_plan
                .synthesis
                .synthesis
                .architecture
                .entry_points,
            ["crates/example/src/lib.rs"]
        );
        assert_eq!(report.diagnostics[0].code, "synthesis.completed");
    }

    #[test]
    fn source_bounds_fail_before_calling_provider() {
        let provider = FakeProvider {
            calls: Cell::new(0),
        };
        let mut request = request();
        request.sources[0].contents = "x".repeat(MAX_SOURCE_DOCUMENT_CHARS + 1);

        let error = synthesize_repository_with_provider(&request, &provider)
            .expect_err("oversized context must fail");

        assert!(error.to_string().contains("source bound exceeded"));
        assert_eq!(provider.calls.get(), 0);
    }

    #[test]
    fn ungrounded_or_unknown_provider_output_is_rejected() {
        let unknown_field = serde_json::from_str::<SynthesisProviderResponse>(
            r#"{"architecture":{"summary":"Summary","entryPoints":[],"keyConcepts":[]},"forAgents":{"howToBuild":"make","howToContribute":"Contribute.","gotchas":[]}}"#,
        )
        .expect_err("provider cannot add factual command fields");
        assert!(unknown_field.to_string().contains("unknown field"));

        let provider = FakeProvider {
            calls: Cell::new(0),
        };
        let mut request = request();
        request.sources[0].contents = "# Orbit\n\nNo entry points are cited.".into();
        let error = synthesize_repository_with_provider(&request, &provider)
            .expect_err("ungrounded entry point must fail");
        assert!(error.to_string().contains("not grounded"));
    }

    #[test]
    fn http_provider_sends_grounded_context_and_parses_bounded_fields() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener binds");
        let address = listener.local_addr().expect("listener address");
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("request accepted");
            let mut bytes = Vec::new();
            let mut buffer = [0u8; 4096];
            loop {
                let count = stream.read(&mut buffer).expect("request read");
                if count == 0 {
                    break;
                }
                bytes.extend_from_slice(&buffer[..count]);
                let text = String::from_utf8_lossy(&bytes);
                let Some((headers, body)) = text.split_once("\r\n\r\n") else {
                    continue;
                };
                let content_length = headers
                    .lines()
                    .find_map(|line| {
                        line.to_ascii_lowercase()
                            .strip_prefix("content-length: ")
                            .and_then(|value| value.parse::<usize>().ok())
                    })
                    .unwrap_or(0);
                if body.len() >= content_length {
                    break;
                }
            }
            let request_text = String::from_utf8(bytes).expect("request is UTF-8");
            assert!(request_text.contains("\"factualManifest\""));
            assert!(request_text.contains("\"path\":\"README.md\""));
            assert!(request_text.contains("\"model\":\"research-model\""));

            let body = r#"{"architecture":{"summary":"Shared core architecture.","entryPoints":["src/lib.rs"],"keyConcepts":["facts first"]},"forAgents":{"howToContribute":"Add tests with changes.","gotchas":[]},"tokensUsed":17}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            )
            .expect("response written");
        });
        let provider = HttpSynthesisProvider {
            endpoint: format!("http://{address}"),
            client: Client::builder()
                .timeout(Duration::from_secs(2))
                .build()
                .expect("client builds"),
        };

        let response = provider.synthesize(&request()).expect("provider succeeds");

        assert_eq!(response.architecture.summary, "Shared core architecture.");
        assert_eq!(response.tokens_used, 17);
        server.join().expect("server completes");
    }
}
