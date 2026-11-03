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
fn refresh_readmes_keep_explicit_documentation_declarations() {
    // README declarations at the upstream revisions retained by refresh PR #204.
    // The full paragraph matters: a physical link line alone is not ownership.
    let cases = [
        // AvaloniaUI/Avalonia@432480ae82f36f40caf8693e1dfb11d4040404ea
        ("Avalonia", "### Documentation\nDocumentation can be found at https://docs.avaloniaui.net.\n", "https://docs.avaloniaui.net"),
        // ClickHouse/ClickHouse@c189bd99fbda59c78489a6734c49397533bdd591
        ("ClickHouse", "* [Documentation](https://clickhouse.com/docs/) provides more in-depth information.", "https://clickhouse.com/docs/"),
        // HugoBlox/hugo-theme-academic-cv@d8ef310c786fe1cb3c0104b5c627da1b170cb022
        ("Academic CV", "- 📚 [**Docs**](https://docs.ownable.dev/?utm_source=github&utm_medium=readme&utm_content=community_academic-cv)", "https://docs.ownable.dev/?utm_source=github&utm_medium=readme&utm_content=community_academic-cv"),
        // LadybirdBrowser/ladybird@222a19374ec2c74516b62d94da670987185a22c9
        ("Ladybird", "Code-related documentation can be found in the [documentation](Documentation/) folder.", "Documentation/"),
        // akaunting/akaunting@a7a5fc790afe01c655ee039aa007b9a824d13af2
        ("Akaunting", "* [Documentation](https://akaunting.com/hc/docs) - Learn how to use", "https://akaunting.com/hc/docs"),
    ];
    for (project, source, expected) in cases {
        let parsed = docs(source, project);
        assert_eq!(
            parsed.root.as_deref(),
            Some(expected),
            "{project}: {source}"
        );
        let evidence = parsed.root_evidence.expect("source declaration retained");
        assert_eq!(
            source.lines().nth(evidence.line - 1),
            Some(evidence.context.as_str())
        );
        assert!(!parsed.root_ambiguous);
    }
}

