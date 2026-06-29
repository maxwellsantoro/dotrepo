use super::common::*;

#[test]
fn render_readme_renders_custom_sections() {
    let root = temp_dir("custom-readme");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[readme]
sections = ["overview", "quickstart"]

[readme.custom_sections.quickstart]
content = "Run `cargo build`."
"#,
    )
    .expect("manifest parses");

    let rendered =
        render_readme(&root, &manifest, b"schema = \"dotrepo/v0.1\"").expect("readme renders");

    assert!(rendered.contains("## Quickstart"));
    assert!(rendered.contains("Run `cargo build`."));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn render_readme_rejects_custom_sections_outside_repository_root() {
    let sandbox = temp_dir("custom-readme-escape");
    let root = sandbox.join("repo");
    fs::create_dir_all(&root).expect("repo dir created");
    fs::write(sandbox.join("secret.txt"), "do not read").expect("secret written");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[readme]
sections = ["overview", "quickstart"]

[readme.custom_sections.quickstart]
path = "../secret.txt"
"#,
    )
    .expect("manifest parses");

    let err = render_readme(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect_err("escape path rejected");
    assert!(err
        .to_string()
        .contains("path must stay within the repository root"));

    fs::remove_dir_all(sandbox).expect("temp dir removed");
}

#[test]
fn validate_manifest_rejects_custom_sections_outside_repository_root() {
    let sandbox = temp_dir("custom-readme-validate-escape");
    let root = sandbox.join("repo");
    fs::create_dir_all(&root).expect("repo dir created");
    fs::write(sandbox.join("secret.txt"), "do not read").expect("secret written");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[readme]
sections = ["quickstart"]

[readme.custom_sections.quickstart]
path = "../secret.txt"
"#,
    )
    .expect("manifest parses");

    let diagnostics = validate_manifest_diagnostics(&root, &manifest);
    assert!(diagnostics.iter().any(|diagnostic| diagnostic
        .message
        .contains("custom README section `quickstart` uses an invalid path")));

    fs::remove_dir_all(sandbox).expect("temp dir removed");
}

