use super::common::*;

#[test]
fn parse_readme_docs_metadata_extracts_docs_and_getting_started_links() {
    let signal = parse_readme_docs_signal(
        "[Docs](./docs/) · [Getting Started](./docs/getting-started.md) · [API](./docs/api.md)",
    );
    assert_eq!(signal.root.as_deref(), Some("./docs/"));
    assert_eq!(
        signal.getting_started.as_deref(),
        Some("./docs/getting-started.md")
    );

    let links = extract_markdown_links(
        "[Docs](./docs/) · [Getting Started](./docs/getting-started.md) · [API](./docs/api.md)",
    );
    assert_eq!(
        links,
        vec![
            ("Docs".to_string(), "./docs/".to_string()),
            (
                "Getting Started".to_string(),
                "./docs/getting-started.md".to_string()
            ),
            ("API".to_string(), "./docs/api.md".to_string())
        ]
    );

    let metadata = parse_readme_metadata(
        r#"# Tidelift

[Docs](./docs/) · [Getting Started](./docs/getting-started.md) · [API](./docs/api.md)

Policy-aware release orchestration for multi-service deploys.
"#,
    );
    assert_eq!(metadata.docs_root.as_deref(), Some("./docs/"));
    assert_eq!(
        metadata.docs_getting_started.as_deref(),
        Some("./docs/getting-started.md")
    );
    assert_eq!(
        metadata.description.as_deref(),
        Some("Policy-aware release orchestration for multi-service deploys.")
    );
}

#[test]
fn parse_readme_docs_metadata_extracts_reference_and_html_docs_links() {
    let reference_metadata = parse_readme_metadata(
        r#"[documentation]: https://gohugo.io/documentation
[installation]: https://gohugo.io/installation

# Hugo

A fast and flexible static site generator.

[Website][] | [Installation][] | [Documentation][]
"#,
    );
    assert_eq!(
        reference_metadata.docs_root.as_deref(),
        Some("https://gohugo.io/documentation")
    );
    assert_eq!(
        reference_metadata.docs_getting_started.as_deref(),
        Some("https://gohugo.io/installation")
    );

    let html_metadata = parse_readme_metadata(
        r#"# Starship

The minimal, blazing-fast, and infinitely customizable prompt for any shell!

<p>
  <a href="https://starship.rs">Website</a>
  <a href="https://starship.rs/config/">Configuration</a>
</p>
"#,
    );
    assert_eq!(
        html_metadata.docs_root.as_deref(),
        Some("https://starship.rs/config/")
    );
}

#[test]
fn parse_readme_metadata_skips_reference_definitions_and_trailing_badges() {
    let metadata = parse_readme_metadata(
        r#"# Serde &emsp; [![Build Status]][actions] [![Latest Version]][crates.io]

[Build Status]: https://img.shields.io/github/actions/workflow/status/serde-rs/serde/ci.yml?branch=master
[actions]: https://github.com/serde-rs/serde/actions?query=branch%3Amaster
[Latest Version]: https://img.shields.io/crates/v/serde.svg
[crates.io]: https://crates.io/crates/serde

**Serde is a framework for *ser*ializing and *de*serializing Rust data structures efficiently and generically.**
"#,
    );
    assert_eq!(metadata.title.as_deref(), Some("Serde"));
    assert_eq!(
            metadata.description.as_deref(),
            Some("Serde is a framework for *ser*ializing and *de*serializing Rust data structures efficiently and generically.")
        );
}

#[test]
fn parse_readme_metadata_preserves_unicode_text_around_markdown_links() {
    let metadata = parse_readme_metadata(
        r#"# Café

Café sécurité pour les dépôts [guides](./docs/guides.md) et l’équipe.
"#,
    );
    assert_eq!(metadata.title.as_deref(), Some("Café"));
    assert_eq!(
        metadata.description.as_deref(),
        Some("Café sécurité pour les dépôts guides et l’équipe.")
    );
}

#[test]
fn parse_readme_title_skips_non_project_headings() {
    let metadata = parse_readme_metadata(
        r#"[![CI](https://img.shields.io/badge/CI-passing-green)]

# Code of Conduct

## NumPy

The fundamental package for scientific computing with Python.
"#,
    );
    assert_eq!(metadata.title.as_deref(), Some("NumPy"));
    assert_eq!(
        metadata.description.as_deref(),
        Some("The fundamental package for scientific computing with Python.")
    );
}

