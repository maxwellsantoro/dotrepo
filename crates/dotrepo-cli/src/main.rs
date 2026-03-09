use anyhow::{bail, Result};
use clap::{Parser, Subcommand, ValueEnum};
use dotrepo_core::{
    detect_unmanaged_files, generate_check_repository, import_repository,
    load_manifest_document, load_manifest_from_root, managed_outputs, query_repository,
    trust_repository, validate_index_root, validate_manifest, validate_repository, ImportMode,
    IndexFindingSeverity,
};
use dotrepo_schema::scaffold_manifest as render_scaffold_manifest;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::process;
use thiserror::Error;

#[derive(Parser)]
#[command(name = "dotrepo")]
#[command(about = "reference cli for the dotrepo protocol")]
struct Cli {
    #[arg(long, default_value = ".")]
    root: PathBuf,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    Init {
        #[arg(long)]
        force: bool,
    },
    Import {
        #[arg(long, value_enum, default_value_t = ImportModeArg::Native)]
        mode: ImportModeArg,
        #[arg(long)]
        source: Option<String>,
        #[arg(long)]
        force: bool,
    },
    Validate,
    ValidateIndex {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
    },
    Query {
        path: String,
        #[arg(long, conflicts_with = "raw")]
        json: bool,
        #[arg(long, conflicts_with = "json")]
        raw: bool,
    },
    Generate {
        #[arg(long)]
        check: bool,
    },
    Doctor,
    Trust,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum ImportModeArg {
    Native,
    Overlay,
}

impl From<ImportModeArg> for ImportMode {
    fn from(value: ImportModeArg) -> Self {
        match value {
            ImportModeArg::Native => ImportMode::Native,
            ImportModeArg::Overlay => ImportMode::Overlay,
        }
    }
}

#[derive(Debug, Error)]
#[error("{message}")]
struct CliExit {
    code: i32,
    message: String,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        let code = err
            .downcast_ref::<CliExit>()
            .map(|err| err.code)
            .unwrap_or(1);
        process::exit(code);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Init { force } => cmd_init(cli.root, force),
        Command::Import {
            mode,
            source,
            force,
        } => cmd_import(cli.root, mode, source, force),
        Command::Validate => cmd_validate(cli.root),
        Command::ValidateIndex { index_root } => cmd_validate_index(index_root),
        Command::Query { path, json, raw } => cmd_query(cli.root, &path, json, raw),
        Command::Generate { check } => cmd_generate(cli.root, check),
        Command::Doctor => cmd_doctor(cli.root),
        Command::Trust => cmd_trust(cli.root),
    }
}

fn cmd_validate(root: PathBuf) -> Result<()> {
    let report = validate_repository(&root);
    if !report.valid {
        return Err(CliExit {
            code: 1,
            message: format!(
                "manifest invalid:\n{}",
                report
                    .diagnostics
                    .into_iter()
                    .map(|diagnostic| format!("- [{}] {}", diagnostic.source, diagnostic.message))
                    .collect::<Vec<_>>()
                    .join("\n")
            ),
        }
        .into());
    }
    println!("manifest valid");
    Ok(())
}

fn cmd_init(root: PathBuf, force: bool) -> Result<()> {
    let manifest_path = root.join(".repo");
    if manifest_path.exists() && !force {
        bail!(
            "{} already exists; rerun with --force to overwrite it",
            manifest_path.display()
        );
    }

    let repo_name = root
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or("repository");
    let manifest = render_scaffold_manifest(repo_name)?;
    fs::write(&manifest_path, manifest)?;
    println!("initialized {}", manifest_path.display());
    Ok(())
}

