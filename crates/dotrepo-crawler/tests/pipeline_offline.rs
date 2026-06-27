use dotrepo_core::{
    import_repository_with_options, validate_index_root, ImportMode, ImportOptions,
};
use dotrepo_crawler::{
    apply_crawl_writeback, CrawlWritebackPlan, FactualWritebackPlan, GitHubRepositorySnapshot,
    RepositoryRef,
};
use dotrepo_schema::parse_manifest;
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn temp_dir(label: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-crawler-offline-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

#[test]
fn offline_writeback_from_import_fixture_validates_index() {
    let fixture = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../dotrepo-core/tests/fixtures/import/root-conventional-files");
    let index_root = temp_dir("offline-index");
    let repository = RepositoryRef {
        host: "github.com".into(),
        owner: "example".into(),
        repo: "orbit".into(),
    };
    let record_root = index_root.join(repository.record_relative_dir());
    let manifest_path = record_root.join("record.toml");
    let evidence_path = record_root.join("evidence.md");

    let import_plan = import_repository_with_options(
        &fixture,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
        &ImportOptions {
            generated_at: Some("2026-03-17T12:00:00Z".into()),
        },
    )
    .expect("import succeeds");

    let report = apply_crawl_writeback(&CrawlWritebackPlan {
        repository: repository.clone(),
        record_root: record_root.clone(),
        github: GitHubRepositorySnapshot {
            html_url: "https://github.com/example/orbit".into(),
            clone_url: "https://github.com/example/orbit.git".into(),
            default_branch: "main".into(),
            head_sha: Some("57c190d5".into()),
            description: Some("GitHub fallback description".into()),
            homepage: None,
            license: None,
            languages: Vec::new(),
            topics: Vec::new(),
            visibility: Some("public".into()),
            stars: None,
            archived: false,
            fork: false,
        },
        factual: FactualWritebackPlan {
            import_plan,
            manifest_path: manifest_path.clone(),
            evidence_path: Some(evidence_path.clone()),
        },
        synthesis: None,
        synthesis_failure: None,
    })
    .expect("writeback succeeds");

    let record_text = fs::read_to_string(&report.manifest_path).expect("record read");
    let manifest = parse_manifest(&record_text).expect("record parses");
    assert_eq!(manifest.repo.name, "Harbor");
    assert!(fs::metadata(&evidence_path).is_ok());
    assert!(validate_index_root(&index_root)
        .expect("index validates")
        .iter()
        .all(|finding| !finding.path.ends_with("record.toml")));

    fs::remove_dir_all(index_root).expect("index temp removed");
}
