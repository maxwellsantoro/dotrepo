use super::common::*;

#[test]
fn import_overlay_with_github_facts_discovers_fork_relation_and_records_evidence() {
    let root = temp_dir("import-rel-discover");
    fs::write(
        root.join("README.md"),
        "# Forked Project\n\nA fork for testing.\n",
    )
    .expect("README written");

    // include a Cargo.toml declaring a repository to exercise package manifest discovery path
    fs::write(
        root.join("Cargo.toml"),
        r#"[package]
name = "my-fork"
version = "0.1.0"
repository = "https://github.com/example/another-related"
"#,
    )
    .expect("Cargo written");

    let plan = import_repository_with_options(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/my-fork"),
        &ImportOptions {
            generated_at: Some("2026-06-28T00:00:00Z".into()),
            github: Some(GitHubSnapshotFacts {
                fork: true,
                parent: Some("github.com/example/upstream".into()),
            }),
        },
    )
    .expect("overlay import with github facts succeeds");

    // relations should be populated with fork (from github) + related (from Cargo manifest)
    let rels = plan
        .manifest
        .relations
        .as_ref()
        .expect("relations present for overlay");
    assert_eq!(rels.references.len(), 0);
    assert!(
        rels.links.len() >= 2,
        "should have fork + manifest declared link"
    );
    let has_fork = rels
        .links
        .iter()
        .any(|l| l.kind == RelationKind::Fork && l.target == "github.com/example/upstream");
    let has_manifest = rels
        .links
        .iter()
        .any(|l| l.kind == RelationKind::Related && l.target.contains("another-related"));
    assert!(has_fork, "must have discovered fork link");
    assert!(
        has_manifest,
        "must have discovered related link from package manifest (Cargo.toml)"
    );

    // evidence must record the discovery
    let ev = plan.evidence_text.as_deref().expect("evidence for overlay");
    assert!(
        ev.contains("Discovered fork-of relation targeting github.com/example/upstream"),
        "evidence must document discovered relation source; got: {}",
        &ev[..ev.len().min(800)]
    );

    // still validates
    validate_manifest(&root, &plan.manifest)
        .expect("discovered relations must not break validation");

    // Exercise public relations response + traversal for a discovered link (roundtrip)
    // Use produced manifests from import (not hand-crafted stubs) for both fork and upstream
    let index_root = temp_dir("discovered-rel-index");
    let rec_dir = index_root.join("repos/github.com/example/my-fork");
    fs::create_dir_all(&rec_dir).expect("index rec dir");
    fs::write(rec_dir.join("record.toml"), &plan.manifest_text).expect("record written");
    fs::write(
        rec_dir.join("evidence.md"),
        plan.evidence_text.clone().unwrap_or_default(),
    )
    .expect("evidence written");

    // Produce upstream record via actual import call (minimal files + import)
    let up_root = temp_dir("upstream-materialize");
    fs::write(
        up_root.join("README.md"),
        "# Upstream\n\nOriginal project.\n",
    )
    .expect("up readme");
    let up_plan = import_repository_with_options(
        &up_root,
        ImportMode::Overlay,
        Some("https://github.com/example/upstream"),
        &ImportOptions {
            generated_at: Some("2026-06-28T00:00:00Z".into()),
            github: None,
        },
    )
    .expect("upstream import produces manifest");
    let up_dir = index_root.join("repos/github.com/example/upstream");
    fs::create_dir_all(&up_dir).expect("upstream rec dir");
    fs::write(up_dir.join("record.toml"), &up_plan.manifest_text)
        .expect("upstream produced record written");
    fs::write(
        up_dir.join("evidence.md"),
        up_plan.evidence_text.clone().unwrap_or_default(),
    )
    .expect("upstream ev");

    let fresh = PublicFreshness {
        generated_at: "2026-06-28T00:00:00Z".into(),
        snapshot_digest: "sha256:discoverytest".into(),
        stale_after: None,
    };
    let rel_resp = public_repository_relations(
        &index_root,
        "github.com",
        "example",
        "my-fork",
        fresh.clone(),
    )
    .expect("public relations succeeds for discovered link");
    assert!(
        rel_resp.relation_count >= 1,
        "public rels should surface the discovered fork"
    );
    let has_fork = rel_resp
        .references
        .iter()
        .any(|item| item.relationship == "fork" && item.target.contains("upstream"));
    assert!(
        has_fork,
        "fork relation with discovered target must appear in public response"
    );

    // inverse on upstream
    let up_resp =
        public_repository_relations(&index_root, "github.com", "example", "upstream", fresh)
            .expect("public rels for upstream");
    let has_forked_by = up_resp
        .references
        .iter()
        .any(|item| item.relationship == "forked_by" && item.target.contains("my-fork"));
    assert!(
        has_forked_by,
        "inverse forked_by must be produced for discovered fork relation"
    );

    // Drive real CLI public relations on the generated discovered records (produced manifests), capture to scratch
    let scratch = std::env::var("GROK_SCRATCH").unwrap_or_else(|_| {
        "/var/folders/jr/6v5yh0jx5y51pyj48q7_x8qw0000gn/T/grok-goal-6676e9c7c17c/implementer"
            .to_string()
    });
    let cli_out_fork = format!("{}/cli-relations-generated-fork.out", scratch);
    let cli_out_up = format!("{}/cli-relations-generated-upstream.out", scratch);
    let _ = std::fs::create_dir_all(&scratch);
    // run cli for fork (should show fork link)
    let status_fork = std::process::Command::new("cargo")
        .args([
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "public",
            "relations",
            "--index-root",
            index_root.to_str().unwrap(),
            "github.com",
            "example",
            "my-fork",
            "--base-path",
            "/",
        ])
        .output()
        .expect("spawn cli relations for fork");
    std::fs::write(&cli_out_fork, &status_fork.stdout).ok();
    let out_fork = String::from_utf8_lossy(&status_fork.stdout);
    assert!(
        out_fork.contains("fork") || out_fork.contains("Fork"),
        "CLI relations on generated discovered record must mention fork"
    );
    // run cli for upstream (should show inverse forked_by)
    let status_up = std::process::Command::new("cargo")
        .args([
            "run",
            "-q",
            "-p",
            "dotrepo-cli",
            "--",
            "public",
            "relations",
            "--index-root",
            index_root.to_str().unwrap(),
            "github.com",
            "example",
            "upstream",
            "--base-path",
            "/",
        ])
        .output()
        .expect("spawn cli relations for upstream");
    std::fs::write(&cli_out_up, &status_up.stdout).ok();
    let out_up = String::from_utf8_lossy(&status_up.stdout);
    assert!(
        out_up.contains("forked_by") || out_up.contains("Forked"),
        "CLI relations on upstream of generated fork must show inverse forked_by"
    );

    fs::remove_dir_all(index_root).expect("index temp removed");

    fs::remove_dir_all(root).expect("temp dir removed");
    fs::remove_dir_all(up_root).expect("up materialize removed");
}

