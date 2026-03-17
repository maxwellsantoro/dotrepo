use dotrepo_core::{get_synthesis, validate_index_root, write_synthesis, IndexFindingSeverity};
use dotrepo_schema::{
    render_synthesis_document, SynthesisArchitecture, SynthesisDocument, SynthesisForAgents,
    SynthesisMode, SynthesisRecord, SYNTHESIS_SCHEMA,
};
use std::fs;
use std::path::PathBuf;

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-core-synthesis-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

fn record_toml(build: Option<&str>, test: Option<&str>) -> String {
    let build_line = build
        .map(|value| format!("build = \"{}\"\n", value))
        .unwrap_or_default();
    let test_line = test
        .map(|value| format!("test = \"{}\"\n", value))
        .unwrap_or_default();
    format!(
        r#"schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"
generated_at = "2026-03-17T12:00:00Z"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
homepage = "https://github.com/example/orbit"
{build_line}{test_line}"#
    )
}

fn sample_synthesis(how_to_build: &str, how_to_test: &str) -> SynthesisDocument {
    SynthesisDocument {
        schema: SYNTHESIS_SCHEMA.into(),
        synthesis: SynthesisRecord {
            generated_at: "2026-03-17T12:30:00Z".into(),
            source_commit: "57c190d5".into(),
            model: "glm-4.7".into(),
            provider: "z.ai".into(),
            mode: SynthesisMode::Generated,
            architecture: SynthesisArchitecture {
                summary: "Thin CLI, MCP, and public surfaces over a shared trust-aware core."
                    .into(),
                entry_points: vec![
                    "crates/dotrepo-cli/src/main.rs".into(),
                    "crates/dotrepo-core/src/lib.rs".into(),
                ],
                key_concepts: vec!["factual-first".into(), "claim-aware selection".into()],
            },
            for_agents: SynthesisForAgents {
                how_to_build: how_to_build.into(),
                how_to_test: how_to_test.into(),
                how_to_contribute: "Update fixtures and docs with the behavioral change.".into(),
                gotchas: vec!["Public apiVersion stays v0.".into()],
            },
        },
    }
}

#[test]
fn write_synthesis_and_get_synthesis_round_trip_against_record_root() {
    let root = temp_dir("round-trip");
    fs::write(
        root.join("record.toml"),
        record_toml(
            Some("cargo build --workspace"),
            Some("cargo test --workspace"),
        ),
    )
    .expect("record written");

    let synthesis = sample_synthesis("cargo build --workspace", "cargo test --workspace");
    let plan = write_synthesis(&root, &synthesis).expect("synthesis plan builds");
    fs::write(&plan.synthesis_path, &plan.synthesis_text).expect("synthesis written");

    let report = get_synthesis(&root).expect("synthesis report loads");
    assert_eq!(report.synthesis_path, "synthesis.toml");
    assert_eq!(report.synthesis, synthesis);

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn write_synthesis_rejects_conflicts_with_factual_build_or_test() {
    let root = temp_dir("conflict");
    fs::write(
        root.join("record.toml"),
        record_toml(
            Some("cargo build --workspace"),
            Some("cargo test --workspace"),
        ),
    )
    .expect("record written");

    let err = write_synthesis(
        &root,
        &sample_synthesis("make build", "cargo test --workspace"),
    )
    .expect_err("conflicting build guidance should fail");
    assert!(err
        .to_string()
        .contains("synthesis.for_agents.how_to_build conflicts with factual repo.build"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_accepts_optional_valid_synthesis_toml() {
    let root = temp_dir("index-valid");
    let record_dir = root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        record_toml(
            Some("cargo build --workspace"),
            Some("cargo test --workspace"),
        ),
    )
    .expect("record written");
    fs::write(
        record_dir.join("evidence.md"),
        "# Evidence\n\n- imported from upstream.\n",
    )
    .expect("evidence written");
    fs::write(
        record_dir.join("synthesis.toml"),
        render_synthesis_document(&sample_synthesis(
            "cargo build --workspace",
            "cargo test --workspace",
        ))
        .expect("synthesis renders"),
    )
    .expect("synthesis written");

    let findings = validate_index_root(&root).expect("index validates");
    assert!(
        findings
            .iter()
            .all(|finding| finding.severity == IndexFindingSeverity::Warning),
        "optional synthesis should not introduce index errors: {findings:#?}"
    );
    assert!(
        findings.iter().all(|finding| {
            finding.path != PathBuf::from("repos/github.com/example/orbit/synthesis.toml")
        }),
        "valid synthesis should not produce synthesis-specific findings: {findings:#?}"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_reports_invalid_synthesis_without_requiring_it() {
    let root = temp_dir("index-invalid");
    let record_dir = root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        record_toml(
            Some("cargo build --workspace"),
            Some("cargo test --workspace"),
        ),
    )
    .expect("record written");
    fs::write(
        record_dir.join("evidence.md"),
        "# Evidence\n\n- imported from upstream.\n",
    )
    .expect("evidence written");
    fs::write(
        record_dir.join("synthesis.toml"),
        render_synthesis_document(&SynthesisDocument {
            schema: SYNTHESIS_SCHEMA.into(),
            synthesis: SynthesisRecord {
                generated_at: "not-a-timestamp".into(),
                source_commit: "57c190d5".into(),
                model: "glm-4.7".into(),
                provider: "z.ai".into(),
                mode: SynthesisMode::Generated,
                architecture: SynthesisArchitecture {
                    summary: "Thin CLI, MCP, and public surfaces over a shared trust-aware core."
                        .into(),
                    entry_points: vec!["crates/dotrepo-cli/src/main.rs".into()],
                    key_concepts: vec!["factual-first".into()],
                },
                for_agents: SynthesisForAgents {
                    how_to_build: "cargo build --workspace".into(),
                    how_to_test: "cargo test --workspace".into(),
                    how_to_contribute: "Update fixtures and docs.".into(),
                    gotchas: vec!["Keep public apiVersion at v0.".into()],
                },
            },
        })
        .expect("invalid synthesis renders"),
    )
    .expect("invalid synthesis written");

    let findings = validate_index_root(&root).expect("index validates");
    assert!(findings.iter().any(|finding| finding.path
        == PathBuf::from("repos/github.com/example/orbit/synthesis.toml")
        && finding.message.contains("synthesis.generated_at")));

    fs::remove_dir_all(root).expect("temp dir removed");
}