#[test]
fn parse_readme_title_skips_installation_and_contributing_headings() {
    let metadata = parse_readme_metadata(
        r#"# Installation

Run `pip install myproject`.

# Contributing

PRs welcome.
"#,
    );
    assert!(metadata.title.is_none());
}

#[test]
fn normalize_description_line_rejects_url_and_file_path_artifacts() {
    assert!(normalize_description_line("https://numfocus.org)").is_none());
    assert!(normalize_description_line("packages/next/README.md").is_none());
    assert!(normalize_description_line("https://example.com/description").is_none());
    assert!(normalize_description_line("Normal project description").is_some());
    assert!(normalize_description_line(
        "The fundamental package for scientific computing with Python."
    )
    .is_some());
}

#[test]
fn normalize_description_line_rejects_unbalanced_brackets() {
    assert!(normalize_description_line("some text] with extra bracket").is_none());
    assert!(normalize_description_line("some text) with extra paren").is_none());
    assert!(normalize_description_line("balanced (yes) description").is_some());
}

#[test]
fn clean_project_description_rejects_quoted_tagline() {
    assert_eq!(clean_project_description("\"Any color you like.\""), None);
    assert_eq!(
        clean_project_description("\u{201c}Any color you like.\u{201d}"),
        None
    );
    assert_eq!(
        clean_project_description("\"Stay hungry, stay foolish.\""),
        None
    );
}

#[test]
fn clean_project_description_accepts_quoted_sentence_with_internal_structure() {
    assert!(clean_project_description(
        "\"Black\" is the uncompromising Python code formatter used by many."
    )
    .is_some());
}

#[test]
fn is_non_project_heading_rejects_sponsor_compound() {
    assert!(is_non_project_heading("Vladimir Sponsors"));
    assert!(is_non_project_heading("Gold Sponsors"));
    assert!(is_non_project_heading("Bronze sponsor"));
    assert!(!is_non_project_heading("Configuration Generator"));
    assert!(!is_non_project_heading("Vite"));
}

#[test]
fn parse_readme_title_line_rejects_promo_link_heading() {
    assert!(parse_readme_title_line(
        "### [Warp, the AI terminal for devs](https://www.warp.dev/cobra)"
    )
    .is_none());
    assert!(parse_readme_title_line("## [Click here to try](https://example.com/promo)").is_none());
    assert!(parse_readme_title_line("# [Sponsored by Acme](https://acme.com)").is_none());
    assert_eq!(
        parse_readme_title_line("# MyProject [link](https://example.com)"),
        Some("MyProject link".to_string())
    );
    assert_eq!(
        parse_readme_title_line("# MyProject"),
        Some("MyProject".to_string())
    );
}

#[test]
fn parse_readme_metadata_uses_logo_alt_before_later_section_headings() {
    let metadata = parse_readme_metadata(
        r#"<p align="center">
  <a href="https://fastapi.tiangolo.com"><img src="logo.png" alt="FastAPI"></a>
</p>
<p align="center">
  <em>FastAPI framework, high performance, easy to learn, fast to code, ready for production</em>
</p>

## Opinions
"#,
    );

    assert_eq!(metadata.title.as_deref(), Some("FastAPI"));
    assert_eq!(
        metadata.description.as_deref(),
        Some("FastAPI framework, high performance, easy to learn, fast to code, ready for production")
    );
}

