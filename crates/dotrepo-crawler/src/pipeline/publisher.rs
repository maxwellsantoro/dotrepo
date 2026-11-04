//! Publisher declarations remain separate from the crawler's observed overlay.
use crate::CrawlDiagnostic;
use anyhow::{Context, Result};
use dotrepo_core::ImportPlan;
use dotrepo_schema::{parse_manifest, RecordMode};
use sha2::{Digest, Sha256};
use std::{fs, path::Path};
use toml::{map::Map, Value};

const MAX_DECLARATION_BYTES: u64 = 65536;

pub(super) fn retain_declaration(
    root: &Path,
    source_url: &str,
    revision: Option<&str>,
    plan: &mut ImportPlan,
    diagnostics: &mut Vec<CrawlDiagnostic>,
) -> Result<()> {
    let path = root.join(".repo");
    let metadata = match fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(()),
        Err(error) => return Err(error).context("inspect publisher .repo"),
    };
    if !metadata.is_file() || metadata.len() > MAX_DECLARATION_BYTES {
        diagnostics.push(CrawlDiagnostic::warning(
            "publisher.declaration_refused",
            "publisher .repo must be a regular file no larger than 64KiB",
        ));
        return Ok(());
    }
    let text = fs::read_to_string(path).context("read publisher .repo")?;
    let declaration = match parse_manifest(&text) {
        Ok(manifest)
            if manifest.record.mode == RecordMode::Native
                && manifest.schema == "dotrepo/v0.1"
                && !manifest.repo.name.trim().is_empty() =>
        {
            manifest
        }
        _ => {
            diagnostics.push(CrawlDiagnostic::warning(
                "publisher.declaration_refused",
                "root .repo does not parse as a v0.1 native declaration; observed-source fallback retained",
            ));
            return Ok(());
        }
    };
    let digest: String = Sha256::digest(text.as_bytes())
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();
    let status = serde_json::to_value(&declaration.record.status)?
        .as_str()
        .unwrap_or("unknown")
        .to_string();
    let mut observation = Map::new();
    for (key, value) in [
        ("source", source_url),
        ("revision", revision.unwrap_or("unknown")),
        ("sha256", digest.as_str()),
        ("declared_status", status.as_str()),
        ("manifest_toml", text.as_str()),
        ("validation", "Parsed structure only; referenced paths, command context and semantic correctness are unassessed in the bounded crawl."),
        ("meaning", "Exact publisher declaration observed at the captured revision. Kept separate from crawler facts; declared status is not an index trust grant or execution validation."),
    ] {
        observation.insert(key.into(), Value::String(value.into()));
    }
    let extension = plan
        .manifest
        .x
        .entry("dotrepo".into())
        .or_insert_with(|| Value::Table(Map::new()));
    if let Some(extension) = extension.as_table_mut() {
        extension.insert("publisher_declaration".into(), Value::Table(observation));
    }
    diagnostics.push(CrawlDiagnostic::info(
        "publisher.native_declaration",
        format!("retained publisher .repo ({digest}, declared {status}) independently of the observed overlay"),
    ));
    if let Some(evidence) = &mut plan.evidence_text {
        evidence.push_str(&format!(
            "\n## Publisher declaration\n\nObserved `{source_url}` root `.repo` at `{}`; SHA-256 `{digest}`, declared status `{status}`. Exact bytes are retained in `x.dotrepo.publisher_declaration.manifest_toml`. Observed facts and declaration remain separate; no maintainer authority or execution qualification is inferred.\n",
            revision.unwrap_or("unknown"),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use dotrepo_core::{import_repository, ImportMode};
    use dotrepo_schema::RecordStatus;

    #[test]
    fn publisher_bytes_and_status_remain_separate_from_observed_facts() {
        let root =
            std::env::temp_dir().join(format!("dotrepo-native-observation-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        fs::write(
            root.join("README.md"),
            "# Observed project\n\nObserved description.\n",
        )
        .unwrap();
        let text = "schema = \"dotrepo/v0.1\"\n[record]\nmode = \"native\"\nstatus = \"draft\"\n[repo]\nname = \"Publisher name\"\ndescription = \"Publisher declaration\"\n[docs]\nroot = \"docs/\"\n";
        fs::write(root.join(".repo"), text).unwrap();
        let mut plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/project"),
        )
        .unwrap();
        let observed_name = plan.manifest.repo.name.clone();
        let mut diagnostics = Vec::new();
        retain_declaration(
            &root,
            "https://github.com/example/project",
            Some("abc"),
            &mut plan,
            &mut diagnostics,
        )
        .unwrap();
        let declaration = &plan.manifest.x["dotrepo"]["publisher_declaration"];
        assert_eq!(declaration["manifest_toml"].as_str(), Some(text));
        assert_eq!(declaration["declared_status"].as_str(), Some("draft"));
        assert_eq!(plan.manifest.repo.name, observed_name);
        assert_eq!(plan.manifest.record.mode, RecordMode::Overlay);
        assert_eq!(plan.manifest.record.status, RecordStatus::Imported);
        // Sparse materialization does not establish whether docs/ exists.
        assert!(declaration["validation"]
            .as_str()
            .unwrap()
            .contains("unassessed"));
        fs::write(root.join(".repo"), text.replace("draft", "canonical")).unwrap();
        retain_declaration(
            &root,
            "https://github.com/example/project",
            Some("abc"),
            &mut plan,
            &mut diagnostics,
        )
        .unwrap();
        assert_eq!(plan.manifest.record.status, RecordStatus::Imported);
        // Malformed/unsupported declarations are reported, without becoming
        // a valid native observation or preventing ordinary source fallback.
        plan.manifest.x.clear();
        fs::write(
            root.join(".repo"),
            text.replace("dotrepo/v0.1", "dotrepo/unsupported"),
        )
        .unwrap();
        retain_declaration(
            &root,
            "https://github.com/example/project",
            Some("abc"),
            &mut plan,
            &mut diagnostics,
        )
        .unwrap();
        assert!(!plan.manifest.x.contains_key("dotrepo"));
        assert!(diagnostics
            .iter()
            .any(|item| item.code == "publisher.declaration_refused"));
        fs::remove_dir_all(root).unwrap();
    }
}
