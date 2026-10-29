use super::*;
use crate::{import_repository, verify_import_plan, ImportMode};
use std::path::PathBuf;

fn guard(contents: &str) -> GoContextGuard {
    GoContextGuard::inspect(&[ImportedFile {
        path: ".github/workflows/ci.yml".into(),
        contents: contents.into(),
    }])
}

fn defaults(guard: &GoContextGuard) -> [bool; 2] {
    let (_, blocked) = guard.selection_candidates(&[ImportedCommandCandidate {
        source_path: "go.mod".into(),
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some("go build ./...".into()),
        test: Some("go test ./...".into()),
    }]);
    blocked
}

#[test]
fn same_job_service_setup_blocks_only_test_default() {
    let checked = guard("jobs:\n  test:\n    steps:\n      - uses: shogo82148/actions-setup-redis@v1\n      - run: go test -race ./...\n");
    assert_eq!(defaults(&checked), [false, true]);
}

#[test]
fn unrelated_service_job_and_non_go_directory_change_do_not_poison_defaults() {
    let checked = guard("jobs:\n  unit:\n    steps:\n      - run: go test ./...\n  docs:\n    steps:\n      - uses: shogo82148/actions-setup-redis@v1\n      - run: |\n          cd examples\n          echo documentation\n");
    assert_eq!(defaults(&checked), [false, false]);
}

#[test]
fn scoped_go_workflow_blocks_metadata_fallthrough_without_nested_manifests() {
    for step in [
        "run: |\n          cd v2\n          go test ./...",
        "working-directory: v2\n        run: go test ./...",
    ] {
        let checked = guard(&format!("jobs:\n  module:\n    steps:\n      - {step}\n"));
        assert_eq!(defaults(&checked), [true, true], "{step}");
    }
}

#[test]
fn workflow_and_job_defaults_apply_but_root_cwd_is_preserved() {
    for directory in [".", "./", "v2", "${{ matrix.directory }}"] {
        for defaults_scope in [true, false] {
            let setting = format!("defaults:\n  run:\n    working-directory: {directory}\n");
            let contents = if defaults_scope {
                format!("{setting}jobs:\n  unit:\n    steps:\n      - run: go test ./...\n")
            } else {
                format!(
                    "jobs:\n  unit:\n{}    steps:\n      - run: go test ./...\n",
                    setting
                        .lines()
                        .map(|line| format!("    {line}\n"))
                        .collect::<String>()
                )
            };
            assert_eq!(
                defaults(&guard(&contents)),
                if directory.starts_with('.') {
                    [false, false]
                } else {
                    [true, true]
                },
                "{contents}"
            );
        }
    }
}

#[test]
fn cd_dot_does_not_reset_a_preceding_component_change() {
    assert_eq!(defaults(&guard("jobs:\n  test:\n    steps:\n      - run: |\n          cd v2\n          cd .\n          go test ./...\n")), [true, true]);
}

#[test]
fn declared_commands_and_unrelated_ecosystems_survive_go_guards() {
    let checked = guard("jobs:\n  test:\n    services:\n      redis:\n        image: redis\n    steps:\n      - run: go test ./...\n");
    for tier in [
        CommandSourceTier::Manifest,
        CommandSourceTier::ContribDoc,
        CommandSourceTier::TaskScript,
    ] {
        let candidates = [ImportedCommandCandidate {
            source_path: "CONTRIBUTING.md".into(),
            source_tier: tier,
            build: Some("go build ./...".into()),
            test: Some("go test ./...".into()),
        }];
        let (selected, blocked) = checked.selection_candidates(&candidates);
        assert_eq!(blocked, [false, false]);
        assert_eq!(selected[0].test.as_deref(), Some("go test ./..."));
    }
    let candidates = [ImportedCommandCandidate {
        source_path: "Cargo.toml".into(),
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some("cargo build".into()),
        test: Some("cargo test".into()),
    }];
    assert_eq!(checked.selection_candidates(&candidates).1, [false, false]);
}

