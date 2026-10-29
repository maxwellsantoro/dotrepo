use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

use super::*;

struct TestRoot(PathBuf);

impl TestRoot {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "dotrepo-context-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(path.join("packages/ui")).unwrap();
        Self(path)
    }

    fn extract(&self, document: &str) -> Vec<(bool, BuildTestCandidate)> {
        extract_contexts(
            &self.0,
            &ImportedFile {
                path: "CONTRIBUTING.md".to_string(),
                contents: document.to_string(),
            },
        )
    }
}

impl Drop for TestRoot {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

#[test]
fn explicit_runtime_prerequisites_preserve_complete_component_tuple() {
    let root = TestRoot::new();
    let extracted = root.extract(
        "## Component tests: packages/ui\n\nPrerequisites:\n- Node.js 22+\n- pnpm >=10.0\n\n```sh\ncd packages/ui\npnpm install\npnpm test --run\n```\n",
    );
    assert_eq!(extracted.len(), 1);
    let (is_build, candidate) = &extracted[0];
    assert!(!is_build);
    assert_eq!(candidate.command, "pnpm test --run");
    assert_eq!(candidate.source, "CONTRIBUTING.md");
    let context = candidate.context.as_ref().unwrap();
    assert_eq!(context.command, candidate.command);
    assert_eq!(context.working_directory, "packages/ui");
    assert_eq!(context.scope, ExecutionScope::Component);
    assert_eq!(context.component.as_deref(), Some("packages/ui"));
    assert_eq!(context.source, candidate.source);
    assert_eq!(
        context.prerequisites,
        [
            "Node.js 22+",
            "pnpm >=10.0",
            "Run `pnpm install` in `packages/ui` before this command."
        ]
    );
}

#[test]
fn explicit_runtime_prerequisites_can_establish_runtime_only_setup() {
    let root = TestRoot::new();
    for requirement in [
        "Rust stable",
        "Rust nightly",
        "Rust 1.90.0",
        "Python 3.11 or higher",
        "Python >=3.12",
        "Go 1.25+",
        "Node.js <=24.0.0",
        "npm ==11.0",
        "uv 0.9.0 or newer",
    ] {
        let document = format!(
            "## Repository build\n\nPrerequisites:\n* {requirement}\n\n```shell\ncd .\ncargo build --release\n```\n"
        );
        let extracted = root.extract(&document);
        assert_eq!(extracted.len(), 1, "{requirement}");
        assert!(extracted[0].0);
        let context = extracted[0].1.context.as_ref().unwrap();
        assert_eq!(context.scope, ExecutionScope::Repository);
        assert_eq!(context.working_directory, ".");
        assert_eq!(context.component, None);
        assert_eq!(context.prerequisites, [requirement]);
    }
}

#[test]
fn prerequisite_lists_abstain_on_incomplete_or_ambiguous_declarations() {
    let root = TestRoot::new();
    for prose in [
        "Prerequisites:",
        "Prerequisites:\n- Rust",
        "Prerequisites:\n- Python latest",
        "Prerequisites:\n- Python 3.x",
        "Prerequisites:\n- Python $VERSION",
        "Prerequisites:\n- Python <version>",
        "Prerequisites:\n- Python 3.12 or 3.13",
        "Prerequisites:\n- Python <=3.12 or higher",
        "Prerequisites:\n- Python >=3.12+",
        "Prerequisites:\n- Node.js 22 if running locally",
        "Prerequisites:\n- [Node.js 22](https://nodejs.org)",
        "Prerequisites:\n- Node.js 22\n  - npm 11",
        "Prerequisites:\n- Node.js 22\n  if running locally",
        "Prerequisites:\n- Node.js 22\nSee setup.md for other requirements.",
        "Prerequisites:\n- Node.js 22\n- Node.js 24",
        "Prerequisites:\n- npm install",
        "Prerequisites:\n- Run npm ci",
        "Prerequisites:\n- Node.js 22; npm ci",
        "Prerequisites: none.\n- Node.js 22",
        "Prerequisites:\n- none.",
        "Prerequisites:\n- Node.js 22\nPrerequisites: none.",
    ] {
        let document = format!("## Repository tests\n\n{prose}\n\n```sh\ncd .\nnpm test\n```\n");
        assert!(root.extract(&document).is_empty(), "{prose}");
    }
}

#[test]
fn explicit_runtime_list_cannot_supply_missing_or_conflicting_context() {
    let root = TestRoot::new();
    for (heading, command_lines) in [
        ("Repository tests", "npm test"),
        ("Repository tests", "cd packages/ui\nnpm test"),
        ("Component tests: packages/ui", "cd .\nnpm test"),
        (
            "Component tests: packages/missing",
            "cd packages/missing\nnpm test",
        ),
        ("Component tests: ../ui", "cd ../ui\nnpm test"),
        ("Repository tests", "cd $ROOT\nnpm test"),
        ("Repository tests", "cd .\nexport TOKEN=value\nnpm test"),
        ("Repository tests", "cd .\nnpm ci && npm test"),
        ("Repository tests", "cd .\nnpm test <target>"),
    ] {
        let document = format!(
            "## {heading}\n\nPrerequisites:\n- Node.js 22\n\n```sh\n{command_lines}\n```\n"
        );
        assert!(root.extract(&document).is_empty(), "{document}");
    }
}

#[test]
fn explicit_runtime_list_cannot_override_external_setup_contracts() {
    let root = TestRoot::new();
    for prefix in [
        "## Prerequisites\n\n- Python 3.12\n\n",
        "## Requirements\n\n- PostgreSQL 16\n\n",
        "## Development\n\nPostgreSQL 16 is required.\n\n",
        "## Setup\n\n```sh\nnpm ci\n```\n\n",
        "## Development\n\nInstall the compiler first.\n\n",
    ] {
        let document = format!(
            "{prefix}## Repository tests\n\nPrerequisites:\n- Node.js 22\n\n```sh\ncd .\nnpm test\n```\n"
        );
        assert!(root.extract(&document).is_empty(), "{prefix}");
    }
}

#[test]
fn scoped_sections_cannot_discard_ancestor_restrictions() {
    let root = TestRoot::new();
    for (prefix, depth) in [
        ("## Windows only\n\n", "###"),
        ("# Contributing\n\n## Windows only\n\n", "###"),
        ("# Windows only\n\n", "##"),
        ("# Linux\n\n", "##"),
        ("# When using Docker\n\n", "##"),
        ("# Component examples\n\n", "##"),
        ("# Contributing\n\n## Development\n\n", "###"),
    ] {
        let document = format!(
            "{prefix}{depth} Repository tests\n\nPrerequisites:\n- Node.js 22\n\n```sh\ncd .\nnpm test\n```\n"
        );
        assert!(root.extract(&document).is_empty(), "{prefix}");
    }
    // A sibling section's qualifier does not qualify this explicit section.
    let document = "# Contributing\n\n## Windows only\n\nPlatform discussion.\n\n## Repository tests\n\nPrerequisites:\n- Node.js 22\n\n```sh\ncd .\nnpm test\n```\n";
    assert_eq!(root.extract(document).len(), 1);
}

#[test]
fn missing_prerequisites_and_contradictory_none_still_abstain() {
    let root = TestRoot::new();
    for document in [
        "## Repository tests\n\n```sh\ncd .\nnpm test\n```\n",
        "## Repository tests\n\nPrerequisites: none.\n\n```sh\ncd .\nnpm ci\nnpm test\n```\n",
        "## Repository tests\n\nPrerequisites:\n- Node.js 22\n\n```sh\ncd .\nnpm test\n```\n\n```sh\nnpm ci\n```\n",
    ] {
        assert!(root.extract(document).is_empty(), "{document}");
    }
}