#[test]
fn managed_outputs_preserve_unmanaged_readme_content_outside_markers() {
    let root = temp_dir("managed-readme");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest parses");
    fs::write(
        root.join("README.md"),
        r#"# Local README

This introduction stays.

<!-- dotrepo:begin id=readme.body -->
Old managed section
<!-- dotrepo:end id=readme.body -->

This footer stays too.
"#,
    )
    .expect("README written");

    let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect("managed outputs render");
    let readme = outputs
        .iter()
        .find(|(path, _)| path == &root.join("README.md"))
        .expect("README output present")
        .1
        .clone();

    assert!(readme.contains("# Local README"));
    assert!(readme.contains("This introduction stays."));
    assert!(readme.contains("<!-- dotrepo:begin id=readme.body -->"));
    assert!(readme.contains("## Overview"));
    assert!(readme.contains("Fast local-first sync engine"));
    assert!(readme.contains("This footer stays too."));
    assert!(!readme.contains("Old managed section"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn managed_outputs_do_not_overwrite_unmanaged_readme_without_markers() {
    let root = temp_dir("unmanaged-readme-skip");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest parses");
    fs::write(root.join("README.md"), "# Keep my hand-written README\n").expect("README written");

    let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect("managed outputs render");
    assert!(!outputs
        .iter()
        .any(|(path, _)| path == &root.join("README.md")));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn adopt_managed_surface_preserves_unmanaged_readme_prose() {
    let root = temp_dir("adopt-readme");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join("README.md"),
        "# Local README\n\nThis introduction stays.\n",
    )
    .expect("README written");

    let plan = adopt_managed_surface(&root, DoctorSurface::Readme).expect("adoption succeeds");
    assert_eq!(plan.path, root.join("README.md"));
    assert!(plan.contents.contains("# Local README"));
    assert!(plan.contents.contains("This introduction stays."));
    assert!(plan
        .contents
        .contains("<!-- dotrepo:begin id=readme.body -->"));
    assert!(plan.contents.contains("## Overview"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn adopt_managed_surface_refuses_missing_supported_file() {
    let root = temp_dir("adopt-missing");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[owners]
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
    )
    .expect(".repo written");

    let err =
        adopt_managed_surface(&root, DoctorSurface::Security).expect_err("missing should fail");
    assert!(err
        .to_string()
        .contains("manage --adopt` only converts existing files"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn managed_outputs_preserve_unmanaged_security_content_outside_markers() {
    let root = temp_dir("managed-security");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[owners]
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
    )
    .expect("manifest parses");
    fs::create_dir_all(root.join(".github")).expect(".github dir created");
    fs::write(
        root.join(".github/SECURITY.md"),
        r#"Intro stays.

<!-- dotrepo:begin id=security.body -->
old security block
<!-- dotrepo:end id=security.body -->

Footer stays.
"#,
    )
    .expect("SECURITY written");

    let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect("managed outputs render");
    let security = outputs
        .iter()
        .find(|(path, _)| path == &root.join(".github/SECURITY.md"))
        .expect("SECURITY output present")
        .1
        .clone();

    assert!(security.contains("Intro stays."));
    assert!(security.contains("# Security"));
    assert!(security.contains("Please report vulnerabilities to security@example.com."));
    assert!(security.contains("Footer stays."));
    assert!(!security.contains("old security block"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn managed_outputs_preserve_unmanaged_contributing_content_outside_markers() {
    let root = temp_dir("managed-contributing");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
build = "cargo build"
test = "cargo test"

[owners]
security_contact = "security@example.com"

[compat.github]
contributing = "generate"
"#,
    )
    .expect("manifest parses");
    fs::write(
        root.join("CONTRIBUTING.md"),
        r#"Local preface.

<!-- dotrepo:begin id=contributing.body -->
old contributing block
<!-- dotrepo:end id=contributing.body -->

Local footer.
"#,
    )
    .expect("CONTRIBUTING written");

    let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect("managed outputs render");
    let contributing = outputs
        .iter()
        .find(|(path, _)| path == &root.join("CONTRIBUTING.md"))
        .expect("CONTRIBUTING output present")
        .1
        .clone();

    assert!(contributing.contains("Local preface."));
    assert!(contributing.contains("# Contributing"));
    assert!(contributing.contains("Run `cargo build` before submitting changes."));
    assert!(contributing.contains("Run `cargo test` before submitting changes."));
    assert!(contributing.contains("Local footer."));
    assert!(!contributing.contains("old contributing block"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn managed_outputs_fail_on_malformed_nested_regions() {
    let root = temp_dir("managed-malformed");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest parses");
    fs::write(
        root.join("README.md"),
        r#"<!-- dotrepo:begin id=readme.body -->
<!-- dotrepo:begin id=security.body -->
bad nesting
<!-- dotrepo:end id=security.body -->
<!-- dotrepo:end id=readme.body -->
"#,
    )
    .expect("README written");

    let err = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect_err("nested regions should fail");
    assert!(err
        .to_string()
        .contains("nested or overlapping managed regions"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn managed_outputs_accept_whitespace_variation_in_markers() {
    let root = temp_dir("managed-whitespace");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest parses");
    fs::write(
        root.join("README.md"),
        r#"Local preface.

<!--   dotrepo:begin   id = readme.body   -->
stale managed content
<!--dotrepo:end id = readme.body-->

Local footer.
"#,
    )
    .expect("README written");

    let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect("managed outputs render");
    let readme = outputs
        .iter()
        .find(|(path, _)| path == &root.join("README.md"))
        .expect("README output present")
        .1
        .clone();

    assert!(readme.contains("Local preface."));
    assert!(readme.contains("## Overview"));
    assert!(readme.contains("Local footer."));
    assert!(!readme.contains("stale managed content"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn managed_outputs_reject_overlay_records() {
    let root = temp_dir("overlay-managed-outputs");
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest parses");

    let err = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
        .expect_err("overlay records should not render managed outputs");
    assert!(err
        .to_string()
        .contains("generate is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn parse_managed_marker_rejects_extra_tokens() {
    assert_eq!(
        parse_managed_marker("<!-- dotrepo:begin id=readme.body -->", "begin").as_deref(),
        Some("readme.body")
    );
    assert_eq!(
        parse_managed_marker("<!-- dotrepo:begin id = readme.body -->", "begin").as_deref(),
        Some("readme.body")
    );
    assert_eq!(
        parse_managed_marker("<!-- dotrepo:begin id=readme.body trailing -->", "begin"),
        None
    );
    assert_eq!(
        parse_managed_marker("<!-- dotrepo:begin -->", "begin"),
        None
    );
}

#[test]
fn generate_check_repository_detects_drift_inside_managed_regions() {
    let root = temp_dir("managed-stale");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest written");
    fs::write(
        root.join("README.md"),
        r#"Preface.

<!-- dotrepo:begin id=readme.body -->
stale managed content
<!-- dotrepo:end id=readme.body -->
"#,
    )
    .expect("README written");

    let report = generate_check_repository(&root).expect("generate check succeeds");
    assert!(report.stale.iter().any(|path| path == "README.md"));
    let readme = report
        .outputs
        .iter()
        .find(|output| output.path == "README.md")
        .expect("README output present");
    assert!(readme.stale);
    assert!(readme.expected.contains("## Overview"));
    assert!(readme
        .current
        .as_ref()
        .expect("current content included")
        .contains("stale managed content"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn generate_check_repository_does_not_flag_unmanaged_readme() {
    let root = temp_dir("unmanaged-generate-check");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest written");
    fs::write(root.join("README.md"), "# Keep my hand-written README\n").expect("README written");

    let report = generate_check_repository(&root).expect("generate check succeeds");
    let readme = report
        .outputs
        .iter()
        .find(|output| output.path == "README.md")
        .expect("README output present");
    assert_eq!(readme.state, ManagedFileState::Unmanaged);
    assert!(!readme.stale);
    assert!(report.stale.is_empty());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn generate_check_repository_rejects_overlay_records() {
    let root = temp_dir("overlay-generate-check");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("record written");

    let err = generate_check_repository(&root)
        .expect_err("overlay records should not run generate-check");
    assert!(err
        .to_string()
        .contains("generate-check is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn inspect_surface_states_reports_supported_and_unsupported_surfaces() {
    let root = temp_dir("doctor");
    fs::write(root.join("README.md"), "# Existing README\n").expect("README written");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(root.join(".github/CODEOWNERS"), "* @alice\n").expect("CODEOWNERS written");

    let findings = inspect_surface_states(&root).expect("doctor findings");
    assert_eq!(findings.len(), 2);
    assert_eq!(findings[0].path, PathBuf::from("README.md"));
    assert_eq!(findings[0].state, ManagedFileState::Unmanaged);
    assert_eq!(findings[1].path, PathBuf::from(".github/CODEOWNERS"));
    assert_eq!(findings[1].state, ManagedFileState::Unsupported);

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn inspect_surface_states_reports_partially_managed_and_malformed_files() {
    let root = temp_dir("doctor-partial");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(
        root.join("README.md"),
        r#"Intro

<!-- dotrepo:begin id=readme.body -->
managed
<!-- dotrepo:end id=readme.body -->
"#,
    )
    .expect("README written");
    fs::write(
        root.join(".github/SECURITY.md"),
        r#"<!-- dotrepo:begin id=security.body -->
broken
"#,
    )
    .expect("SECURITY written");

    let findings = inspect_surface_states(&root).expect("doctor findings");
    assert_eq!(findings[0].path, PathBuf::from("README.md"));
    assert_eq!(findings[0].state, ManagedFileState::PartiallyManaged);
    assert_eq!(findings[1].path, PathBuf::from(".github/SECURITY.md"));
    assert_eq!(findings[1].state, ManagedFileState::MalformedManaged);

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn inspect_surface_states_treats_partially_managed_readme_as_honest() {
    let root = temp_dir("doctor-partial-readme");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"

[readme]
title = "Example"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join("README.md"),
        r#"Project-specific introduction.

<!-- dotrepo:begin id=readme.body -->
managed
<!-- dotrepo:end id=readme.body -->

Repository-specific footer.
"#,
    )
    .expect("README written");

    let findings = inspect_surface_states(&root).expect("doctor findings");
    let readme = findings
        .iter()
        .find(|finding| finding.surface == DoctorSurface::Readme)
        .expect("readme finding present");

    assert_eq!(readme.state, ManagedFileState::PartiallyManaged);
    assert_eq!(
        readme.ownership_honesty,
        Some(DoctorOwnershipHonesty::Honest)
    );
    assert_eq!(
        readme.recommended_mode,
        Some(DoctorRecommendedMode::PartiallyManaged)
    );
    assert_eq!(readme.would_drop_unmanaged_content, Some(false));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn inspect_surface_states_flags_lossy_contributing_generation() {
    let root = temp_dir("doctor-lossy-contributing");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"
build = "cargo build --locked"
test = "cargo nextest run --locked"

[owners]
maintainers = ["@alice"]
security_contact = "security@example.com"

[compat.github]
contributing = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join("CONTRIBUTING.md"),
        r#"# Contributing

Read this repository-specific guide before opening a pull request.

## Local workflow

- Use the internal bootstrap script.
- Coordinate releases in the maintainer chat before tagging.
"#,
    )
    .expect("CONTRIBUTING written");

    let findings = inspect_surface_states(&root).expect("doctor findings");
    let contributing = findings
        .iter()
        .find(|finding| finding.surface == DoctorSurface::Contributing)
        .expect("contributing finding present");

    assert_eq!(contributing.state, ManagedFileState::Unmanaged);
    assert_eq!(contributing.declared_mode, Some(CompatMode::Generate));
    assert_eq!(
        contributing.ownership_honesty,
        Some(DoctorOwnershipHonesty::LossyFullGeneration)
    );
    assert_eq!(
        contributing.recommended_mode,
        Some(DoctorRecommendedMode::PartiallyManaged)
    );
    assert_eq!(contributing.would_drop_unmanaged_content, Some(true));
    assert_eq!(
        contributing.renderer_coverage,
        Some(DoctorRendererCoverage::StubOnly)
    );
    assert!(contributing.supports_managed_regions);
    assert!(contributing.message.contains("declared as fully generated"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn inspect_surface_states_treats_partially_managed_security_as_honest() {
    let root = temp_dir("doctor-partial-security");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"

[owners]
maintainers = ["@alice"]
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join(".github/SECURITY.md"),
        r#"Project-specific introduction.

<!-- dotrepo:begin id=security.body -->
managed
<!-- dotrepo:end id=security.body -->

Repository-specific disclosure notes.
"#,
    )
    .expect("SECURITY written");

    let findings = inspect_surface_states(&root).expect("doctor findings");
    let security = findings
        .iter()
        .find(|finding| finding.surface == DoctorSurface::Security)
        .expect("security finding present");

    assert_eq!(security.state, ManagedFileState::PartiallyManaged);
    assert_eq!(security.declared_mode, Some(CompatMode::Generate));
    assert_eq!(
        security.ownership_honesty,
        Some(DoctorOwnershipHonesty::Honest)
    );
    assert_eq!(
        security.recommended_mode,
        Some(DoctorRecommendedMode::PartiallyManaged)
    );
    assert_eq!(security.would_drop_unmanaged_content, Some(false));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn inspect_surface_states_flags_lossy_pull_request_template_generation() {
    let root = temp_dir("doctor-lossy-pr-template");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"
test = "cargo nextest run --locked"

[compat.github]
pull_request_template = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join(".github/pull_request_template.md"),
        r#"## Type of change

- [ ] Feature
- [ ] Fix

## Repo-specific checks

- [ ] Mention the rollout plan.
"#,
    )
    .expect("PR template written");

    let findings = inspect_surface_states(&root).expect("doctor findings");
    let pr_template = findings
        .iter()
        .find(|finding| finding.surface == DoctorSurface::PullRequestTemplate)
        .expect("PR template finding present");

    assert_eq!(pr_template.state, ManagedFileState::Unsupported);
    assert_eq!(pr_template.declared_mode, Some(CompatMode::Generate));
    assert_eq!(
        pr_template.ownership_honesty,
        Some(DoctorOwnershipHonesty::LossyFullGeneration)
    );
    assert_eq!(
        pr_template.recommended_mode,
        Some(DoctorRecommendedMode::Skip)
    );
    assert_eq!(pr_template.would_drop_unmanaged_content, Some(true));
    assert!(!pr_template.supports_managed_regions);
    assert!(pr_template
        .message
        .contains("partial management is not supported"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn load_manifest_from_root_falls_back_to_record_toml() {
    let root = temp_dir("overlay");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://example.com/repo"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("record written");

    let manifest = load_manifest_from_root(&root).expect("manifest loads from record.toml");
    assert_eq!(manifest.repo.name, "orbit");

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn load_manifest_document_returns_path_and_raw_bytes() {
    let root = temp_dir("document");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest written");

    let document = load_manifest_document(&root).expect("document loads");
    assert_eq!(document.path, root.join(".repo"));
    assert!(!document.raw.is_empty());
    assert_eq!(document.manifest.repo.name, "orbit");

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn github_outputs_generate_remaining_compat_files() {
    let manifest = parse_manifest(
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
build = "cargo build"
test = "cargo test"

[owners]
security_contact = "security@example.com"

[compat.github]
codeowners = "skip"
security = "skip"
contributing = "generate"
pull_request_template = "generate"
"#,
    )
    .expect("manifest parses");

    let outputs = github_outputs(&manifest, b"schema = \"dotrepo/v0.1\"");
    assert!(outputs
        .iter()
        .any(|(path, _)| path == Path::new("CONTRIBUTING.md")));
    assert!(outputs
        .iter()
        .any(|(path, _)| path == Path::new(".github/pull_request_template.md")));
}