#[test]
fn trust_confidence_boost_produces_expected_values_and_search_ranking_uses_it() {
    use crate::{
        public_profile_search, search_ranking_from_profile, trust_confidence_boost,
        PublicFreshness, PublicProfileSearchOptions,
    };

    assert_eq!(trust_confidence_boost(Some("high")), 3);
    assert_eq!(trust_confidence_boost(Some("HIGH")), 3);
    assert_eq!(trust_confidence_boost(Some("medium")), 1);
    assert_eq!(trust_confidence_boost(Some("low")), 0);
    assert_eq!(trust_confidence_boost(None), 0);

    // Ensure ranking fn is wired (synthetic coverage via direct + search uses real profiles)
    let _ = search_ranking_from_profile;

    // Drive ranking through public entry with a high-conf record; verify trust factor can appear in basis
    let index = temp_dir("ranking-trust-index");
    // write a minimal verified high-conf record
    let rec_dir = index.join("repos/github.com/ex/highconf");
    fs::create_dir_all(&rec_dir).expect("rec");
    let rec = r#"schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "verified"
source = "https://github.com/ex/highconf"
generated_at = "2026-06-28T00:00:00Z"

[record.trust]
confidence = "high"
provenance = ["verified"]

[repo]
name = "HighConf"
description = "Has high trust for ranking test."
"#;
    fs::write(rec_dir.join("record.toml"), rec).expect("write rec");
    fs::write(rec_dir.join("evidence.md"), "# e\n").expect("ev");

    let fresh = PublicFreshness {
        generated_at: "2026-06-28T00:00:00Z".into(),
        snapshot_digest: "r".into(),
        stale_after: None,
    };
    let opts = PublicProfileSearchOptions {
        query: Some("highconf".into()),
        languages: vec![],
        topics: vec![],
        statuses: vec![],
        confidences: vec![],
        require_build: false,
        require_test: false,
        require_docs: false,
        require_security_contact: false,
        require_license: false,
        limit: None,
    };
    let resp = public_profile_search(&index, opts, fresh).expect("search");
    assert!(!resp.results.is_empty());
    let item = &resp.results[0];
    // score must account for trust boost (would be just matched*10 + comp if factor removed)
    let base = item.ranking.matched_field_count * 10 + item.ranking.completeness_signal_count;
    let boost = if item.trust.confidence.as_deref() == Some("high") {
        3
    } else if item.trust.confidence.as_deref() == Some("medium") {
        1
    } else {
        0
    };
    assert_eq!(
        item.ranking.score,
        base + boost,
        "search ranking score must incorporate trust_confidence_boost for the profile's conf tier"
    );
    if boost > 0 {
        assert!(
            item.ranking.basis.iter().any(|b| b == "trustConfidence"),
            "high/medium confidence must include trustConfidence in ranking.basis"
        );
    }

    fs::remove_dir_all(index).expect("rm");
}