#[test]
fn full_import_f1_go_context_fixture_contracts() {
    for (fixture, build, test) in [
        ("f1-go-multimodule-context", None, None),
        ("f1-go-service-context", Some("go build ./..."), None),
        (
            "f1-go-declared-context",
            Some("go build ./..."),
            Some("go test ./..."),
        ),
        (
            "f1-go-unrelated-service-context",
            Some("go build ./..."),
            Some("go test ./..."),
        ),
        (
            "f1-go-example-module-context",
            Some("go build ./..."),
            Some("go test ./..."),
        ),
        ("f1-go-services-block-context", Some("go build ./..."), None),
    ] {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/fixtures/import")
            .join(fixture);
        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://example.test/context"),
        )
        .unwrap();
        assert_eq!(plan.manifest.repo.build.as_deref(), build, "{fixture}");
        assert_eq!(plan.manifest.repo.test.as_deref(), test, "{fixture}");
        let verification = verify_import_plan(&root, &plan, "https://example.test/context");
        let scores = crate::score_import_fields(&plan, &verification);
        for (field, missing) in [
            ("repo.build", build.is_none()),
            ("repo.test", test.is_none()),
        ] {
            if missing {
                assert!(!plan.command_candidates.candidates.is_empty());
                assert!(
                    verification
                        .unresolved_fields
                        .iter()
                        .any(|value| value == field),
                    "{fixture}"
                );
                assert!(
                    matches!(
                        scores
                            .scores
                            .iter()
                            .find(|score| score.field == field)
                            .unwrap()
                            .confidence,
                        crate::FieldConfidence::Unresolved
                    ),
                    "{fixture}"
                );
            }
        }
        let native = import_repository(&root, ImportMode::Native, None).unwrap();
        assert_eq!(native.manifest.repo.build.as_deref(), build, "{fixture}");
        assert_eq!(native.manifest.repo.test.as_deref(), test, "{fixture}");
        println!(
            "F1_FIXTURE_PLAN {}",
            serde_json::json!({"fixture":fixture, "manifest":plan.manifest, "nativeManifest":native.manifest, "importedSources":plan.imported_sources, "inferredFields":plan.inferred_fields, "evidence":plan.evidence_text})
        );
    }
}

#[test]
fn comments_and_explicit_go_directory_flags_do_not_erase_scope() {
    for command in [
        "go -C v2 test ./...",
        "go test -C v2 ./...",
        "go -C=v2 test ./...",
    ] {
        assert_eq!(
            defaults(&guard(&format!(
                "jobs: # CI\n  test: # module\n    steps:\n      - run: {command}\n"
            ))),
            [true, true]
        );
    }
    assert_eq!(defaults(&guard("jobs: # CI\n  unit:\n    steps:\n      - working-directory: '.' # repository\n        run: go test ./...\n")), [false, false]);
}

#[test]
fn inline_services_and_explicit_redis_preparation_remain_prerequisites() {
    for contents in [
        "jobs:\n  test:\n    services: {redis: {image: 'redis:7'}}\n    steps:\n      - run: go test -race ./...\n",
        "jobs:\n  test:\n    steps:\n      - run: sudo apt-get install redis-server\n      - run: go test -race ./...\n",
        "jobs:\n  test:\n    steps:\n      - run: redis-server --daemonize yes\n      - run: go test -race\n",
    ] {
        assert_eq!(defaults(&guard(contents)), [false, true], "{contents}");
    }
    assert_eq!(defaults(&guard("jobs:\n  test:\n    services: {}\n    steps:\n      - uses: actions/setup-go@v5\n      - run: go test -race ./...\n")), [false, false]);
}

#[test]
fn quoted_hash_in_nonroot_directory_is_not_an_inline_comment() {
    assert_eq!(defaults(&guard("jobs:\n  test:\n    steps:\n      - working-directory: '. #component'\n        run: go test ./...\n")), [true, true]);
}

