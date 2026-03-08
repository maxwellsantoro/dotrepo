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
    #[serde(default)]
    pub x: BTreeMap<String, toml::Value>,
    #[serde(default, rename = "trust", skip_serializing)]
    legacy_trust: Option<Trust>,
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
pub enum RecordMode {
    Native,
    Overlay,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
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
    #[serde(default)]
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

#[derive(thiserror::Error, Debug)]
pub enum ParseError {
    #[error("failed to parse manifest: {0}")]
    Toml(#[from] toml::de::Error),
    #[error(
        "trust metadata must be declared under [record.trust], not both [record.trust] and [trust]"
    )]
    ConflictingTrustPlacement,
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
}
