use dotrepo_core::{
    public_repository_batch_profiles_with_base, public_repository_batch_query_with_base,
    PublicFreshness, PublicRepositoryIdentity, PUBLIC_BATCH_MAX_IDENTITIES, PUBLIC_BATCH_MAX_PATHS,
    PUBLIC_BATCH_MAX_QUERY_RESULTS,
};
use std::path::PathBuf;

fn fixture_index_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/public_export/index")
}

fn freshness() -> PublicFreshness {
    PublicFreshness {
        generated_at: "2026-03-17T12:00:00Z".into(),
        snapshot_digest: "test".into(),
        stale_after: None,
    }
}

#[test]
fn batch_profiles_rejects_identity_overflow() {
    let index_root = fixture_index_root();
    let identities = (0..=PUBLIC_BATCH_MAX_IDENTITIES)
        .map(|index| PublicRepositoryIdentity {
            host: "github.com".into(),
            owner: "example".into(),
            repo: format!("repo-{index}"),
            source: None,
        })
        .collect::<Vec<_>>();

    let err =
        public_repository_batch_profiles_with_base(&index_root, &identities, freshness(), "/")
            .expect_err("identity overflow should fail");

    assert!(err
        .to_string()
        .contains(&PUBLIC_BATCH_MAX_IDENTITIES.to_string()));
}

#[test]
fn batch_query_rejects_result_overflow() {
    let index_root = fixture_index_root();
    let identities = (0..PUBLIC_BATCH_MAX_IDENTITIES)
        .map(|index| PublicRepositoryIdentity {
            host: "github.com".into(),
            owner: "example".into(),
            repo: format!("repo-{index}"),
            source: None,
        })
        .collect::<Vec<_>>();
    let paths = (0..PUBLIC_BATCH_MAX_PATHS)
        .map(|index| format!("repo.field_{index}"))
        .collect::<Vec<_>>();

    let err =
        public_repository_batch_query_with_base(&index_root, &identities, &paths, freshness(), "/")
            .expect_err("result overflow should fail");

    assert!(err
        .to_string()
        .contains(&PUBLIC_BATCH_MAX_QUERY_RESULTS.to_string()));
}
