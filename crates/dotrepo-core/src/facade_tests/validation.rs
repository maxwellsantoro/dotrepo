use super::common::*;

#[test]
fn parse_codeowners_metadata_prefers_repo_wide_team_over_narrower_team_rules() {
    let metadata = parse_codeowners_metadata(
            "* @maintainer @org/release-team security@example.com\n/docs/ @org/docs-team\n*.rs @maintainer\n",
        );

    assert_eq!(
        metadata.owners,
        vec![
            "@maintainer",
            "@org/release-team",
            "security@example.com",
            "@org/docs-team",
        ]
    );
    assert_eq!(metadata.team.as_deref(), Some("@org/release-team"));
    assert!(metadata
        .note
        .as_deref()
        .is_some_and(|note| note.contains("prefers `@org/release-team` from the repo-wide rule")));
}

#[test]
fn parse_codeowners_metadata_keeps_team_unset_when_broad_ownership_is_ambiguous() {
    let metadata = parse_codeowners_metadata(
            "* @org/platform-team @org/release-team @alice\n/docs/ @org/docs-team\n/services/payments/ @org/payments-team\n",
        );

    assert_eq!(
        metadata.owners,
        vec![
            "@org/platform-team",
            "@org/release-team",
            "@alice",
            "@org/docs-team",
            "@org/payments-team",
        ]
    );
    assert_eq!(metadata.team, None);
    assert!(metadata
        .note
        .as_deref()
        .is_some_and(|note| note.contains("`owners.team` was left unset")));
}

