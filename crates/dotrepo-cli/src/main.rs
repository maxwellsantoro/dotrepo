use anyhow::{bail, Result};
use clap::{Parser, Subcommand};
use dotrepo_core::{
    detect_unmanaged_files, load_manifest_document, load_manifest_from_root, managed_outputs,
    query_manifest_value, validate_index_root, validate_manifest,
};
use dotrepo_schema::scaffold_manifest as render_scaffold_manifest;
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};
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
        Command::Validate => cmd_validate(cli.root),
        Command::ValidateIndex { index_root } => cmd_validate_index(index_root),
        Command::Query { path, json, raw } => cmd_query(cli.root, &path, json, raw),
        Command::Generate { check } => cmd_generate(cli.root, check),
        Command::Doctor => cmd_doctor(cli.root),
        Command::Trust => cmd_trust(cli.root),
    }
}

fn cmd_validate(root: PathBuf) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
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

fn cmd_query(root: PathBuf, path: &str, json: bool, raw: bool) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    let value = query_manifest_value(&manifest, path)?;
    println!("{}", format_query_value(&value, json, raw)?);
    Ok(())
}

fn cmd_validate_index(index_root: PathBuf) -> Result<()> {
    let findings = validate_index_root(&index_root)?;
    if findings.is_empty() {
        println!("index valid");
        return Ok(());
    }

    Err(CliExit {
        code: 1,
        message: format!(
            "index validation failed:\n{}",
            findings
                .into_iter()
                .map(|finding| format!("- {}: {}", finding.path.display(), finding.message))
                .collect::<Vec<_>>()
                .join("\n")
        ),
    }
    .into())
}

fn cmd_generate(root: PathBuf, check: bool) -> Result<()> {
    let document = load_manifest_document(&root)?;
    validate_manifest(&root, &document.manifest)?;
    let outputs = managed_outputs(&root, &document.manifest, &document.raw)?;

    if check {
        let stale = outputs
            .iter()
            .filter_map(|(path, contents)| {
                let current = fs::read_to_string(path).unwrap_or_default();
                if current != *contents {
                    Some(display_path(&root, path))
                } else {
                    None
                }
            })
            .collect::<Vec<_>>();

        if !stale.is_empty() {
            return Err(CliExit {
                code: 2,
                message: format!(
                    "generated files are out of date:\n{}",
                    stale
                        .into_iter()
                        .map(|path| format!("- {}", path))
                        .collect::<Vec<_>>()
                        .join("\n")
                ),
            }
            .into());
        }
    } else {
        for (path, contents) in outputs {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::write(&path, contents)?;
            println!("generated {}", path.display());
        }
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
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    println!("status: {:?}", manifest.record.status);
    println!("mode: {:?}", manifest.record.mode);
    if let Some(source) = manifest.record.source {
        println!("source: {:?}", source);
    }
    if let Some(trust) = manifest.record.trust {
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

fn display_path(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .display()
        .to_string()
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
}