#[test]
fn descriptive_declarations_still_require_the_whole_project_subject() {
    for source in [
        "Other's [Documentation](https://custom.example/manual) provides more in-depth information.",
        "[Documentation](https://custom.example/manual) provides more in-depth information\nfor Other's integration.",
        "- [Documentation](https://custom.example/manual) - Learn how to use Other",
        "- Other integration:\n  [Documentation](https://custom.example/manual) - Learn how to use",
        "## Documentation\nOther's documentation can be found at https://custom.example/manual.",
        "## Documentation\nDocumentation can be found at https://custom.example/manual\nfor Other's integration.",
        "Code-related documentation can be found in the [documentation](Documentation/) folder\nfor Other's integration.",
        "- 📚 Other's [**Docs**](https://custom.example/manual)",
        "- 📚 第三方 [**Docs**](https://custom.example/manual)",
        "- 📚 [**Other Docs**](https://custom.example/manual)",
    ] {
        let parsed = docs(source, "Orbit");
        assert_eq!(parsed.root, None, "{source}");
        assert_eq!(parsed.getting_started, None, "{source}");
    }
    let parsed = docs("- 📚 [**Docs**](https://one.example/manual)\n- 📖 [Documentation](https://two.example/manual)", "Orbit");
    assert_eq!(parsed.root, None);
    assert!(parsed.root_ambiguous);
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
fn physical_prefixes_cannot_override_a_paragraph_or_list_subject() {
    for source in [
        "# Orbit\n\nOther's integration setup includes its own\nDocs: [manual](https://shared.example/orbit/manual)\n",
        "# Orbit\n\n- Other's integration setup includes its own\n  Documentation: [manual](https://shared.example/orbit/manual)\n",
        "# Orbit\n\nOther's integration setup includes its own\nGetting started: [guide](https://shared.example/orbit/manual)\n",
        "# Orbit\n\nDocs: [manual](https://shared.example/orbit/manual) for Other's integration.\n",
        "1. Other's integration setup includes its own\n   Docs: [manual](https://shared.example/orbit/manual)",
        "Quickstart: [guide](https://shared.example/orbit/manual)\nfor Other's integration.",
    ] {
        let parsed = docs(source, "Orbit");
        assert_eq!(parsed.root, None, "{source}");
        assert_eq!(parsed.getting_started, None, "{source}");
    }
}

#[test]
fn documentation_heading_bare_urls_keep_the_whole_paragraph_subject() {
    for source in [
        "## Docs\nhttps://other.example/guide\nfor Other's integration.",
        "## Docs\n- https://other.example/guide\n  for Other's integration.",
        "## Docs\nOther's integration uses\nhttps://other.example/guide",
    ] {
        assert_eq!(docs(source, "Orbit").root, None, "{source}");
    }
    for source in [
        "## Docs\nhttps://custom.example/manual",
        "## Docs\n\n- https://custom.example/manual",
        "## Docs\n\nOur documentation:\n\n- https://custom.example/manual",
    ] {
        assert_eq!(
            docs(source, "Orbit").root.as_deref(),
            Some("https://custom.example/manual"),
            "{source}"
        );
    }
}

#[test]
fn complete_prefix_declarations_preserve_neutral_titles_and_list_owners() {
    for source in [
        "Docs: [manual](https://custom.example/manual)",
        "**Documentation**: [manual](https://custom.example/manual)",
        "Documentation: [manual](https://custom.example/manual).",
        "Docs:\n[manual](https://custom.example/manual)",
        "- Documentation: [manual](https://custom.example/manual)",
        "1. Docs: [manual](https://custom.example/manual)",
        "- Other integration is described separately.\n- Docs: [manual](https://custom.example/manual)",
        "Documentation: https://custom.example/manual",
    ] {
        assert_eq!(docs(source, "Orbit").root.as_deref(), Some("https://custom.example/manual"), "{source}");
    }
    for source in [
        "Getting started: [guide](https://custom.example/start)",
        "Quickstart:\n[guide](https://custom.example/start)",
        "1) Getting started: [guide](https://custom.example/start)",
    ] {
        assert_eq!(
            docs(source, "Orbit").getting_started.as_deref(),
            Some("https://custom.example/start"),
            "{source}"
        );
    }
}

#[test]
fn docs_section_intro_must_have_a_neutral_or_current_project_subject() {
    for subject in ["Other's docs at:", "Other's documentation is available at:"] {
        let source = format!("## Docs\n\n{subject}\n\n- https://custom.example/manual");
        assert_eq!(docs(&source, "Orbit").root, None, "{source}");
    }
    for subject in [
        "You can read our docs at:",
        "Documentation is available at:",
        "Orbit's documentation is available at:",
        "Documentation for Orbit is available at:",
    ] {
        let source = format!("## Docs\n\n{subject}\n\n- https://custom.example/manual");
        assert_eq!(
            docs(&source, "Orbit").root.as_deref(),
            Some("https://custom.example/manual"),
            "{source}"
        );
    }
    assert_eq!(
        docs(
            "Orbit's documentation is available at:\n[guide](https://custom.example/manual)",
            "Orbit"
        )
        .root
        .as_deref(),
        Some("https://custom.example/manual")
    );
    let parsed = docs("Documentation: [manual](https://custom.example/manual)\nGetting Started: [Quickstart](https://custom.example/start)", "Orbit");
    assert_eq!(
        parsed.root.as_deref(),
        Some("https://custom.example/manual")
    );
    assert_eq!(
        parsed.getting_started.as_deref(),
        Some("https://custom.example/start")
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

#[test]
fn html_navigation_is_separate_from_adjacent_prose_paragraphs() {
    // Caddy README@053be179d8602b65d93db6980397c176ecba2f89, lines 13-20.
    let source = "<h3 align=\"center\">Every site on HTTPS</h3>\n<p align=\"center\">Caddy is an extensible server platform that uses TLS by default.</p>\n<p align=\"center\">\n<a href=\"https://github.com/caddyserver/caddy/releases\">Releases</a> ·\n<a href=\"https://caddyserver.com/docs/\">Documentation</a> ·\n<a href=\"https://caddy.community\">Get Help</a>\n</p>\n<p>Neighboring prose is separate.</p>";
    let parsed = docs(source, "Caddy");
    assert_eq!(
        parsed.root.as_deref(),
        Some("https://caddyserver.com/docs/")
    );
    let evidence = parsed.root_evidence.unwrap();
    assert_eq!(evidence.line, 5);
    assert_eq!(source.lines().nth(4), Some(evidence.context.as_str()));

    for tag in ["<p>", "<P ALIGN='center'>", "<p title=\"a > b\">"] {
        let source = format!(
            "Unrelated prose.\n{tag}\n[Docs](https://custom.example/manual)\n</p>\nMore prose."
        );
        assert_eq!(
            docs(&source, "Orbit").root.as_deref(),
            Some("https://custom.example/manual")
        );
    }
}

#[test]
fn html_wrapping_keeps_third_party_subjects_and_qualifiers() {
    for source in [
        "<p>\nOther's integration uses its\n[Documentation](https://other.example/manual)\n</p>",
        "<p>\n[Documentation](https://other.example/manual)\nfor Other's integration.\n</p>",
        "<p>Other's integration uses its\n[Documentation](https://other.example/manual)\n</p>",
        "<p>\n[Documentation](https://other.example/manual)\nfor Other's integration.</p>",
        "Other's integration uses its\n<br>\n[Documentation](https://other.example/manual)",
        "Other's integration uses its\n<span>\n[Documentation](https://other.example/manual)\n</span>",
        "Other's integration uses its\n<p title='unclosed>\n[Documentation](https://other.example/manual)",
        "Other's integration uses its\n<p>for Other\n[Documentation](https://other.example/manual)",
        "Other's integration uses its\n<p><span>\n[Documentation](https://other.example/manual)",
        "Other's integration uses its\n<picture>\n[Documentation](https://other.example/manual)",
    ] {
        let parsed = docs(source, "Orbit");
        assert_eq!(parsed.root, None, "{source}");
        assert_eq!(parsed.getting_started, None, "{source}");
    }
}

#[test]
fn distinct_html_paragraphs_do_not_resolve_conflicting_declarations() {
    let source = "<p>\n[Docs](https://one.example/manual)\n</p>\n<p>\n[Documentation](https://two.example/manual)\n</p>";
    let parsed = docs(source, "Orbit");
    assert_eq!(parsed.root, None);
    assert!(parsed.root_ambiguous);
}

#[test]
fn explicit_html_documentation_badges_use_the_outer_link() {
    // browser-use/browser-use@b49a68e4060acb226da8f784194fef301c53a6d7.
    let source = "<div align=\"center\">\n<a href=\"#demos\"><img src=\"https://media.browser-use.tools/badges/demos\" alt=\"Demos\"></a>\n<img width=\"16\" height=\"1\" alt=\"\">\n<a href=\"https://docs.browser-use.com\"><img src=\"https://media.browser-use.tools/badges/docs\" alt=\"Docs\"></a>\n</div>";
    let parsed = docs(source, "Browser Use");
    assert_eq!(parsed.root.as_deref(), Some("https://docs.browser-use.com"));
    let evidence = parsed.root_evidence.unwrap();
    assert_eq!(evidence.line, 4);
    assert_eq!(source.lines().nth(3), Some(evidence.context.as_str()));
    assert_eq!(
        docs(
            "<a href='https://custom.example/manual?a=1&amp;b=2'><img alt='Docs'></a>",
            "Orbit"
        )
        .root
        .as_deref(),
        Some("https://custom.example/manual?a=1&b=2")
    );
    for tag in ["article", "aside"] {
        let source =
            format!("<{tag}><a href='https://custom.example/manual'>Documentation</a></{tag}>");
        assert_eq!(
            docs(&source, "Orbit").root.as_deref(),
            Some("https://custom.example/manual")
        );
    }
    assert_eq!(docs("<a href='https://custom.example/manual'><IMG ALT = 'Documentation' src='badge.svg' /></a>", "Orbit").root.as_deref(), Some("https://custom.example/manual"));
}

#[test]
fn html_badges_do_not_invent_labels_or_discard_prose() {
    for inner in [
        "<img src='https://docs.example/badge.svg'>",
        "<img alt='Build' src='https://docs.example/badge.svg'>",
        "<img data-alt='Docs' src='badge.svg'>",
        "<img title='alt=\"Docs\"' src='badge.svg'>",
        "<img alt='Other Docs' src='badge.svg'>",
        "<img alt='Docs' alt='Other Docs' src='badge.svg'>",
        "<img alt alt='Docs' src='badge.svg'>",
        "<img alt='Docs src='badge.svg'>",
        "<img alt='Docs'><img alt='Other'>",
        "<img alt='Docs'> for Other",
    ] {
        let source = format!("<a href='https://other.example/manual'>{inner}</a>");
        assert_eq!(docs(&source, "Orbit").root, None, "{source}");
    }
    let badge = "<a href='https://other.example/manual'><img src='badge.svg' alt='Docs'></a>";
    for anchor in [
        "<a data-href='https://other.example/manual'>",
        "<a title='href=\"https://other.example/manual\"'>",
        "<a href href='https://other.example/manual'>",
        "<a href='https://one.example/manual' href='https://two.example/manual'>",
        "<aside href='https://other.example/manual'>",
    ] {
        let source = format!("{anchor}<img alt='Docs' src='badge.svg'></a>");
        assert_eq!(docs(&source, "Orbit").root, None, "{source}");
    }
    for source in [
        format!("Other's integration uses its\n{badge}"),
        format!("{badge}\nfor Other's integration."),
        format!("- Other integration: {badge}"),
    ] {
        assert_eq!(docs(&source, "Orbit").root, None, "{source}");
    }
    let parsed = docs(&format!("{badge}\n<a href='https://two.example/manual'><img alt='Documentation' src='badge.svg'></a>"), "Orbit");
    assert_eq!(parsed.root, None);
    assert!(parsed.root_ambiguous);
}
