use crate::CrawlWritebackPlan;
use anyhow::{bail, Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct WritebackReport {
    pub record_root: PathBuf,
    pub manifest_path: PathBuf,
    pub evidence_path: Option<PathBuf>,
    pub synthesis_path: Option<PathBuf>,
}

struct StagedWrite {
    tmp_path: PathBuf,
    final_path: PathBuf,
}

/// Apply a crawl writeback plan with multi-artifact durability:
/// 1. stage every artifact as `*.tmp` (no finals updated yet)
/// 2. rename all staged files to their finals
///
/// This prevents the partial-update case where a new `record.toml` lands and a
/// later evidence write fails, leaving the index half-updated.
pub(crate) fn apply_writeback_plan(plan: &CrawlWritebackPlan) -> Result<WritebackReport> {
    fs::create_dir_all(&plan.record_root)
        .with_context(|| format!("failed to create {}", plan.record_root.display()))?;

    let mut staged: Vec<StagedWrite> = Vec::new();

    let manifest_tmp = plan.factual.manifest_path.with_extension("toml.tmp");
    stage_write(
        &manifest_tmp,
        &plan.factual.import_plan.manifest_text,
        &plan.factual.manifest_path,
        &mut staged,
    )
    .with_context(|| {
        format!(
            "failed to stage factual manifest {}",
            plan.factual.manifest_path.display()
        )
    })?;

    match (
        plan.factual.evidence_path.as_ref(),
        plan.factual.import_plan.evidence_text.as_ref(),
    ) {
        (Some(path), Some(text)) => {
            let evidence_tmp = path.with_extension("md.tmp");
            stage_write(&evidence_tmp, text, path, &mut staged)
                .with_context(|| format!("failed to stage evidence {}", path.display()))?;
        }
        (Some(_), None) => {
            cleanup_staged(&staged);
            bail!("writeback plan is missing evidence text");
        }
        (None, Some(_)) => {
            cleanup_staged(&staged);
            bail!("writeback plan is missing an evidence path");
        }
        (None, None) => {}
    }

    if let Some(synthesis) = &plan.synthesis {
        let synth_tmp = synthesis.synthesis_path.with_extension("toml.tmp");
        if let Err(err) = stage_write(
            &synth_tmp,
            &synthesis.write_plan.synthesis_text,
            &synthesis.synthesis_path,
            &mut staged,
        ) {
            cleanup_staged(&staged);
            return Err(err).with_context(|| {
                format!(
                    "failed to stage synthesis document {}",
                    synthesis.synthesis_path.display()
                )
            });
        }
    }

    commit_staged(&staged).with_context(|| {
        format!(
            "failed to commit writeback artifacts under {}",
            plan.record_root.display()
        )
    })?;

    Ok(WritebackReport {
        record_root: plan.record_root.clone(),
        manifest_path: plan.factual.manifest_path.clone(),
        evidence_path: plan.factual.evidence_path.clone(),
        synthesis_path: plan
            .synthesis
            .as_ref()
            .map(|synthesis| synthesis.synthesis_path.clone()),
    })
}

fn stage_write(
    tmp_path: &Path,
    contents: &str,
    final_path: &Path,
    staged: &mut Vec<StagedWrite>,
) -> Result<()> {
    fs::write(tmp_path, contents)
        .with_context(|| format!("failed to write temp file {}", tmp_path.display()))?;
    staged.push(StagedWrite {
        tmp_path: tmp_path.to_path_buf(),
        final_path: final_path.to_path_buf(),
    });
    Ok(())
}

fn commit_staged(staged: &[StagedWrite]) -> Result<()> {
    for item in staged {
        if let Err(err) = fs::rename(&item.tmp_path, &item.final_path) {
            // Best-effort: remove any remaining temps so a retry starts clean.
            cleanup_staged(staged);
            return Err(err).with_context(|| {
                format!(
                    "failed to rename {} to {}",
                    item.tmp_path.display(),
                    item.final_path.display()
                )
            });
        }
    }
    Ok(())
}

fn cleanup_staged(staged: &[StagedWrite]) {
    for item in staged {
        let _ = fs::remove_file(&item.tmp_path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        CrawlWritebackPlan, FactualWritebackPlan, GitHubRepositorySnapshot, RepositoryRef,
    };
    use dotrepo_core::{import_repository_with_options, ImportMode, ImportOptions};
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir(label: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-crawler-writeback-{}-{}-{}",
            label,
            std::process::id(),
            nanos
        ));
        fs::create_dir_all(&path).expect("temp dir");
        path
    }

    #[test]
    fn writeback_stages_all_artifacts_before_any_final_commit() {
        let fixture = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../dotrepo-core/tests/fixtures/import/root-conventional-files");
        let index_root = temp_dir("stage-all");
        let repository = RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "stage-all".into(),
        };
        let record_root = index_root.join(repository.record_relative_dir());
        let manifest_path = record_root.join("record.toml");
        let evidence_path = record_root.join("evidence.md");

        let import_plan = import_repository_with_options(
            &fixture,
            ImportMode::Overlay,
            Some("https://github.com/example/stage-all"),
            &ImportOptions {
                generated_at: Some("2026-03-17T12:00:00Z".into()),
                ..ImportOptions::default()
            },
        )
        .expect("import succeeds");

        assert!(
            import_plan.evidence_text.is_some(),
            "fixture should produce evidence"
        );

        let plan = CrawlWritebackPlan {
            repository: repository.clone(),
            record_root: record_root.clone(),
            github: GitHubRepositorySnapshot {
                html_url: "https://github.com/example/stage-all".into(),
                clone_url: "https://github.com/example/stage-all.git".into(),
                default_branch: "main".into(),
                head_sha: Some("abc123".into()),
                description: None,
                homepage: None,
                license: None,
                languages: Vec::new(),
                topics: Vec::new(),
                visibility: Some("public".into()),
                stars: None,
                archived: false,
                fork: false,
                parent: None,
            },
            factual: FactualWritebackPlan {
                import_plan,
                manifest_path: manifest_path.clone(),
                evidence_path: Some(evidence_path.clone()),
            },
            synthesis: None,
            synthesis_failure: None,
        };

        apply_writeback_plan(&plan).expect("writeback succeeds");
        assert!(manifest_path.is_file(), "manifest committed");
        assert!(evidence_path.is_file(), "evidence committed");
        assert!(
            !manifest_path.with_extension("toml.tmp").exists(),
            "manifest temp cleaned by rename"
        );
        assert!(
            !evidence_path.with_extension("md.tmp").exists(),
            "evidence temp cleaned by rename"
        );

        fs::remove_dir_all(index_root).expect("cleanup");
    }

    #[test]
    fn writeback_rejects_missing_evidence_text_without_partial_finals() {
        let index_root = temp_dir("missing-evidence");
        let repository = RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "missing-evidence".into(),
        };
        let record_root = index_root.join(repository.record_relative_dir());
        let manifest_path = record_root.join("record.toml");
        let evidence_path = record_root.join("evidence.md");

        let fixture = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../dotrepo-core/tests/fixtures/import/root-conventional-files");
        let mut import_plan = import_repository_with_options(
            &fixture,
            ImportMode::Overlay,
            Some("https://github.com/example/missing-evidence"),
            &ImportOptions {
                generated_at: Some("2026-03-17T12:00:00Z".into()),
                ..ImportOptions::default()
            },
        )
        .expect("import succeeds");
        import_plan.evidence_text = None;

        let plan = CrawlWritebackPlan {
            repository,
            record_root,
            github: GitHubRepositorySnapshot {
                html_url: "https://github.com/example/missing-evidence".into(),
                clone_url: "https://github.com/example/missing-evidence.git".into(),
                default_branch: "main".into(),
                head_sha: None,
                description: None,
                homepage: None,
                license: None,
                languages: Vec::new(),
                topics: Vec::new(),
                visibility: None,
                stars: None,
                archived: false,
                fork: false,
                parent: None,
            },
            factual: FactualWritebackPlan {
                import_plan,
                manifest_path: manifest_path.clone(),
                evidence_path: Some(evidence_path.clone()),
            },
            synthesis: None,
            synthesis_failure: None,
        };

        let err = apply_writeback_plan(&plan).expect_err("missing evidence text must fail");
        assert!(err.to_string().contains("missing evidence text"));
        assert!(
            !manifest_path.exists(),
            "manifest must not land without evidence sibling"
        );
        assert!(!evidence_path.exists());

        fs::remove_dir_all(index_root).expect("cleanup");
    }
}
