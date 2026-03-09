use dotrepo_core::{import_repository, ImportMode};
use std::fs;
use std::path::{Path, PathBuf};

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("import")
}

fn fixture_cases() -> Vec<PathBuf> {
    let mut cases = fs::read_dir(fixture_root())
        .expect("fixture root exists")
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .filter(|path| path.file_name().and_then(|name| name.to_str()) != Some(".github"))
        .collect::<Vec<_>>();
    cases.sort();
    cases
}

fn fixture_name(path: &Path) -> &str {
    path.file_name()
        .and_then(|name| name.to_str())
        .expect("fixture name")
}

fn fixture_case(name: &str) -> PathBuf {
    fixture_root().join(name)
}

#[test]
fn import_fixture_pack_supports_native_and_overlay_bootstrap() {
    let cases = fixture_cases();
    assert!(!cases.is_empty(), "fixture pack should not be empty");

    for case in cases {
        let name = fixture_name(&case);
        let overlay_source = format!("https://example.com/fixtures/{}", name);

        let native =
            import_repository(&case, ImportMode::Native, None).expect("native import succeeds");
        assert!(
            !native.manifest.repo.name.trim().is_empty(),
            "native import should set repo.name for {}",
            name
        );
        assert!(
            !native.manifest.repo.description.trim().is_empty(),
            "native import should set repo.description for {}",
            name
        );
        assert!(
            native.manifest.record.trust.is_some(),
            "native import should set trust metadata for {}",
            name
        );
        assert!(
            native.evidence_text.is_none(),
            "native import should not emit evidence text for {}",
            name
        );

        let overlay = import_repository(&case, ImportMode::Overlay, Some(&overlay_source))
            .expect("overlay import succeeds");
        assert_eq!(
            overlay.manifest.record.source.as_deref(),
            Some(overlay_source.as_str()),
            "overlay import should preserve the provided source for {}",
            name
        );
        assert_eq!(
            overlay.manifest.repo.homepage.as_deref(),
            Some(overlay_source.as_str()),
            "overlay import should mirror source to repo.homepage for {}",
            name
        );
        assert!(
            overlay
                .evidence_text
                .as_deref()
                .is_some_and(|text| text.starts_with("# Evidence\n\n")),
            "overlay import should emit evidence text for {}",
            name
        );
        assert!(
            overlay.manifest.record.trust.is_some(),
            "overlay import should set trust metadata for {}",
            name
        );
    }
}

#[test]
fn import_fixture_pack_captures_readme_title_and_description_edge_cases() {
    let setext = import_repository(&fixture_case("setext-heading-readme"), ImportMode::Native, None)
        .expect("setext README imports");
    assert_eq!(setext.manifest.repo.name, "Forge");
    assert_eq!(
        setext.manifest.repo.description,
        "Release train coordinator for multi-crate workspaces."
    );
    assert!(setext.inferred_fields.is_empty());

    let html = import_repository(&fixture_case("html-heading-readme"), ImportMode::Native, None)
        .expect("HTML heading README imports");
    assert_eq!(html.manifest.repo.name, "Nimbus");
    assert_eq!(
        html.manifest.repo.description,
        "Small deployment orchestrator for self-hosted services."
    );
    assert!(html.inferred_fields.is_empty());

    let description_only = import_repository(
        &fixture_case("description-only-readme"),
        ImportMode::Native,
        None,
    )
    .expect("description-only README imports");
    assert_eq!(
        description_only.manifest.repo.description,
        "Lightweight release notes generator for Git repositories."
    );
    assert_eq!(description_only.inferred_fields, vec!["repo.name"]);
}

#[test]
fn import_fixture_pack_strengthens_owner_and_security_extraction() {
    let codeowners = import_repository(&fixture_case("mixed-codeowners"), ImportMode::Native, None)
        .expect("mixed CODEOWNERS fixture imports");
    let owners = codeowners.manifest.owners.as_ref().expect("owners imported");
    assert_eq!(owners.team.as_deref(), Some("@org/release-team"));
    assert_eq!(
        owners.maintainers,
        vec![
            "@maintainer",
            "@org/release-team",
            "security@example.com",
            "@docs-team",
        ]
    );

    let security = import_repository(
        &fixture_case("security-markdown-link"),
        ImportMode::Native,
        None,
    )
    .expect("markdown SECURITY fixture imports");
    assert_eq!(
        security
            .manifest
            .owners
            .as_ref()
            .and_then(|owners| owners.security_contact.as_deref()),
        Some("security@example.com")
    );

    let unknown = import_repository(
        &fixture_case("security-contact-unknown"),
        ImportMode::Native,
        None,
    )
    .expect("unknown SECURITY fixture imports");
    assert_eq!(
        unknown
            .manifest
            .owners
            .as_ref()
            .and_then(|owners| owners.security_contact.as_deref()),
        Some("unknown")
    );
}