#[test]
fn parse_security_contact_supports_reference_links_html_anchors_and_mailto_queries() {
    assert_eq!(
            parse_security_contact(
                "Please report vulnerabilities through our [security mailbox][security-mailbox].\n\n[security-mailbox]: mailto:security@example.com\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
    assert_eq!(
            parse_security_contact(
                "For responsible disclosure, contact <a href=\"mailto:security@example.com\">the security team</a>.\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
    assert_eq!(
            parse_security_contact(
                "Report vulnerabilities through our [security desk](mailto:security@example.com?subject=Security%20Report).\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
    assert_eq!(
            parse_security_contact(
                "Please report it to us at [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report).\n",
            )
            .as_deref(),
            Some("https://msrc.microsoft.com/create-report")
        );
    assert_eq!(
            parse_security_contact(
                "If you believe you have found a security vulnerability that meets [Microsoft's definition of a security vulnerability](https://aka.ms/security.md/definition), please report it to us as described below.\n\n## Reporting Security Issues\nPlease report it to us at [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report).\n",
            )
            .as_deref(),
            Some("https://msrc.microsoft.com/create-report")
        );
}

#[test]
fn parse_security_import_metadata_marks_policy_urls_as_partial_security_channels() {
    let metadata = parse_security_import_metadata(
        "Please use https://example.com/security for coordinated disclosure.\n",
    );

    assert_eq!(
        metadata.contact.as_deref(),
        Some("https://example.com/security")
    );
    assert!(metadata
        .note
        .as_deref()
        .is_some_and(|note| note.contains("policy or reporting URL rather than a direct mailbox")));
}

#[test]
fn parse_security_contact_prefers_reporting_url_over_redirect_destination() {
    assert_eq!(
            parse_security_contact(
                "Please report vulnerabilities via [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report).\n",
            )
            .as_deref(),
            Some("https://msrc.microsoft.com/create-report")
        );
}

#[test]
fn parse_security_contact_preserves_unicode_context_around_links() {
    assert_eq!(
            parse_security_contact(
                "Pour un signalement sécurité, utilisez [security@example.com](mailto:security@example.com?subject=Rapport%20sécurité).\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
}

#[test]
fn parse_contributing_security_extracts_email_from_section() {
    let contact = parse_contributing_security(
            "# Contributing\n\n## How to Help\n\nSubmit PRs.\n\n## Security\n\nReport vulnerabilities to security@example.com.\n",
        );
    assert_eq!(contact.as_deref(), Some("security@example.com"));
}

#[test]
fn parse_contributing_security_extracts_email_from_responsible_disclosure_heading() {
    let contact = parse_contributing_security(
        "# Contributing\n\n## Responsible Disclosure\n\nSend reports to disclose@example.com.\n",
    );
    assert_eq!(contact.as_deref(), Some("disclose@example.com"));
}

#[test]
fn parse_contributing_security_ignores_non_security_sections() {
    let contact = parse_contributing_security(
            "# Contributing\n\n## Getting Started\n\nEmail dev@example.com for help.\n\n## Code Review\n\nUse PRs.\n",
        );
    assert!(contact.is_none());
}

#[test]
fn parse_issue_template_security_extracts_email() {
    let contact = parse_issue_template_security(
        "---\ntitle: Security Vulnerability\n---\n\nReport to security@example.com.\n",
    );
    assert_eq!(contact.as_deref(), Some("security@example.com"));
}

#[test]
fn parse_security_contact_finds_backtick_email() {
    assert_eq!(
        parse_security_contact(
            "Please email `cobra-security@googlegroups.com` for vulnerabilities.\n",
        )
        .as_deref(),
        Some("cobra-security@googlegroups.com")
    );
}

#[test]
fn parse_security_contact_rejects_non_security_url() {
    assert_eq!(
            parse_security_contact(
                "## Best Practices\n\n2. [Use Go modules](https://go.dev/blog/using-go-modules) for dependency management.\n",
            )
            .as_deref(),
            None
        );
}

#[test]
fn validate_manifest_diagnostics_accumulates_multiple_errors() {
    let root = temp_dir("validate-many");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v9.9"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "   "
description = "Broken overlay"
"#,
    )
    .expect("manifest parses");

    let diagnostics = validate_manifest_diagnostics(&root, &manifest);
    assert!(diagnostics.len() >= 3);
    assert!(diagnostics
        .iter()
        .any(|diagnostic| diagnostic.message.contains("unsupported schema")));
    assert!(diagnostics
        .iter()
        .any(|diagnostic| diagnostic.message.contains("repo.name must not be empty")));
    assert!(diagnostics
        .iter()
        .any(|diagnostic| diagnostic.message.contains("record.source must be set")));
    assert!(diagnostics
        .iter()
        .any(|diagnostic| diagnostic.message.contains("record.trust must be set")));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_accepts_seed_overlay_layout() {
    let root = temp_dir("index");
    let record_dir = root.join("repos/github.com/BurntSushi/ripgrep");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/BurntSushi/ripgrep"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "ripgrep"
description = "Line-oriented search tool"
homepage = "https://github.com/BurntSushi/ripgrep"
"#,
    )
    .expect("record written");
    fs::write(
        record_dir.join("evidence.md"),
        "# Evidence\n\n- imported from the upstream repository homepage.\n",
    )
    .expect("evidence written");

    let findings = validate_index_root(&root).expect("index validates");
    assert!(findings.is_empty());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_reports_path_mismatches_and_missing_evidence() {
    let root = temp_dir("index-bad");
    let record_dir = root.join("repos/github.com/ripgrep/ripgrep");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/BurntSushi/ripgrep"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "ripgrep"
description = "Line-oriented search tool"
homepage = "https://github.com/BurntSushi/ripgrep"
"#,
    )
    .expect("record written");

    let findings = validate_index_root(&root).expect("index validates");
    let error_count = findings
        .iter()
        .filter(|finding| finding.severity == IndexFindingSeverity::Error)
        .count();
    assert_eq!(error_count, 3);
    assert!(findings
        .iter()
        .any(|finding| finding.message.contains("evidence.md")));
    assert!(findings
        .iter()
        .any(|finding| finding.message.contains("record.source resolves")));
    assert!(findings
        .iter()
        .any(|finding| finding.message.contains("repo.homepage resolves")));
    assert!(findings
        .iter()
        .any(|finding| finding.severity == IndexFindingSeverity::Warning));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_emits_quality_warnings_for_non_reference_vocab() {
    let root = temp_dir("index-warn");
    let record_dir = root.join("repos/github.com/sharkdp/bat");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/sharkdp/bat"

[record.trust]
confidence = "very-high"
provenance = ["imported", "maintainer-reviewed"]

[repo]
name = "bat"
description = "A cat clone with wings"
homepage = "https://github.com/sharkdp/bat"
build = "cargo build --locked"
test = "cargo test --locked"

[owners]
security_contact = "unknown"
"#,
    )
    .expect("record written");
    fs::write(
        record_dir.join("evidence.md"),
        "# Evidence\n\n- Imported from the upstream repository.\n",
    )
    .expect("evidence written");

    let findings = validate_index_root(&root).expect("index validates");
    assert!(findings
        .iter()
        .all(|finding| finding.severity == IndexFindingSeverity::Warning));
    assert!(findings.iter().any(|finding| {
        finding
            .message
            .contains("record.trust.confidence uses non-reference vocabulary")
    }));
    assert!(findings.iter().any(|finding| {
        finding
            .message
            .contains("record.trust.provenance includes non-reference value")
    }));
    assert!(findings
        .iter()
        .any(|finding| finding.message.contains("build command")));
    assert!(findings
        .iter()
        .any(|finding| finding.message.contains("test command")));
    assert!(findings
        .iter()
        .any(|finding| finding.message.contains("security_contact = \"unknown\"")));

    fs::remove_dir_all(root).expect("temp dir removed");
}
