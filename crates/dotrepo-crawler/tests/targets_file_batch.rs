use dotrepo_crawler::{
    discovery_report_from_targets, load_repository_targets, parse_repository_targets, RepositoryRef,
};
use std::path::Path;

#[test]
fn parse_repository_targets_supports_comments_and_dedupes() {
    let parsed = parse_repository_targets(
        "# tranche one\n\ngithub.com/tokio-rs/tokio\ntokio-rs/tokio\n",
        "github.com",
    )
    .expect("targets parse");

    assert_eq!(parsed.len(), 1);
    assert_eq!(
        parsed[0],
        RepositoryRef {
            host: "github.com".into(),
            owner: "tokio-rs".into(),
            repo: "tokio".into(),
        }
    );
}

#[test]
fn load_repository_targets_reads_targets_file_fixture() {
    let path = Path::new("tests/fixtures/targets/tranche-sample.txt");
    let parsed = load_repository_targets(path, "github.com").expect("targets file loads");

    assert_eq!(parsed.len(), 2);
    assert_eq!(parsed[0].owner, "example");
    assert_eq!(parsed[0].repo, "alpha");
    assert_eq!(parsed[1].owner, "example");
    assert_eq!(parsed[1].repo, "beta");
}

#[test]
fn discovery_report_from_targets_respects_limit() {
    let repositories = parse_repository_targets(
        "github.com/a/one\ngithub.com/a/two\ngithub.com/a/three\n",
        "github.com",
    )
    .expect("targets parse");
    let report = discovery_report_from_targets("github.com", repositories, 2);

    assert_eq!(report.requested_limit, 2);
    assert_eq!(report.discovered.len(), 2);
    assert!(!report.exhausted_bands);
    assert_eq!(report.discovered[0].repository.repo, "one");
    assert_eq!(report.discovered[1].repository.repo, "two");
}