fn cmd_import(
    root: PathBuf,
    mode: ImportModeArg,
    source: Option<String>,
    force: bool,
) -> Result<()> {
    let plan = import_repository(&root, mode.into(), source.as_deref())?;

    let mut outputs = vec![(plan.manifest_path.clone(), plan.manifest_text.clone())];
    if let (Some(path), Some(contents)) = (&plan.evidence_path, &plan.evidence_text) {
        outputs.push((path.clone(), contents.clone()));
    }

    for (path, _) in &outputs {
        if path.exists() && !force {
            bail!(
                "{} already exists; rerun with --force to overwrite imported artifacts",
                path.display()
            );
        }
    }

    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&path, contents)?;
        println!("imported {}", path.display());
    }

    if !plan.imported_sources.is_empty() {
        println!("- imported from: {}", plan.imported_sources.join(", "));
    }
    if !plan.inferred_fields.is_empty() {
        println!("- inferred defaults: {}", plan.inferred_fields.join(", "));
    }
    println!("- mode: {:?}", plan.manifest.record.mode);
    println!("- status: {:?}", plan.manifest.record.status);

    Ok(())
}

fn cmd_query(root: PathBuf, path: &str, json: bool, raw: bool) -> Result<()> {
    let report = query_repository(&root, path)?;
    println!("{}", format_query_value(&report.value, json, raw)?);
    Ok(())
}

fn cmd_validate_index(index_root: PathBuf) -> Result<()> {
    let findings = validate_index_root(&index_root)?;
    if findings.is_empty() {
        println!("index valid");
        return Ok(());
    }

    let mut warnings = Vec::new();
    let mut errors = Vec::new();
    for finding in findings {
        match finding.severity {
            IndexFindingSeverity::Warning => warnings.push(finding),
            IndexFindingSeverity::Error => errors.push(finding),
        }
    }

    if errors.is_empty() {
        println!("index valid with warnings");
        for finding in warnings {
            println!("warning: {}: {}", finding.path.display(), finding.message);
        }
        return Ok(());
    }

    let mut sections = vec![format!(
        "index validation failed:\n{}",
        errors
            .into_iter()
            .map(|finding| format!("- {}: {}", finding.path.display(), finding.message))
            .collect::<Vec<_>>()
            .join("\n")
    )];

    if !warnings.is_empty() {
        sections.push(format!(
            "warnings:\n{}",
            warnings
                .into_iter()
                .map(|finding| format!("- {}: {}", finding.path.display(), finding.message))
                .collect::<Vec<_>>()
                .join("\n")
        ));
    }

    Err(CliExit {
        code: 1,
        message: sections.join("\n"),
    }
    .into())
}

fn cmd_generate(root: PathBuf, check: bool) -> Result<()> {
    if check {
        let report = generate_check_repository(&root)?;
        if !report.stale.is_empty() {
            return Err(CliExit {
                code: 2,
                message: format!(
                    "generated files are out of date:\n{}",
                    report
                        .stale
                        .into_iter()
                        .map(|path| format!("- {}", path))
                        .collect::<Vec<_>>()
                        .join("\n")
                ),
            }
            .into());
        }
        return Ok(());
    }

    let document = load_manifest_document(&root)?;
    validate_manifest(&root, &document.manifest)?;
    let outputs = managed_outputs(&root, &document.manifest, &document.raw)?;

    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&path, contents)?;
        println!("generated {}", path.display());
    }

    Ok(())
}

fn cmd_doctor(root: PathBuf) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    let findings = detect_unmanaged_files(&root);
    println!("dotrepo doctor");
    println!("- mode: {:?}", manifest.record.mode);
    println!("- status: {:?}", manifest.record.status);
    if findings.is_empty() {
        println!("- no unmanaged conventional files detected");
    } else {
        println!("- unmanaged conventional files:");
        for finding in findings {
            println!("  - {}: {}", finding.path.display(), finding.message);
        }
    }
    Ok(())
}

fn cmd_trust(root: PathBuf) -> Result<()> {
    let report = trust_repository(&root)?;
    println!("status: {:?}", report.record.status);
    println!("mode: {:?}", report.record.mode);
    if let Some(source) = report.record.source {
        println!("source: {:?}", source);
    }
    if let Some(trust) = report.record.trust {
        println!("confidence: {:?}", trust.confidence);
        println!("provenance: {:?}", trust.provenance);
        println!("notes: {:?}", trust.notes);
    } else {
        println!("confidence: None");
        println!("provenance: []");
        println!("notes: None");
    }
    Ok(())
}