#[test]
fn escalation_cannot_restore_context_blocked_scalars_even_with_model_budget() {
    use crate::import::{
        build_adjudication_requests, run_import_escalation, AdjudicationProvider,
        AdjudicationProviderResponse, AdjudicationRequest, AdjudicationTier,
        ImportEscalationOptions, TieredAdjudicationProviders,
    };
    use std::sync::atomic::{AtomicUsize, Ordering};

    struct RejectUnexpectedCall(AtomicUsize);
    impl AdjudicationProvider for RejectUnexpectedCall {
        fn tier(&self) -> AdjudicationTier {
            AdjudicationTier::LocalPrimary
        }
        fn adjudicate(
            &self,
            request: &AdjudicationRequest,
        ) -> anyhow::Result<AdjudicationProviderResponse> {
            self.0.fetch_add(1, Ordering::SeqCst);
            anyhow::bail!("unexpected guarded-field request: {}", request.field)
        }
    }
    for (fixture, blocked_fields) in [
        ("f1-go-multimodule-context", vec!["repo.build", "repo.test"]),
        ("f1-go-service-context", vec!["repo.test"]),
        ("f1-go-services-block-context", vec!["repo.test"]),
    ] {
        for model_budget in [0, 2] {
            let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("tests/fixtures/import")
                .join(fixture);
            let mut plan = import_repository(
                &root,
                ImportMode::Overlay,
                Some("https://example.test/context"),
            )
            .unwrap();
            let original_candidates = plan.command_candidates.candidates.len();
            assert_eq!(
                plan.command_candidates.blocked_scalar_fields,
                blocked_fields
            );
            let verification = verify_import_plan(&root, &plan, "https://example.test/context");
            let mut scores = crate::score_import_fields(&plan, &verification);
            assert!(build_adjudication_requests(&scores, &plan)
                .iter()
                .all(|request| !blocked_fields.contains(&request.field.as_str())));
            if !blocked_fields.contains(&"repo.build") {
                let mut suspect_build = scores.clone();
                suspect_build
                    .scores
                    .iter_mut()
                    .find(|score| score.field == "repo.build")
                    .unwrap()
                    .confidence = crate::FieldConfidence::Suspect;
                let requests = build_adjudication_requests(&suspect_build, &plan);
                assert!(requests.iter().any(|request| request.field == "repo.build"));
                assert!(requests.iter().all(|request| request.field != "repo.test"));
            }
            let provider = RejectUnexpectedCall(AtomicUsize::new(0));
            let report = run_import_escalation(
                &root,
                &mut plan,
                &verification,
                &mut scores,
                &ImportEscalationOptions {
                    max_adjudication_calls: model_budget,
                    ..ImportEscalationOptions::default()
                },
                TieredAdjudicationProviders {
                    local_primary: Some(&provider),
                    local_second_opinion: None,
                    api_escalation: None,
                },
            );
            assert_eq!(provider.0.load(Ordering::SeqCst), 0);
            assert_eq!(report.model_calls, 0);
            assert_eq!(
                plan.command_candidates.candidates.len(),
                original_candidates
            );
            for field in blocked_fields.iter() {
                assert_eq!(
                    scores
                        .scores
                        .iter()
                        .find(|score| score.field == *field)
                        .unwrap()
                        .confidence,
                    crate::FieldConfidence::Unresolved,
                    "{fixture}/{field}/budget={model_budget}"
                );
                assert!(if *field == "repo.build" {
                    plan.manifest.repo.build.is_none()
                } else {
                    plan.manifest.repo.test.is_none()
                });
            }
            println!(
                "F1_ESCALATION_CONTROL {}",
                serde_json::json!({"fixture":fixture,"modelBudget":model_budget,"blockedScalarFields":plan.command_candidates.blocked_scalar_fields,"modelCalls":report.model_calls,"deterministicRequests":report.deterministic_requests,"manifest":plan.manifest,"unresolved":scores.summary.unresolved})
            );
        }
    }
}

