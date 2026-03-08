use anyhow::{bail, Result};
use clap::{Parser, Subcommand};
use dotrepo_core::{
    detect_unmanaged_files, load_manifest_from_root, managed_outputs, query_manifest,
    validate_manifest,
};
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
    Query {
        path: String,
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
        Command::Query { path } => cmd_query(cli.root, &path),
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

    let manifest = scaffold_manifest(&root);
    fs::write(&manifest_path, manifest)?;
    println!("initialized {}", manifest_path.display());
    Ok(())
}

fn cmd_query(root: PathBuf, path: &str) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    println!("{}", query_manifest(&manifest, path)?);
    Ok(())
}

fn cmd_generate(root: PathBuf, check: bool) -> Result<()> {
    let source = fs::read(root.join(".repo"))?;
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    let outputs = managed_outputs(&root, &manifest, &source)?;

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

fn scaffold_manifest(root: &Path) -> String {
    let repo_name = root
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or("repository");

    format!(
        "schema = \"dotrepo/v0.1\"\n\n[record]\nmode = \"native\"\nstatus = \"draft\"\n\n[record.trust]\nconfidence = \"high\"\nprovenance = [\"declared\"]\nnotes = \"Maintainer-authored scaffold.\"\n\n[repo]\nname = \"{}\"\ndescription = \"TODO: describe this repository\"\nlanguages = []\ntopics = []\n\n[owners]\nmaintainers = []\n\n[readme]\ntitle = \"{}\"\nsections = [\"overview\", \"security\"]\n\n[compat.github]\ncodeowners = \"skip\"\nsecurity = \"skip\"\ncontributing = \"skip\"\npull_request_template = \"skip\"\n",
        repo_name, repo_name
    )
}

fn display_path(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .display()
        .to_string()
}
