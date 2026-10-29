use super::parse_readme_docs_metadata;

fn docs(source: &str, name: &str) -> super::ReadmeDocsMetadata {
    parse_readme_docs_metadata(&source.lines().collect::<Vec<_>>(), Some(name))
}

#[test]
fn integration_prose_does_not_establish_project_documentation() {
    // Exact pinned SwiftLint README wording; the label names the project,
    // while the possessive and surrounding prose identify the integration.
    let source = "### MegaLinter\n\nSwiftLint is also embedded in [MegaLinter](https://megalinter.io), an\nopen-source aggregator of linters for CI. See its\n[SwiftLint documentation](https://megalinter.io/latest/descriptors/swift_swiftlint/)\nfor setup instructions.";
    assert_eq!(docs(source, "SwiftLint").root, None);
    assert_eq!(
        docs(
            "See its [Documentation](https://shared.example/integration).",
            "Orbit"
        )
        .root,
        None
    );
}

#[test]
fn quickstart_subject_must_match_the_project() {
    // Exact pinned MinIO README link sentence, referring to the client.
    let source = "Follow the MinIO Client [Quickstart Guide](https://docs.min.io/community/minio-object-store/reference/minio-mc.html#quickstart) for further instructions.";
    assert_eq!(docs(source, "MinIO").getting_started, None);
    assert_eq!(
        docs(source, "MinIO Client").getting_started.as_deref(),
        Some("https://docs.min.io/community/minio-object-store/reference/minio-mc.html#quickstart")
    );
    for source in [
        "Getting started: [Other Quickstart Guide](https://custom.example/start)",
        "Quickstart: [Getting Started for Other](https://custom.example/start)",
        "[Orbit Client Quickstart](https://custom.example/start)",
        "Other's [Quickstart](https://custom.example/start) is useful.",
    ] {
        assert_eq!(docs(source, "Orbit").getting_started, None, "{source}");
    }
}

#[test]
fn direct_and_navigation_declarations_keep_custom_domains() {
    for source in [
        "[Documentation](https://shared.example/other/project)",
        "Docs: [manual](https://shared.example/other/project)",
        "Documentation: [docs/](https://shared.example/other/project)",
        "## Documentation\n\n[Manual](https://shared.example/other/project)",
        "## Documentation\n\nAvailable [here](https://shared.example/other/project).",
        "## Docs\n\nYou can read our docs at:\n\n- https://shared.example/other/project",
        "Orbit's documentation is available at [guide](https://shared.example/other/project).",
        "Documentation for Orbit is available at [guide](https://shared.example/other/project).",
        "Read the [Orbit documentation](https://shared.example/other/project) for more information.",
    ] {
        assert_eq!(docs(source, "Orbit").root.as_deref(), Some("https://shared.example/other/project"), "{source}");
    }
    let nav = docs("[Docs](./manual/) | [Getting Started](./start.md)", "Orbit");
    assert_eq!(nav.root.as_deref(), Some("./manual/"));
    assert_eq!(nav.getting_started.as_deref(), Some("./start.md"));
    assert_eq!(
        docs(
            "Getting started: [guide](https://custom.example/start)",
            "Orbit"
        )
        .getting_started
        .as_deref(),
        Some("https://custom.example/start")
    );
}

#[test]
fn third_party_subjects_and_misleading_prefixes_do_not_declare_ownership() {
    for source in [
        "Other's documentation is available at [Documentation](https://custom.example/manual).",
        "## Documentation\n\nOther's documentation is available at [Documentation](https://custom.example/manual).",
        "Documentation: [Other documentation](https://custom.example/manual)",
        "The catalogue includes [Orbit documentation](https://custom.example/manual).",
        "See the [Documentation](https://custom.example/manual) for Other.",
        "Read the [license](https://custom.example/manual).",
        "Read the [code of conduct](https://custom.example/manual).",
        "See the [issue tracker](https://custom.example/manual).",
        "- Other integration: see its\n  [Documentation](https://custom.example/manual).",
    ] {
        assert_eq!(docs(source, "Orbit").root, None, "{source}");
    }
}

#[test]
fn start_labels_are_exact_generic_or_project_qualified() {
    for label in [
        "Getting Started",
        "Getting Started Guide",
        "Quickstart",
        "Quickstart Guide",
        "Quick Start",
        "Quick Start Guide",
        "Installation",
        "Installation Guide",
        "Installation Documentation",
        "Orbit Quickstart Guide",
        "Getting Started for Orbit",
    ] {
        let source = format!("[{label}](https://custom.example/start)");
        assert_eq!(
            docs(&source, "Orbit").getting_started.as_deref(),
            Some("https://custom.example/start"),
            "{label}"
        );
    }
    assert_eq!(
        docs(
            "See the [installation documentation](https://custom.example/start).",
            "Orbit"
        )
        .getting_started
        .as_deref(),
        Some("https://custom.example/start")
    );
}

#[test]
fn ambiguous_declarations_still_abstain_and_retain_evidence() {
    let parsed = docs(
        "[Docs](https://one.example/manual) | [Documentation](https://two.example/manual)",
        "Orbit",
    );
    assert_eq!(parsed.root, None);
    assert!(parsed.root_ambiguous);
    let parsed = docs(
        "# Orbit\n\nDocs: [manual](https://custom.example/manual)",
        "Orbit",
    );
    assert_eq!(parsed.root_evidence.unwrap().line, 3);
}

#[test]
fn documentation_badges_are_independent_of_neighboring_badges() {
    let source = "[![CI](https://ci.example/badge.svg)](https://ci.example/run)\n[![docs](https://badge.example/docs.svg)](https://custom.example/manual)\n[![license](https://badge.example/license.svg)](https://custom.example/license)";
    assert_eq!(
        docs(source, "Orbit").root.as_deref(),
        Some("https://custom.example/manual")
    );
}

#[test]
fn integration_hosts_are_valid_when_the_source_declares_project_docs_directly() {
    assert_eq!(
        docs(
            "[SwiftLint documentation](https://megalinter.io/latest/descriptors/swift_swiftlint/)",
            "SwiftLint"
        )
        .root
        .as_deref(),
        Some("https://megalinter.io/latest/descriptors/swift_swiftlint/")
    );
}

#[test]
fn a_long_wrapped_paragraph_builds_its_context_only_once() {
    use super::{markdown_reference_definitions, DocsParagraphCache};
    let mut lines = vec!["Other's integration documentation and catalogue:"; 20_000];
    for index in (1..lines.len()).step_by(10) {
        lines[index] = "See its [Orbit documentation](https://custom.example/integration) for setup instructions.";
    }
    assert!(lines.iter().map(|line| line.len()).sum::<usize>() > 1_000_000);
    let definitions = markdown_reference_definitions(&lines);
    let mut cache = DocsParagraphCache::default();
    for index in 0..lines.len() {
        let context = cache.context(&lines, index, &definitions);
        assert!(!context.navigation);
        assert_eq!(context.link_count, 2_000);
    }
    assert_eq!(cache.builds, 1);
    assert_eq!(parse_readme_docs_metadata(&lines, Some("Orbit")).root, None);
}