#[test]
fn independent_explicit_defaults_remain_adjudication_eligible() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/import/f1-go-declared-context");
    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://example.test/context"),
    )
    .unwrap();
    assert!(plan.command_candidates.blocked_scalar_fields.is_empty());
    let verification = verify_import_plan(&root, &plan, "https://example.test/context");
    let mut scores = crate::score_import_fields(&plan, &verification);
    // A later suspect assessment must still allow the independent declaration
    // through the ordinary candidate-constrained ladder.
    for score in &mut scores.scores {
        if matches!(score.field.as_str(), "repo.build" | "repo.test") {
            score.confidence = crate::FieldConfidence::Suspect;
        }
    }
    let requests = crate::import::build_adjudication_requests(&scores, &plan);
    for field in ["repo.build", "repo.test"] {
        assert!(requests.iter().any(|request| request.field == field
            && request
                .candidates
                .iter()
                .any(|candidate| candidate.source_path == "CONTRIBUTING.md")));
    }
}

#[test]
fn quoted_supported_mapping_keys_preserve_scope_and_service_association() {
    for quote in ["", "\"", "'"] {
        let key = |name: &str| format!("{quote}{name}{quote}");
        let contents = format!("{}:\n  {}:\n    {}:\n      redis:\n        image: redis:7\n    {}:\n      - {}: go test -race ./...\n",key("jobs"),key("unit"),key("services"),key("steps"),key("run"));
        assert_eq!(defaults(&guard(&contents)), [false, true], "{contents}");
        let contents = format!("{}:\n  unit:\n    {}:\n      - {}: shogo82148/actions-setup-redis@v1\n      - {}: go test -race ./...\n",key("jobs"),key("steps"),key("uses"),key("run"));
        assert_eq!(defaults(&guard(&contents)), [false, true], "{contents}");
        let contents = format!(
            "{}:\n  unit:\n    {}:\n      - {}: v2\n        {}: go test ./...\n",
            key("jobs"),
            key("steps"),
            key("working-directory"),
            key("run")
        );
        assert_eq!(defaults(&guard(&contents)), [true, true], "{contents}");
    }
}

#[test]
fn non_run_literal_and_folded_scalar_bodies_are_configuration_data() {
    for style in ["|", "|-", ">", ">-"] {
        for location in ["workflow", "job", "step-name", "step-env"] {
            let data = "working-directory: examples\nuses: shogo82148/actions-setup-redis@v1\nservices:\n  redis:\n    image: redis:7\njobs:\n  example:\n    steps:\n      - run: go test ./...\n";
            let indented = |count: usize| {
                data.lines()
                    .map(|line| format!("{}{line}\n", " ".repeat(count)))
                    .collect::<String>()
            };
            let contents = match location {
                "workflow" => format!("env:\n  CONFIG: {style}\n{}jobs:\n  unit:\n    steps:\n      - run: go test ./...\n",indented(4)),
                "job" => format!("jobs:\n  unit:\n    env:\n      CONFIG: {style}\n{}    steps:\n      - run: go test ./...\n",indented(8)),
                "step-name" => format!("jobs:\n  unit:\n    steps:\n      - name: {style}\n{}        run: go test ./...\n",indented(10)),
                _ => format!("jobs:\n  unit:\n    steps:\n      - env:\n          CONFIG: {style}\n{}        run: go test ./...\n",indented(12)),
            };
            assert_eq!(
                defaults(&guard(&contents)),
                [false, false],
                "{location}/{style}: {contents}"
            );
        }
    }
}