fn format_query_value(value: &Value, json: bool, raw: bool) -> Result<String> {
    if json {
        return Ok(serde_json::to_string_pretty(value)?);
    }

    match value {
        Value::String(text) => Ok(text.clone()),
        Value::Null => {
            if raw {
                Ok(String::new())
            } else {
                Ok("null".into())
            }
        }
        Value::Bool(flag) => Ok(flag.to_string()),
        Value::Number(number) => Ok(number.to_string()),
        Value::Array(_) | Value::Object(_) => {
            if raw {
                bail!("--raw is only supported for scalar query results");
            }
            Ok(serde_json::to_string_pretty(value)?)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn format_query_value_defaults_to_human_readable_strings() {
        let rendered =
            format_query_value(&Value::String("orbit".into()), false, false).expect("formats");
        assert_eq!(rendered, "orbit");
    }

    #[test]
    fn format_query_value_supports_json_mode() {
        let rendered = format_query_value(&Value::String("orbit".into()), true, false)
            .expect("formats as json");
        assert_eq!(rendered, "\"orbit\"");
    }

    #[test]
    fn format_query_value_rejects_raw_composite_values() {
        let err = format_query_value(
            &Value::Array(vec![Value::String("orbit".into())]),
            false,
            true,
        )
        .expect_err("raw composite values should fail");
        assert!(err.to_string().contains("--raw"));
    }

    #[test]
    fn validate_index_allows_warning_only_runs() {
        let root = temp_dir("index-warning");
        let record_dir = root.join("repos/github.com/example/project");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "project"
description = "Example project"
homepage = "https://github.com/example/project"

[owners]
security_contact = "unknown"
"#,
        )
        .expect("record written");
        fs::write(
            record_dir.join("evidence.md"),
            "# Evidence\n\n- Imported from the upstream repository.\n",
        )
        .expect("evidence written");

        cmd_validate_index(root.clone()).expect("warning-only index should pass");

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_fails_on_structural_errors() {
        let root = temp_dir("index-error");
        let record_dir = root.join("repos/github.com/example/project");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "project"
description = "Example project"
homepage = "https://github.com/example/project"
"#,
        )
        .expect("record written");

        let err = cmd_validate_index(root.clone()).expect_err("invalid index should fail");
        let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
        assert_eq!(exit.code, 1);
        assert!(exit.message.contains("record.mode = \"overlay\""));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_writes_overlay_manifest_and_evidence() {
        let root = temp_dir("import-overlay");
        fs::write(
            root.join("README.md"),
            "# Example Project\n\nProject summary from the README.\n",
        )
        .expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(root.join(".github/CODEOWNERS"), "* @example\n").expect("CODEOWNERS written");
        fs::write(
            root.join(".github/SECURITY.md"),
            "Report vulnerabilities to security@example.com.\n",
        )
        .expect("SECURITY written");

        cmd_import(
            root.clone(),
            ImportModeArg::Overlay,
            Some("https://github.com/example/project".into()),
            false,
        )
        .expect("overlay import succeeds");

        let manifest = load_manifest_from_root(&root).expect("manifest loads");
        assert_eq!(manifest.record.mode, dotrepo_schema::RecordMode::Overlay);
        assert_eq!(
            manifest.record.status,
            dotrepo_schema::RecordStatus::Imported
        );
        assert_eq!(manifest.repo.name, "Example Project");
        assert!(root.join("evidence.md").exists());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_reports_multiple_diagnostics() {
        let root = temp_dir("validate-many");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v9.9"

[record]
mode = "overlay"
status = "imported"

[repo]
name = " "
description = "Broken overlay"
"#,
        )
        .expect("record written");

        let err = cmd_validate(root.clone()).expect_err("invalid manifest should fail");
        let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
        assert!(exit.message.contains("unsupported schema"));
        assert!(exit.message.contains("repo.name must not be empty"));
        assert!(exit.message.contains("record.source must be set"));
        assert!(exit.message.contains("record.trust must be set"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-cli-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }
}
