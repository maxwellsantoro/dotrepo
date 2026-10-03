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

/// Stage all artifacts, then commit with backups and rollback on I/O errors.
/// A per-record lock prevents concurrent writers from sharing staging paths.
/// This is not a crash-atomic filesystem transaction; failed rollback retains
/// backups for operator recovery instead of discarding the previous data.
pub(crate) fn apply_writeback_plan(plan: &CrawlWritebackPlan) -> Result<WritebackReport> {
    fs::create_dir_all(&plan.record_root)
        .with_context(|| format!("failed to create {}", plan.record_root.display()))?;

    let lock_path = plan.record_root.join(".writeback.lock");
    let _lock_file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&lock_path)
        .with_context(|| {
            format!(
                "writeback already locked or lock unavailable: {}",
                lock_path.display()
            )
        })?;
    struct LockGuard(PathBuf);
    impl Drop for LockGuard {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.0);
        }
    }
    let _lock = LockGuard(lock_path);
    if let Ok(text) = fs::read_to_string(&plan.factual.manifest_path) {
        if let Ok(manifest) = dotrepo_schema::parse_manifest(&text) {
            if manifest.record.mode == dotrepo_schema::RecordMode::Native
                || matches!(
                    manifest.record.status,
                    dotrepo_schema::RecordStatus::Canonical
                        | dotrepo_schema::RecordStatus::Reviewed
                )
            {
                bail!("autonomous writeback cannot replace maintainer-owned or human-reviewed records");
            }
        }
    }
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
            if let Err(error) = stage_write(&evidence_tmp, text, path, &mut staged) {
                cleanup_staged(&staged);
                return Err(error)
                    .with_context(|| format!("failed to stage evidence {}", path.display()));
            }
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
    if let Err(error) = fs::write(tmp_path, contents) {
        let _ = fs::remove_file(tmp_path);
        return Err(error)
            .with_context(|| format!("failed to write temp file {}", tmp_path.display()));
    }
    staged.push(StagedWrite {
        tmp_path: tmp_path.to_path_buf(),
        final_path: final_path.to_path_buf(),
    });
    Ok(())
}

fn commit_staged(staged: &[StagedWrite]) -> Result<()> {
    let mut backups: Vec<Option<PathBuf>> = Vec::new();
    // Preflight every destination and back up every existing file before changing any.
    let prepare = (|| -> Result<()> {
        for item in staged {
            match fs::symlink_metadata(&item.final_path) {
                Ok(metadata) if metadata.file_type().is_file() => {
                    let backup = item.tmp_path.with_extension("backup");
                    // Never overwrite backups left by an interrupted transaction.
                    let mut output = fs::OpenOptions::new()
                        .write(true)
                        .create_new(true)
                        .open(&backup)?;
                    backups.push(Some(backup));
                    let mut input = fs::File::open(&item.final_path)?;
                    std::io::copy(&mut input, &mut output)?;
                    output.sync_all()?;
                }
                Ok(_) => bail!(
                    "writeback destination is not a regular file: {}",
                    item.final_path.display()
                ),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => backups.push(None),
                Err(error) => return Err(error.into()),
            }
        }
        Ok(())
    })();
    if let Err(error) = prepare {
        for backup in backups.iter().flatten() {
            let _ = fs::remove_file(backup);
        }
        cleanup_staged(staged);
        return Err(error);
    }
    for (committed, item) in staged.iter().enumerate() {
        if let Err(error) = fs::rename(&item.tmp_path, &item.final_path) {
            let mut recovery_errors = Vec::new();
            for index in (0..committed).rev() {
                let result = match &backups[index] {
                    Some(backup) => fs::rename(backup, &staged[index].final_path),
                    None => fs::remove_file(&staged[index].final_path),
                };
                if let Err(rollback) = result {
                    recovery_errors.push(rollback.to_string());
                }
            }
            cleanup_staged(staged);
            if !recovery_errors.is_empty() {
                bail!(
                    "writeback failed: {error}; rollback failed: {}; retained backups: {:?}",
                    recovery_errors.join("; "),
                    backups
                );
            }
            for backup in backups.iter().flatten() {
                let _ = fs::remove_file(backup);
            }
            return Err(error).with_context(|| {
                format!(
                    "failed to commit {}; previous artifacts restored",
                    item.final_path.display()
                )
            });
        }
    }
    for backup in backups.iter().flatten() {
        let _ = fs::remove_file(backup);
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
    fn commit_failure_restores_existing_artifacts_and_removes_new_ones() {
        let root = temp_dir("rollback");
        let paths = [
            root.join("record.toml"),
            root.join("new.md"),
            root.join("evidence.md"),
        ];
        fs::write(&paths[0], "old record").unwrap();
        fs::write(&paths[2], "old evidence").unwrap();
        let mut staged = Vec::new();
        for path in &paths {
            stage_write(&path.with_extension("tmp"), "new", path, &mut staged).unwrap();
        }
        // Fail the last rename after two successful commits.
        fs::remove_file(&staged[2].tmp_path).unwrap();
        assert!(commit_staged(&staged).is_err());
        assert_eq!(fs::read_to_string(&paths[0]).unwrap(), "old record");
        assert!(!paths[1].exists());
        assert_eq!(fs::read_to_string(&paths[2]).unwrap(), "old evidence");
        assert_eq!(fs::read_dir(&root).unwrap().count(), 2);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn invalid_destination_does_not_change_any_final_artifacts() {
        let root = temp_dir("preflight");
        let record = root.join("record.toml");
        let evidence = root.join("evidence.md");
        fs::write(&record, "old").unwrap();
        fs::create_dir(&evidence).unwrap();
        let mut staged = Vec::new();
        for path in [&record, &evidence] {
            stage_write(&path.with_extension("tmp"), "new", path, &mut staged).unwrap();
        }
        assert!(commit_staged(&staged).is_err());
        assert_eq!(fs::read_to_string(record).unwrap(), "old");
        fs::remove_dir_all(root).unwrap();
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

        // Human authority remains untouched even when a public writeback caller
        // bypasses crawl planning.
        for status in [
            dotrepo_schema::RecordStatus::Reviewed,
            dotrepo_schema::RecordStatus::Canonical,
        ] {
            let mut protected = plan.factual.import_plan.manifest.clone();
            protected.record.status = status;
            let text = dotrepo_schema::render_manifest(&protected).unwrap();
            fs::write(&manifest_path, &text).unwrap();
            assert!(apply_writeback_plan(&plan).is_err());
            assert_eq!(fs::read_to_string(&manifest_path).unwrap(), text);
        }

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