#[test]
fn run_body_and_heredoc_data_are_not_execution_properties_or_commands() {
    let contents = "jobs:\n  unit:\n    steps:\n      - run: |\n          cat <<'CONFIG'\n          working-directory: examples\n          uses: shogo82148/actions-setup-redis@v1\n          services:\n            redis:\n              image: redis:7\n          cd v2\n          redis-server --daemonize yes\n          go test ./...\n          CONFIG\n          go test ./...\n";
    assert_eq!(defaults(&guard(contents)), [false, false]);
    let real_cwd = contents.replace("          CONFIG\n", "          CONFIG\n          cd v2\n");
    assert_eq!(defaults(&guard(&real_cwd)), [true, true]);
    let real_service = contents.replace(
        "          CONFIG\n",
        "          CONFIG\n          redis-server --daemonize yes\n",
    );
    assert_eq!(defaults(&guard(&real_service)), [false, true]);
}

#[test]
fn applicable_directory_overrides_follow_workflow_job_step_precedence() {
    for (workflow, job, step, expected) in [
        ("v2", None, Some("."), [false, false]),
        ("v2", Some("."), None, [false, false]),
        ("v2", Some("examples"), Some("."), [false, false]),
        (".", Some("examples"), Some("."), [false, false]),
        (".", Some("."), Some("v2"), [true, true]),
        ("v2", None, None, [true, true]),
    ] {
        let job_default = job
            .map(|directory| {
                format!("    defaults:\n      run:\n        working-directory: {directory}\n")
            })
            .unwrap_or_default();
        let step_setting = step
            .map(|directory| format!("        working-directory: {directory}\n"))
            .unwrap_or_default();
        let contents = format!("defaults:\n  run:\n    working-directory: {workflow}\njobs:\n  unit:\n{job_default}    steps:\n      - run: go test ./...\n{step_setting}");
        assert_eq!(defaults(&guard(&contents)), expected, "{contents}");
    }
    assert_eq!(defaults(&guard("defaults:\n  run:\n    working-directory: v2\njobs:\n  unit:\n    steps:\n      - working-directory: .\n        run: |\n          cd v2\n          go test ./...\n")),[true,true]);
}

#[test]
fn unsupported_run_or_flow_context_remains_unresolved() {
    for contents in [
        "jobs:\n  unit:\n    steps:\n      - run: >\n          go\n          test ./...\n",
        "jobs:\n  unit:\n    \"\\u0073teps\":\n      - run: go test ./...\n",
        "jobs:\n  unit:\n    steps:\n      - \"\\u0072un\": go test ./...\n",
        "jobs:\n  unit: {steps: [{run: go test ./...}]}\n",
        "jobs:\n  unit: *external_job\n",
        "jobs:\n  unit:\n    steps:\n      - {run: go test ./...}\n",
        "jobs:\n  unit:\n    steps:\n      - *external_step\n",
        "jobs:\n  unit:\n    steps:\n      - run: \"go\\n test ./...\"\n",
        "jobs:\n  unit:\n    steps:\n      - run: \"go\n          test ./...\"\n",
        "jobs:\n  unit:\n    steps:\n      - run: ${{ inputs.command }}\n",
        "jobs:\n  unit:\n    steps: [{run: go test ./...}]\n",
        "jobs: {unit: {steps: [{run: go test ./...}]}}\n",
        "jobs:\n  unit:\n    steps:\n      - run: |\n          cat <<'END'\n          go test ./...\n",
    ] {
        assert_eq!(defaults(&guard(contents)), [true, true], "{contents}");
    }
}

