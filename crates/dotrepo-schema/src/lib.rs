use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Manifest {
    pub schema: String,
    pub record: Record,
    pub repo: Repo,
    #[serde(default)]
    pub owners: Option<Owners>,
    #[serde(default)]
    pub docs: Option<Docs>,
    #[serde(default)]
    pub readme: Option<Readme>,
    #[serde(default)]
    pub compat: Option<Compat>,
    #[serde(default)]
    pub relations: Option<Relations>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub x: BTreeMap<String, toml::Value>,
    #[serde(default, rename = "trust", skip_serializing)]
    legacy_trust: Option<Trust>,
}

impl Manifest {
    pub fn new(record: Record, repo: Repo) -> Self {
        Self {
            schema: "dotrepo/v0.1".into(),
            record,
            repo,
            owners: None,
            docs: None,
            readme: None,
            compat: None,
            relations: None,
            x: BTreeMap::new(),
            legacy_trust: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Record {
    pub mode: RecordMode,
    pub status: RecordStatus,
    #[serde(default)]
    pub source: Option<String>,
    #[serde(default)]
    pub generated_at: Option<String>,
    #[serde(default)]
    pub trust: Option<Trust>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[derive(PartialEq, Eq)]
pub enum RecordMode {
    Native,
    Overlay,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[derive(PartialEq, Eq)]
pub enum RecordStatus {
    Draft,
    Imported,
    Inferred,
    Reviewed,
    Verified,
    Canonical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Repo {
    pub name: String,
    pub description: String,
    #[serde(default)]
    pub homepage: Option<String>,
    #[serde(default)]
    pub license: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub visibility: Option<String>,
    #[serde(default)]
    pub languages: Vec<String>,
    #[serde(default)]
    pub build: Option<String>,
    #[serde(default)]
    pub test: Option<String>,
    #[serde(default)]
    pub topics: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Owners {
    #[serde(default)]
    pub maintainers: Vec<String>,
    #[serde(default)]
    pub team: Option<String>,
    #[serde(default)]
    pub security_contact: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Docs {
    #[serde(default)]
    pub root: Option<String>,
    #[serde(default)]
    pub getting_started: Option<String>,
    #[serde(default)]
    pub architecture: Option<String>,
    #[serde(default)]
    pub api: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Readme {
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub tagline: Option<String>,
    #[serde(default)]
    pub sections: Vec<String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub custom_sections: BTreeMap<String, ReadmeCustomSection>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadmeCustomSection {
    #[serde(default)]
    pub content: Option<String>,
    #[serde(default)]
    pub path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Compat {
    #[serde(default)]
    pub github: Option<GitHubCompat>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitHubCompat {
    #[serde(default)]
    pub codeowners: Option<CompatMode>,
    #[serde(default)]
    pub security: Option<CompatMode>,
    #[serde(default)]
    pub contributing: Option<CompatMode>,
    #[serde(default)]
    pub pull_request_template: Option<CompatMode>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[derive(PartialEq, Eq)]
pub enum CompatMode {
    Generate,
    Skip,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trust {
    #[serde(default)]
    pub confidence: Option<String>,
    #[serde(default)]
    pub provenance: Vec<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Relations {
    #[serde(default)]
    pub references: Vec<String>,
}

pub const SYNTHESIS_SCHEMA: &str = "dotrepo-synthesis/v0";
pub const SYNTHESIS_SUMMARY_MAX_CHARS: usize = 500;
pub const SYNTHESIS_GUIDANCE_MAX_CHARS: usize = 200;
pub const SYNTHESIS_LIST_MAX_ITEMS: usize = 8;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SynthesisDocument {
    pub schema: String,
    pub synthesis: SynthesisRecord,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SynthesisRecord {
    pub generated_at: String,
    pub source_commit: String,
    pub model: String,
    pub provider: String,
    pub mode: SynthesisMode,
    pub architecture: SynthesisArchitecture,
    pub for_agents: SynthesisForAgents,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum SynthesisMode {
    Generated,
    Contributed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SynthesisArchitecture {
    pub summary: String,
    #[serde(default)]
    pub entry_points: Vec<String>,
    #[serde(default)]
    pub key_concepts: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SynthesisForAgents {
    pub how_to_build: String,
    pub how_to_test: String,
    pub how_to_contribute: String,
    #[serde(default)]
    pub gotchas: Vec<String>,
}

#[derive(thiserror::Error, Debug)]
pub enum ParseError {
    #[error("failed to parse manifest: {0}")]
    Toml(#[from] toml::de::Error),
    #[error(
        "trust metadata must be declared under [record.trust], not both [record.trust] and [trust]"
    )]
    ConflictingTrustPlacement,
}

#[derive(thiserror::Error, Debug)]
pub enum RenderError {
    #[error("failed to serialize manifest: {0}")]
    Toml(#[from] toml::ser::Error),
}

#[derive(thiserror::Error, Debug)]
pub enum SynthesisParseError {
    #[error("failed to parse synthesis document: {0}")]
    Toml(#[from] toml::de::Error),
}

#[derive(thiserror::Error, Debug)]
pub enum SynthesisRenderError {
    #[error("failed to serialize synthesis document: {0}")]
    Toml(#[from] toml::ser::Error),
}

#[derive(thiserror::Error, Debug, PartialEq, Eq)]
pub enum SynthesisValidationError {
    #[error("unsupported synthesis schema `{found}`; expected {expected}")]
    UnsupportedSchema {
        found: String,
        expected: &'static str,
    },
    #[error("{field} must not be empty")]
    EmptyField { field: &'static str },
    #[error("{field} must not exceed {max_chars} characters")]
    FieldTooLong {
        field: &'static str,
        max_chars: usize,
    },
    #[error("{field} must not contain more than {max_items} items")]
    TooManyItems {
        field: &'static str,
        max_items: usize,
    },
    #[error("{field}[{index}] must not be empty")]
    EmptyListItem { field: &'static str, index: usize },
}

pub fn parse_manifest(input: &str) -> Result<Manifest, ParseError> {
    let mut manifest = toml::from_str::<Manifest>(input)?;

    match (
        manifest.record.trust.is_some(),
        manifest.legacy_trust.is_some(),
    ) {
        (true, true) => Err(ParseError::ConflictingTrustPlacement),
        (false, true) => {
            manifest.record.trust = manifest.legacy_trust.take();
            Ok(manifest)
        }
        _ => Ok(manifest),
    }
}

pub fn render_manifest(manifest: &Manifest) -> Result<String, RenderError> {
    Ok(toml::to_string_pretty(manifest)?)
}

pub fn parse_synthesis_document(input: &str) -> Result<SynthesisDocument, SynthesisParseError> {
    Ok(toml::from_str::<SynthesisDocument>(input)?)
}

pub fn render_synthesis_document(
    synthesis: &SynthesisDocument,
) -> Result<String, SynthesisRenderError> {
    Ok(toml::to_string_pretty(synthesis)?)
}

fn validate_non_empty(field: &'static str, value: &str) -> Result<(), SynthesisValidationError> {
    if value.trim().is_empty() {
        return Err(SynthesisValidationError::EmptyField { field });
    }
    Ok(())
}

fn validate_bounded_text(
    field: &'static str,
    value: &str,
    max_chars: usize,
) -> Result<(), SynthesisValidationError> {
    validate_non_empty(field, value)?;
    if value.chars().count() > max_chars {
        return Err(SynthesisValidationError::FieldTooLong { field, max_chars });
    }
    Ok(())
}

fn validate_bounded_list(
    field: &'static str,
    values: &[String],
) -> Result<(), SynthesisValidationError> {
    if values.len() > SYNTHESIS_LIST_MAX_ITEMS {
        return Err(SynthesisValidationError::TooManyItems {
            field,
            max_items: SYNTHESIS_LIST_MAX_ITEMS,
        });
    }

    for (index, value) in values.iter().enumerate() {
        if value.trim().is_empty() {
            return Err(SynthesisValidationError::EmptyListItem { field, index });
        }
    }

    Ok(())
}

pub fn validate_synthesis_document(
    synthesis: &SynthesisDocument,
) -> Result<(), SynthesisValidationError> {
    if synthesis.schema.trim() != SYNTHESIS_SCHEMA {
        return Err(SynthesisValidationError::UnsupportedSchema {
            found: synthesis.schema.clone(),
            expected: SYNTHESIS_SCHEMA,
        });
    }

    validate_non_empty("synthesis.generated_at", &synthesis.synthesis.generated_at)?;
    validate_non_empty(
        "synthesis.source_commit",
        &synthesis.synthesis.source_commit,
    )?;
    validate_non_empty("synthesis.model", &synthesis.synthesis.model)?;
    validate_non_empty("synthesis.provider", &synthesis.synthesis.provider)?;
    validate_bounded_text(
        "synthesis.architecture.summary",
        &synthesis.synthesis.architecture.summary,
        SYNTHESIS_SUMMARY_MAX_CHARS,
    )?;
    validate_bounded_text(
        "synthesis.for_agents.how_to_build",
        &synthesis.synthesis.for_agents.how_to_build,
        SYNTHESIS_GUIDANCE_MAX_CHARS,
    )?;
    validate_bounded_text(
        "synthesis.for_agents.how_to_test",
        &synthesis.synthesis.for_agents.how_to_test,
        SYNTHESIS_GUIDANCE_MAX_CHARS,
    )?;
    validate_bounded_text(
        "synthesis.for_agents.how_to_contribute",
        &synthesis.synthesis.for_agents.how_to_contribute,
        SYNTHESIS_GUIDANCE_MAX_CHARS,
    )?;
    validate_bounded_list(
        "synthesis.architecture.entry_points",
        &synthesis.synthesis.architecture.entry_points,
    )?;
    validate_bounded_list(
        "synthesis.architecture.key_concepts",
        &synthesis.synthesis.architecture.key_concepts,
    )?;
    validate_bounded_list(
        "synthesis.for_agents.gotchas",
        &synthesis.synthesis.for_agents.gotchas,
    )?;

    Ok(())
}

pub fn scaffold_manifest(repo_name: &str) -> Result<String, RenderError> {
    let mut manifest = Manifest::new(
        Record {
            mode: RecordMode::Native,
            status: RecordStatus::Draft,
            source: None,
            generated_at: None,
            trust: Some(Trust {
                confidence: Some("low".into()),
                provenance: vec!["inferred".into()],
                notes: Some("Machine-generated scaffold — review and update trust before publishing.".into()),
            }),
        },
        Repo {
            name: repo_name.into(),
            description: "TODO: describe this repository".into(),
            homepage: None,
            license: None,
            status: None,
            visibility: None,
            languages: Vec::new(),
            build: None,
            test: None,
            topics: Vec::new(),
        },
    );
    manifest.owners = Some(Owners {
        maintainers: Vec::new(),
        team: None,
        security_contact: None,
    });
    manifest.readme = Some(Readme {
        title: Some(repo_name.into()),
        tagline: None,
        sections: vec!["overview".into(), "security".into()],
        custom_sections: BTreeMap::new(),
    });
    manifest.compat = Some(Compat {
        github: Some(GitHubCompat {
            codeowners: Some(CompatMode::Skip),
            security: Some(CompatMode::Skip),
            contributing: Some(CompatMode::Skip),
            pull_request_template: Some(CompatMode::Skip),
        }),
    });
    render_manifest(&manifest)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_manifest_lifts_legacy_top_level_trust() {
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[trust]
confidence = "high"
provenance = ["declared"]
"#,
        )
        .expect("manifest parses");

        let trust = manifest
            .record
            .trust
            .expect("trust normalized under record");
        assert_eq!(trust.confidence.as_deref(), Some("high"));
        assert_eq!(trust.provenance, vec!["declared"]);
    }

    #[test]
    fn parse_manifest_rejects_split_trust_sections() {
        let err = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[trust]
confidence = "medium"
provenance = ["imported"]
"#,
        )
        .expect_err("split trust placement should fail");

        assert!(matches!(err, ParseError::ConflictingTrustPlacement));
    }

    #[test]
    fn scaffold_manifest_renders_parseable_manifest() {
        let scaffold = scaffold_manifest("orbit").expect("scaffold renders");
        let manifest = parse_manifest(&scaffold).expect("scaffold parses");

        assert_eq!(manifest.record.mode, RecordMode::Native);
        assert_eq!(manifest.record.status, RecordStatus::Draft);
        assert_eq!(manifest.repo.name, "orbit");
        assert_eq!(
            manifest
                .record
                .trust
                .as_ref()
                .and_then(|trust| trust.confidence.as_deref()),
            Some("low")
        );
        assert_eq!(
            manifest
                .compat
                .as_ref()
                .and_then(|compat| compat.github.as_ref())
                .and_then(|github| github.codeowners.as_ref()),
            Some(&CompatMode::Skip)
        );
    }

    #[test]
    fn synthesis_document_round_trips_through_parse_and_render() {
        let synthesis = SynthesisDocument {
            schema: SYNTHESIS_SCHEMA.into(),
            synthesis: SynthesisRecord {
                generated_at: "2026-03-17T12:00:00Z".into(),
                source_commit: "57c190d5".into(),
                model: "glm-4.7".into(),
                provider: "z.ai".into(),
                mode: SynthesisMode::Generated,
                architecture: SynthesisArchitecture {
                    summary: "CLI-first release tooling for repository metadata.".into(),
                    entry_points: vec!["crates/dotrepo-cli/src/main.rs".into()],
                    key_concepts: vec!["factual-first".into(), "claim-aware precedence".into()],
                },
                for_agents: SynthesisForAgents {
                    how_to_build: "cargo build --workspace".into(),
                    how_to_test: "cargo test --workspace".into(),
                    how_to_contribute: "Update fixtures with the code change.".into(),
                    gotchas: vec!["Public apiVersion stays v0.".into()],
                },
            },
        };

        let rendered = render_synthesis_document(&synthesis).expect("synthesis renders");
        let reparsed = parse_synthesis_document(&rendered).expect("synthesis reparses");
        assert_eq!(reparsed, synthesis);
        validate_synthesis_document(&reparsed).expect("synthesis validates");
    }

    #[test]
    fn synthesis_validation_rejects_oversized_and_empty_fields() {
        let err = validate_synthesis_document(&SynthesisDocument {
            schema: SYNTHESIS_SCHEMA.into(),
            synthesis: SynthesisRecord {
                generated_at: "2026-03-17T12:00:00Z".into(),
                source_commit: "57c190d5".into(),
                model: "glm-4.7".into(),
                provider: "z.ai".into(),
                mode: SynthesisMode::Generated,
                architecture: SynthesisArchitecture {
                    summary: "x".repeat(SYNTHESIS_SUMMARY_MAX_CHARS + 1),
                    entry_points: vec!["entry".into()],
                    key_concepts: vec!["concept".into()],
                },
                for_agents: SynthesisForAgents {
                    how_to_build: "cargo build".into(),
                    how_to_test: "cargo test".into(),
                    how_to_contribute: "   ".into(),
                    gotchas: vec!["gotcha".into()],
                },
            },
        })
        .expect_err("invalid synthesis should fail validation");

        assert!(matches!(
            err,
            SynthesisValidationError::FieldTooLong {
                field: "synthesis.architecture.summary",
                ..
            } | SynthesisValidationError::EmptyField {
                field: "synthesis.for_agents.how_to_contribute"
            }
        ));

        let empty_field_err = validate_synthesis_document(&SynthesisDocument {
            schema: SYNTHESIS_SCHEMA.into(),
            synthesis: SynthesisRecord {
                generated_at: "2026-03-17T12:00:00Z".into(),
                source_commit: "57c190d5".into(),
                model: "glm-4.7".into(),
                provider: "z.ai".into(),
                mode: SynthesisMode::Generated,
                architecture: SynthesisArchitecture {
                    summary: "Valid summary".into(),
                    entry_points: vec!["entry".into()],
                    key_concepts: vec!["concept".into()],
                },
                for_agents: SynthesisForAgents {
                    how_to_build: "cargo build".into(),
                    how_to_test: "cargo test".into(),
                    how_to_contribute: "   ".into(),
                    gotchas: vec!["gotcha".into()],
                },
            },
        })
        .expect_err("empty contribution guidance should fail");
        assert!(matches!(
            empty_field_err,
            SynthesisValidationError::EmptyField {
                field: "synthesis.for_agents.how_to_contribute"
            }
        ));
    }
}