#[test]
fn parse_readme_metadata_ignores_promotions_before_and_after_title() {
    let metadata = parse_readme_metadata(
        r#"*[TokioConf 2026 program and tickets are now available!](https://tokioconf.com)*

---

# Tokio

A runtime for writing reliable, asynchronous, and slim applications with the Rust programming language.
"#,
    );
    assert_eq!(metadata.title.as_deref(), Some("Tokio"));
    assert_eq!(
        metadata.description.as_deref(),
        Some("A runtime for writing reliable, asynchronous, and slim applications with the Rust programming language.")
    );

    let release = parse_readme_metadata(
        r#"# Gin Web Framework

[![Go Reference](https://pkg.go.dev/badge/github.com/gin-gonic/gin?status.svg)](https://pkg.go.dev/github.com/gin-gonic/gin?tab=doc)

## Gin 1.12.0 is now available!

We're excited to announce the release of Gin 1.12.0! This release brings new features.

---

Gin is a high-performance HTTP web framework written in Go.
"#,
    );
    assert_eq!(
        release.description.as_deref(),
        Some("Gin is a high-performance HTTP web framework written in Go.")
    );
    assert_eq!(release.docs_root, None);
}

#[test]
fn try_parse_multiline_html_heading_extracts_name() {
    let lines: Vec<&str> = vec![
        "<h1 align=\"center\">",
        "Vitest",
        "</h1>",
        "<p>Next generation testing framework.</p>",
    ];
    let result = try_parse_multiline_html_heading(&lines, 0);
    assert_eq!(result, Some(("Vitest".to_string(), 3)));

    let lines2: Vec<&str> = vec!["<h2>", "The Uncompromising", "Code Formatter", "</h2>"];
    let result2 = try_parse_multiline_html_heading(&lines2, 0);
    assert_eq!(
        result2,
        Some(("The Uncompromising Code Formatter".to_string(), 4))
    );

    let lines3: Vec<&str> = vec!["<h1>Sponsors</h1>"];
    assert!(try_parse_multiline_html_heading(&lines3, 0).is_none());

    let lines4: Vec<&str> = vec!["not a heading"];
    assert!(try_parse_multiline_html_heading(&lines4, 0).is_none());
}

#[test]
fn infer_pyproject_commands_produces_default_test_when_build_system_exists() {
    let candidate = infer_pyproject_commands(&ImportedFile {
        path: "pyproject.toml".into(),
        contents: "[build-system]\nrequires = [\"setuptools\"]\n".into(),
    })
    .expect("candidate produced");
    assert_eq!(candidate.build.as_deref(), Some("python -m build"));
    assert_eq!(candidate.test.as_deref(), Some("python -m pytest"));
}

#[test]
fn infer_pyproject_commands_detects_tox() {
    let candidate = infer_pyproject_commands(&ImportedFile {
        path: "pyproject.toml".into(),
        contents: "[build-system]\nrequires = [\"setuptools\"]\n[tool.tox]\n".into(),
    })
    .expect("candidate produced");
    assert_eq!(candidate.test.as_deref(), Some("tox"));
}

#[test]
fn infer_pyproject_commands_detects_nox() {
    let candidate = infer_pyproject_commands(&ImportedFile {
        path: "pyproject.toml".into(),
        contents: "[build-system]\nrequires = [\"setuptools\"]\n[tool.nox]\n".into(),
    })
    .expect("candidate produced");
    assert_eq!(candidate.test.as_deref(), Some("nox"));
}

#[test]
fn infer_pyproject_commands_detects_optional_test_dependencies() {
    let candidate = infer_pyproject_commands(&ImportedFile {
            path: "pyproject.toml".into(),
            contents: "[build-system]\nrequires = [\"setuptools\"]\n[project.optional-dependencies]\ntest = [\"pytest\"]\n".into(),
        })
        .expect("candidate produced");
    assert_eq!(candidate.test.as_deref(), Some("python -m pytest"));
}

#[test]
fn infer_pyproject_commands_prefers_explicit_tool_over_default() {
    let candidate = infer_pyproject_commands(&ImportedFile {
        path: "pyproject.toml".into(),
        contents: "[build-system]\nrequires = [\"setuptools\"]\n[tool.pytest]\n".into(),
    })
    .expect("candidate produced");
    assert_eq!(candidate.test.as_deref(), Some("python -m pytest"));
}

#[test]
fn conflicting_node_and_python_test_signals_abstain() {
    // A repository with both a declared package.json test script and a Python
    // packaging default is genuinely polyglot: neither `npm test` nor
    // `python -m pytest` is the single honest answer, so `repo.test` abstains.
    let pyproject = ImportedFile {
        path: "pyproject.toml".into(),
        contents: "[build-system]\nrequires = [\"setuptools\"]\n".into(),
    };
    let package_json = ImportedFile {
        path: "package.json".into(),
        contents: r#"{"scripts": {"test": "npm test"}}"#.into(),
    };

    let result = infer_imported_commands(&ImportSources {
        readme: None,
        cargo_toml: None,
        rust_toolchain_toml: None,
        rust_toolchain: None,
        package_json: Some(&package_json),
        pyproject_toml: Some(&pyproject),
        setup_py: None,
        setup_cfg: None,
        tox_ini: None,
        go_mod: None,
        pom_xml: None,
        maven_wrapper: false,
        build_gradle: None,
        gradle_wrapper: false,
        composer_json: None,
        csproj: None,
        solution: None,
        mix_exs: None,
        rebar_config: None,
        cmake_presets_json: None,
        makefile: None,
        justfile: None,
        rakefile: None,
        contributing: None,
        workflow_files: &[],
    });
    assert!(result.test.is_none());
    assert!(result
        .notes
        .iter()
        .any(|note| note.contains("conflicting test commands")));
}

#[test]
fn cargo_build_beats_generic_pyproject_build_default() {
    let cargo = ImportedFile {
        path: "Cargo.toml".into(),
        contents: "[workspace]\nmembers = [\"crates/cli\"]\n".into(),
    };
    let pyproject = ImportedFile {
        path: "pyproject.toml".into(),
        contents: "[build-system]\nrequires = [\"hatchling\"]\n".into(),
    };

    let result = infer_imported_commands(&ImportSources {
        readme: None,
        cargo_toml: Some(&cargo),
        rust_toolchain_toml: None,
        rust_toolchain: None,
        package_json: None,
        pyproject_toml: Some(&pyproject),
        setup_py: None,
        setup_cfg: None,
        tox_ini: None,
        go_mod: None,
        pom_xml: None,
        maven_wrapper: false,
        build_gradle: None,
        gradle_wrapper: false,
        composer_json: None,
        csproj: None,
        solution: None,
        mix_exs: None,
        rebar_config: None,
        cmake_presets_json: None,
        makefile: None,
        justfile: None,
        rakefile: None,
        contributing: None,
        workflow_files: &[],
    });

    assert_eq!(
        result
            .build
            .as_ref()
            .map(|selection| selection.command.as_str()),
        Some("cargo build --workspace")
    );
    assert!(
        result.test.is_none(),
        "test should remain unresolved when Cargo and Python defaults conflict"
    );
}

#[test]
fn clean_project_name_accepts_real_project_names() {
    // Single-token and short multi-word names survive (calibrated against the
    // pinned fixture expectations, whose longest valid name is four words).
    for accepted in [
        "Orbit",
        "Serde",
        "Vitest",
        "Crate Atlas",
        "Signal Harbor",
        "The Uncompromising Code Formatter",
        // Genuine names that begin with "v" + digit must be preserved.
        "v2rayN",
        "V8",
    ] {
        assert_eq!(
            clean_project_name(accepted, "fallback"),
            Some(accepted.to_string()),
            "{accepted:?} should be kept as a project name"
        );
    }
}

#[test]
fn clean_project_name_rejects_question_and_announcement_headings() {
    // These README H1 patterns must fall back to the dir name, not become the
    // published repo.name (regression: redis/redis, rust-lang/rust, bevy, etc.).
    for rejected in [
        "What is Redis?",
        "What is Bevy?",
        "Why Rust?",
        "How Does It Work?",
        "What's in the download?",
        "In Chinese?",
        "Introducing MMSegmentation v1.0.0",
        "Welcome to Streamlit",
        "We are working on the next release",
        "v2.15 is out!",
        "Vue 2 has reached End of Life",
    ] {
        assert!(
            clean_project_name(rejected, "fallback").is_none(),
            "{rejected:?} should be rejected as a project name"
        );
    }
}

#[test]
fn clean_project_name_rejects_nav_bars_badge_spill_and_sentences() {
    for rejected in [
        "Website | Roadmap | Blog | Docs",
        "Website](https://example.org) ![CI](https://example.org/badge.svg)",
        "ClickHouse is an open-source column-oriented database management system",
        "Using the Marshaler and encoding.TextUnmarshaler interfaces",
        "Build a JAR and run it",
        "The web has evolved. Finally, testing has too.",
    ] {
        assert!(
            clean_project_name(rejected, "fallback").is_none(),
            "{rejected:?} should be rejected as a project name"
        );
    }
}

#[test]
fn clean_project_name_recovers_slug_from_colon_tagline() {
    // "pandas: tagline" / "fp-go: tagline" → keep the single-token name.
    assert_eq!(
        clean_project_name("pandas: A Powerful Python Data Analysis Toolkit", "fb"),
        Some("pandas".into())
    );
    assert_eq!(
        clean_project_name("fp-go: Functional Programming Library for Go", "fb"),
        Some("fp-go".into())
    );
    // A real multi-word name with a colon is preserved (no single-token prefix).
    assert_eq!(
        clean_project_name("Crate Atlas: release automation", "fb"),
        Some("Crate Atlas: release automation".into())
    );
}