#[test]
fn amendment_full_import_and_escalation_association_controls() {
    use crate::import::{
        build_adjudication_requests, run_import_escalation, ImportEscalationOptions,
        TieredAdjudicationProviders,
    };
    let cases = [
        ("root-default", "jobs:\n  unit:\n    steps:\n      - run: go test ./...\n", false),
        ("plain-service", "jobs:\n  unit:\n    services:\n      redis:\n        image: redis:7\n    steps:\n      - run: go test -race ./...\n", true),
        ("quoted-jobs-service", "\"jobs\":\n  unit:\n    services:\n      redis:\n        image: redis:7\n    steps:\n      - run: go test -race ./...\n", true),
        ("quoted-steps-service", "jobs:\n  unit:\n    services:\n      redis:\n        image: redis:7\n    \"steps\":\n      - run: go test -race ./...\n", true),
        ("workflow-env-data", "env:\n  EXAMPLE_CONFIGURATION: |\n    working-directory: examples\njobs:\n  unit:\n    steps:\n      - run: go test ./...\n", false),
        ("job-env-data", "jobs:\n  unit:\n    env:\n      EXAMPLE_CONFIGURATION: |\n        working-directory: examples\n    steps:\n      - run: go test ./...\n", false),
        ("step-overrides-default", "defaults:\n  run:\n    working-directory: v2\njobs:\n  unit:\n    steps:\n      - run: go test ./...\n        working-directory: .\n", false),
        ("heredoc-data", "jobs:\n  unit:\n    steps:\n      - run: |\n          cat <<'END'\n          working-directory: examples\n          uses: shogo82148/actions-setup-redis@v1\n          services:\n            redis:\n              image: redis:7\n          cd v2\n          redis-server --daemonize yes\n          go test ./...\n          END\n          go test ./...\n", false),
    ];
    let root = std::env::temp_dir().join(format!(
        "dotrepo-go-context-amendment-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(root.join(".github/workflows")).unwrap();
    std::fs::write(
        root.join("README.md"),
        "# Amendment control\n\nOwned synthetic Go association control.\n",
    )
    .unwrap();
    std::fs::write(
        root.join("go.mod"),
        "module example.test/amendment\n\ngo 1.22\n",
    )
    .unwrap();
    for (name, workflow, blocked_test) in cases {
        std::fs::write(root.join(".github/workflows/ci.yml"), workflow).unwrap();
        for budget in [0, 2] {
            let mut plan = import_repository(
                &root,
                ImportMode::Overlay,
                Some("https://example.test/amendment"),
            )
            .unwrap();
            let verification = verify_import_plan(&root, &plan, "https://example.test/amendment");
            let mut scores = crate::score_import_fields(&plan, &verification);
            if blocked_test {
                assert_eq!(
                    plan.command_candidates.blocked_scalar_fields,
                    vec!["repo.test"]
                );
                assert!(build_adjudication_requests(&scores, &plan)
                    .iter()
                    .all(|request| request.field != "repo.test"));
            } else {
                assert!(
                    plan.command_candidates.blocked_scalar_fields.is_empty(),
                    "{name}"
                );
            }
            let provider = crate::import::StubAdjudicationProvider::new(
                crate::import::AdjudicationTier::LocalPrimary,
                Vec::new(),
            );
            let result = run_import_escalation(
                &root,
                &mut plan,
                &verification,
                &mut scores,
                &ImportEscalationOptions {
                    max_adjudication_calls: budget,
                    ..Default::default()
                },
                TieredAdjudicationProviders {
                    local_primary: Some(&provider),
                    local_second_opinion: None,
                    api_escalation: None,
                },
            );
            assert_eq!(result.model_calls, 0, "{name}");
            assert_eq!(
                plan.manifest.repo.build.as_deref(),
                Some("go build ./..."),
                "{name}"
            );
            assert_eq!(
                plan.manifest.repo.test.as_deref(),
                if blocked_test {
                    None
                } else {
                    Some("go test ./...")
                },
                "{name}"
            );
            if blocked_test {
                assert_eq!(
                    scores
                        .scores
                        .iter()
                        .find(|s| s.field == "repo.test")
                        .unwrap()
                        .confidence,
                    crate::FieldConfidence::Unresolved
                );
            }
            println!(
                "F1_AMENDMENT_CONTROL {}",
                serde_json::json!({"case":name,"workflow":workflow,"budget":budget,"blockedScalarFields":plan.command_candidates.blocked_scalar_fields,"modelCalls":result.model_calls,"build":plan.manifest.repo.build,"test":plan.manifest.repo.test,"unresolved":scores.summary.unresolved})
            );
        }
    }
    std::fs::remove_dir_all(root).unwrap();
}
